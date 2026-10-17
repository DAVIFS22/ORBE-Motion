"""Cenários gerados por código (Pillow + NumPy).

São a alternativa visual quando a pesquisa não encontra imagem licenciada
adequada. São ilustrações abstratas/estilizadas feitas por este programa:
nunca são apresentadas como fotografias nem como registros históricos, e o
relatório as identifica como "gerada por código".
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

LARGURA_BASE, ALTURA_BASE = 2400, 1350

MOTIVOS = [
    "ceu_estrelado", "cosmos", "deserto_egito", "templo_grego", "nordico", "tempestade", "roma_judeia",
    "aldeia", "luz_dourada", "cruz_colina", "tumulo", "amanhecer", "mar_galileia", "ruinas", "pergaminho",
]


# ------------------------------------------------------------ primitivas ---

def _rng(semente: int) -> np.random.Generator:
    return np.random.default_rng(semente)


def _gradiente(w, h, paradas):
    """Gradiente vertical; paradas = [(posição 0..1, (r,g,b)), ...]."""
    ys = np.linspace(0, 1, h)[:, None]
    pos = [p for p, _ in paradas]
    canais = []
    for c in range(3):
        vals = [cor[c] for _, cor in paradas]
        canais.append(np.interp(ys, pos, vals).repeat(w, axis=1))
    return np.stack(canais, axis=2).astype(np.float32)


def _ruido(w, h, escala, oitavas, semente, persistencia=0.5):
    """Ruído fractal normalizado em [0,1]."""
    rng = _rng(semente)
    total = np.zeros((h, w), np.float32)
    amp, soma = 1.0, 0.0
    for o in range(oitavas):
        gw, gh = max(2, int(w / escala * 2 ** o) + 2), max(2, int(h / escala * 2 ** o) + 2)
        grade = rng.random((gh, gw), dtype=np.float32)
        img = Image.fromarray((grade * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        total += amp * np.asarray(img, np.float32) / 255
        soma += amp
        amp *= persistencia
    total /= soma
    lo, hi = np.percentile(total, 1), np.percentile(total, 99)
    return np.clip((total - lo) / max(hi - lo, 1e-6), 0, 1)


def _brilho(canvas, x, y, raio, cor, forca=1.0):
    """Soma um brilho radial gaussiano ao canvas (float32 HxWx3, 0..255)."""
    h, w = canvas.shape[:2]
    x0, x1 = int(max(0, x - raio * 3)), int(min(w, x + raio * 3))
    y0, y1 = int(max(0, y - raio * 3)), int(min(h, y + raio * 3))
    if x1 <= x0 or y1 <= y0:
        return
    xs = np.arange(x0, x1)[None, :]
    ys = np.arange(y0, y1)[:, None]
    g = np.exp(-(((xs - x) ** 2 + (ys - y) ** 2) / (2 * raio ** 2))).astype(np.float32) * forca
    for c in range(3):
        canvas[y0:y1, x0:x1, c] += g * cor[c]


def _estrelas(canvas, n, semente, altura_max=1.0, brilho=1.0):
    h, w = canvas.shape[:2]
    rng = _rng(semente)
    xs = rng.integers(0, w, n)
    ys = (rng.random(n) ** 1.4 * h * altura_max).astype(int)
    mag = rng.random(n) ** 3
    for x, y, m in zip(xs, ys, mag):
        v = (0.35 + 0.65 * m) * brilho
        canvas[y, x] += 255 * v
        if m > 0.8:
            _brilho(canvas, x, y, 2.2 + 3 * m, (255, 245, 230), 0.55 * v)


def _silhueta(w, h, y_base, amplitude, escala, semente, rugosidade=0.35):
    """Máscara (h,w) float 0/1 do relevo abaixo de uma linha de horizonte irregular."""
    rng = _rng(semente)
    xs = np.linspace(0, 1, w)
    perfil = np.zeros(w)
    for k in range(1, 7):
        fase = rng.random() * 2 * math.pi
        perfil += np.sin(xs * math.pi * 2 * k * escala + fase) / (k ** (1 + rugosidade))
    perfil = perfil / max(np.abs(perfil).max(), 1e-6)
    topo = (y_base + perfil * amplitude).astype(int)
    ys = np.arange(h)[:, None]
    return (ys >= topo[None, :]).astype(np.float32)


def _misturar(canvas, mascara, cor, opacidade=1.0):
    m = mascara[..., None] * opacidade
    canvas[:] = canvas * (1 - m) + np.array(cor, np.float32)[None, None, :] * m


def _desenho(w, h):
    img = Image.new("L", (w, h), 0)
    return img, ImageDraw.Draw(img)


def _final(canvas) -> Image.Image:
    return Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8), "RGB")


def _nevoa(canvas, y, espessura, cor, forca, semente):
    h, w = canvas.shape[:2]
    ruido = _ruido(w, h, 260, 3, semente)
    ys = np.arange(h)[:, None]
    banda = np.exp(-((ys - y) ** 2) / (2 * espessura ** 2)).astype(np.float32)
    m = (banda * ruido * forca)[..., None]
    canvas[:] = canvas * (1 - m) + np.array(cor, np.float32) * m


# --------------------------------------------------------------- motivos ---

def ceu_estrelado(w, h, s):
    c = _gradiente(w, h, [(0, (2, 4, 12)), (0.6, (10, 22, 48)), (1, (28, 44, 74))])
    banda = _ruido(w, h, 420, 4, s + 1)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    dist = np.abs((xs / w - 0.15) * 0.9 + (ys / h - 0.1) * -1.1 + 0.25) / 0.45
    leite = np.clip(1 - dist, 0, 1) ** 2 * banda
    c += leite[..., None] * np.array([70, 80, 110], np.float32)
    _estrelas(c, 2600, s)
    _misturar(c, _silhueta(w, h, h * 0.86, h * 0.05, 1.4, s + 4), (3, 4, 8))
    return _final(c)


def cosmos(w, h, s):
    c = np.zeros((h, w, 3), np.float32) + np.array([4, 5, 14], np.float32)
    for k, cor in enumerate([(90, 40, 120), (30, 70, 150), (160, 70, 60)]):
        n = _ruido(w, h, 380 - 60 * k, 5, s + k) ** 2.2
        c += n[..., None] * np.array(cor, np.float32) * 0.9
    _estrelas(c, 3200, s + 9, brilho=1.1)
    _brilho(c, w * 0.62, h * 0.4, 120, (255, 230, 190), 0.5)
    return _final(c)


def deserto_egito(w, h, s):
    c = _gradiente(w, h, [(0, (22, 18, 54)), (0.45, (150, 70, 62)), (0.68, (240, 160, 80)), (1, (252, 214, 140))])
    _brilho(c, w * 0.7, h * 0.64, 70, (255, 235, 190), 1.0)
    _brilho(c, w * 0.7, h * 0.64, 380, (255, 170, 90), 0.55)
    _estrelas(c, 500, s, altura_max=0.35, brilho=0.8)
    # pirâmides (triângulos) sobre o horizonte
    img, d = _desenho(w, h)
    base = int(h * 0.74)
    for cx, largura, alt in [(0.30, 0.20, 0.17), (0.43, 0.13, 0.11), (0.18, 0.10, 0.07)]:
        d.polygon([(w * (cx - largura / 2), base), (w * cx, base - h * alt), (w * (cx + largura / 2), base)], fill=255)
    _misturar(c, np.asarray(img, np.float32) / 255, (70, 36, 40), 0.92)
    for i, (y, amp, cor) in enumerate([(0.74, 0.015, (92, 48, 42)), (0.82, 0.03, (60, 30, 30)), (0.92, 0.04, (30, 16, 20))]):
        _misturar(c, _silhueta(w, h, h * y, h * amp, 0.9 + i * 0.4, s + i, 0.9), cor)
    _nevoa(c, h * 0.74, 60, (250, 190, 120), 0.35, s + 7)
    return _final(c)


def templo_grego(w, h, s):
    c = _gradiente(w, h, [(0, (36, 52, 96)), (0.5, (170, 130, 150)), (0.78, (240, 190, 130)), (1, (250, 220, 170))])
    _brilho(c, w * 0.5, h * 0.6, 260, (255, 215, 160), 0.65)
    _misturar(c, _silhueta(w, h, h * 0.66, h * 0.07, 1.1, s + 1, 0.8), (88, 84, 112), 0.85)
    img, d = _desenho(w, h)
    esq, dire, topo_col, base = w * 0.2, w * 0.8, h * 0.40, h * 0.80
    d.rectangle([esq - 40, base, dire + 40, base + 26], fill=255)  # degraus
    d.rectangle([esq - 20, base + 26, dire + 20, base + 48], fill=255)
    n = 9
    for i in range(n):
        x = esq + (dire - esq) * i / (n - 1)
        d.polygon([(x - 17, topo_col), (x + 17, topo_col), (x + 12, base), (x - 12, base)], fill=255)
    d.rectangle([esq - 30, topo_col - 52, dire + 30, topo_col], fill=255)  # arquitrave
    d.polygon([(esq - 40, topo_col - 52), (w / 2, topo_col - 190), (dire + 40, topo_col - 52)], fill=255)  # frontão
    m = np.asarray(img, np.float32) / 255
    _misturar(c, m, (24, 22, 36))
    _misturar(c, _silhueta(w, h, h * 0.94, h * 0.02, 1.6, s + 3), (12, 10, 18))
    return _final(c)


def nordico(w, h, s):
    c = _gradiente(w, h, [(0, (3, 8, 20)), (0.55, (8, 30, 48)), (1, (22, 56, 70))])
    _estrelas(c, 1500, s, altura_max=0.6)
    xs = np.linspace(0, 1, w)[None, :]
    ys = np.arange(h)[:, None].astype(np.float32)
    for k, (cor, fase) in enumerate([((40, 255, 150), 0.0), ((90, 200, 255), 1.3), ((180, 90, 255), 2.4)]):
        centro = h * (0.28 + 0.06 * k) + np.sin(xs * 7 + fase + s) * h * 0.06 + np.sin(xs * 17 + fase) * h * 0.015
        faixa = np.exp(-((ys - centro) ** 2) / (2 * (h * 0.045) ** 2))
        cortina = (0.55 + 0.45 * np.sin(xs * 90 + fase * 3)) * _ruido(w, h, 600, 3, s + k)
        c += (faixa * cortina)[..., None] * np.array(cor, np.float32) * 0.55
    _misturar(c, _silhueta(w, h, h * 0.62, h * 0.12, 1.9, s + 5, 0.7), (6, 12, 20))
    agua = np.zeros((h, w), np.float32)
    agua[int(h * 0.78):, :] = 1
    _misturar(c, agua, (10, 24, 34), 0.9)
    _nevoa(c, h * 0.78, 45, (120, 170, 190), 0.4, s + 8)
    return _final(c)


def tempestade(w, h, s):
    nuvens = _ruido(w, h, 320, 6, s) ** 1.4
    c = _gradiente(w, h, [(0, (10, 14, 24)), (1, (44, 54, 70))]) * (0.35 + 0.9 * nuvens[..., None])
    rng = _rng(s)
    img = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)

    def raio(x, y, passos, largura):
        for _ in range(passos):
            nx = x + rng.normal(0, 38) + (w * 0.0)
            ny = y + rng.uniform(26, 62)
            d.line([(x, y), (nx, ny)], fill=255, width=largura)
            if rng.random() < 0.16 and largura > 2:
                raio(nx, ny, int(passos * 0.35), max(1, largura - 2))
            x, y = nx, ny
    raio(w * rng.uniform(0.35, 0.65), 0, 24, 7)
    nucleo = np.asarray(img, np.float32) / 255
    halo = np.asarray(img.filter(ImageFilter.GaussianBlur(28)), np.float32) / 255
    c += halo[..., None] * np.array([120, 150, 255], np.float32) * 2.2
    c += nucleo[..., None] * 255
    _misturar(c, _silhueta(w, h, h * 0.9, h * 0.04, 1.2, s + 2), (4, 6, 10))
    return _final(c)


def roma_judeia(w, h, s):
    c = _gradiente(w, h, [(0, (50, 56, 100)), (0.5, (196, 126, 100)), (0.78, (244, 190, 120)), (1, (250, 220, 160))])
    _brilho(c, w * 0.25, h * 0.66, 90, (255, 235, 190), 0.9)
    _misturar(c, _silhueta(w, h, h * 0.70, h * 0.04, 1.0, s + 1, 0.9), (118, 76, 70), 0.9)
    img, d = _desenho(w, h)
    base, topo = int(h * 0.78), int(h * 0.50)
    for i in range(6):
        x0 = w * (0.30 + i * 0.1)
        d.rectangle([x0, topo, x0 + w * 0.1, base], fill=255)
        d.pieslice([x0 + 14, base - w * 0.1 + 14, x0 + w * 0.1 - 14, base + w * 0.1 - 14 - 20], 180, 360, fill=0)
        d.rectangle([x0 + 14, base - w * 0.05 + 6, x0 + w * 0.1 - 14, base + 4], fill=0)
    d.rectangle([w * 0.3, topo - 24, w * 0.9, topo], fill=255)
    _misturar(c, np.asarray(img, np.float32) / 255, (46, 30, 40), 0.95)
    _misturar(c, _silhueta(w, h, h * 0.9, h * 0.035, 1.5, s + 4, 0.8), (24, 16, 20))
    return _final(c)


def aldeia(w, h, s):
    c = _gradiente(w, h, [(0, (40, 50, 96)), (0.5, (214, 130, 96)), (0.8, (250, 200, 130)), (1, (250, 224, 170))])
    _brilho(c, w * 0.8, h * 0.62, 80, (255, 238, 200), 0.9)
    _misturar(c, _silhueta(w, h, h * 0.66, h * 0.08, 1.2, s + 1, 0.8), (110, 84, 92), 0.9)
    _misturar(c, _silhueta(w, h, h * 0.76, h * 0.06, 1.7, s + 2, 0.8), (72, 52, 58))
    img, d = _desenho(w, h)
    rng = _rng(s)
    janelas = []
    for i in range(14):
        x = w * (0.08 + 0.065 * i) + rng.integers(-18, 18)
        larg, alt = rng.integers(70, 120), rng.integers(60, 110)
        y = h * 0.80 - alt + rng.integers(-18, 18)
        d.rectangle([x, y, x + larg, y + alt], fill=255)
        janelas.append((x + larg * 0.3, y + alt * 0.35))
    _misturar(c, np.asarray(img, np.float32) / 255, (36, 26, 30))
    for x, y in janelas:
        if rng.random() < 0.7:
            _brilho(c, x, y, 7, (255, 200, 110), 1.2)
    _misturar(c, _silhueta(w, h, h * 0.93, h * 0.03, 1.5, s + 6), (16, 12, 14))
    return _final(c)


def luz_dourada(w, h, s):
    c = _gradiente(w, h, [(0, (12, 10, 18)), (0.6, (60, 38, 28)), (1, (28, 18, 16))])
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    ang = np.arctan2(xs - w * 0.5, ys + h * 0.25)
    raios = (0.5 + 0.5 * np.sin(ang * 26 + s) * np.sin(ang * 9 + 1.1)) ** 3
    dist = np.sqrt((xs - w * 0.5) ** 2 + (ys + h * 0.25) ** 2) / h
    c += (raios * np.exp(-dist * 1.1))[..., None] * np.array([255, 205, 120], np.float32) * 0.9
    _brilho(c, w * 0.5, h * 0.1, 220, (255, 225, 160), 0.8)
    n = _ruido(w, h, 300, 5, s)
    c *= (0.65 + 0.5 * n)[..., None]
    return _final(c)


def cruz_colina(w, h, s):
    c = _gradiente(w, h, [(0, (20, 12, 28)), (0.5, (120, 36, 40)), (0.78, (236, 120, 60)), (1, (250, 180, 90))])
    nuvens = _ruido(w, h, 300, 5, s) ** 1.6
    c *= (0.55 + 0.7 * nuvens[..., None])
    _brilho(c, w * 0.5, h * 0.7, 120, (255, 200, 120), 0.8)
    _misturar(c, _silhueta(w, h, h * 0.78, h * 0.05, 0.8, s + 1, 1.0), (14, 8, 12))
    img, d = _desenho(w, h)
    base = int(h * 0.80)
    for cx, alt, largura in [(0.5, 0.36, 0.11), (0.41, 0.27, 0.085), (0.59, 0.27, 0.085)]:
        x = w * cx
        topo = base - h * alt
        d.rectangle([x - 7, topo, x + 7, base], fill=255)
        d.rectangle([x - w * largura / 2, topo + h * alt * 0.2, x + w * largura / 2, topo + h * alt * 0.2 + 13], fill=255)
    _misturar(c, np.asarray(img, np.float32) / 255, (6, 4, 8))
    return _final(c)


def tumulo(w, h, s):
    pedra = _ruido(w, h, 90, 6, s)
    c = np.stack([pedra * 70 + 25, pedra * 66 + 26, pedra * 62 + 30], axis=2).astype(np.float32)
    c *= _gradiente(w, h, [(0, (0.5, 0.5, 0.6)), (1, (0.9, 0.85, 0.8))]) / 1.0
    img, d = _desenho(w, h)
    cx, base = w * 0.5, h * 0.88
    d.rectangle([cx - 190, h * 0.42, cx + 190, base], fill=255)
    d.pieslice([cx - 190, h * 0.42 - 190, cx + 190, h * 0.42 + 190], 180, 360, fill=255)
    abertura = np.asarray(img, np.float32) / 255
    interior = np.asarray(img.filter(ImageFilter.GaussianBlur(14)), np.float32) / 255
    c = c * (1 - abertura[..., None]) + abertura[..., None] * np.array([255, 232, 190], np.float32) * (0.5 + 0.5 * interior[..., None])
    _brilho(c, cx, h * 0.55, 380, (255, 220, 150), 0.7)
    disco = Image.new("L", (w, h), 0)
    dd = ImageDraw.Draw(disco)
    dd.ellipse([w * 0.14, h * 0.52, w * 0.14 + 330, h * 0.52 + 330], fill=255)
    m = np.asarray(disco.filter(ImageFilter.GaussianBlur(2)), np.float32) / 255
    _misturar(c, m, (74, 70, 72), 0.95)
    c *= 0.85
    return _final(c)


def amanhecer(w, h, s):
    c = _gradiente(w, h, [(0, (36, 56, 110)), (0.45, (176, 130, 160)), (0.7, (250, 190, 130)), (1, (255, 226, 170))])
    _brilho(c, w * 0.5, h * 0.66, 90, (255, 250, 225), 1.2)
    _brilho(c, w * 0.5, h * 0.66, 420, (255, 200, 130), 0.7)
    for i, (y, cor) in enumerate([(0.68, (150, 118, 140)), (0.76, (110, 90, 112)), (0.86, (64, 54, 78))]):
        _misturar(c, _silhueta(w, h, h * y, h * 0.04, 1.0 + 0.4 * i, s + i, 0.9), cor, 0.95)
        _nevoa(c, h * (y + 0.01), 40, (255, 220, 180), 0.35, s + 10 + i)
    return _final(c)


def mar_galileia(w, h, s):
    c = _gradiente(w, h, [(0, (46, 66, 112)), (0.4, (190, 150, 160)), (0.52, (246, 200, 150)), (0.5, (246, 200, 150)), (1, (50, 70, 100))])
    ys = np.arange(h)[:, None]
    agua = (ys > h * 0.52).astype(np.float32)
    ondas = _ruido(w, h, 120, 4, s)
    espelho = _gradiente(w, h, [(0.52, (250, 200, 150)), (0.7, (110, 100, 130)), (1, (30, 46, 74))])
    c = c * (1 - agua[..., None]) + espelho * agua[..., None] * (0.8 + 0.4 * ondas[..., None])
    _brilho(c, w * 0.62, h * 0.5, 80, (255, 238, 205), 0.9)
    _brilho(c, w * 0.62, h * 0.66, 160, (255, 210, 150), 0.35)
    _misturar(c, _silhueta(w, h, h * 0.5, h * 0.04, 1.3, s + 1, 0.9) * (ys < h * 0.56), (84, 68, 94))
    return _final(c)


def ruinas(w, h, s):
    c = _gradiente(w, h, [(0, (30, 36, 70)), (0.55, (146, 110, 110)), (0.8, (226, 170, 120)), (1, (240, 200, 150))])
    _brilho(c, w * 0.78, h * 0.62, 100, (255, 232, 190), 0.9)
    _misturar(c, _silhueta(w, h, h * 0.70, h * 0.05, 1.0, s + 1, 0.9), (100, 78, 90), 0.9)
    img, d = _desenho(w, h)
    rng = _rng(s)
    base = int(h * 0.84)
    for i in range(7):
        x = w * (0.1 + 0.12 * i) + rng.integers(-20, 20)
        alt = h * rng.uniform(0.12, 0.34)
        larg = rng.integers(26, 40)
        topo = base - alt
        d.polygon([(x - larg, base), (x - larg * 0.8, topo), (x + larg * 0.8, topo + rng.integers(0, 30)), (x + larg, base)], fill=255)
        if rng.random() < 0.5:
            d.rectangle([x - larg * 1.3, topo - 20, x + larg * 1.3, topo], fill=255)
    _misturar(c, np.asarray(img, np.float32) / 255, (28, 20, 28), 0.96)
    _misturar(c, _silhueta(w, h, h * 0.9, h * 0.03, 1.7, s + 4, 0.8), (16, 12, 16))
    _nevoa(c, h * 0.84, 50, (230, 180, 140), 0.3, s + 9)
    return _final(c)


def pergaminho(w, h, s):
    base = _ruido(w, h, 180, 6, s)
    manchas = _ruido(w, h, 700, 3, s + 3)
    c = np.stack([205 + 40 * base - 30 * manchas, 178 + 38 * base - 40 * manchas, 130 + 34 * base - 50 * manchas], axis=2)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    borda = np.sqrt(((xs / w - 0.5) / 0.5) ** 2 + ((ys / h - 0.5) / 0.5) ** 2)
    c *= (1.0 - np.clip(borda - 0.55, 0, 1) ** 1.6 * 0.9)[..., None]
    return _final(c.astype(np.float32))


_FUNCOES = {
    "ceu_estrelado": ceu_estrelado, "cosmos": cosmos, "deserto_egito": deserto_egito, "templo_grego": templo_grego,
    "nordico": nordico, "tempestade": tempestade, "roma_judeia": roma_judeia, "aldeia": aldeia,
    "luz_dourada": luz_dourada, "cruz_colina": cruz_colina, "tumulo": tumulo, "amanhecer": amanhecer,
    "mar_galileia": mar_galileia, "ruinas": ruinas, "pergaminho": pergaminho,
}


def gerar(motivo: str, semente: int = 7, largura: int = LARGURA_BASE, altura: int = ALTURA_BASE) -> Image.Image:
    if motivo not in _FUNCOES:
        raise KeyError(f"Motivo desconhecido: {motivo!r}. Disponíveis: {', '.join(MOTIVOS)}")
    return _FUNCOES[motivo](largura, altura, semente)


# ------------------------------------------------------------ mapa esquemático ---

LUGARES = {  # (rótulo, longitude, latitude, deslocamento do rótulo) — coordenadas reais aproximadas
    "Egito": ("Egito", 31.2, 30.0, (-250, 18)), "Atenas": ("Grécia", 23.7, 37.98, (-200, -70)),
    "Roma": ("Roma", 12.5, 41.9, (-170, -64)), "Jerusalém": ("Judeia", 35.2, 31.8, (30, -62)),
    "Oslo": ("Escandinávia", 10.7, 59.9, (34, -30)),
}


def mapa_esquematico(semente: int = 7, largura: int = LARGURA_BASE, altura: int = ALTURA_BASE,
                     destaques: list[str] | None = None) -> tuple[Image.Image, dict[str, tuple[float, float]]]:
    """Mapa esquemático (sem contornos de costa): grade geográfica real + pontos.

    Não pretende mostrar fronteiras ou costas. Serve de base para movimentos de
    câmera quando não há um mapa licenciado. Devolve (imagem, {lugar: (x, y)}).
    """
    from .text_graphics import carregar_fonte
    fundo = pergaminho(largura, altura, semente)
    d = ImageDraw.Draw(fundo, "RGBA")
    lat0, lat1 = 26.0, 64.0
    escala = altura * 0.84 / (lat1 - lat0)
    lon_c = 24.0
    lon0, lon1 = lon_c - largura * 0.5 / escala, lon_c + largura * 0.5 / escala
    oy = altura * 0.08

    def proj(lon, lat):
        return (lon - lon0) * escala, altura - (oy + (lat - lat0) * escala)

    for lon in range(int(lon0 // 5) * 5, int(lon1) + 1, 5):
        d.line([proj(lon, lat0 - 2), proj(lon, lat1 + 2)], fill=(90, 62, 36, 70), width=2)
    for lat in range(int(lat0), int(lat1) + 1, 5):
        d.line([proj(lon0, lat), proj(lon1, lat)], fill=(90, 62, 36, 70), width=2)
    fonte = carregar_fonte("serif", True, 54)
    pequena = carregar_fonte("serif", False, 30)
    pontos = {}
    for chave, (rotulo, lon, lat, (dx, dy)) in LUGARES.items():
        x, y = proj(lon, lat)
        pontos[chave] = (x, y)
        destaque = destaques is None or chave in destaques
        cor = (120, 28, 24, 255) if destaque else (110, 80, 50, 200)
        d.ellipse([x - 16, y - 16, x + 16, y + 16], fill=cor, outline=(40, 20, 12, 255), width=3)
        d.ellipse([x - 40, y - 40, x + 40, y + 40], outline=(120, 28, 24, 120 if destaque else 40), width=3)
        d.text((x + dx, y + dy), rotulo, font=fonte, fill=(52, 30, 18, 255))
    d.text((60, altura - 56), "Mapa esquemático: grade de longitude/latitude real; sem contornos de costa.",
           font=pequena, fill=(90, 62, 36, 220))
    return fundo, pontos
