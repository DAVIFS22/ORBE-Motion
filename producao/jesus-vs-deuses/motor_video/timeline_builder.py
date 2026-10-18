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
from . import fundos3d
from .motion_conteudo import CONTEUDO as CONTEUDO_MO
from .visual_effects import PRESETS

DUR_TRANSICAO = {"dissolve": 0.9, "dip_black": 1.2, "dip_gold": 1.4, "dip_white": 1.2, "corte": 0.0}
MIN_CENA_S = 1.5  # cenas mais curtas são incorporadas à anterior
MIN_PLANO_S = 2.2
# Planos com cenário gerado por código: mais curtos e cortados nas frases da narração, alternando o plano aberto com um
# reenquadramento fechado do mesmo cenário (algo novo na tela a cada poucos segundos, sem trocar de lugar).
ALVO_SEM_IMAGEM = {"rapido": 3.6, "normal": 5.0, "lento": 6.5}
ALTERNATIVAS = ("deriva", "pan_dir", "zoom_out", "pan_esq", "tilt_cima", "respiro", "zoom_in", "tilt_baixo")


@dataclass
class CenaPlanejada:
    cena: Cena
    inicio: float
    fim: float
    palavra_ini: int
    ancora_confiavel: bool
    planos_desejados: int = 1
    reserva_3d: bool = False  # o 1º plano será uma cena 3D (não precisa de imagem)
    unico: bool = False       # a cena inteira é um plano só (composição de motion ou texto que a ocupa toda)

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
    motion: dict | None = None  # pedido de composição de motion graphics (Node/Chromium) para este plano, se elegível

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
                   avisos: list[str] | None = None, cfg3d: dict | None = None, cfgmo: dict | None = None) -> list[CenaPlanejada]:
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
        cp.unico = cp.planos_desejados == 1 and _texto_ocupa_cena(cp)
        if cfgmo and cfgmo.get("ok") and cp.cena.mo and cp.duracao <= 16:   # a composição de motion ocupa a cena inteira
            cp.planos_desejados = 1
            cp.unico = True
        cp.reserva_3d = _usa_3d_sempre(cp.cena, cfg3d) and cp.duracao / max(1, cp.planos_desejados) >= MIN_PLANO_S
    return resultado


def _texto_ocupa_cena(cp: CenaPlanejada) -> bool:
    return any(o["tipo"] in ("versiculo", "lista", "ponto", "titulo") for o in cp.cena.overlays) and cp.duracao <= 16


