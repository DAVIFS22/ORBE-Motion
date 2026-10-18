"""Gráficos de inspeção do áudio (PNG, sem matplotlib): forma de onda e nível por faixa, com seções e eventos marcados, e espectrograma.

Servem para inspecionar visualmente o que foi medido (níveis, ducking, caudas, estalos). Não substituem a escuta.
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

CORES = {"narração": (236, 230, 214), "música": (232, 190, 105), "efeitos": (120, 170, 210), "fundo": (170, 150, 120), "mix": (200, 205, 215)}


def _fonte(t: int):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"):
        if Path(f).is_file():
            return ImageFont.truetype(f, t)
    return ImageFont.load_default()


def _mono(caminho: Path, taxa: int, ini: float = 0.0, dur: float | None = None) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{ini:.3f}", *(["-t", f"{dur:.3f}"] if dur else []), "-i", str(caminho), "-ac", "1", "-ar", str(taxa), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, np.float32)


def formas_de_onda(destino: Path, faixas: list[tuple[str, Path]], duracao: float, marcos: list[tuple[float, str]] | None = None,
                   secoes: list[tuple[float, str]] | None = None, largura: int = 1800, alt_faixa: int = 170) -> Path:
    """Uma linha por faixa: envoltória mín/máx (forma de onda) + curva de nível RMS em dBFS (−60…0)."""
    taxa = 4000
    margem, topo = 70, 40
    img = Image.new("RGB", (largura + margem + 20, topo + alt_faixa * len(faixas) + 40), (12, 12, 16))
    d = ImageDraw.Draw(img)
    f, fp = _fonte(16), _fonte(12)
    for k, (nome, cam) in enumerate(faixas):
        x = _mono(cam, taxa, 0, duracao)
        y0 = topo + k * alt_faixa
        meio = y0 + alt_faixa // 2
        d.rectangle([margem, y0 + 4, margem + largura, y0 + alt_faixa - 4], outline=(40, 40, 48))
        d.text((6, y0 + 8), nome, fill=CORES.get(nome.split(" ")[0], (220, 220, 220)), font=f)
        if len(x) < 2:
            continue
        n = len(x)
        por = max(1, n // largura)
        cor = CORES.get(nome.split(" ")[0], (220, 220, 220))
        for i in range(largura):
            seg = x[i * por:(i + 1) * por]
            if not len(seg):
                break
            a, b = float(seg.min()), float(seg.max())
            d.line([(margem + i, meio - b * (alt_faixa / 2 - 10)), (margem + i, meio - a * (alt_faixa / 2 - 10))], fill=tuple(int(c * 0.55) for c in cor))
        pts = []
        for i in range(largura):
            seg = x[i * por:(i + 1) * por]
            if not len(seg):
                break
            db = 20 * math.log10(max(float(np.sqrt(np.mean(seg.astype(np.float64) ** 2))), 1e-6))
            pts.append((margem + i, y0 + 6 + (min(0, max(-60, db)) / -60) * (alt_faixa - 12)))
        if len(pts) > 1:
            d.line(pts, fill=cor, width=2)
        for v in (-20, -40):
            yy = y0 + 6 + (v / -60) * (alt_faixa - 12)
            d.text((margem - 34, yy - 7), f"{v}", fill=(110, 110, 120), font=fp)
    base = topo + alt_faixa * len(faixas)
    for s in range(0, int(duracao) + 1, max(5, int(duracao // 20))):
        xx = margem + s / duracao * largura
        d.line([(xx, base), (xx, base + 6)], fill=(150, 150, 160))
        d.text((xx - 10, base + 8), f"{s}s", fill=(150, 150, 160), font=fp)
    for t, rot in (secoes or []):
        xx = margem + t / duracao * largura
        d.line([(xx, topo), (xx, base)], fill=(90, 90, 150), width=1)
        d.text((xx + 3, topo - 18), rot[:22], fill=(150, 150, 210), font=fp)
    for t, rot in (marcos or []):
        xx = margem + t / duracao * largura
        d.line([(xx, base - 8), (xx, base)], fill=(230, 120, 90), width=2)
    img.save(destino)
    return destino


def espectrograma(destino: Path, caminho: Path, duracao: float, largura: int = 1800, altura: int = 420) -> Path:
    """Espectrograma em escala log de frequência (40 Hz – 8 kHz), magnitude em dB (cores: escuro → âmbar)."""
    taxa = 16000
    x = _mono(caminho, taxa, 0, duracao).astype(np.float64)
    nfft, passo = 2048, max(1, len(x) // largura)
    jan = np.hanning(nfft)
    freq = np.fft.rfftfreq(nfft, 1 / taxa)
    bordas = np.geomspace(40, 8000, altura + 1)
    idx = [np.nonzero((freq >= bordas[i]) & (freq < bordas[i + 1]))[0] for i in range(altura)]
    M = np.full((altura, largura), -120.0)
    for c in range(largura):
        i = c * passo
        seg = x[i:i + nfft]
        if len(seg) < nfft:
            break
        P = 20 * np.log10(np.abs(np.fft.rfft(seg * jan)) + 1e-9)
        for r, ii in enumerate(idx):
            if len(ii):
                M[altura - 1 - r, c] = P[ii].max()
    v = np.clip((M - (M.max() - 80)) / 80, 0, 1)
    rgb = np.stack([v ** 0.8 * 245, v ** 1.4 * 190, v ** 3 * 110], axis=-1).astype(np.uint8)
    img = Image.fromarray(rgb, "RGB")
    d = ImageDraw.Draw(img)
    for fz in (100, 300, 1000, 3400, 8000):
        r = altura - 1 - int(np.searchsorted(bordas, fz))
        d.line([(0, r), (12, r)], fill=(200, 200, 200))
        d.text((16, r - 7), f"{fz} Hz", fill=(200, 200, 200), font=_fonte(12))
    img.save(destino)
    return destino
