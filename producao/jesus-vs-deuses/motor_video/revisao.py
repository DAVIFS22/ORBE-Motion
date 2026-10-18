"""Ciclo de revisão antes da renderização final: folhas de contato por batida, métricas objetivas e registro auditável das notas.

Fluxo (cada rodada grava em `09-revisao/rodada-NN/`):
  A) `gerar_rodada` escolhe um quadro por batida relevante de `beats.json` (cortes, seções, eventos sonoros e pontos de animação),
     compõe os quadros com o MESMO compositor do vídeo final (em baixa resolução) e monta folhas de contato rotuladas com
     tempo, compasso:tempo, plano e dados de áudio (nível da música/efeitos/mix no instante);
  B) a avaliação (1–10 em seis critérios) só é aceita por `registrar_avaliacao` se apontar as folhas realmente vistas;
  C/D) as correções e a rodada seguinte ficam registradas no mesmo arquivo; `aprovado` exige todas as notas >= 8;
  E) só então se renderiza o vídeo final.
Nada aqui atribui notas sozinho: as notas vêm de quem olhou as folhas; o código calcula apenas métricas objetivas.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .config import ErroProducao, log, salvar_json

CRITERIOS = ("impacto_2s", "legibilidade_celular", "qualidade_movimento", "variedade_visual", "coerencia_historica", "sincronia_audiovisual")
NOTA_MINIMA = 8
EVENTOS_VISUAIS = {"revelar", "ping", "faixa", "rota"}


# ------------------------------------------------------------------------------------------ amostras ---

def _batida_proxima(batidas: list[dict], t: float) -> dict | None:
    if not batidas:
        return None
    ts = np.array([b["t"] for b in batidas])
    return batidas[int(np.argmin(np.abs(ts - t)))]


def escolher_amostras(tl: dict, grade: dict, limite: float | None = None, separacao_min: float = 0.7) -> tuple[list[dict], str]:
    """Um quadro por batida relevante. Devolve (amostras, decisão registrada).

    Batidas relevantes: (1) a batida mais próxima da entrada de cada plano (corte/transição); (2) planos de motion/3D ganham
    quadros extras no meio e no fim da animação; (3) o primeiro tempo forte de cada seção; (4) as batidas dos eventos sonoros de
    revelação/impacto; (5) os dois primeiros segundos (0,5 / 1,2 / 2,0 s) para avaliar o impacto de abertura.
    """
    batidas = grade.get("batidas", [])
    cand: list[dict] = []

    def add(t, motivo, plano=None, prio=5):
        if limite is not None and t >= limite:
            return
        b = _batida_proxima(batidas, t)
        cand.append({"t": round(float(t), 3), "motivo": motivo, "prio": prio, "plano": plano["id"] if plano else None,
                     "cena": plano["cena_id"] if plano else None,
                     "compasso": b["compasso"] if b else None, "tempo": b["tempo"] if b else None, "forte": b["forte"] if b else None,
                     "dt_batida_ms": round((t - b["t"]) * 1000, 0) if b else None})

    for t in (0.5, 1.2, 2.0):
        add(t, "abertura (impacto nos 2 primeiros segundos)", None, 0)
    for i, p in enumerate(tl["planos"]):
        dur = p["fim"] - p["inicio"]
        t_in = p["inicio"] + min(0.9, 0.25 * dur)
        b = _batida_proxima([x for x in batidas if p["inicio"] + 0.15 <= x["t"] <= p["fim"] - 0.15], t_in)
        add(b["t"] if b and abs(b["t"] - t_in) <= 0.6 else t_in, "entrada do plano (batida mais próxima)", p, 2)
        origem = p["fundo"].get("origem")
        if origem == "motion" or p.get("cena3d"):
            if dur >= 3.0:
                add(p["inicio"] + 0.55 * dur, "meio da animação (motion/3D)", p, 3)
                add(p["inicio"] + max(0.0, dur - 0.9), "fim da animação (motion/3D)", p, 3)
        elif dur >= 8.0:
            add(p["inicio"] + 0.6 * dur, "plano longo: meio", p, 4)
    for s in grade.get("secoes", []):
        add(s["inicio"] + 0.1, f"início da seção {s['id']} (compasso 1, tempo forte)", None, 1)
    for ev in tl.get("eventos_audio", []):
        if ev.get("tipo") in ("impacto", "revelar") and ev["t"] > 0.3:
            add(ev["t"] + 0.12, f"evento sonoro '{ev['tipo']}'", None, 4)
    cand.sort(key=lambda c: (c["t"], c["prio"]))
    # remove quase-duplicatas mantendo a de maior prioridade (menor número)
    mantidas: list[dict] = []
    for c in cand:
        if mantidas and c["t"] - mantidas[-1]["t"] < separacao_min:
            if c["prio"] < mantidas[-1]["prio"]:
                mantidas[-1] = c
            continue
        mantidas.append(c)
    for i, c in enumerate(mantidas):
        c["n"] = i
        c.pop("prio", None)
    decisao = (f"{len(mantidas)} quadros escolhidos entre {len(batidas)} batidas de beats.json: não se mostra uma por batida porque a "
               f"grade tem uma batida a cada ~1 s (vídeo de {tl['duracao_video_s']/60:.0f} min); usam-se as batidas relevantes "
               f"(cortes, seções, eventos sonoros, animações), com separação mínima de {separacao_min} s.")
    return mantidas, decisao


# ----------------------------------------------------------------------------------------- áudio ---

def _wav_info(caminho: Path) -> dict:
    with open(caminho, "rb") as f:
        if f.read(4) != b"RIFF":
            raise ErroProducao(f"{caminho.name} não é WAV.")
        f.read(4)
        f.read(4)
        fmt = None
        while True:
            cab = f.read(8)
            if len(cab) < 8:
                raise ErroProducao(f"{caminho.name}: bloco 'data' ausente.")
            nome, tam = cab[:4], int.from_bytes(cab[4:], "little")
            if nome == b"fmt ":
                d = f.read(tam)
                fmt = {"tag": int.from_bytes(d[0:2], "little"), "canais": int.from_bytes(d[2:4], "little"),
                       "taxa": int.from_bytes(d[4:8], "little"), "bits": int.from_bytes(d[14:16], "little")}
            elif nome == b"data":
                fmt["offset"] = f.tell()
                fmt["bytes"] = tam if tam < 0xFFFFFFF0 else caminho.stat().st_size - f.tell()
                return fmt
            else:
                f.seek(tam + (tam & 1), 1)
                continue
            if tam & 1:
                f.seek(1, 1)


def nivel_db(caminho: Path | None, t: float, janela: float = 0.5, info: dict | None = None) -> float | None:
    """RMS (dBFS) de uma janela centrada em `t`, lendo só os bytes necessários (WAV PCM 16/24/32 ou float32)."""
    if caminho is None or not caminho.is_file():
        return None
    info = info or _wav_info(caminho)
    bps = info["bits"] // 8
    quadro = bps * info["canais"]
    ini = max(0, int((t - janela / 2) * info["taxa"]))
    n = int(janela * info["taxa"])
    with open(caminho, "rb") as f:
        f.seek(info["offset"] + ini * quadro)
        raw = f.read(n * quadro)
    n = len(raw) // quadro
    if n < 16:
        return None
    raw = raw[: n * quadro]
    if info["tag"] == 3 and info["bits"] == 32:
        x = np.frombuffer(raw, dtype="<f4").astype(np.float64)
    elif info["bits"] == 24:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        v = np.where(v >= 1 << 23, v - (1 << 24), v)
        x = v.astype(np.float64) / (1 << 23)
    elif info["bits"] == 16:
        x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    else:
        x = np.frombuffer(raw, dtype="<i4").astype(np.float64) / (1 << 31)
    rms = math.sqrt(float(np.mean(x * x)) + 1e-18)
    return round(20 * math.log10(rms), 1)


# ---------------------------------------------------------------------------------------- quadros ---

def renderizar_amostras(cfg, tl: dict, amostras: list[dict], pasta_imagens: Path, pasta_saida: Path, largura: int = 640, altura: int = 360) -> list[Path]:
    """Compõe os quadros com o compositor do vídeo final (mesmos planos, câmeras, transições, vinheta, grão)."""
    from .visual_effects import Compositor
    planos = [dict(p) for p in tl["planos"]]
    for p in planos:
        p["fundo"] = dict(p["fundo"])
        if p["fundo"].get("arquivo") and (p["fundo"].get("tipo") == "imagem" or p["fundo"].get("relativo_imagens")):
            p["fundo"]["arquivo"] = str((pasta_imagens / p["fundo"]["arquivo"]).resolve())
    pasta_saida.mkdir(parents=True, exist_ok=True)
    comp = Compositor(planos, largura, altura, tl["fps"], tl["duracao_video_s"], cfg.pasta("06-temporarios") / "procedural-revisao", rapido=True)
    arquivos = []
    try:
        for a in amostras:
            n = int(round(a["t"] * tl["fps"]))
            destino = pasta_saida / f"q{a['n']:04d}_{a['t']:08.2f}s.png"
            comp.quadro(n).save(destino)
            arquivos.append(destino)
    finally:
        comp.fechar()
    return arquivos


def _fonte(tam: int):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
              "C:/Windows/Fonts/arial.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        if Path(f).is_file():
            return ImageFont.truetype(f, tam)
    return ImageFont.load_default()


def _mmss(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def montar_folhas(amostras: list[dict], quadros: list[Path], destino: Path, colunas: int = 4, linhas: int = 5,
                  miniatura: tuple[int, int] = (480, 270)) -> list[Path]:
    """Folhas de contato rotuladas: cada miniatura traz tempo, compasso:tempo, plano, motivo e níveis de áudio."""
    destino.mkdir(parents=True, exist_ok=True)
    mw, mh = miniatura
    rot_h = 58
    f1, f2 = _fonte(15), _fonte(13)
    por_folha = colunas * linhas
    folhas = []
    for k in range(0, len(amostras), por_folha):
        grupo = list(zip(amostras[k:k + por_folha], quadros[k:k + por_folha]))
        n_lin = math.ceil(len(grupo) / colunas)
        folha = Image.new("RGB", (colunas * mw, n_lin * (mh + rot_h)), (14, 14, 18))
        d = ImageDraw.Draw(folha)
        for i, (a, q) in enumerate(grupo):
            x, y = (i % colunas) * mw, (i // colunas) * (mh + rot_h)
            im = Image.open(q).convert("RGB").resize((mw, mh), Image.LANCZOS)
            folha.paste(im, (x, y))
            ct = f"{a['compasso']}:{a['tempo']}{'*' if a.get('forte') else ''}" if a.get("compasso") else "-"
            au = a.get("audio", {})
            fmt = lambda v: "—" if v is None else f"{v:.0f}"          # noqa: E731
            d.text((x + 6, y + mh + 4), f"#{a['n']}  {_mmss(a['t'])}  c:t {ct}  Δbat {a.get('dt_batida_ms', 0):+.0f}ms", fill=(236, 230, 214), font=f1)
            d.text((x + 6, y + mh + 24), f"{(a.get('plano') or 'sem plano')[:30]} · {a['motivo'][:34]}", fill=(180, 170, 140), font=f2)
            d.text((x + 6, y + mh + 40), f"áudio dB  mix {fmt(au.get('mix'))}  música {fmt(au.get('musica'))}  efeitos {fmt(au.get('efeitos'))}", fill=(120, 170, 200), font=f2)
        arq = destino / f"folha-{k // por_folha + 1:02d}.png"
        folha.save(arq)
        folhas.append(arq)
    return folhas


# ---------------------------------------------------------------------------------------- métricas ---

def metricas_objetivas(tl: dict, grade: dict, amostras: list[dict], quadros: list[Path]) -> dict:
    """Métricas calculadas (não são notas): variedade visual, sincronia dos cortes com a grade e energia da abertura."""
    batidas = np.array([b["t"] for b in grade.get("batidas", [])]) if grade.get("batidas") else np.array([])
    planos = tl["planos"]
    total = tl["duracao_video_s"]
    # mudanças visuais significativas = entradas de plano + eventos visuais de motion/3D (revelações, marcadores, rotas)
    mudancas = [p["inicio"] for p in planos[1:]]
    for ev in tl.get("eventos_audio", []):
        if ev.get("tipo") in EVENTOS_VISUAIS:
            mudancas.append(ev["t"])
    mudancas = sorted(set(round(t, 2) for t in mudancas))
    pontos = [0.0] + mudancas + [total]
    janelas = np.diff(pontos)
    longas = [(round(pontos[i], 1), round(float(janelas[i]), 1)) for i in np.argsort(-janelas)[:8]]
    tempo_longo = float(janelas[janelas > 4.0].sum())
    anim = sum(p["fim"] - p["inicio"] for p in planos if p["fundo"].get("origem") == "motion" or p.get("cena3d"))
    por_tipo: dict[str, float] = {}
    for p in planos:
        f = p["fundo"]
        k = "motion/3D (Three.js, Canvas, SVG)" if f.get("origem") == "motion" else "3D Blender" if p.get("cena3d") else \
            "imagem/foto" if f.get("tipo") == "imagem" else "vídeo/filmagem" if f.get("tipo") == "video" else "cenário procedural"
        por_tipo[k] = por_tipo.get(k, 0.0) + (p["fim"] - p["inicio"])
    # sincronia dos cortes com a grade
    dist = []
    if len(batidas):
        for p in planos[1:]:
            dist.append(float(np.min(np.abs(batidas - p["inicio"]))))
    dist_a = np.array(dist) if dist else np.array([0.0])
    # energia da abertura: diferença média entre quadros consecutivos dentro de 0–2 s e contraste do quadro de 2,0 s
    abertura = [(a, q) for a, q in zip(amostras, quadros) if a["motivo"].startswith("abertura")]
    energia = None
    contraste = None
    if len(abertura) >= 2:
        ims = [np.asarray(Image.open(q).convert("L").resize((160, 90)), dtype=np.float64) for _, q in abertura]
        energia = round(float(np.mean([np.mean(np.abs(ims[i + 1] - ims[i])) for i in range(len(ims) - 1)])), 2)
        contraste = round(float(np.std(ims[-1])), 1)
    return {
        "variedade_visual": {"mudancas_significativas": len(mudancas), "intervalo_mediano_s": round(float(np.median(janelas)), 2),
                             "tempo_em_janelas_maiores_que_4s_pct": round(100 * tempo_longo / total, 1),
                             "maiores_janelas_estaticas": [{"inicio_s": a, "duracao_s": b} for a, b in longas],
                             "tempo_com_animacao_continua_motion_3d_pct": round(100 * anim / total, 1),
                             "tempo_por_tipo_de_fundo_pct": {k: round(100 * v / total, 1) for k, v in sorted(por_tipo.items(), key=lambda kv: -kv[1])}},
        "sincronia_cortes_com_grade": {"cortes": len(dist), "mediana_ms": round(float(np.median(dist_a)) * 1000), "p90_ms": round(float(np.percentile(dist_a, 90)) * 1000),
                                       "dentro_de_120ms_pct": round(100 * float(np.mean(dist_a <= 0.12)), 1)},
        "abertura_0_2s": {"energia_media_entre_quadros": energia, "contraste_quadro_2s": contraste},
    }


# ----------------------------------------------------------------------------------------- rodada ---

def gerar_rodada(cfg, tl: dict, grade: dict, pasta_imagens: Path, mix: Path | None, stem_musica: Path | None, stem_efeitos: Path | None,
                 rodada: int, limite: float | None = None) -> dict:
    """Etapa A: quadros por batida, dados de áudio, folhas de contato e métricas. Devolve o caminho de cada artefato."""
    base = cfg.pasta("09-revisao") / f"rodada-{rodada:02d}"
    amostras, decisao = escolher_amostras(tl, grade, limite)
    log().info("Revisão, rodada %d: %d quadros (%s)", rodada, len(amostras), decisao)
    quadros = renderizar_amostras(cfg, tl, amostras, pasta_imagens, base / "quadros")
    infos = {k: (_wav_info(p) if p and p.is_file() else None) for k, p in (("mix", mix), ("musica", stem_musica), ("efeitos", stem_efeitos))}
    for a in amostras:
        a["audio"] = {"mix": nivel_db(mix, a["t"], info=infos["mix"]), "musica": nivel_db(stem_musica, a["t"], info=infos["musica"]),
                      "efeitos": nivel_db(stem_efeitos, a["t"], info=infos["efeitos"])}
    folhas = montar_folhas(amostras, quadros, base)
    met = metricas_objetivas(tl, grade, amostras, quadros)
    salvar_json(base / "amostras.json", {"decisao": decisao, "amostras": amostras})
    salvar_json(base / "metricas.json", met)
    log().info("   folhas de contato: %s", ", ".join(f.name for f in folhas))
    return {"pasta": str(base), "folhas": [str(f) for f in folhas], "amostras": len(amostras), "metricas": met, "decisao": decisao}


def registrar_avaliacao(pasta_rodada: Path, notas: dict, justificativas: dict, piores_problemas: list[dict], evidencias: list[str],
                        correcoes_aplicadas: list[str] | None = None) -> dict:
    """Etapa B/C: grava a avaliação. Exige: as seis notas (1–10), justificativa por nota e evidências (folhas/arquivos) existentes."""
    faltam = [c for c in CRITERIOS if c not in notas]
    if faltam:
        raise ErroProducao(f"Faltam notas para: {', '.join(faltam)}")
    for c, v in notas.items():
        if not (isinstance(v, (int, float)) and 1 <= v <= 10):
            raise ErroProducao(f"Nota inválida em {c}: {v!r} (use 1 a 10)")
        if not str(justificativas.get(c, "")).strip():
            raise ErroProducao(f"Falta a justificativa da nota de {c}")
    if not evidencias:
        raise ErroProducao("Nenhuma evidência informada: não há nota sem inspeção das folhas de contato e dos dados de áudio.")
    ausentes = [e for e in evidencias if not (pasta_rodada / e).exists() and not Path(e).exists()]
    if ausentes:
        raise ErroProducao(f"Evidências inexistentes: {ausentes}")
    if len(piores_problemas) != 3 and min(notas.values()) < NOTA_MINIMA:
        raise ErroProducao("Quando alguma nota é menor que 8, liste exatamente os 3 piores problemas.")
    aval = {"rodada": pasta_rodada.name, "notas": notas, "justificativas": justificativas, "piores_problemas": piores_problemas,
            "correcoes_aplicadas": correcoes_aplicadas or [], "evidencias": evidencias, "aprovado": all(v >= NOTA_MINIMA for v in notas.values()),
            "minimo": min(notas.values())}
    salvar_json(pasta_rodada / "avaliacao.json", aval)
    return aval


def resumo_markdown(pasta_revisao: Path) -> str:
    """Consolida todas as rodadas em AVALIACAO.md (notas, problemas, correções e evidências)."""
    linhas = ["# Avaliação visual e sonora antes da renderização final", "",
              "Notas de 1 a 10 dadas por inspeção das folhas de contato (um quadro por batida relevante) e dos dados de áudio rotulados nelas.",
              f"Critério de aprovação: todas as notas ≥ {NOTA_MINIMA}.", ""]
    for rod in sorted(pasta_revisao.glob("rodada-*")):
        f = rod / "avaliacao.json"
        if not f.is_file():
            continue
        a = json.loads(f.read_text(encoding="utf-8"))
        linhas += [f"## {a['rodada']} — {'APROVADA' if a['aprovado'] else 'reprovada (corrigir e repetir)'}", "",
                   "| Critério | Nota | Justificativa |", "|---|---|---|"]
        for c in CRITERIOS:
            linhas.append(f"| {c.replace('_', ' ')} | {a['notas'][c]} | {a['justificativas'][c]} |")
        if a["piores_problemas"]:
            linhas += ["", "Três piores problemas:"] + [f"{i + 1}. {p.get('problema', p)} — correção: {p.get('correcao', '-')}" for i, p in enumerate(a["piores_problemas"])]
        if a["correcoes_aplicadas"]:
            linhas += ["", "Correções aplicadas depois desta rodada:"] + [f"- {c}" for c in a["correcoes_aplicadas"]]
        linhas += ["", "Evidências: " + ", ".join(a["evidencias"]), ""]
    return "\n".join(linhas)
