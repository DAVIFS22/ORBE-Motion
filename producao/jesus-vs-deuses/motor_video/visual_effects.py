"""Movimentos de câmera, correção de cor, sobreposições e transições.

Cada quadro é calculado por código: o recorte da imagem (zoom/panorâmica) é
amostrado com `Image.transform` (bicúbico, subpixel) a partir de uma cópia
pré-reduzida da fonte, o que evita o tremor típico de zooms por pixel inteiro.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageEnhance, ImageFilter

from . import procedural_art, text_graphics as tg

ASPECTO = 16 / 9
LARGURA_RECORTE_REF = 2112  # largura do recorte "cover" após o pré-redimensionamento

PRESETS = ["zoom_in", "zoom_out", "pan_esq", "pan_dir", "tilt_cima", "tilt_baixo", "deriva", "respiro", "foco"]

GRADES = {  # multiplicadores RGB, saturação, contraste, brilho
    "neutro": dict(tint=(1.0, 1.0, 1.0), sat=0.96, con=1.05, bri=1.0),
    "frio": dict(tint=(0.95, 0.99, 1.06), sat=0.86, con=1.06, bri=0.98),
    "quente": dict(tint=(1.06, 1.0, 0.92), sat=1.0, con=1.05, bri=1.0),
    "dourado": dict(tint=(1.10, 1.02, 0.86), sat=1.02, con=1.08, bri=1.03),
    "escuro": dict(tint=(0.97, 0.98, 1.02), sat=0.82, con=1.14, bri=0.80),
    "tempestade": dict(tint=(0.90, 0.97, 1.08), sat=0.72, con=1.20, bri=0.86),
}


# ------------------------------------------------------------------ foco ---

def detectar_foco(img: Image.Image) -> tuple[float, float, float, float]:
    """Região de interesse (x0,y0,x1,y1 normalizados).

    Usa detecção de rostos (OpenCV) quando disponível; senão, um mapa de
    saliência por gradiente com preferência pelo centro. É uma estimativa:
    o storyboard pode fixar o foco manualmente (`foco`).
    """
    try:  # pragma: no cover - depende de OpenCV opcional
        import cv2  # type: ignore
        cascata = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        cinza = np.asarray(img.convert("L").resize((640, max(1, int(640 * img.height / img.width)))))
        rostos = cascata.detectMultiScale(cinza, 1.1, 5, minSize=(40, 40))
        if len(rostos):
            h_, w_ = cinza.shape
            x0 = min(r[0] for r in rostos) / w_
            y0 = min(r[1] for r in rostos) / h_
            x1 = max(r[0] + r[2] for r in rostos) / w_
            y1 = max(r[1] + r[3] for r in rostos) / h_
            mx, my = (x1 - x0) * 0.35, (y1 - y0) * 0.5
            return (max(0, x0 - mx), max(0, y0 - my), min(1, x1 + mx), min(1, y1 + my))
    except Exception:
        pass
    w = 160
    h = max(8, int(w * img.height / img.width))
    g = np.asarray(img.convert("L").resize((w, h), Image.BILINEAR), np.float32)
    gy, gx = np.gradient(g)
    mag = Image.fromarray(np.clip(np.hypot(gx, gy) * 4, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))
    sal = np.asarray(mag, np.float32) ** 1.5
    ys, xs = np.mgrid[0:h, 0:w]
    prior = np.exp(-(((xs / w - 0.5) / 0.38) ** 2 + ((ys / h - 0.5) / 0.38) ** 2))
    sal = sal * prior
    if sal.sum() <= 0:
        return (0.3, 0.25, 0.7, 0.75)
    limiar = np.percentile(sal, 85)
    m = sal >= limiar
    px, py = xs[m] / w, ys[m] / h
    peso = sal[m]

    def quantil(v, q):
        ordem = np.argsort(v)
        acum = np.cumsum(peso[ordem]) / peso.sum()
        return float(v[ordem][np.searchsorted(acum, q)])
    x0, x1 = quantil(px, 0.06), quantil(px, 0.94)
    y0, y1 = quantil(py, 0.06), quantil(py, 0.94)
    mx, my = (x1 - x0) * 0.12 + 0.02, (y1 - y0) * 0.12 + 0.02
    return (max(0.0, x0 - mx), max(0.0, y0 - my), min(1.0, x1 + mx), min(1.0, y1 + my))


# ---------------------------------------------------------------- câmera ---

@dataclass
class Camera:
    """Retângulos de recorte inicial e final (centro e largura, em pixels da fonte)."""
    cx0: float
    cy0: float
    cw0: float
    cx1: float
    cy1: float
    cw1: float
    layout: str = "cover"  # cover | contain
    z0: float = 1.0  # só em "contain": escala inicial/final da imagem inteira
    z1: float = 1.0

    def retangulo(self, p: float) -> tuple[float, float, float, float]:
        e = facilitar(p)
        cx = self.cx0 + (self.cx1 - self.cx0) * e
        cy = self.cy0 + (self.cy1 - self.cy0) * e
        cw = self.cw0 + (self.cw1 - self.cw0) * e
        ch = cw / ASPECTO
        return cx - cw / 2, cy - ch / 2, cw, ch


def facilitar(p: float) -> float:
    """Mistura de linear com suavização nas pontas: sem arranque nem parada bruscos."""
    p = max(0.0, min(1.0, p))
    suave = p * p * (3 - 2 * p)
    return 0.4 * suave + 0.6 * p


def escolher_layout(src_w: int, src_h: int, foco) -> str:
    proporcao = src_w / src_h
    if proporcao < 1.22:
        return "contain"
    if foco is not None and proporcao < ASPECTO:
        # em cover só vemos src_w/ASPECTO de altura; o foco precisa caber nisso
        visivel = (src_w / ASPECTO) / src_h
        if (foco[3] - foco[1]) > visivel * 0.92:
            return "contain"
    return "cover"


def calcular_camera(src_w: int, src_h: int, preset: str, intensidade: float = 1.0,
                    foco: tuple[float, float, float, float] | None = None, duracao: float = 10.0,
                    layout: str | None = None) -> Camera:
    """Calcula o movimento sem cortar o foco e sem sair da imagem.

    O recorte interpola linearmente centro e largura; se o retângulo contém o
    foco nas duas pontas, contém em todos os instantes intermediários.
    """
    layout = layout or escolher_layout(src_w, src_h, foco)
    if layout == "contain":
        # em "contain" a imagem inteira aparece; o movimento é uma escala suave
        z0, z1 = {"zoom_out": (1.07, 1.0), "respiro": (1.0, 1.03)}.get(preset, (1.0, 1.0 + 0.06 * intensidade))
        return Camera(src_w / 2, src_h / 2, src_w, src_w / 2, src_h / 2, src_w, "contain", z0, z1)

    cw_max = min(src_w, src_h * ASPECTO)
    ch_max = cw_max / ASPECTO
    if foco is not None:
        fx0, fy0, fx1, fy1 = foco[0] * src_w, foco[1] * src_h, foco[2] * src_w, foco[3] * src_h
        z_seguro = max(1.0, min(cw_max / max((fx1 - fx0) * 1.08, 1), ch_max / max((fy1 - fy0) * 1.08, 1)))
        fcx, fcy = (fx0 + fx1) / 2, (fy0 + fy1) / 2
    else:
        fx0 = fy0 = fx1 = fy1 = None
        z_seguro = 1.25
        fcx, fcy = src_w / 2, src_h / 2

    def ajustar(cx, cy, cw):
        ch = cw / ASPECTO
        cx = min(max(cx, cw / 2), src_w - cw / 2)
        cy = min(max(cy, ch / 2), src_h - ch / 2)
        if fx0 is not None:  # desloca o recorte para conter o foco, se couber
            if fx1 - fx0 <= cw:
                cx = min(max(cx, fx1 - cw / 2), fx0 + cw / 2)
            if fy1 - fy0 <= ch:
                cy = min(max(cy, fy1 - ch / 2), fy0 + ch / 2)
            cx = min(max(cx, cw / 2), src_w - cw / 2)
            cy = min(max(cy, ch / 2), src_h - ch / 2)
        return cx, cy, cw

    centro = (src_w / 2, src_h / 2)
    zoom_alvo = min(1.0 + 0.16 * intensidade, z_seguro)
    # a panorâmica cobre no máximo ~5% da largura do quadro por segundo
    pan_max = 0.05 * duracao * cw_max

    if preset == "zoom_in" or preset == "foco":
        alvo = (fcx, fcy) if preset == "foco" else (centro[0] * 0.4 + fcx * 0.6, centro[1] * 0.4 + fcy * 0.6)
        p0 = ajustar(*centro, cw_max)
        p1 = ajustar(*alvo, cw_max / max(1.0, zoom_alvo if preset == "zoom_in" else min(1.0 + 0.22 * intensidade, z_seguro)))
    elif preset == "zoom_out":
        alvo = (centro[0] * 0.4 + fcx * 0.6, centro[1] * 0.4 + fcy * 0.6)
        p0 = ajustar(*alvo, cw_max / max(1.0, zoom_alvo))
        p1 = ajustar(*centro, cw_max)
    elif preset in ("pan_esq", "pan_dir", "tilt_cima", "tilt_baixo"):
        z = max(1.0 + 0.07 * intensidade, 1.0)
        z = min(z, max(z_seguro, 1.0))
        cw = cw_max / z
        ch = cw / ASPECTO
        folga_x, folga_y = src_w - cw, src_h - ch
        if preset in ("pan_esq", "pan_dir"):
            curso = min(folga_x * 0.9, pan_max)
            a = src_w / 2 - curso / 2
            b = src_w / 2 + curso / 2
            (xa, xb) = (b, a) if preset == "pan_esq" else (a, b)
            p0, p1 = ajustar(xa, fcy if foco else src_h / 2, cw), ajustar(xb, fcy if foco else src_h / 2, cw)
        else:
            curso = min(folga_y * 0.9, pan_max / ASPECTO * 1.0)
            a = src_h / 2 - curso / 2
            b = src_h / 2 + curso / 2
            (ya, yb) = (b, a) if preset == "tilt_cima" else (a, b)
            p0, p1 = ajustar(fcx if foco else src_w / 2, ya, cw), ajustar(fcx if foco else src_w / 2, yb, cw)
    elif preset == "deriva":
        z0, z1 = 1.03, min(1.03 + 0.05 * intensidade, max(1.03, z_seguro))
        p0 = ajustar(centro[0] - 0.01 * src_w, centro[1], cw_max / z0)
        p1 = ajustar(centro[0] + 0.01 * src_w, centro[1] - 0.008 * src_h, cw_max / z1)
    else:  # respiro (praticamente estático)
        p0 = ajustar(*centro, cw_max / 1.0)
        p1 = ajustar(*centro, cw_max / min(1.03, max(1.0, z_seguro)))
    return Camera(p0[0], p0[1], p0[2], p1[0], p1[1], p1[2], "cover")


# ------------------------------------------------------------------ cor ---

def aplicar_grade(img: Image.Image, nome: str, auto_contraste: bool = True) -> Image.Image:
    g = GRADES.get(nome, GRADES["neutro"])
    a = np.asarray(img, np.float32) / 255.0
    if auto_contraste:
        # estica só a luminância (mesmo fator nos três canais): preserva o matiz de pores do sol, céus, etc.
        lum = (a * np.array([0.299, 0.587, 0.114], np.float32)).sum(axis=2)
        lo, hi = np.percentile(lum[::4, ::4], [0.3, 99.7])
        if hi - lo > 0.08:
            fator = min(1.0 / (hi - lo), 1.5)
            a = 0.65 * np.clip((a - lo) * fator, 0, 1) + 0.35 * a
    a = a * np.array(g["tint"], np.float32)
    lum = (a * np.array([0.299, 0.587, 0.114], np.float32)).sum(axis=2, keepdims=True)
    a = lum + (a - lum) * g["sat"]
    a = (a - 0.5) * g["con"] + 0.5
    a = a * g["bri"]
    # curva em S suave (filmica) preservando pretos e brancos
    a = np.clip(a, 0, 1)
    a = a + 0.10 * np.sin((a - 0.5) * math.pi) * 0.5
    return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB")


# ----------------------------------------------------------------- fonte ---

def _vinheta(w: int, h: int, forca: float = 0.30) -> Image.Image:
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xs - w / 2) / (w / 2)) ** 2 + ((ys - h / 2) / (h / 2)) ** 2) / math.sqrt(2)
    m = 1.0 - forca * np.clip((r - 0.35) / 0.65, 0, 1) ** 1.7
    return Image.fromarray((m * 255).astype(np.uint8), "L").convert("RGB")


def _gradiente_inferior(w: int, h: int, forca: float) -> Image.Image:
    ys = np.linspace(0, 1, h)[:, None].repeat(w, axis=1)
    return Image.fromarray((np.clip((ys - 0.45) / 0.55, 0, 1) ** 1.3 * forca * 255).astype(np.uint8), "L")


AMPLITUDE_GRAO = 2  # ±2 níveis: protege gradientes de banding sem inflar o bitrate (±4 multiplicava o bitrate por ~18)


def _grao(w: int, h: int, n: int = 6, amplitude: int = AMPLITUDE_GRAO):
    """Variantes de grão: ruído em [0, 2*amplitude]; aplicado com offset -amplitude (uma só operação)."""
    rng = np.random.default_rng(1234)
    return [Image.fromarray(rng.integers(0, 2 * amplitude + 1, (h, w), dtype=np.uint8), "L").convert("RGB")
            for _ in range(n)]


class FonteVideo:
    """Quadros de um vídeo (clipe 3D renderizado ou filmagem licenciada), lidos sequencialmente pelo FFmpeg.

    Acesso aleatório (verificação de qualidade) reabre o decodificador na posição pedida.
    """

    def __init__(self, arquivo: str, inicio_clip: float, span: float, w: int, h: int, fps: int):
        self.arquivo, self.inicio, self.span = arquivo, inicio_clip, span
        self.w, self.h, self.fps = w, h, fps
        self.n = max(1, int(round(span * fps)))
        self._proc = None
        self._idx = -1
        self._ultimo: Image.Image | None = None

    def _abrir(self, k: int):
        import subprocess
        self.fechar()
        t0 = self.inicio + k / self.fps
        filtro = (f"scale={self.w}:{self.h}:force_original_aspect_ratio=increase:flags=lanczos:in_color_matrix=bt709:"
                  f"in_range=limited:out_range=full,crop={self.w}:{self.h},fps={self.fps},format=rgb24")
        self._proc = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-ss", f"{t0:.4f}", "-i", self.arquivo, "-an", "-vf", filtro, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=self.w * self.h * 3 * 2)
        self._idx = k - 1

    def _ler(self):
        n = self.w * self.h * 3
        dados = self._proc.stdout.read(n)
        if len(dados) < n:
            return None
        return Image.frombytes("RGB", (self.w, self.h), dados)

    def quadro(self, p: float) -> Image.Image:
        k = max(0, min(self.n - 1, int(round(p * self.span * self.fps))))
        if k == self._idx and self._ultimo is not None:
            return self._ultimo
        if self._proc is None or k < self._idx or k > self._idx + 900:
            self._abrir(k)
        while self._idx < k:
            img = self._ler()
            if img is None:  # fim do vídeo: mantém o último quadro
                break
            self._ultimo = img
            self._idx += 1
        if self._ultimo is None:
            self._ultimo = Image.new("RGB", (self.w, self.h), (0, 0, 0))
        return self._ultimo

    def fechar(self):
        if self._proc is not None:
            try:
                self._proc.kill()
                self._proc.stdout.close()
                self._proc.wait()
            except Exception:  # noqa: BLE001
                pass
            self._proc = None

    def __del__(self):
        self.fechar()


class FonteVisual:
    """Fonte de imagem preparada (cor, escala) + câmera, pronta para amostrar quadros."""

    def __init__(self, fundo: dict, grade: str, camera: dict, duracao: float, w: int, h: int, cache: Path | None,
                 rapido: bool = False):
        self.w, self.h = w, h
        self._rs = Image.BILINEAR if rapido else Image.BICUBIC
        self._video = None
        if fundo.get("tipo") == "video":
            self._video = FonteVideo(fundo["arquivo"], float(fundo.get("inicio_clip", 0.0)), duracao, w, h, int(fundo.get("fps", 30)))
            self.foco, self.camera = None, None
            return
        img, foco_auto = self._carregar(fundo, cache)
        self.foco = tuple(camera["foco"]) if camera.get("foco") else (foco_auto if fundo.get("tipo") == "imagem" else None)
        src_w, src_h = img.size
        self.camera = calcular_camera(src_w, src_h, camera.get("preset", "zoom_in"), camera.get("intensidade", 1.0),
                                      self.foco, duracao, camera.get("layout"))
        # pré-escala: o recorte "cover" de referência fica com ~LARGURA_RECORTE_REF pixels
        cw_ref = min(src_w, src_h * ASPECTO)
        fator = min(1.0, LARGURA_RECORTE_REF / cw_ref)
        if fator < 0.999:
            img = img.resize((max(2, round(src_w * fator)), max(2, round(src_h * fator))), Image.LANCZOS)
        else:
            fator = 1.0
        self.fator = fator
        self.img = aplicar_grade(img, grade, auto_contraste=fundo.get("tipo") == "imagem")
        c = self.camera
        self._cam_px = Camera(c.cx0 * fator, c.cy0 * fator, c.cw0 * fator, c.cx1 * fator, c.cy1 * fator, c.cw1 * fator,
                              c.layout, c.z0, c.z1)
        if self.camera.layout == "contain":
            self._preparar_contain()

    @staticmethod
    def _carregar(fundo: dict, cache: Path | None):
        tipo = fundo["tipo"]
        if tipo == "imagem":
            img = Image.open(fundo["arquivo"]).convert("RGB")
            return img, detectar_foco(img)
        if tipo == "motivo":
            motivo, semente = fundo["motivo"], int(fundo.get("semente", 7))
            arq = (cache / f"{motivo}-{semente}.png") if cache else None
            if arq and arq.is_file():
                return Image.open(arq).convert("RGB"), None
            img = procedural_art.gerar(motivo, semente)
            if arq:
                import os
                arq.parent.mkdir(parents=True, exist_ok=True)
                tmp = arq.with_name(f"{arq.stem}.{os.getpid()}.tmp.png")
                img.save(tmp, compress_level=1)
                os.replace(tmp, arq)  # atômico: outro processo nunca lê arquivo pela metade
            return img, None
        if tipo == "mapa":
            img, _ = procedural_art.mapa_esquematico(int(fundo.get("semente", 7)), destaques=fundo.get("destaques"))
            return img, None
        raise ValueError(f"Tipo de fundo desconhecido: {tipo}")

    def _preparar_contain(self):
        w, h = self.w, self.h
        src = self.img
        escala_bg = max(w / src.width, h / src.height) * 1.12
        bg = src.resize((max(w, round(src.width * escala_bg)), max(h, round(src.height * escala_bg))), Image.BILINEAR)
        self._bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(34))).enhance(0.45)
        self._fit = min(0.94 * h / src.height, 0.94 * w / src.width)
        self._fg = src

    def fechar(self):
        if self._video is not None:
            self._video.fechar()

    def quadro(self, p: float) -> Image.Image:
        w, h = self.w, self.h
        if self._video is not None:
            return self._video.quadro(p)
        if self.camera.layout == "contain":
            return self._quadro_contain(p)
        x, y, cw, ch = self._cam_px.retangulo(p)
        iw, ih = self.img.size
        x = min(max(0.0, x), iw - cw)
        y = min(max(0.0, y), ih - ch)
        # `box` fracionário: amostragem subpixel com filtro antialiasing (sem tremor)
        return self.img.resize((w, h), self._rs, box=(x, y, x + cw, y + ch))

    def _quadro_contain(self, p: float) -> Image.Image:
        """Imagem inteira (retrato/quadrada) sobre fundo desfocado da própria imagem."""
        w, h = self.w, self.h
        e = facilitar(p)
        c = self._cam_px
        bw, bh = self._bg.size
        sb = 1.0 + 0.03 * e
        vw, vh = bw / sb, bh / sb
        x0, y0 = (bw - vw) / 2, (bh - vh) / 2
        quadro = self._bg.resize((w, h), Image.BILINEAR, box=(x0, y0, x0 + vw, y0 + vh))
        s = self._fit * (c.z0 + (c.z1 - c.z0) * e)
        fw, fh = self._fg.size
        dw, dh = max(2, round(fw * s)), max(2, round(fh * s))
        fg = self._fg.resize((dw, dh), Image.BICUBIC)
        quadro.paste(fg.convert("RGB"), ((w - dw) // 2, (h - dh) // 2))
        return quadro


# ------------------------------------------------------------ overlays ---

@dataclass
class Overlay:
    camadas: list
    t0: float
    dur: float
    escurecer: float = 0.0
    gradiente: float = 0.0
    _grad_img: Image.Image | None = None

    def aplicar(self, quadro: Image.Image, t: float) -> Image.Image:
        lt = t - self.t0
        if lt < 0 or lt > self.dur:
            return quadro
        a = max(c.alpha(lt, self.dur) for c in self.camadas) if self.camadas else 0.0
        if a <= 0.003:
            return quadro
        if self.escurecer > 0:
            quadro = Image.blend(quadro, Image.new("RGB", quadro.size, (0, 0, 0)), self.escurecer * a)
        if self.gradiente > 0:
            if self._grad_img is None or self._grad_img.size != quadro.size:
                self._grad_img = _gradiente_inferior(quadro.width, quadro.height, self.gradiente)
            m = self._grad_img.point(lambda v, a=a: int(v * a))
            quadro.paste((0, 0, 0), (0, 0), m)
        for i, c in enumerate(self.camadas):
            # camadas de lista: revelação em sequência (0.55 s entre itens)
            atraso = 0.55 * i if len(self.camadas) > 2 else 0.0
            c.aplicar(quadro, lt - atraso, self.dur - atraso)
        return quadro


def construir_overlays(specs: list[dict], w: int, h: int, dur_plano: float) -> list[Overlay]:
    saida: list[Overlay] = []
    for s in specs:
        tipo = s["tipo"]
        t0 = float(s.get("atraso", 0.0))
        dur = float(s.get("duracao", dur_plano - t0))
        dur = max(0.2, min(dur, dur_plano - t0))
        if tipo == "titulo":
            saida.append(Overlay(tg.titulo_principal(s["texto"], s.get("subtitulo"), w, h), t0, dur, escurecer=0.38))
        elif tipo == "capitulo":
            saida.append(Overlay(tg.titulo_capitulo(s["texto"], s.get("linha2"), w, h), t0, dur, gradiente=0.55))
        elif tipo == "versiculo":
            saida.append(Overlay(tg.cartao_versiculo(s.get("citacao"), s["referencia"], s.get("nota"), w, h), t0, dur, escurecer=0.55))
        elif tipo == "lista":
            saida.append(Overlay(tg.cartao_lista(s["titulo"], s["itens"], w, h), t0, dur, escurecer=0.6))
        elif tipo == "ponto":
            saida.append(Overlay(tg.numero_ponto(int(s["numero"]), s["rotulo"], w, h), t0, dur, gradiente=0.6))
        elif tipo == "credito":
            saida.append(Overlay([tg.selo_credito(s["texto"], w, h)], t0, dur))
        elif tipo == "rotulo":
            saida.append(Overlay([tg.rotulo_arte(s["texto"], w, h)], t0, dur, gradiente=0.35))
        else:
            raise ValueError(f"Tipo de overlay desconhecido: {tipo}")
    return saida


# ------------------------------------------------------------ renderizador ---

class RenderizadorPlano:
    def __init__(self, plano: dict, w: int, h: int, cache: Path | None, rapido: bool = False):
        self.plano = plano
        self.w, self.h = w, h
        d_in = plano.get("transicao_entrada", {}).get("duracao", 0.0) if plano.get("transicao_entrada", {}).get("tipo") != "corte" else 0.0
        d_out = plano.get("_dur_saida", 0.0)
        self.span_ini = plano["inicio"] - d_in / 2
        self.span_fim = plano["fim"] + d_out / 2
        self.fonte = FonteVisual(plano["fundo"], plano.get("cor", "neutro"), plano.get("camera", {}),
                                 self.span_fim - self.span_ini, w, h, cache, rapido)
        self.overlays = construir_overlays(plano.get("overlays", []), w, h, plano["fim"] - plano["inicio"])

    def quadro(self, t: float) -> Image.Image:
        p = (t - self.span_ini) / max(1e-6, self.span_fim - self.span_ini)
        q = self.fonte.quadro(p)
        for o in self.overlays:
            q = o.aplicar(q, t - self.plano["inicio"])
        return q


def misturar(a: Image.Image, b: Image.Image, p: float, tipo: str) -> Image.Image:
    """Transição de `a` para `b` com progresso p (0..1)."""
    p = max(0.0, min(1.0, p))
    suave = p * p * (3 - 2 * p)
    if tipo == "corte":
        return b if p >= 0.5 else a
    if tipo == "dissolve":
        return Image.blend(a, b, suave)
    cor = {"dip_black": (0, 0, 0), "dip_gold": (255, 226, 160), "dip_white": (255, 250, 240)}.get(tipo)
    if cor is None:
        raise ValueError(f"Transição desconhecida: {tipo}")
    fundo = Image.new("RGB", a.size, cor)
    if p < 0.5:
        return Image.blend(a, fundo, _suave2(p * 2) * (0.95 if tipo != "dip_black" else 1.0))
    return Image.blend(fundo, b, _suave2((p - 0.5) * 2) if tipo == "dip_black" else 1 - (1 - _suave2((p - 0.5) * 2)) * 0.95)


def _suave2(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


class Compositor:
    """Gera o quadro de índice `n` de toda a linha do tempo (com transições e fades)."""

    def __init__(self, planos: list[dict], w: int, h: int, fps: int, duracao_total: float,
                 cache: Path | None = None, fade_inicio: float = 1.0, fade_fim: float = 1.6,
                 legendas: list[tuple[float, float, str]] | None = None, rapido: bool = False, grao: bool = True):
        self.rapido = rapido
        self.grao = grao
        self.planos = planos
        self.w, self.h, self.fps = w, h, fps
        self.duracao_total = duracao_total
        self.cache = cache
        self.fade_inicio, self.fade_fim = fade_inicio, fade_fim
        self.inicios = [p["inicio"] for p in planos]
        for i, p in enumerate(planos):
            seg = planos[i + 1] if i + 1 < len(planos) else None
            t = (seg or {}).get("transicao_entrada", {})
            p["_dur_saida"] = t.get("duracao", 0.0) if t.get("tipo", "corte") != "corte" else 0.0
        self._cache_r: dict[int, RenderizadorPlano] = {}
        self._vinheta = _vinheta(w, h)
        self._graos = _grao(w, h) if grao else []
        self._legendas = legendas or []
        self._leg_cache: dict[str, tg.Camada] = {}

    def fechar(self):
        """Encerra os decodificadores de vídeo abertos."""
        for r in self._cache_r.values():
            r.fonte.fechar()
        self._cache_r.clear()

    def _renderizador(self, i: int) -> RenderizadorPlano:
        if i not in self._cache_r:
            if len(self._cache_r) > 3:  # mantém só alguns planos vizinhos na memória
                for k in sorted(self._cache_r)[:-2]:
                    if abs(k - i) > 1:
                        self._cache_r[k].fonte.fechar()
                        del self._cache_r[k]
            self._cache_r[i] = RenderizadorPlano(self.planos[i], self.w, self.h, self.cache, self.rapido)
        return self._cache_r[i]

    def indice_plano(self, t: float) -> int:
        return max(0, bisect.bisect_right(self.inicios, t + 1e-9) - 1)

    def quadro(self, n: int) -> Image.Image:
        t = n / self.fps
        i = self.indice_plano(t)
        q = self._renderizador(i).quadro(t)
        # transição de entrada do plano i
        tr = self.planos[i].get("transicao_entrada", {})
        if i > 0 and tr.get("tipo", "corte") != "corte":
            d = tr["duracao"]
            ini = self.planos[i]["inicio"] - d / 2
            if ini <= t < ini + d:
                anterior = self._renderizador(i - 1).quadro(t)
                q = misturar(anterior, self._renderizador(i).quadro(t), (t - ini) / d, tr["tipo"])
        # transição de saída (a janela começa antes do fim do plano i)
        if i + 1 < len(self.planos):
            tr2 = self.planos[i + 1].get("transicao_entrada", {})
            if tr2.get("tipo", "corte") != "corte":
                d = tr2["duracao"]
                ini = self.planos[i + 1]["inicio"] - d / 2
                if ini <= t < ini + d:
                    q = misturar(self._renderizador(i).quadro(t), self._renderizador(i + 1).quadro(t), (t - ini) / d, tr2["tipo"])
        q = ImageChops.multiply(q, self._vinheta)
        if self._graos:
            q = ImageChops.add(q, self._graos[n % len(self._graos)], 1.0, -AMPLITUDE_GRAO)
        for ini, fim, texto in self._legendas:
            if ini <= t < fim:
                cam = self._leg_cache.get(texto) or self._leg_cache.setdefault(texto, tg.legenda_queimada(texto, self.w, self.h))
                cam.aplicar(q, 1.0, 2.0)
        a = 1.0
        if t < self.fade_inicio:
            a = min(a, t / self.fade_inicio)
        if t > self.duracao_total - self.fade_fim:
            a = min(a, max(0.0, (self.duracao_total - t) / self.fade_fim))
        if a < 0.999:
            q = Image.blend(Image.new("RGB", q.size, (0, 0, 0)), q, a)
        return q
