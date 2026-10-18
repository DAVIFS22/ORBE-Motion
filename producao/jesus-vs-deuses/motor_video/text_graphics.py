"""Tipografia e elementos gráficos (Pillow): títulos, versículos, capítulos, créditos."""

from __future__ import annotations

import functools
import os
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

_CANDIDATAS = {
    ("serif", True): ["georgiab.ttf", "Georgia Bold.ttf", "timesbd.ttf", "cambriab.ttf", "DejaVuSerif-Bold.ttf",
                      "LiberationSerif-Bold.ttf", "FreeSerifBold.ttf"],
    ("serif", False): ["georgia.ttf", "Georgia.ttf", "times.ttf", "cambria.ttc", "DejaVuSerif.ttf",
                       "LiberationSerif-Regular.ttf", "FreeSerif.ttf"],
    ("serif-it", False): ["georgiai.ttf", "timesi.ttf", "DejaVuSerif-Italic.ttf", "LiberationSerif-Italic.ttf",
                          "FreeSerifItalic.ttf"],
    ("sans", True): ["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"],
    ("sans", False): ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"],
}


def _pastas_de_fontes() -> list[Path]:
    pastas = [Path(os.environ.get("MOTOR_FONTES", "")) if os.environ.get("MOTOR_FONTES") else None,
              Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts", Path("/usr/share/fonts"),
              Path("/usr/local/share/fonts"), Path("/Library/Fonts"), Path("/System/Library/Fonts/Supplemental"),
              Path.home() / ".fonts", Path.home() / "Library/Fonts"]
    return [p for p in pastas if p and p.exists()]


@functools.lru_cache(maxsize=None)
def _achar(nome: str) -> str | None:
    for pasta in _pastas_de_fontes():
        direto = pasta / nome
        if direto.is_file():
            return str(direto)
        for achado in pasta.rglob(nome):
            return str(achado)
    return None


@functools.lru_cache(maxsize=64)
def carregar_fonte(familia: str, negrito: bool, tamanho: int) -> ImageFont.FreeTypeFont:
    chave = (familia, negrito) if (familia, negrito) in _CANDIDATAS else (familia, False)
    for nome in _CANDIDATAS[chave]:
        caminho = _achar(nome)
        if caminho:
            try:
                return ImageFont.truetype(caminho, tamanho)
            except OSError:
                continue
    return ImageFont.load_default(tamanho)


def medir(texto: str, fonte, espacamento: float = 0.0) -> float:
    return fonte.getlength(texto) + espacamento * max(0, len(texto) - 1)


def desenhar_espacado(d: ImageDraw.ImageDraw, xy, texto: str, fonte, cor, espacamento: float = 0.0):
    x, y = xy
    if espacamento == 0:
        d.text((x, y), texto, font=fonte, fill=cor)
        return
    for ch in texto:
        d.text((x, y), ch, font=fonte, fill=cor)
        x += fonte.getlength(ch) + espacamento


def quebrar(texto: str, fonte, largura_max: float) -> list[str]:
    linhas, atual = [], ""
    for palavra in texto.split():
        teste = f"{atual} {palavra}".strip()
        if medir(teste, fonte) <= largura_max or not atual:
            atual = teste
        else:
            linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


@dataclass
class Camada:
    """Camada de texto: RGB + máscara (L) posicionadas em `pos`, com animação própria."""
    rgb: Image.Image
    mascara: Image.Image
    pos: tuple[int, int]
    entrada: float = 0.7
    saida: float = 0.7
    deslize: int = 22  # pixels de subida na entrada

    def alpha(self, t: float, duracao: float) -> float:
        if t < 0 or t > duracao:
            return 0.0
        a = 1.0
        if self.entrada > 0 and t < self.entrada:
            a = min(a, _suave(t / self.entrada))
        if self.saida > 0 and t > duracao - self.saida:
            a = min(a, _suave((duracao - t) / self.saida))
        return a

    def aplicar(self, quadro: Image.Image, t: float, duracao: float):
        a = self.alpha(t, duracao)
        if a <= 0.003:
            return
        x, y = self.pos
        if self.entrada > 0 and t < self.entrada:
            y += int(self.deslize * (1 - _suave(t / self.entrada)))
        mascara = self.mascara if a >= 0.999 else self.mascara.point(lambda v, a=a: int(v * a))
        quadro.paste(self.rgb, (x, y), mascara)


