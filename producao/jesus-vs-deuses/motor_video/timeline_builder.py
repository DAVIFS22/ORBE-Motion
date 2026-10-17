"""Construção da linha do tempo: cenas ancoradas no roteiro -> planos com tempo, imagem, câmera, som.

Fluxo: `planejar_cenas` resolve as âncoras em tempos (usando o alinhamento
com a transcrição) e diz quantas imagens cada cena precisa; depois da
pesquisa de imagens, `construir` monta os planos e valida a cobertura total.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

from . import script_analyzer as sa
from .asset_manager import Asset
from .config import ErroProducao, log
from .storyboard import RITMOS, Cena, Secao
from .visual_effects import PRESETS

DUR_TRANSICAO = {"dissolve": 0.9, "dip_black": 1.2, "dip_gold": 1.4, "dip_white": 1.2, "corte": 0.0}
MIN_CENA_S = 1.5  # cenas mais curtas são incorporadas à anterior
MIN_PLANO_S = 2.2


@dataclass
class CenaPlanejada:
    cena: Cena
    inicio: float
    fim: float
    palavra_ini: int
    ancora_confiavel: bool
    planos_desejados: int = 1
    reserva_3d: bool = False  # o 1º plano será uma cena 3D (não precisa de imagem)

    @property
    def duracao(self) -> float:
        return self.fim - self.inicio


@dataclass
class Plano:
    id: str
    cena_id: str
    secao: str
    inicio: float
    fim: float
    narracao: str
    descricao: str
    fundo: dict
    camera: dict
    cor: str
    transicao_entrada: dict
    overlays: list[dict]
    fonte: dict
    asset_id: str | None = None
    movimento: str = ""
    cena3d: dict | None = None  # pedido de cena 3D (Blender) para este plano, se elegível

    @property
    def duracao(self) -> float:
        return self.fim - self.inicio


@dataclass
class Timeline:
    duracao_audio: float
    duracao_video: float
    fps: int
    planos: list[Plano]
    eventos_audio: list[dict]
    secoes: list[dict]
    avisos: list[str] = field(default_factory=list)

    def para_dict(self) -> dict:
        return {
            "duracao_audio_s": round(self.duracao_audio, 3), "duracao_video_s": round(self.duracao_video, 3),
            "fps": self.fps, "avisos": self.avisos, "secoes": self.secoes, "eventos_audio": self.eventos_audio,
            "planos": [asdict(p) for p in self.planos],
        }

    def planos_dict(self) -> list[dict]:
        return [asdict(p) for p in self.planos]


# --------------------------------------------------------------- planejar ---

def _usa_3d_sempre(c: Cena, cfg3d: dict | None) -> bool:
    s = c.cena3d
    return bool(s and cfg3d and cfg3d.get("blender_ok") and s["modo"] == "sempre" and s["prioridade"] <= cfg3d["prioridade"])


def planejar_cenas(al: sa.Alinhamento, cenas: list[Cena], duracao_video: float, plano_alvo_s: float = 11.0,
                   avisos: list[str] | None = None, cfg3d: dict | None = None) -> list[CenaPlanejada]:
    avisos = avisos if avisos is not None else []
    brutas: list[CenaPlanejada] = []
    pos = 0
    for c in cenas:
        idx = sa.localizar_ancora(al, c.ancora, pos)
        t, confiavel = sa.tempo_confiavel(al, idx)
        pos = idx + 1
        brutas.append(CenaPlanejada(c, t, t, idx, confiavel))
    # a primeira cena começa em 0 (a narração pode ter silêncio inicial)
    brutas[0].inicio = 0.0
    for a, b in zip(brutas, brutas[1:]):
        a.fim = max(a.inicio, b.inicio)
    brutas[-1].fim = duracao_video

    # incorpora cenas curtíssimas à anterior e descarta as de duração nula
    resultado: list[CenaPlanejada] = []
    for cp in brutas:
        if resultado and cp.duracao < 1e-3:
            avisos.append(f"Cena '{cp.cena.id}' começa em trecho do roteiro sem correspondência na transcrição "
                          f"(duração 0): descartada. Texto: {cp.cena.ancora!r}")
            continue
        if resultado and cp.duracao < MIN_CENA_S and not cp.cena.overlays and not any(s.startswith("silencio") for s in cp.cena.sfx):
            avisos.append(f"Cena '{cp.cena.id}' dura só {cp.duracao:.2f}s: incorporada à cena anterior.")
            resultado[-1].fim = cp.fim
            continue
        resultado.append(cp)
    for a, b in zip(resultado, resultado[1:]):  # recompõe a continuidade após descartes
        a.fim = b.inicio
    for cp in resultado:
        alvo = RITMOS[cp.cena.ritmo] if cp.cena.ritmo != "normal" else plano_alvo_s
        cp.planos_desejados = _quantos_planos(cp, alvo)
        cp.reserva_3d = _usa_3d_sempre(cp.cena, cfg3d) and cp.duracao / max(1, cp.planos_desejados) >= MIN_PLANO_S
    return resultado


def _quantos_planos(cp: CenaPlanejada, alvo: float) -> int:
    d = cp.duracao
    if any(o["tipo"] in ("versiculo", "lista", "ponto", "titulo") for o in cp.cena.overlays) and d <= 16:
        return 1
    return max(1, int(round(d / alvo)))


# ----------------------------------------------------------------- cortes ---

def _cortes(al: sa.Alinhamento, ini: float, fim: float, n: int) -> list[float]:
    """Instantes de corte entre planos, alinhados a inícios de frase/trecho quando possível."""
    if n <= 1:
        return [ini, fim]
    tamanho = (fim - ini) / n
    candidatos = sorted({al.t_ini[f.palavra_ini] for f in al.frases} | {c for c in _inicios_de_trecho(al)})
    cortes = [ini]
    for k in range(1, n):
        ideal = ini + k * tamanho
        proximo = min(candidatos, key=lambda t: abs(t - ideal), default=ideal)
        corte = proximo if abs(proximo - ideal) <= 0.3 * tamanho else ideal
        corte = min(max(corte, cortes[-1] + MIN_PLANO_S), fim - MIN_PLANO_S * (n - k))
        cortes.append(corte)
    cortes.append(fim)
    return cortes


def _inicios_de_trecho(al: sa.Alinhamento):
    # início de cada palavra reconhecida logo após uma pausa >= 0,35 s (respiração, vírgula)
    prev_fim = None
    for i, (a, b) in enumerate(zip(al.t_ini, al.t_fim)):
        if prev_fim is not None and al.reconhecida[i] and a - prev_fim >= 0.35:
            yield a
        prev_fim = b


# -------------------------------------------------------------- construir ---

def _credito_tela(asset: Asset) -> str:
    autor = (asset.autor or "").strip()
    autor = autor if autor and autor != "não informado" else "autor não informado"
    nome = {"commons": "Wikimedia Commons", "met": "The Met (CC0)", "aic": "Art Institute of Chicago (CC0)"}.get(asset.fonte, asset.fonte)
    return f"Imagem: {autor[:60]} · {nome} · {asset.licenca[:28]}"


def construir(
    al: sa.Alinhamento, planejadas: list[CenaPlanejada], secoes: dict[str, Secao],
    assets_por_cena: dict[str, list[Asset]], duracao_audio: float, duracao_video: float, fps: int,
    creditos_na_tela: bool = True, avisos: list[str] | None = None, mapa_pontos: dict | None = None,
    cfg3d: dict | None = None, videos_por_cena: dict[str, Asset] | None = None,
) -> Timeline:
    avisos = avisos if avisos is not None else []
    planos: list[Plano] = []
    ultimo_preset = ""
    semente = 11
    for cp in planejadas:
        c = cp.cena
        assets = assets_por_cena.get(c.id, [])
        n_w = cp.planos_desejados
        if assets:
            n = min(n_w, max(len(assets), math.ceil(cp.duracao / (1.7 * (RITMOS[c.ritmo] if c.ritmo != "normal" else 11.0)))))
        else:
            n = max(1, min(n_w, math.ceil(cp.duracao / (1.7 * 11.0))))
        n = max(1, min(n, int(cp.duracao // MIN_PLANO_S) or 1))
        cortes = _cortes(al, cp.inicio, cp.fim, n)
        desloc = 1 if cp.reserva_3d else 0   # com 3D reservado no plano 0, as imagens vão para os planos seguintes
        for k in range(n):
            ini, fim = cortes[k], cortes[k + 1]
            idx_img = k - desloc
            asset = assets[idx_img] if 0 <= idx_img < len(assets) else None
            if cp.reserva_3d and k == 0:
                asset = None
            semente += 7
            preset = _escolher_preset(c.camera, k, ultimo_preset, asset)
            ultimo_preset = preset
            intens = 1.0 if c.ritmo != "lento" else 0.8
            camera = {"preset": preset, "intensidade": intens}
            video = (videos_por_cena or {}).get(c.id) if k == 0 and not cp.reserva_3d else None
            if video is not None and video.duracao >= (fim - ini) + 2.2:
                asset = video  # filmagem licenciada (precisa durar mais que o plano, com folga para as transições)
                fundo = {"tipo": "video", "arquivo": video.arquivo_trabalho, "relativo_imagens": True, "inicio_clip": 0.0, "fps": fps,
                         "asset_id": video.id}
                fonte = {"origem": video.fonte, "titulo": video.titulo, "autor": video.autor, "licenca": video.licenca,
                         "url": video.url_pagina or video.url_arquivo, "natureza": video.natureza, "gerada_por_codigo": False}
            elif asset is not None:
                fundo = {"tipo": "imagem", "arquivo": asset.arquivo_trabalho, "asset_id": asset.id}
                fonte = {"origem": asset.fonte, "titulo": asset.titulo, "autor": asset.autor, "licenca": asset.licenca,
                         "url": asset.url_pagina or asset.url_arquivo, "natureza": asset.natureza, "gerada_por_codigo": False}
            elif c.mapa:
                fundo = {"tipo": "mapa", "semente": 7, "destaques": [c.lugar] if c.lugar else None}
                if c.lugar and mapa_pontos and c.lugar in mapa_pontos:
                    x, y = mapa_pontos[c.lugar]
                    camera.update(foco=[(x - 330) / 2400, (y - 190) / 1350, (x + 330) / 2400, (y + 190) / 1350],
                                  preset="foco", intensidade=3.0)
                fonte = _fonte_codigo("mapa esquemático (grade de coordenadas reais, sem contornos de costa)")
            else:
                fundo = {"tipo": "motivo", "motivo": c.motivo, "semente": semente}
                fonte = _fonte_codigo(f"cenário estilizado “{c.motivo}”")
            if c.foco and asset is not None:
                camera["foco"] = c.foco
            overlays = []
            if k == 0:
                overlays.extend(dict(o) for o in c.overlays)
            if asset is not None and asset.exige_atribuicao and creditos_na_tela:
                overlays.append({"tipo": "credito", "texto": _credito_tela(asset), "atraso": 1.0,
                                 "duracao": max(1.0, min(6.0, (fim - ini) - 1.6))})
            pedido3d = _pedido_3d(c, k, asset, fim - ini, cfg3d, creditos_na_tela)
            plano = Plano(
                id=f"{c.id}#{k + 1}", cena_id=c.id, secao=c.secao, inicio=ini, fim=fim,
                narracao=sa.texto_entre(al, ini, fim), descricao=c.descricao, fundo=fundo, camera=camera, cor=c.cor,
                transicao_entrada={"tipo": "corte", "duracao": 0.0}, overlays=overlays, fonte=fonte,
                asset_id=asset.id if asset else None, movimento=preset, cena3d=pedido3d,
            )
            planos.append(plano)
            if k == 0 and len(planos) > 1:
                planos[-1].transicao_entrada = {"tipo": c.transicao, "duracao": DUR_TRANSICAO[c.transicao]}
            elif k > 0:
                planos[-1].transicao_entrada = {"tipo": "dissolve", "duracao": DUR_TRANSICAO["dissolve"]}
    _ajustar_transicoes(planos)
    eventos = _eventos_audio(planejadas, planos, secoes, duracao_video)
    sec = _spans_secoes(planos, secoes)
    tl = Timeline(duracao_audio, duracao_video, fps, planos, eventos, sec, list(avisos))
    validar(tl)
    return tl


def _pedido_3d(c: Cena, k: int, asset: Asset | None, dur: float, cfg3d: dict | None, creditos: bool) -> dict | None:
    """Pedido de cena 3D para o plano k, se a política (prioridade, modo, Blender disponível) permitir."""
    if not cfg3d or not cfg3d.get("blender_ok") or dur < MIN_PLANO_S:
        return None
    s = c.cena3d
    if s and k == s.get("plano", 0) and s["prioridade"] <= cfg3d["prioridade"]:
        if s["modo"] == "sempre" or asset is None:
            return {"cena": s["cena"], "prioridade": s["prioridade"], "modo": s["modo"], "params": dict(s.get("params", {}))}
    if c.paralaxe is not None and asset is not None and cfg3d["prioridade"] >= 3 and k == 0:
        return {"cena": "foto_2_5d", "prioridade": 3, "modo": "sempre",
                "params": {"imagem": asset.arquivo_trabalho, "horizonte": c.paralaxe, "intensidade": 0.5, "_relativo_imagens": True}}
    return None


def _fonte_codigo(descricao: str) -> dict:
    return {"origem": "gerada por código (ORBE Motion)", "titulo": descricao, "autor": "ORBE Motion (código)",
            "licenca": "obra própria, sem material de terceiros", "url": "",
            "natureza": "ilustração gerada por código: não é fotografia nem registro histórico", "gerada_por_codigo": True}


def _escolher_preset(preferidos: tuple[str, ...], k: int, anterior: str, asset: Asset | None) -> str:
    if asset is not None and asset.largura / max(1, asset.altura) >= 2.3:
        return "pan_dir" if anterior != "pan_dir" else "pan_esq"
    cand = [preferidos[(k + i) % len(preferidos)] for i in range(len(preferidos))]
    for p in cand:
        if p != anterior:
            return p
    for p in ("zoom_in", "deriva", "pan_dir", "zoom_out", "tilt_cima"):
        if p != anterior and p in PRESETS:
            return p
    return cand[0]


def _ajustar_transicoes(planos: list[Plano]):
    """Limita cada transição a 35% do menor plano vizinho."""
    for i, p in enumerate(planos):
        t = p.transicao_entrada
        if i == 0 or t["tipo"] == "corte":
            continue
        limite = 0.35 * min(p.duracao, planos[i - 1].duracao)
        t["duracao"] = math.floor(min(t["duracao"], limite) * 1000) / 1000  # nunca arredonda para cima do limite
        if t["duracao"] < 0.15:
            p.transicao_entrada = {"tipo": "corte", "duracao": 0.0}


def _spans_secoes(planos: list[Plano], secoes: dict[str, Secao]) -> list[dict]:
    spans: list[dict] = []
    for p in planos:
        if spans and spans[-1]["secao"] == p.secao:
            spans[-1]["fim"] = p.fim
        else:
            s = secoes[p.secao]
            spans.append({"secao": p.secao, "inicio": p.inicio, "fim": p.fim, "musica": s.musica, "ambiencia": s.ambiencia})
    return spans


def _eventos_audio(planejadas: list[CenaPlanejada], planos: list[Plano], secoes: dict[str, Secao], duracao: float) -> list[dict]:
    """Efeitos pontuais e automações de música, sincronizados aos planos."""
    eventos: list[dict] = []
    por_cena: dict[str, list[Plano]] = {}
    for p in planos:
        por_cena.setdefault(p.cena_id, []).append(p)
    for cp in planejadas:
        ps = por_cena.get(cp.cena.id)
        if not ps:
            continue
        p0 = ps[0]
        t0 = p0.inicio
        trans_ini = t0 - p0.transicao_entrada["duracao"] / 2
        for s in cp.cena.sfx:
            nome, _, arg = s.partition(":")
            if nome == "whoosh":
                eventos.append({"t": max(0.0, trans_ini), "tipo": "whoosh", "cena": cp.cena.id})
            elif nome == "impacto":
                eventos.append({"t": t0, "tipo": "impacto", "cena": cp.cena.id})
            elif nome == "nota":
                eventos.append({"t": t0 + 0.25, "tipo": "nota", "cena": cp.cena.id})
            elif nome == "passos":
                eventos.append({"t": t0 + 0.4, "tipo": "passos", "dur": min(6.0, cp.duracao - 0.4), "cena": cp.cena.id})
            elif nome == "tecido":
                eventos.append({"t": t0 + 0.6, "tipo": "tecido", "cena": cp.cena.id})
            elif nome == "pergaminho":
                eventos.append({"t": max(0.0, trans_ini + 0.2), "tipo": "pergaminho", "cena": cp.cena.id})
            elif nome == "silencio":
                eventos.append({"t": t0, "tipo": "silencio", "dur": float(arg or 2.0), "cena": cp.cena.id})
            elif nome == "vento_forte":
                eventos.append({"t": t0, "tipo": "vento_forte", "dur": cp.duracao, "cena": cp.cena.id})
        tem_whoosh = any(x.startswith("whoosh") for x in cp.cena.sfx)
        if (p0.transicao_entrada["tipo"] in ("dip_gold", "dip_white", "dip_black") and not tem_whoosh and t0 > 1.0
                and cp.cena.secao not in ("5-morte", "6-crucificacao") and not any(x.startswith("silencio") for x in cp.cena.sfx)):
            # transição importante: um whoosh discreto (as variantes se alternam no mixer)
            eventos.append({"t": max(0.0, trans_ini), "tipo": "whoosh", "cena": cp.cena.id, "auto": True})
        if cp.cena.musica:
            eventos.append({"t": t0, "tipo": "musica_nivel", "modo": cp.cena.musica, "dur": cp.duracao, "cena": cp.cena.id})
    eventos.sort(key=lambda e: (e["t"], e["tipo"]))
    return eventos


# --------------------------------------------------------------- validação ---

def validar(tl: Timeline, tolerancia: float = 1e-3):
    """A linha do tempo cobre [0, duração do vídeo] sem lacunas nem sobreposições."""
    if not tl.planos:
        raise ErroProducao("Linha do tempo vazia.")
    if abs(tl.planos[0].inicio) > tolerancia:
        raise ErroProducao(f"A linha do tempo não começa em 0 (começa em {tl.planos[0].inicio:.3f}s).")
    for a, b in zip(tl.planos, tl.planos[1:]):
        if abs(a.fim - b.inicio) > tolerancia:
            raise ErroProducao(f"Lacuna/sobreposição entre {a.id} e {b.id}: {a.fim:.3f}s -> {b.inicio:.3f}s.")
    if abs(tl.planos[-1].fim - tl.duracao_video) > tolerancia:
        raise ErroProducao(f"A linha do tempo termina em {tl.planos[-1].fim:.3f}s, não em {tl.duracao_video:.3f}s.")
    for p in tl.planos:
        if p.duracao < 1.0 / tl.fps:
            raise ErroProducao(f"Plano {p.id} dura menos de um quadro.")
    if tl.duracao_video + 1e-6 < tl.duracao_audio:
        raise ErroProducao("O vídeo termina antes da narração.")


# --------------------------------------------------------------- cenas 3D ---

def coletar_pedidos_3d(tl: Timeline, limite: float | None = None) -> list:
    """Pedidos de cena 3D da linha do tempo, com a duração de clipe necessária (plano + metade das transições)."""
    from .blender_bridge import Pedido3D, semente_da_cena
    from .storyboard_jesus import ROTULOS_3D
    pedidos = []
    for i, p in enumerate(tl.planos):
        if not p.cena3d or (limite is not None and p.inicio >= limite):
            continue
        d_in = p.transicao_entrada["duracao"] if p.transicao_entrada["tipo"] != "corte" else 0.0
        d_out = 0.0
        if i + 1 < len(tl.planos):
            prox = tl.planos[i + 1].transicao_entrada
            d_out = prox["duracao"] if prox["tipo"] != "corte" else 0.0
        c3 = p.cena3d
        pedidos.append(Pedido3D(
            plano_id=p.id, cena=c3["cena"], duracao=p.duracao + (d_in + d_out) / 2, prioridade=c3["prioridade"], modo=c3["modo"],
            params=dict(c3["params"]), rotulo=ROTULOS_3D.get(c3["cena"], "Reconstrução artística em 3D, não é registro histórico"),
            semente=semente_da_cena(p.id)))
    return pedidos


def aplicar_clipes_3d(tl: Timeline, pedidos: list, fps: int, creditos_na_tela: bool = True):
    """Troca o fundo dos planos cujo clipe 3D foi gerado; os demais mantêm a imagem/cenário alternativo."""
    por_id = {p.plano_id: p for p in pedidos}
    for pl in tl.planos:
        ped = por_id.get(pl.id)
        if ped is None or ped.status not in ("renderizado", "reaproveitado") or not ped.clipe:
            continue
        pl.fundo = {"tipo": "video", "arquivo": ped.clipe, "fps": fps, "inicio_clip": 0.0, "origem": "cena3d", "cena3d": ped.cena}
        pl.asset_id = None
        pl.movimento = "câmera 3D (Blender)"
        pl.overlays = [o for o in pl.overlays if o["tipo"] != "credito"]
        pl.overlays.append({"tipo": "rotulo", "texto": ped.rotulo, "atraso": 0.8, "duracao": max(1.2, min(5.5, pl.duracao - 1.4))})
        pl.fonte = {"origem": "Blender (cena 3D procedural gerada por código)", "titulo": f"{ped.cena}: {ped.rotulo}",
                    "autor": "ORBE Motion (código)", "licenca": "obra própria, sem material de terceiros", "url": "",
                    "natureza": "reconstrução/representação artística em 3D: não é fotografia nem registro histórico",
                    "gerada_por_codigo": True, "cena3d": ped.cena, "prioridade_3d": ped.prioridade}
