"""Downloads, validação, deduplicação e registro de licenças das imagens.

Depois do download só existem arquivos locais validados: a renderização nunca
depende de URLs. O manifesto (`manifesto-imagens.json`) guarda autor, fonte,
licença e URL original de cada arquivo, as pendências e as falhas.
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from .config import ErroProducao, ler_json, log, salvar_json
from .image_research import (AcessoNegado, Candidato, ClienteHTTP, RedeIndisponivel, e_suspeito, pontuar)

Image.MAX_IMAGE_PIXELS = 250_000_000

LADO_MAX_TRABALHO = 3200
MIN_LARGURA_PADRAO = 1280


class ImagemInvalida(ErroProducao):
    pass


@dataclass
class Asset:
    id: str
    arquivo_original: str  # relativo à pasta de imagens
    arquivo_trabalho: str  # JPEG normalizado usado na renderização
    fonte: str
    titulo: str
    autor: str
    licenca: str
    licenca_categoria: str
    licenca_url: str
    url_pagina: str
    url_arquivo: str
    natureza: str
    largura: int
    altura: int
    sha256: str
    phash: str
    credito: str = ""
    consulta: str = ""
    cenas: list[str] = field(default_factory=list)

    @property
    def exige_atribuicao(self) -> bool:
        return self.licenca_categoria in ("cc-by", "cc-by-sa")

    def linha_credito(self) -> str:
        autor = self.autor or "autor não informado"
        return f"“{self.titulo}” — {autor} — {self.licenca} — {self.url_pagina or self.url_arquivo}"


def dhash(img: Image.Image) -> str:
    g = img.convert("L").resize((9, 8), Image.LANCZOS)
    px = list(g.getdata())
    bits = 0
    for y in range(8):
        for x in range(8):
            bits = (bits << 1) | (px[y * 9 + x] > px[y * 9 + x + 1])
    return f"{bits:016x}"


def distancia_hash(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def sha256_bytes(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def abrir_e_validar(caminho: Path, min_largura: int = MIN_LARGURA_PADRAO) -> Image.Image:
    """Abre a imagem por completo; levanta ImagemInvalida se algo estiver errado."""
    try:
        with Image.open(caminho) as probe:
            probe.verify()
        img = Image.open(caminho)
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError, ValueError) as e:
        raise ImagemInvalida(f"arquivo não abre como imagem ({e.__class__.__name__}: {e})") from e
    img = ImageOps.exif_transpose(img)
    w, h = img.size
    if max(w, h) < min_largura or min(w, h) < 600:
        raise ImagemInvalida(f"resolução baixa demais ({w}x{h})")
    proporcao = w / h
    if proporcao > 4.0 or proporcao < 0.5:
        raise ImagemInvalida(f"proporção inadequada ({w}x{h})")
    amostra = img.convert("L").resize((64, 64))
    pixels = list(amostra.getdata())
    media = sum(pixels) / len(pixels)
    desvio = (sum((p - media) ** 2 for p in pixels) / len(pixels)) ** 0.5
    if desvio < 3.0:
        raise ImagemInvalida("imagem praticamente uniforme (vazia ou em branco)")
    return img


def normalizar_para_trabalho(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        fundo = Image.new("RGB", img.size, (0, 0, 0))
        fundo.paste(img, mask=img.getchannel("A"))
        img = fundo
    elif img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    if max(w, h) > LADO_MAX_TRABALHO:
        fator = LADO_MAX_TRABALHO / max(w, h)
        img = img.resize((max(1, round(w * fator)), max(1, round(h * fator))), Image.LANCZOS)
    return img


class GerenciadorAssets:
    def __init__(self, pasta: Path, http: ClienteHTTP | None = None, min_largura: int = MIN_LARGURA_PADRAO):
        self.pasta = pasta
        self.http = http
        self.min_largura = min_largura
        self.dir_orig = pasta / "originais"
        self.dir_trab = pasta / "trabalho"
        self.dir_orig.mkdir(parents=True, exist_ok=True)
        self.dir_trab.mkdir(parents=True, exist_ok=True)
        self.caminho_manifesto = pasta / "manifesto-imagens.json"
        self.assets: dict[str, Asset] = {}
        self.pendencias: list[dict] = []
        self.falhas: list[dict] = []
        self.cache_buscas: dict[str, list[dict]] = {}
        self._carregar()

    # persistência -----------------------------------------------------
    def _carregar(self):
        if not self.caminho_manifesto.is_file():
            return
        dados = ler_json(self.caminho_manifesto)
        for d in dados.get("assets", []):
            a = Asset(**d)
            if (self.pasta / a.arquivo_trabalho).is_file():
                self.assets[a.id] = a
        self.pendencias = dados.get("pendencias", [])
        self.falhas = dados.get("falhas", [])
        self.cache_buscas = dados.get("cache_buscas", {})

    def salvar(self):
        salvar_json(self.caminho_manifesto, {
            "assets": [asdict(a) for a in self.assets.values()],
            "pendencias": self.pendencias, "falhas": self.falhas, "cache_buscas": self.cache_buscas,
        })

    # consultas --------------------------------------------------------
    def caminho_trabalho(self, asset: Asset) -> Path:
        return self.pasta / asset.arquivo_trabalho

    def duplicada(self, sha: str, ph: str) -> str | None:
        for a in self.assets.values():
            if a.sha256 == sha:
                return a.id
            if distancia_hash(a.phash, ph) <= 5:
                return a.id
        return None

    def registrar_falha(self, cena: str, cand: Candidato | None, motivo: str):
        self.falhas.append({
            "cena": cena, "fonte": cand.fonte if cand else None, "titulo": cand.titulo if cand else None,
            "url": cand.url_arquivo if cand else None, "motivo": motivo,
        })
        log().info("   descartada (%s): %s", motivo, cand.titulo if cand else "")

    def registrar_pendencia(self, cena: str, motivo: str, consultas: list[str]):
        self.pendencias.append({"cena": cena, "motivo": motivo, "consultas": consultas})
        log().warning("   PENDÊNCIA em %s: %s", cena, motivo)

    # download ---------------------------------------------------------
    def baixar(self, cand: Candidato, cena: str, consulta: str) -> Asset:
        if self.http is None:
            raise RedeIndisponivel("modo offline")
        motivo = e_suspeito(cand)
        if motivo:
            raise ImagemInvalida(f"metadados indicam IA/marca d'água/estoque ({motivo})")
        base = re.sub(r"[^a-z0-9]+", "-", f"{cand.fonte}-{cand.titulo}".lower()).strip("-")[:70] or "imagem"
        sufixo = {"image/png": ".png", "image/webp": ".webp"}.get(cand.mime, ".jpg")
        destino = self.dir_orig / f"{base}-{cand.id_fonte}{sufixo}"
        if not destino.is_file():
            self.http.baixar(cand.url_arquivo, destino)
        try:
            img = abrir_e_validar(destino, self.min_largura)
        except ImagemInvalida:
            destino.unlink(missing_ok=True)
            raise
        sha = sha256_bytes(destino)
        ph = dhash(img)
        existente = self.duplicada(sha, ph)
        if existente:
            raise ImagemInvalida(f"duplicada de {existente}")
        aid = sha[:12]
        trabalho = self.dir_trab / f"{aid}.jpg"
        norm = normalizar_para_trabalho(img)
        norm.save(trabalho, "JPEG", quality=93, subsampling=0)
        asset = Asset(
            id=aid, arquivo_original=str(destino.relative_to(self.pasta)),
            arquivo_trabalho=str(trabalho.relative_to(self.pasta)), fonte=cand.fonte, titulo=cand.titulo,
            autor=cand.autor, licenca=cand.licenca, licenca_categoria=cand.licenca_categoria,
            licenca_url=cand.licenca_url, url_pagina=cand.url_pagina, url_arquivo=cand.url_arquivo,
            natureza=cand.natureza, largura=img.size[0], altura=img.size[1], sha256=sha, phash=ph,
            credito=cand.credito, consulta=consulta, cenas=[cena],
        )
        self.assets[aid] = asset
        self.salvar()
        return asset

    def importar_local(self, caminho: Path, cena: str) -> Asset:
        """Imagem fornecida pelo usuário (a licença é responsabilidade dele)."""
        img = abrir_e_validar(caminho, 900)
        sha = sha256_bytes(caminho)
        ph = dhash(img)
        aid = sha[:12]
        if aid in self.assets:
            if cena not in self.assets[aid].cenas:
                self.assets[aid].cenas.append(cena)
            return self.assets[aid]
        trabalho = self.dir_trab / f"{aid}.jpg"
        normalizar_para_trabalho(img).save(trabalho, "JPEG", quality=93, subsampling=0)
        asset = Asset(
            id=aid, arquivo_original=str(caminho), arquivo_trabalho=str(trabalho.relative_to(self.pasta)),
            fonte="usuario", titulo=caminho.stem, autor="não informado", licenca="fornecida pelo usuário",
            licenca_categoria="usuario", licenca_url="", url_pagina="", url_arquivo=str(caminho),
            natureza="imagem fornecida pelo usuário", largura=img.size[0], altura=img.size[1],
            sha256=sha, phash=ph, consulta="(local)", cenas=[cena],
        )
        self.assets[aid] = asset
        self.salvar()
        return asset


# --------------------------------------------------------------- pesquisa ---

def obter_imagens_para_cena(
    cena_id: str, consultas: list[dict], quantidade: int, gerenciador: GerenciadorAssets,
    provedores: list, permitir_mapa: bool = False, titulos_commons: list[str] | None = None,
) -> list[Asset]:
    """Busca até `quantidade` imagens distintas e válidas para a cena.

    Candidatos indisponíveis, inválidos ou duplicados são substituídos pelo
    próximo da lista. Se faltar imagem, registra a pendência (o chamador usa
    a alternativa visual gerada por código).
    """
    achadas: list[Asset] = []
    por_nome = {p.nome: p for p in provedores}
    rede_caiu = False
    consultas_texto = [c["q"] for c in consultas]

    def tentar(cands: list[Candidato], q: str):
        nonlocal rede_caiu
        ordenados = sorted(cands, key=lambda c: -pontuar(c, q, gerenciador.min_largura, permitir_mapa))
        for cand in ordenados:
            if len(achadas) >= quantidade or rede_caiu:
                return
            cand.pontuacao = pontuar(cand, q, gerenciador.min_largura, permitir_mapa)
            if cand.pontuacao < 0.5:
                continue
            try:
                a = gerenciador.baixar(cand, cena_id, q)
            except ImagemInvalida as e:
                gerenciador.registrar_falha(cena_id, cand, str(e))
                continue
            except AcessoNegado as e:
                gerenciador.registrar_falha(cena_id, cand, f"acesso negado: {e}")
                continue
            except RedeIndisponivel as e:
                gerenciador.registrar_falha(cena_id, cand, f"rede indisponível: {e}")
                rede_caiu = True
                return
            except ErroProducao as e:
                gerenciador.registrar_falha(cena_id, cand, str(e))
                continue
            if a.id not in {x.id for x in achadas}:
                if cena_id not in a.cenas:
                    a.cenas.append(cena_id)
                achadas.append(a)
                log().info("   + %s (%s, %s)", a.titulo[:60], a.fonte, a.licenca)

    if titulos_commons and "commons" in por_nome:
        try:
            tentar(por_nome["commons"].por_titulos(titulos_commons), " ".join(titulos_commons))
        except (RedeIndisponivel, AcessoNegado) as e:
            gerenciador.registrar_falha(cena_id, None, f"consulta por título: {e}")
            rede_caiu = isinstance(e, RedeIndisponivel)

    for consulta in consultas:
        q = consulta["q"]
        for nome in consulta.get("fontes", ["commons", "met", "aic"]):
            if len(achadas) >= quantidade or rede_caiu:
                break
            prov = por_nome.get(nome)
            if prov is None:
                continue
            chave = f"{nome}|{q}"
            try:
                if chave in gerenciador.cache_buscas:
                    cands = [Candidato(**d) for d in gerenciador.cache_buscas[chave]]
                else:
                    cands = prov.buscar(q)
                    gerenciador.cache_buscas[chave] = [c.para_dict() for c in cands]
                    gerenciador.salvar()
            except RedeIndisponivel as e:
                gerenciador.registrar_falha(cena_id, None, f"busca '{q}' em {nome}: {e}")
                rede_caiu = True
                break
            except ErroProducao as e:
                gerenciador.registrar_falha(cena_id, None, f"busca '{q}' em {nome}: {e}")
                continue
            tentar(cands, q)
        if len(achadas) >= quantidade or rede_caiu:
            break

    if len(achadas) < quantidade:
        motivo = ("rede indisponível" if rede_caiu else "nenhuma imagem adequada e licenciada encontrada")
        faltam = quantidade - len(achadas)
        gerenciador.registrar_pendencia(cena_id, f"{motivo}; faltam {faltam} de {quantidade} imagem(ns)", consultas_texto)
    gerenciador.salvar()
    return achadas
