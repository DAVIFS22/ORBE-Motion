"""Validação do vídeo final. O fim do FFmpeg sem erro NÃO é critério de sucesso.

Verificações: integridade e decodificação completa, fluxos (codec, resolução, FPS,
canais), duração em relação à narração, sincronia de áudio por correlação cruzada
com a narração, quadros do vídeo contra o que a linha do tempo manda mostrar
(imagens ausentes/ordem errada), telas pretas inesperadas, congelamentos, clipping
e loudness, legendas e integridade dos arquivos originais.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import subtitle_generator as sg
from .audio_mixer import decodificar_mono
from .config import Config, ErroProducao, ffprobe_json, log
from .timeline_builder import Timeline


@dataclass
class Item:
    nome: str
    status: str  # ok | aviso | falha
    detalhe: str
    dados: dict = field(default_factory=dict)


@dataclass
class Resultado:
    itens: list[Item] = field(default_factory=list)

    def add(self, nome, status, detalhe, **dados):
        self.itens.append(Item(nome, status, detalhe, dados))
        marca = {"ok": "OK   ", "aviso": "AVISO", "falha": "FALHA"}[status]
        log().info("  [%s] %s: %s", marca, nome, detalhe)

    @property
    def ok(self) -> bool:
        return not any(i.status == "falha" for i in self.itens)

    def para_dict(self) -> dict:
        return {"aprovado": self.ok, "itens": [i.__dict__ for i in self.itens]}


def _fracao(txt: str) -> float:
    a, _, b = txt.partition("/")
    return float(a) / float(b or 1) if float(b or 1) else 0.0


def _analisar_streams(video: Path, cfg: Config, res: Resultado, tem_legenda: bool):
    info = ffprobe_json(video)
    s = info.get("streams", [])
    v = [x for x in s if x["codec_type"] == "video"]
    a = [x for x in s if x["codec_type"] == "audio"]
    st = [x for x in s if x["codec_type"] == "subtitle"]
    if len(v) != 1 or len(a) != 1:
        res.add("fluxos", "falha", f"esperado 1 faixa de vídeo e 1 de áudio; encontrado {len(v)} e {len(a)}")
        return info, None, None
    v, a = v[0], a[0]
    problemas = []
    if v["codec_name"] != "h264":
        problemas.append(f"codec de vídeo {v['codec_name']}")
    if v.get("pix_fmt") != "yuv420p":
        problemas.append(f"pix_fmt {v.get('pix_fmt')}")
    if (v["width"], v["height"]) != (cfg.largura, cfg.altura):
        problemas.append(f"resolução {v['width']}x{v['height']}")
    if abs(_fracao(v["r_frame_rate"]) - cfg.fps) > 0.01 or abs(_fracao(v["avg_frame_rate"]) - cfg.fps) > 0.05:
        problemas.append(f"FPS {v['r_frame_rate']} (média {v['avg_frame_rate']})")
    if a["codec_name"] != "aac" or a.get("channels") != 2 or int(a.get("sample_rate", 0)) != 48000:
        problemas.append(f"áudio {a['codec_name']} {a.get('channels')}ch {a.get('sample_rate')}Hz")
    if tem_legenda and not st:
        problemas.append("trilha de legendas ausente")
    if problemas:
        res.add("fluxos", "falha", "; ".join(problemas))
    else:
        res.add("fluxos", "ok", f"H.264 {v['width']}x{v['height']} {v['r_frame_rate']} fps yuv420p + AAC estéreo 48 kHz"
                + (" + legendas" if st else ""))
    return info, v, a


def _janelas_pretas_permitidas(tl: Timeline, dur: float) -> list[tuple[float, float]]:
    ok = [(0.0, 1.4), (dur - 2.2, dur + 1)]
    for p in tl.planos:
        t = p.transicao_entrada
        if t["tipo"] == "dip_black":
            c = p.inicio
            ok.append((c - t["duracao"] / 2 - 0.15, c + t["duracao"] / 2 + 0.15))
    return ok


def _passada_analise(video: Path, tl: Timeline, res: Resultado, dur_video: float, alvo_lufs: float):
    """Uma única decodificação completa: erros de decodificação, preto, congelamento, silêncio, loudness."""
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-v", "info", "-i", str(video),
           "-vf", "blackdetect=d=0.3:pix_th=0.06:pic_th=0.985,freezedetect=n=0.0008:d=5",
           "-af", "silencedetect=n=-60dB:d=3,ebur128=peak=true:framelog=quiet", "-f", "null", "-"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    saida = proc.stderr
    erros = [l for l in saida.splitlines() if re.search(r"\b(error|invalid|corrupt|missing|concealing)\b", l, re.I)
             and "ebur128" not in l.lower()]
    if proc.returncode != 0 or erros:
        res.add("reprodução", "falha", f"erros ao decodificar do início ao fim: {' | '.join(erros[:3]) or proc.returncode}")
    else:
        res.add("reprodução", "ok", "decodificação completa sem erros, do início ao fim")

    pretos = [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", saida)]
    permitido = _janelas_pretas_permitidas(tl, dur_video)
    inesperados = [(a, b) for a, b in pretos if not any(a >= p0 - 0.05 and b <= p1 + 0.05 for p0, p1 in permitido)]
    if inesperados:
        res.add("telas pretas", "falha", "tela preta inesperada em " + ", ".join(f"{a:.1f}-{b:.1f}s" for a, b in inesperados[:6]),
                intervalos=inesperados)
    else:
        res.add("telas pretas", "ok", f"nenhuma tela preta inesperada ({len(pretos)} intervalo(s) escuros previstos: fades/transições)")

    congelados = re.findall(r"freeze_start: ([\d.]+)", saida)
    if congelados:
        res.add("congelamento", "aviso", f"imagem sem variação ≥5 s em {len(congelados)} ponto(s), ex.: {congelados[:4]}")
    else:
        res.add("congelamento", "ok", "nenhum trecho de imagem congelada")

    pico = re.search(r"Peak:\s+(-?[\d.]+) dBFS", saida)
    integ = re.search(r"I:\s+(-?[\d.]+) LUFS", saida)
    if pico and integ:
        p, i = float(pico.group(1)), float(integ.group(1))
        if p > -0.5:
            res.add("clipping", "falha", f"pico real de {p:.1f} dBTP (possível clipping)")
        else:
            res.add("clipping", "ok", f"pico real {p:.1f} dBTP (sem clipping)")
        if abs(i - alvo_lufs) > 1.5:
            res.add("loudness", "aviso", f"{i:.1f} LUFS (alvo {alvo_lufs:.1f})")
        else:
            res.add("loudness", "ok", f"{i:.1f} LUFS integrado (alvo {alvo_lufs:.1f})")
    else:
        res.add("loudness", "aviso", "não foi possível ler as medições de loudness")
    silencios = re.findall(r"silence_start: ([\d.]+)", saida)
    if silencios:
        res.add("silêncios", "aviso", f"{len(silencios)} silêncio(s) ≥3 s (abaixo de -60 dB) começando em {silencios[:5]} s")
    else:
        res.add("silêncios", "ok", "nenhum silêncio acidental ≥3 s")


def _correlacao_lag(ref: np.ndarray, sig: np.ndarray, taxa: int, max_lag_s: float = 0.5) -> tuple[float, float]:
    """Atraso (s) de `sig` em relação a `ref` e correlação normalizada no pico."""
    n = len(ref) + len(sig)
    nfft = 1 << (n - 1).bit_length()
    r = ref - ref.mean()
    s = sig - sig.mean()
    cc = np.fft.irfft(np.fft.rfft(s, nfft) * np.conj(np.fft.rfft(r, nfft)), nfft)
    m = int(max_lag_s * taxa)
    cc = np.concatenate([cc[-m:], cc[: m + 1]])
    k = int(np.argmax(cc))
    lag = (k - m) / taxa
    den = np.sqrt((r ** 2).sum() * (s ** 2).sum()) + 1e-12
    return lag, float(cc[k] / den)


def _sincronia_audio(video: Path, narracao_wav: Path, narr: dict, res: Resultado, limite_s: float | None):
    taxa = 8000
    ref = decodificar_mono(narracao_wav, taxa)
    sig = decodificar_mono(video, taxa)
    atividade = narr["atividade"]
    res_hz = narr["resolucao_hz"]
    dur = min(len(ref), len(sig)) / taxa
    if limite_s:
        dur = min(dur, limite_s)
    janela = 20.0
    # janelas centradas em trechos com fala contínua, distribuídas ao longo do vídeo
    pontos = np.linspace(janela, max(janela, dur - janela - 1), 7)
    lags = []
    for p in pontos:
        i0, i1 = int(p * res_hz), int((p + janela) * res_hz)
        if i1 > len(atividade) or atividade[i0:i1].mean() < 0.6:
            continue
        a, b = int(p * taxa), int((p + janela) * taxa)
        lag, c = _correlacao_lag(ref[a:b], sig[a:b], taxa)
        lags.append((p, lag, c))
    if not lags:
        res.add("sincronia áudio", "aviso", "nenhuma janela de fala contínua para medir a sincronia")
        return
    piores = max(abs(l[1]) for l in lags)
    fracas = [l for l in lags if l[2] < 0.35]
    detalhe = "; ".join(f"{p:.0f}s: {lag * 1000:+.1f} ms (r={c:.2f})" for p, lag, c in lags)
    if piores > 0.02:
        res.add("sincronia áudio", "falha", f"atraso entre narração e áudio final acima de 20 ms: {detalhe}")
    elif fracas:
        res.add("sincronia áudio", "aviso", f"correlação baixa em {len(fracas)} janela(s): {detalhe}")
    else:
        res.add("sincronia áudio", "ok", f"narração do vídeo alinhada com a original (maior desvio {piores * 1000:.1f} ms): {detalhe}")


def _amostrar_quadros(video: Path, numeros: list[int], w: int, h: int) -> list[np.ndarray]:
    expr = "+".join(f"eq(n,{n})" for n in numeros)
    cmd = ["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"select='{expr}',scale={w}:{h}:flags=area,format=gray",
           "-vsync", "0", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise ErroProducao("Falha ao extrair quadros para verificação: " + proc.stderr.decode(errors="replace")[-300:])
    dados = np.frombuffer(proc.stdout, np.uint8)
    n = len(dados) // (w * h)
    return [dados[i * w * h:(i + 1) * w * h].reshape(h, w).astype(np.float32) for i in range(n)]


def _quadros_vs_timeline(video: Path, tl: Timeline, cfg: Config, pasta_imagens: Path, res: Resultado, dur: float,
                         cache_proc: Path | None = None):
    """Compara quadros reais do MP4 com o que a linha do tempo manda exibir naquele instante."""
    from .visual_effects import Compositor
    w, h = 320, 180
    amostras: list[tuple[int, str]] = []
    for p in tl.planos:
        if p.inicio >= dur:
            break
        t = p.inicio + 0.45 * min(p.duracao, dur - p.inicio)
        amostras.append((int(round(t * cfg.fps)), p.id))
    amostras.sort()
    numeros = [n for n, _ in amostras]
    reais = _amostrar_quadros(video, numeros, w, h)
    if len(reais) != len(numeros):
        res.add("quadros x linha do tempo", "falha", f"{len(numeros)} quadros pedidos, {len(reais)} extraídos")
        return
    planos = tl.planos_dict()
    for p in planos:
        if p["fundo"].get("arquivo"):
            p["fundo"]["arquivo"] = str((pasta_imagens / p["fundo"]["arquivo"]).resolve())
    comp = Compositor(planos, w, h, cfg.fps, tl.duracao_video, cache_proc, rapido=True, grao=False)
    ruins, medias = [], []
    from PIL import Image, ImageFilter

    def suave(x: np.ndarray) -> np.ndarray:  # compara estrutura grossa: tolera deslocamentos de 1 px em texto fino
        return np.asarray(Image.fromarray(np.clip(x, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)), np.float32)

    for (n, pid), real in zip(amostras, reais):
        esperado = np.asarray(comp.quadro(n).convert("L"), np.float32)
        a, b = suave(real) - suave(real).mean(), suave(esperado) - suave(esperado).mean()
        den = np.sqrt((a ** 2).sum() * (b ** 2).sum())
        r = float((a * b).sum() / den) if den > 1e-6 else (1.0 if abs(real.mean() - esperado.mean()) < 6 else 0.0)
        medias.append(r)
        if real.mean() < 2.5:
            ruins.append((pid, "quadro preto", r))
        elif r < 0.80:
            ruins.append((pid, f"correlação {r:.2f}", r))
    if ruins:
        res.add("quadros x linha do tempo", "falha",
                f"{len(ruins)} de {len(amostras)} quadros não correspondem ao previsto: " + "; ".join(f"{p} ({m})" for p, m, _ in ruins[:5]))
    else:
        res.add("quadros x linha do tempo", "ok",
                f"{len(amostras)} quadros amostrados (um por plano) coincidem com a linha do tempo "
                f"(correlação média {np.mean(medias):.3f}, mínima {np.min(medias):.3f})", correlacao_media=float(np.mean(medias)))


def verificar(video: Path, narracao_wav: Path, narr: dict, tl: Timeline, cfg: Config, pasta_imagens: Path,
              legendas_srt: Path | None, originais: dict | None, cache_proc: Path | None = None) -> Resultado:
    res = Resultado()
    log().info("Validando %s", video.name)
    if not video.is_file() or video.stat().st_size < 10_000:
        res.add("arquivo", "falha", f"MP4 inexistente ou vazio: {video}")
        return res
    res.add("arquivo", "ok", f"{video.name} ({video.stat().st_size / 1e6:.1f} MB)")

    info, v, a = _analisar_streams(video, cfg, res, legendas_srt is not None and legendas_srt.is_file())
    if v is None:
        return res

    # duração e sincronização de contêiner
    dur_fmt = float(info["format"]["duration"])
    dur_v, dur_a = float(v.get("duration", dur_fmt)), float(a.get("duration", dur_fmt))
    esperado = min(tl.duracao_video, cfg.limite_segundos) if cfg.limite_segundos else tl.duracao_video
    narr_dur = narr["duracao_s"] if not cfg.limite_segundos else min(narr["duracao_s"], cfg.limite_segundos)
    um_quadro = 1.0 / cfg.fps
    erros = []
    if dur_fmt < narr_dur - 0.03:
        erros.append(f"vídeo ({dur_fmt:.2f}s) termina antes da narração ({narr_dur:.2f}s)")
    if abs(dur_fmt - esperado) > 0.15:
        erros.append(f"duração {dur_fmt:.2f}s difere da prevista {esperado:.2f}s")
    if abs(dur_v - dur_a) > 0.1:
        erros.append(f"faixas com durações diferentes: vídeo {dur_v:.3f}s, áudio {dur_a:.3f}s")
    ini_v, ini_a = float(v.get("start_time", 0)), float(a.get("start_time", 0))
    if abs(ini_v - ini_a) > 0.05:
        erros.append(f"início das faixas defasado: vídeo {ini_v:.3f}s, áudio {ini_a:.3f}s")
    if erros:
        res.add("duração e sincronia de faixas", "falha", "; ".join(erros))
    else:
        res.add("duração e sincronia de faixas", "ok",
                f"vídeo {dur_v:.3f}s, áudio {dur_a:.3f}s, narração {narr_dur:.3f}s; início das faixas {ini_v:.3f}/{ini_a:.3f}s")

    proc = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                           "stream=nb_read_frames", "-of", "csv=p=0", str(video)], capture_output=True, text=True)
    try:
        n_real = int(proc.stdout.strip().split(",")[0])
        n_esp = int(round(esperado * cfg.fps))
        if abs(n_real - n_esp) > 1:
            res.add("quadros", "falha", f"{n_real} quadros; esperado {n_esp}")
        else:
            res.add("quadros", "ok", f"{n_real} quadros a {cfg.fps} fps (esperado {n_esp})")
    except ValueError:
        res.add("quadros", "aviso", "não foi possível contar os quadros")

    _passada_analise(video, tl, res, dur_fmt, cfg.loudness_alvo)
    try:
        _sincronia_audio(video, narracao_wav, narr, res, cfg.limite_segundos)
    except ErroProducao as e:
        res.add("sincronia áudio", "falha", str(e))
    try:
        _quadros_vs_timeline(video, tl, cfg, pasta_imagens, res, dur_fmt, cache_proc)
    except ErroProducao as e:
        res.add("quadros x linha do tempo", "falha", str(e))

    faltando = [p.id for p in tl.planos if p.fundo.get("arquivo") and not (pasta_imagens / p.fundo["arquivo"]).is_file()]
    if faltando:
        res.add("imagens da linha do tempo", "falha", f"arquivo ausente para: {faltando[:5]}")
    else:
        n_img = sum(1 for p in tl.planos if p.fundo.get("arquivo"))
        res.add("imagens da linha do tempo", "ok", f"{n_img} plano(s) com imagem baixada (todos os arquivos existem); "
                f"{len(tl.planos) - n_img} com cenário gerado por código")

    if legendas_srt is not None and legendas_srt.is_file():
        lg = sg.ler_srt(legendas_srt)
        problemas = sg.validar(lg, dur_fmt)
        if problemas or not lg:
            res.add("legendas", "falha", "; ".join(problemas[:4]) or "SRT vazio")
        else:
            res.add("legendas", "ok", f"{len(lg)} legendas, sem sobreposição, dentro da duração do áudio")

    if originais:
        alterados = [k for k, v in originais.items() if not v["inalterado"]]
        if alterados:
            res.add("arquivos originais", "falha", f"originais alterados: {alterados}")
        else:
            res.add("arquivos originais", "ok", "os arquivos originais continuam idênticos (SHA-256)")
    return res