def _quantos_planos(cp: CenaPlanejada, alvo: float) -> int:
    if _texto_ocupa_cena(cp):
        return 1
    return max(1, int(round(cp.duracao / alvo)))


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
    cfg3d: dict | None = None, videos_por_cena: dict[str, Asset] | None = None, cfgmo: dict | None = None,
) -> Timeline:
    avisos = avisos if avisos is not None else []
    planos: list[Plano] = []
    historico: list[str] = []
    cont_stills: dict = {}
    semente = 11
    for cp in planejadas:
        c = cp.cena
        assets = assets_por_cena.get(c.id, [])
        n_w = cp.planos_desejados
        if assets:
            n = min(n_w, max(len(assets), math.ceil(cp.duracao / (1.7 * (RITMOS[c.ritmo] if c.ritmo != "normal" else 11.0)))))
        elif cp.unico or cp.reserva_3d:
            n = max(1, min(n_w, math.ceil(cp.duracao / (1.7 * 11.0))))
        else:
            n = max(1, int(round(cp.duracao / ALVO_SEM_IMAGEM[c.ritmo])))
        n = max(1, min(n, int(cp.duracao // MIN_PLANO_S) or 1))
        cortes = _cortes(al, cp.inicio, cp.fim, n)
        k_mo = 0                               # plano que recebe a composição de motion da cena
        tf = _inicio_da_frase(c, cp, al, cfgmo)
        if tf is not None and not assets and tf - cp.inicio >= 2.6:
            # tipografia cinética que só começa no meio da cena: planos normais antes, a frase entra junto com a fala
            n_pre = max(1, min(int(round((tf - cp.inicio) / ALVO_SEM_IMAGEM[c.ritmo])), int((tf - cp.inicio) // MIN_PLANO_S)))
            cortes = _cortes(al, cp.inicio, tf, n_pre)[:-1] + [tf, cp.fim]
            n, k_mo = len(cortes) - 1, len(cortes) - 2
        remover = set(CONTEUDO_MO[c.mo].get("remove_overlays", [])) if (c.mo and cfgmo and cfgmo.get("ok") and c.mo in CONTEUDO_MO) else set()
        desloc = 1 if cp.reserva_3d else 0   # com 3D reservado no plano 0, as imagens vão para os planos seguintes
        semente += 7                           # mesmo cenário em todos os planos da cena (os cortes mudam o ponto de vista)
        still = fundos3d.escolher(c.secao, c.motivo, cont_stills) if (cfgmo and cfgmo.get("ok") and not assets and not c.mapa) else None
        for k in range(n):
            ini, fim = cortes[k], cortes[k + 1]
            idx_img = k - desloc
            asset = assets[idx_img] if 0 <= idx_img < len(assets) else None
            if cp.reserva_3d and k == 0:
                asset = None
            intens = 1.0 if c.ritmo != "lento" else 0.8
            if k % 2 == 1 and not assets and not c.mapa:
                preset = "fechado"
                camera = {"preset": preset, "intensidade": intens, "lado": 1.0 if (k // 2) % 2 == 0 else -1.0}
            else:
                preset = _escolher_preset(c.camera, k // 2 if not assets else k, historico, asset)
                camera = {"preset": preset, "intensidade": intens}
            historico.append(preset)
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
                if still:                          # cenário 3D estático (renderizado depois, em fundos3d.aplicar)
                    fundo = {"tipo": "still3d", "still": still, "alternativa": fundo}
            if c.foco and asset is not None:
                camera["foco"] = c.foco
            overlays = []
            if k == 0:
                overlays.extend(dict(o) for o in c.overlays if not (k_mo > 0 and o["tipo"] in remover))
            if asset is not None and asset.exige_atribuicao and creditos_na_tela:
                overlays.append({"tipo": "credito", "texto": _credito_tela(asset), "atraso": 1.0,
                                 "duracao": max(1.0, min(6.0, (fim - ini) - 1.6))})
            pedido3d = _pedido_3d(c, k, asset, fim - ini, cfg3d, creditos_na_tela)
            motion = _pedido_motion(c, k, asset, fim - ini, cfgmo, k_mo)
            if motion and motion["comp"] == "frase":
                tt = _tempos_da_frase(c, cp, al, cfgmo)
                if tt:
                    motion["ultima_palavra"] = round(tt[1], 3)
            if motion:                                   # a composição de motion substitui o 3D e traz a própria ficha informativa
                pedido3d = None
                overlays = [o for o in overlays if o["tipo"] not in ("capitulo", "credito", *motion.get("remove_overlays", []))]
            plano = Plano(
                id=f"{c.id}#{k + 1}", cena_id=c.id, secao=c.secao, inicio=ini, fim=fim,
                narracao=sa.texto_entre(al, ini, fim), descricao=c.descricao, fundo=fundo, camera=camera, cor=c.cor,
                transicao_entrada={"tipo": "corte", "duracao": 0.0}, overlays=overlays, fonte=fonte,
                asset_id=asset.id if asset else None, movimento=preset, cena3d=pedido3d, motion=motion,
            )
            planos.append(plano)
            if k == 0 and len(planos) > 1:
                tipo = _transicao_auto(c, planos[-2]) if c.transicao == "auto" else c.transicao
                planos[-1].transicao_entrada = {"tipo": tipo, "duracao": DUR_TRANSICAO[tipo]}
            # k > 0: corte seco no início da frase (o plano seguinte é outro ponto de vista do mesmo assunto)
    _estender_frases(planos, al)
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


def _tempos_da_frase(c: Cena, cp: CenaPlanejada, al: sa.Alinhamento, cfgmo: dict | None) -> tuple[float, float] | None:
    """Tipografia cinética: (primeira, última) palavra da frase em segundos absolutos, pelo alinhamento."""
    if not cfgmo or not cfgmo.get("ok") or not c.mo or CONTEUDO_MO.get(c.mo, {}).get("comp") != "frase":
        return None
    from types import SimpleNamespace
    from .motion_bridge import linhas_da_frase
    falso = SimpleNamespace(inicio=cp.inicio, fim=cp.fim, duracao=cp.duracao)
    linhas, achadas = linhas_da_frase(CONTEUDO_MO[c.mo]["params"]["texto"], falso, al)
    if not achadas:
        return None
    ts = [w["t"] for l in linhas for w in l]
    return cp.inicio + min(ts), cp.inicio + max(ts)


def _inicio_da_frase(c: Cena, cp: CenaPlanejada, al: sa.Alinhamento, cfgmo: dict | None) -> float | None:
    """Para cenas com tipografia cinética: instante (absoluto) em que a frase deve entrar — o início de frase/trecho da
    fala logo antes da primeira palavra (até 1,5 s antes), ou 0,5 s antes dela."""
    tt = _tempos_da_frase(c, cp, al, cfgmo)
    if tt is None:
        return None
    ta = tt[0]
    cand = [t for t in ({al.t_ini[f.palavra_ini] for f in al.frases} | set(_inicios_de_trecho(al))) if ta - 1.5 <= t <= ta - 0.1]
    return max(cand) if cand else max(cp.inicio, ta - 0.5)


def _pedido_motion(c: Cena, k: int, asset: Asset | None, dur: float, cfgmo: dict | None, k_mo: int = 0) -> dict | None:
    """Composição de motion para o plano k, se a cena tiver conteúdo, houver motor e (quando exigida) imagem."""
    if not cfgmo or not cfgmo.get("ok") or not c.mo or k != k_mo or dur < MIN_PLANO_S:
        return None
    from .motion_conteudo import CONTEUDO
    ct = CONTEUDO[c.mo]
    if ct["exige_imagem"] and asset is None:
        return None
    return {"conteudo": c.mo, "comp": ct["comp"], "exige_imagem": ct["exige_imagem"], "imagem": asset.arquivo_trabalho if asset is not None else None,
            "remove_overlays": list(ct.get("remove_overlays", []))}


def _fonte_codigo(descricao: str) -> dict:
    return {"origem": "gerada por código (ORBE Motion)", "titulo": descricao, "autor": "ORBE Motion (código)",
            "licenca": "obra própria, sem material de terceiros", "url": "",
            "natureza": "ilustração gerada por código: não é fotografia nem registro histórico", "gerada_por_codigo": True}


def _transicao_auto(c: Cena, anterior: Plano) -> str:
    """Corte seco na fala, por padrão. Fusão só onde há passagem de tempo/espaço: mudança de seção sem transição própria
    ou cena de ritmo lento (contemplação)."""
    if anterior.secao != c.secao or c.ritmo == "lento":
        return "dissolve"
    return "corte"


def _escolher_preset(preferidos: tuple[str, ...], k: int, historico: list[str], asset: Asset | None) -> str:
    """Preset de câmera preferido pela cena, evitando repetir os movimentos dos planos mais recentes."""
    recentes = [p for p in historico[-3:] if p != "fechado"]
    anterior = recentes[-1] if recentes else ""
    if asset is not None and asset.largura / max(1, asset.altura) >= 2.3:
        return "pan_dir" if anterior != "pan_dir" else "pan_esq"
    cand = [preferidos[(k + i) % len(preferidos)] for i in range(len(preferidos))]
    for p in cand:
        if p not in recentes:
            return p
    uso = {p: historico[-12:].count(p) for p in ALTERNATIVAS}
    livres = [p for p in ALTERNATIVAS if p not in recentes and p in PRESETS]
    return min(livres, key=lambda p: (uso[p], ALTERNATIVAS.index(p))) if livres else cand[0]


LEITURA_S = 1.3   # tempo mínimo de tela da frase depois da última palavra dita


def _estender_frases(planos: list[Plano], al: sa.Alinhamento):
    """Corte em L: se a última palavra da tipografia é dita perto do fim do plano, o plano avança sobre o seguinte (um plano
    comum, que continua com duração mínima) para dar tempo de leitura."""
    for i, p in enumerate(planos[:-1]):
        m = p.motion
        if not m or m.get("comp") != "frase" or "ultima_palavra" not in m:
            continue
        falta = m["ultima_palavra"] + LEITURA_S - p.fim
        prox = planos[i + 1]
        if falta <= 0.05 or prox.motion or prox.cena3d or prox.fundo.get("tipo") == "video" or prox.secao != p.secao:   # não mexe nas fronteiras de seção (música)
            continue
        ext = min(falta, prox.duracao - MIN_PLANO_S)
        if ext <= 0.05:
            continue
        p.fim = round(p.fim + ext, 4)
        prox.inicio = p.fim
        p.narracao, prox.narracao = sa.texto_entre(al, p.inicio, p.fim), sa.texto_entre(al, prox.inicio, prox.fim)


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


def coletar_pedidos_motion(tl: Timeline, al: sa.Alinhamento | None, pasta_imagens, batidas: list[float] | None = None,
                           limite: float | None = None) -> list:
    """Pedidos de composição de motion: duração visível = plano; pré/pós-rolagem = metade das transições vizinhas."""
    from .motion_bridge import PedidoMotion, montar_params, semente
    from .motion_conteudo import CONTEUDO
    pedidos = []
    for i, p in enumerate(tl.planos):
        if not p.motion or (limite is not None and p.inicio >= limite):
            continue
        d_in = p.transicao_entrada["duracao"] if p.transicao_entrada["tipo"] != "corte" else 0.0
        d_out = 0.0
        if i + 1 < len(tl.planos):
            prox = tl.planos[i + 1].transicao_entrada
            d_out = prox["duracao"] if prox["tipo"] != "corte" else 0.0
        m = p.motion
        imagem = str((pasta_imagens / m["imagem"]).resolve()) if m.get("imagem") else None
        if imagem is None and CONTEUDO[m["conteudo"]].get("fundo_do_plano"):
            imagem = fundo_do_plano(p, pasta_imagens)
        pedidos.append(PedidoMotion(
            plano_id=p.id, conteudo=m["conteudo"], comp=m["comp"], dur_visivel=p.duracao, t0=d_in / 2, t1=d_out / 2,
            params=montar_params(m["conteudo"], p, al, batidas or []), imagem=imagem, seed=semente(p.id)))
    return pedidos


def fundo_do_plano(p: Plano, pasta_imagens) -> str | None:
    """Imagem do fundo do plano com a mesma correção de cor do filme (para composições que desenham sobre ele)."""
    import hashlib
    import json
    from pathlib import Path
    from .visual_effects import FonteVisual, aplicar_grade
    f = dict(p.fundo)
    if f["tipo"] not in ("motivo", "imagem", "mapa"):
        return None
    if f["tipo"] == "imagem" and not Path(f["arquivo"]).is_absolute():
        f["arquivo"] = str(Path(pasta_imagens) / f["arquivo"])
    chave = hashlib.sha1(json.dumps({"f": f, "cor": p.cor}, sort_keys=True).encode()).hexdigest()[:16]
    destino = Path(pasta_imagens) / "trabalho" / "fundos-motion" / f"{chave}.jpg"
    if not destino.is_file():
        img, _ = FonteVisual._carregar(f, None)
        destino.parent.mkdir(parents=True, exist_ok=True)
        aplicar_grade(img, p.cor, auto_contraste=f["tipo"] == "imagem" and not f.get("gerada")).save(destino, quality=93)
    return str(destino.resolve())


def aplicar_clipes_motion(tl: Timeline, pedidos: list, fps: int):
    """Troca o fundo dos planos cujo clipe de motion foi gerado e inclui os eventos sonoros das revelações."""
    por_id = {p.plano_id: p for p in pedidos}
    novos = []
    for pl in tl.planos:
        ped = por_id.get(pl.id)
        if ped is None or ped.status not in ("renderizado", "reaproveitado") or not ped.clipe:
            continue
        ficha = ped.params.get("ficha", {})
        pl.fundo = {"tipo": "video", "arquivo": ped.clipe, "fps": fps, "inicio_clip": 0.0, "origem": "motion", "composicao": ped.comp}
        pl.movimento = f"motion graphics ({ped.comp})"
        pl.overlays = [o for o in pl.overlays if o["tipo"] not in ("credito", "rotulo", "capitulo", *((pl.motion or {}).get("remove_overlays", [])))]
        pl.cena3d = None
        cena3d_js = ped.comp.startswith("cena3d_")
        pl.fonte = {"origem": ("Cena 3D por código (Three.js/WebGL, geometria e texturas procedurais)" if cena3d_js
                               else "Motion graphics (HTML/CSS/SVG/Canvas/GSAP, gerado por código)"), "titulo": f"{ped.comp}: {ficha.get('nome', ped.conteudo)}",
                    "autor": "ORBE Motion (código)", "licenca": "obra própria; imagem fornecida pelo usuário: licença não verificada" if ped.imagem else "obra própria, sem material de terceiros",
                    "url": "", "natureza": ("reconstrução artística por código: não é evidência arqueológica nem fotografia" if cena3d_js
                                            else "gráfico informativo animado; ilustrações modernas não são fontes históricas"),
                    "gerada_por_codigo": True, "composicao": ped.comp, "categoria_informacao": ficha.get("categoria")}
        proprios = {e.get("tipo") for e in ped.eventos}
        if proprios & {"impacto", "whoosh"}:       # o clipe traz o próprio impacto/whoosh sincronizado: tira o do storyboard nesta cena
            tl.eventos_audio = [ev for ev in tl.eventos_audio if not (ev.get("cena") == pl.cena_id and ev["tipo"] in proprios & {"impacto", "whoosh"})]
        for e in ped.eventos:
            if e.get("tipo") in ("revelar", "ping", "faixa", "rota", "whoosh", "impacto"):
                novos.append({"t": round(pl.inicio + float(e["t"]), 3), "tipo": e["tipo"], "cena": pl.cena_id, "origem": "motion", "comp": ped.comp})
    if novos:
        tl.eventos_audio.extend(novos)
        tl.eventos_audio.sort(key=lambda ev: ev["t"])