def _e(h: int, v: float) -> float:
    """Medida em pixels de um quadro de 1080 de altura, escalada para a altura `h` (layout igual em qualquer resolução)."""
    return v * h / 1080


def _suave(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _camada_de_texto(largura: int, altura: int, desenhar, *, sombra: int = 10, pos=(0, 0), **kw) -> Camada:
    """Cria RGB+máscara com sombra suave a partir de uma função `desenhar(draw)`."""
    esc = kw.pop("h", 1080) / 1080  # a sombra/respiro escalam com a resolução (verificação em baixa resolução)
    sombra = max(1, round(sombra * esc))
    kw["deslize"] = round(kw.get("deslize", 22) * esc)
    pad = sombra * 3
    rgba = Image.new("RGBA", (largura + 2 * pad, altura + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(rgba)
    desenhar(d, pad)
    alpha = rgba.getchannel("A")
    if sombra:
        sombra_img = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
        sombra_img.putalpha(alpha.filter(ImageFilter.GaussianBlur(sombra)).point(lambda v: int(v * 0.85)))
        base = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
        base.paste((0, 0, 0, 255), (0, 0), sombra_img.getchannel("A"))
        base.alpha_composite(rgba)
        rgba = base
    rgb = rgba.convert("RGB")
    return Camada(rgb=rgb, mascara=rgba.getchannel("A"), pos=(pos[0] - pad, pos[1] - pad), **kw)


OURO = (232, 190, 105)
MARFIM = (246, 238, 222)


def titulo_principal(texto: str, subtitulo: str | None, w: int, h: int) -> list[Camada]:
    """Título centralizado, em maiúsculas espaçadas, com linha dourada."""
    fonte = carregar_fonte("serif", True, int(h * 0.092))
    sub = carregar_fonte("serif-it", False, int(h * 0.04))
    linhas = quebrar(texto.upper(), fonte, w * 0.84)
    esp = h * 0.006
    alt_linha = int(fonte.size * 1.18)
    altura_total = alt_linha * len(linhas) + (int(h * 0.1) if subtitulo else 0)
    y0 = int(h * 0.5 - altura_total / 2)

    def desenhar(d, pad):
        y = y0 - y0 + pad
        for ln in linhas:
            largura = medir(ln, fonte, esp)
            desenhar_espacado(d, (pad + (w - largura) / 2, y), ln, fonte, MARFIM, esp)
            y += alt_linha
        d.line([(pad + w * 0.38, y + _e(h, 12)), (pad + w * 0.62, y + _e(h, 12))], fill=OURO, width=max(1, round(_e(h, 4))))
        if subtitulo:
            largura = medir(subtitulo, sub, _e(h, 2))
            desenhar_espacado(d, (pad + (w - largura) / 2, y + _e(h, 34)), subtitulo, sub, OURO, _e(h, 2))

    return [_camada_de_texto(w, altura_total + int(_e(h, 40)), desenhar, sombra=14, h=h, pos=(0, y0), entrada=1.1, saida=0.9)]


def titulo_capitulo(texto: str, linha2: str | None, w: int, h: int) -> list[Camada]:
    """Título de capítulo no terço inferior esquerdo, com barra dourada."""
    fonte = carregar_fonte("serif", True, int(h * 0.058))
    sub = carregar_fonte("serif-it", False, int(h * 0.032))
    x0, y0 = int(w * 0.07), int(h * 0.72)
    larg = int(w * 0.8)
    esp = h * 0.004

    def desenhar(d, pad):
        d.rectangle([pad, pad, pad + max(1, _e(h, 8)), pad + int(fonte.size * 1.35) + (int(sub.size * 1.5) if linha2 else 0)], fill=OURO)
        desenhar_espacado(d, (pad + _e(h, 30), pad - _e(h, 2)), texto.upper(), fonte, MARFIM, esp)
        if linha2:
            desenhar_espacado(d, (pad + _e(h, 32), pad + int(fonte.size * 1.2)), linha2, sub, OURO, _e(h, 1.5))

    alt = int(fonte.size * 1.4) + (int(sub.size * 1.6) if linha2 else 0)
    return [_camada_de_texto(larg, alt, desenhar, sombra=9, h=h, pos=(x0, y0), entrada=0.8, saida=0.8, deslize=18)]


def cartao_versiculo(citacao: str | None, referencia: str, nota: str | None, w: int, h: int) -> list[Camada]:
    """Citação (se literal do roteiro) + referência bíblica, sobre faixa escurecida."""
    f_cit = carregar_fonte("serif-it", False, int(h * 0.062))
    f_ref = carregar_fonte("serif", True, int(h * 0.042))
    f_nota = carregar_fonte("serif", False, int(h * 0.034))
    largura = int(w * 0.72)
    linhas = quebrar(f"“{citacao}”", f_cit, largura) if citacao else []
    linhas_nota = quebrar(nota, f_nota, largura) if nota else []
    alt_cit, alt_nota = int(f_cit.size * 1.35), int(f_nota.size * 1.4)
    altura = alt_cit * len(linhas) + alt_nota * len(linhas_nota) + int(f_ref.size * 2.4) + int(_e(h, 40))
    y0 = int(h * 0.5 - altura / 2)

    def desenhar(d, pad):
        y = pad
        for ln in linhas:
            desenhar_espacado(d, (pad + (w - medir(ln, f_cit)) / 2, y), ln, f_cit, MARFIM)
            y += alt_cit
        for ln in linhas_nota:
            desenhar_espacado(d, (pad + (w - medir(ln, f_nota)) / 2, y), ln, f_nota, MARFIM)
            y += alt_nota
        y += int(f_ref.size * 0.5)
        d.line([(pad + w * 0.44, y), (pad + w * 0.56, y)], fill=OURO, width=max(1, round(_e(h, 3))))
        ref = referencia.upper()
        desenhar_espacado(d, (pad + (w - medir(ref, f_ref, _e(h, 4))) / 2, y + _e(h, 16)), ref, f_ref, OURO, _e(h, 4))

    return [_camada_de_texto(w, altura, desenhar, sombra=12, h=h, pos=(0, y0), entrada=0.9, saida=0.9)]


def cartao_lista(titulo: str, itens: list[str], w: int, h: int, numerar: bool = True) -> list[Camada]:
    """Lista de pontos (ex.: os cinco argumentos), cada um revelado em sequência."""
    f_tit = carregar_fonte("serif", True, int(h * 0.05))
    f_item = carregar_fonte("serif", True, int(h * 0.056))
    x0 = int(w * 0.14)
    y_ini = int(h * 0.20)
    passo = int(h * 0.12)
    camadas = []

    def titulo_d(d, pad):
        desenhar_espacado(d, (pad, pad), titulo.upper(), f_tit, OURO, _e(h, 5))
    camadas.append(_camada_de_texto(int(w * 0.7), int(f_tit.size * 1.4), titulo_d, sombra=9, h=h, pos=(x0, y_ini - int(h * 0.1)),
                                    entrada=0.7, saida=0.7))
    for i, item in enumerate(itens):
        def d_item(d, pad, i=i, item=item):
            if numerar:
                d.ellipse([pad, pad, pad + f_item.size * 1.2, pad + f_item.size * 1.2], outline=OURO, width=max(1, round(_e(h, 4))))
                n = str(i + 1)
                d.text((pad + f_item.size * 0.6 - medir(n, f_item) / 2, pad + f_item.size * 0.02), n, font=f_item, fill=OURO)
            d.text((pad + f_item.size * 1.7, pad + f_item.size * 0.04), item, font=f_item, fill=MARFIM)
        camadas.append(_camada_de_texto(int(w * 0.72), int(f_item.size * 1.4), d_item, sombra=9, h=h,
                                        pos=(x0, y_ini + i * passo + int(h * 0.04)), entrada=0.7, saida=0.7))
    return camadas


def numero_ponto(numero: int, rotulo: str, w: int, h: int) -> list[Camada]:
    """Marcador de ponto central (ex.: “1 · ETERNO”) no canto inferior esquerdo."""
    f_num = carregar_fonte("serif", True, int(h * 0.15))
    f_rot = carregar_fonte("serif", True, int(h * 0.052))
    x0, y0 = int(w * 0.07), int(h * 0.64)

    def desenhar(d, pad):
        d.text((pad, pad - int(f_num.size * 0.12)), str(numero), font=f_num, fill=OURO)
        deslocamento = int(medir(str(numero), f_num) + _e(h, 28))
        d.rectangle([pad + deslocamento, pad + int(f_num.size * 0.2), pad + deslocamento + max(1, _e(h, 5)), pad + int(f_num.size * 0.95)], fill=OURO)
        desenhar_espacado(d, (pad + deslocamento + _e(h, 26), pad + int(f_num.size * 0.34)), rotulo.upper(), f_rot, MARFIM, _e(h, 4))

    return [_camada_de_texto(int(w * 0.6), int(f_num.size * 1.2), desenhar, sombra=10, h=h, pos=(x0, y0),
                             entrada=0.7, saida=0.7)]


def selo_credito(texto: str, w: int, h: int) -> Camada:
    """Crédito de imagem, pequeno, no canto inferior direito."""
    f = carregar_fonte("sans", False, int(h * 0.0185))
    while medir(texto, f) > w * 0.46 and len(texto) > 20:
        texto = texto[:-4].rstrip() + "…"
    larg = int(medir(texto, f)) + 6
    alt = int(f.size * 1.5)

    def desenhar(d, pad):
        d.text((pad, pad), texto, font=f, fill=(238, 232, 220))

    c = _camada_de_texto(larg, alt, desenhar, sombra=4, h=h, pos=(int(w - larg - w * 0.018), int(h - alt - h * 0.022)),
                         entrada=0.6, saida=0.6, deslize=0)
    return c


def legenda_queimada(texto: str, w: int, h: int) -> Camada:
    f = carregar_fonte("sans", True, int(h * 0.043))
    linhas = texto.split("\n")
    alt = int(f.size * 1.3) * len(linhas)
    larg = int(max(medir(ln, f) for ln in linhas)) + 8

    def desenhar(d, pad):
        y = pad
        for ln in linhas:
            d.text((pad + (larg - medir(ln, f)) / 2, y), ln, font=f, fill=(255, 255, 255),
                   stroke_width=max(1, round(_e(h, 3))), stroke_fill=(0, 0, 0))
            y += int(f.size * 1.3)
    return _camada_de_texto(larg, alt, desenhar, sombra=5, h=h, pos=(int((w - larg) / 2), int(h * 0.9 - alt)),
                            entrada=0.0, saida=0.0, deslize=0)


def rotulo_arte(texto: str, w: int, h: int) -> Camada:
    """Rótulo discreto (canto inferior esquerdo) para reconstruções/representações artísticas."""
    f = carregar_fonte("serif-it", False, int(h * 0.026))
    while medir(texto, f) > w * 0.7 and len(texto) > 20:
        texto = texto[:-4].rstrip() + "…"
    larg = int(medir(texto, f)) + 8
    alt = int(f.size * 1.5)

    def desenhar(d, pad):
        d.text((pad, pad), texto, font=f, fill=(244, 236, 220))

    return _camada_de_texto(larg, alt, desenhar, sombra=6, h=h, pos=(int(w * 0.035), int(h * 0.925 - alt)), entrada=0.7, saida=0.7, deslize=0)
