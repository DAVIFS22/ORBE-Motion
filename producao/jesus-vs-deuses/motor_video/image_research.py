"""Pesquisa de imagens em fontes abertas, com licença e atribuição.

Provedores (APIs públicas, sem contornar autenticação nem paywalls):

* Wikimedia Commons (MediaWiki API): metadados de licença/autor via extmetadata.
* The Metropolitan Museum of Art (Open Access, CC0).
* Art Institute of Chicago (somente obras com `is_public_domain`).

Só entram licenças que permitem uso e adaptação: domínio público, CC0,
CC BY e CC BY-SA. Licenças NC/ND, "uso justo", GFDL isolada e arquivos
marcados como não livres são descartados. Imagens geradas por IA e arquivos
com marca d'água declarada (nos metadados) também.
"""

from __future__ import annotations

import html
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from .config import ErroProducao, log

USER_AGENT = ("ORBE-Motion-DocumentaryEngine/1.0 "
              "(https://github.com/DAVIFS22/ORBE-Motion; pesquisa de imagens para documentário)")


class AcessoNegado(ErroProducao):
    """HTTP 401/403/451: não insistimos nem tentamos contornar."""


class RedeIndisponivel(ErroProducao):
    """Falha de rede (DNS, proxy, tempo esgotado)."""


# ------------------------------------------------------------------ HTTP ---

class ClienteHTTP:
    def __init__(self, intervalo: float = 0.3, tentativas: int = 4, timeout: float = 30.0):
        self.intervalo = intervalo
        self.tentativas = tentativas
        self.timeout = timeout
        self._ultimo = 0.0
        self._falhas_seguidas = 0  # disjuntor: após 2 falhas de rede seguidas, não insiste mais

    def conectado(self) -> bool:
        return self._falhas_seguidas < 2

    def _esperar(self):
        falta = self.intervalo - (time.monotonic() - self._ultimo)
        if falta > 0:
            time.sleep(falta)
        self._ultimo = time.monotonic()

    def _abrir(self, url: str):
        if not self.conectado():
            raise RedeIndisponivel("rede indisponível (as tentativas anteriores falharam; não insistindo)")
        ultimo_erro: Exception | None = None
        for tentativa in range(self.tentativas):
            self._esperar()
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
            try:
                resp = urllib.request.urlopen(req, timeout=self.timeout)
                self._falhas_seguidas = 0
                return resp
            except urllib.error.HTTPError as e:
                if e.code in (401, 403, 451):
                    raise AcessoNegado(f"Acesso negado (HTTP {e.code}) a {url}") from e
                if e.code in (429, 500, 502, 503, 504):
                    espera = min(60.0, float(e.headers.get("Retry-After") or (2 ** tentativa)))
                    log().debug("HTTP %s em %s; aguardando %.1fs", e.code, url, espera)
                    time.sleep(espera)
                    ultimo_erro = e
                    continue
                raise ErroProducao(f"HTTP {e.code} em {url}") from e
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
                ultimo_erro = e
                time.sleep(min(8.0, 2 ** tentativa))
        self._falhas_seguidas += 1
        raise RedeIndisponivel(f"Sem resposta de {url}: {ultimo_erro}")

    def json(self, base: str, params: dict | None = None) -> dict:
        url = base + (("?" + urllib.parse.urlencode(params, doseq=True)) if params else "")
        with self._abrir(url) as r:
            return json.loads(r.read().decode("utf-8"))

    def baixar(self, url: str, destino: Path, max_bytes: int = 80 * 1024 * 1024) -> int:
        destino.parent.mkdir(parents=True, exist_ok=True)
        parcial = destino.with_suffix(destino.suffix + ".part")
        total = 0
        try:
            with self._abrir(url) as r, open(parcial, "wb") as f:
                esperado = r.headers.get("Content-Length")
                while True:
                    bloco = r.read(1 << 16)
                    if not bloco:
                        break
                    total += len(bloco)
                    if total > max_bytes:
                        raise ErroProducao(f"Arquivo maior que {max_bytes // (1 << 20)} MB: {url}")
                    f.write(bloco)
            if esperado and int(esperado) != total:
                raise ErroProducao(f"Download incompleto ({total} de {esperado} bytes): {url}")
            parcial.replace(destino)
            return total
        finally:
            parcial.unlink(missing_ok=True)


# ------------------------------------------------------------ candidatos ---

@dataclass
class Candidato:
    fonte: str  # commons | met | aic
    id_fonte: str
    titulo: str
    url_arquivo: str
    url_pagina: str
    largura: int
    altura: int
    mime: str
    licenca: str
    licenca_categoria: str  # dominio_publico | cc0 | cc-by | cc-by-sa
    licenca_url: str = ""
    autor: str = ""
    credito: str = ""
    descricao: str = ""
    categorias: list[str] = field(default_factory=list)
    natureza: str = "imagem de acervo aberto"
    rank: int = 0
    pontuacao: float = 0.0

    def para_dict(self) -> dict:
        return dict(self.__dict__)


_RE_TAG = re.compile(r"<[^>]+>")


def texto_limpo(valor: str | None) -> str:
    if not valor:
        return ""
    return re.sub(r"\s+", " ", html.unescape(_RE_TAG.sub(" ", valor))).strip()


def classificar_licenca(texto: str) -> str | None:
    """Categoria da licença ou None se não for permitida."""
    t = re.sub(r"\s+", " ", (texto or "").lower()).strip()
    if not t:
        return None
    if re.search(r"\bcc[ -]?by[ -]?(nc|nd)|non-?commercial|no derivatives|noderiv|fair use|non-?free|all rights reserved", t):
        return None
    if re.search(r"\bcc0\b|cc[ -]zero|\bcc[ -]?0\b", t):
        return "cc0"
    if re.search(r"public domain|dom[ií]nio p[uú]blico|\bpd\b|\bpd[- ]|no known copyright|no restrictions", t):
        return "dominio_publico"
    if re.search(r"\bcc[ -]?by[ -]?sa\b", t):
        return "cc-by-sa"
    if re.search(r"\bcc[ -]?by\b", t):
        return "cc-by"
    return None


_RE_SUSPEITO = re.compile(
    r"ai[- ]generated|generated (?:by|with|using) (?:ai|midjourney|dall|stable ?diffusion)|midjourney|stable ?diffusion|"
    r"dall-?e|artificial intelligence|gerad[ao] por (?:ia|inteligência artificial)|"
    r"watermark|marca d.[aá]gua|shutterstock|getty ?images|alamy|dreamstime|istock|depositphotos|123rf|adobe stock",
    re.I)


def e_suspeito(c: Candidato) -> str | None:
    """Motivo pelo qual o candidato deve ser evitado (IA, marca d'água, estoque)."""
    campos = " ".join([c.titulo, c.descricao, c.credito, " ".join(c.categorias)])
    m = _RE_SUSPEITO.search(campos)
    return m.group(0) if m else None


_PENALIZA = re.compile(r"\b(logo|icon|coat of arms|flag of|diagram|stamp|banknote|coin|screenshot|"
                       r"cropped|detail of|map of|svg)\b", re.I)


def pontuar(c: Candidato, consulta: str, min_largura: int, permitir_mapa: bool = False) -> float:
    w, h = c.largura, c.altura
    s = 0.0
    if w and h:
        s += 3.0 * min(1.5, min(w, h * 16 / 9) / 1920)
        proporcao = w / h
        s -= 1.2 * min(1.0, abs(math.log(proporcao / (16 / 9))))
        if w < min_largura:
            s -= 5.0
    termos = {t for t in re.findall(r"[a-zà-ú0-9]{4,}", consulta.lower())}
    corpo = " ".join([c.titulo, c.descricao, " ".join(c.categorias)]).lower()
    s += min(5.0, sum(1.0 for t in termos if t in corpo))
    s += {"dominio_publico": 1.0, "cc0": 1.0, "cc-by": 0.5, "cc-by-sa": 0.3}.get(c.licenca_categoria, 0)
    s -= 0.05 * c.rank
    if not permitir_mapa and _PENALIZA.search(c.titulo):
        s -= 3.0
    return s


# ------------------------------------------------------------ provedores ---

class ProvedorCommons:
    nome = "commons"

    def __init__(self, http: ClienteHTTP, base: str = "https://commons.wikimedia.org/w/api.php"):
        self.http, self.base = http, base

    _META = ("LicenseShortName|LicenseUrl|UsageTerms|AttributionRequired|Artist|Credit|ImageDescription|"
             "ObjectName|Restrictions|NonFree|Categories")

    def _params(self, extra: dict) -> dict:
        p = {"action": "query", "format": "json", "formatversion": "2", "prop": "imageinfo",
             "iiprop": "url|size|mime|extmetadata", "iiurlwidth": "3840",
             "iiextmetadatafilter": self._META}
        p.update(extra)
        return p

    def buscar(self, consulta: str, limite: int = 20) -> list[Candidato]:
        dados = self.http.json(self.base, self._params({
            "generator": "search", "gsrsearch": f"{consulta} filetype:bitmap", "gsrnamespace": "6",
            "gsrlimit": str(limite)}))
        return self._converter(dados)

    def por_titulos(self, titulos: list[str]) -> list[Candidato]:
        dados = self.http.json(self.base, self._params({"titles": "|".join(titulos)}))
        return self._converter(dados)

    def _converter(self, dados: dict) -> list[Candidato]:
        paginas = (dados.get("query") or {}).get("pages") or []
        if isinstance(paginas, dict):  # formatversion 1
            paginas = list(paginas.values())
        resultado: list[Candidato] = []
        for pg in paginas:
            infos = pg.get("imageinfo") or []
            if not infos:
                continue
            info = infos[0]
            meta = {k: texto_limpo((v or {}).get("value")) for k, v in (info.get("extmetadata") or {}).items()}
            if meta.get("NonFree", "").lower() in ("true", "1", "yes"):
                continue
            lic_texto = meta.get("LicenseShortName") or meta.get("UsageTerms") or ""
            cat = classificar_licenca(lic_texto)
            if cat is None:
                continue
            mime = info.get("mime", "")
            w, h = int(info.get("width") or 0), int(info.get("height") or 0)
            url = info.get("url", "")
            usa_miniatura = bool(info.get("thumburl")) and (
                w > 3840 or mime not in ("image/jpeg", "image/png", "image/webp") or mime == "image/svg+xml")
            if usa_miniatura:
                url = info["thumburl"]
                if w > 3840:
                    h = round(h * 3840 / w)
                    w = 3840
                elif info.get("thumbwidth"):
                    w, h = int(info["thumbwidth"]), int(info.get("thumbheight") or h)
            if not url:
                continue
            titulo = (pg.get("title") or "").removeprefix("File:")
            cats = [c.strip() for c in meta.get("Categories", "").split("|") if c.strip()]
            resultado.append(Candidato(
                fonte="commons", id_fonte=str(pg.get("pageid", titulo)), titulo=titulo, url_arquivo=url,
                url_pagina=info.get("descriptionurl", ""), largura=w, altura=h, mime=mime,
                licenca=lic_texto, licenca_categoria=cat, licenca_url=meta.get("LicenseUrl", ""),
                autor=meta.get("Artist", ""), credito=meta.get("Credit", ""),
                descricao=meta.get("ImageDescription", "") or meta.get("ObjectName", ""),
                categorias=cats, rank=int(pg.get("index", len(resultado))),
            ))
        resultado.sort(key=lambda c: c.rank)
        return resultado


class ProvedorMet:
    nome = "met"

    def __init__(self, http: ClienteHTTP, base: str = "https://collectionapi.metmuseum.org/public/collection/v1",
                 max_objetos: int = 6):
        self.http, self.base, self.max_objetos = http, base, max_objetos

    def buscar(self, consulta: str, limite: int = 6) -> list[Candidato]:
        dados = self.http.json(f"{self.base}/search", {"q": consulta, "hasImages": "true", "isPublicDomain": "true"})
        ids = (dados.get("objectIDs") or [])[: min(limite, self.max_objetos)]
        saida: list[Candidato] = []
        for rank, oid in enumerate(ids):
            obj = self.http.json(f"{self.base}/objects/{oid}")
            if not obj.get("isPublicDomain") or not obj.get("primaryImage"):
                continue
            autor = obj.get("artistDisplayName") or obj.get("culture") or "Autor desconhecido"
            saida.append(Candidato(
                fonte="met", id_fonte=str(oid), titulo=obj.get("title", f"Met {oid}"),
                url_arquivo=obj["primaryImage"], url_pagina=obj.get("objectURL", ""),
                largura=0, altura=0, mime="image/jpeg",  # dimensões conferidas após o download
                licenca="CC0 (Open Access, The Metropolitan Museum of Art)", licenca_categoria="cc0",
                licenca_url="https://www.metmuseum.org/about-the-met/policies-and-documents/open-access",
                autor=autor, credito=obj.get("creditLine", ""),
                descricao=" ".join(filter(None, [obj.get("objectName"), obj.get("medium"), obj.get("objectDate")])),
                categorias=[t.get("term", "") for t in (obj.get("tags") or []) if isinstance(t, dict)],
                natureza="obra de arte (digitalização do acervo do museu)", rank=rank,
            ))
        return saida


class ProvedorAIC:
    nome = "aic"

    def __init__(self, http: ClienteHTTP, base: str = "https://api.artic.edu/api/v1",
                 iiif: str = "https://www.artic.edu/iiif/2"):
        self.http, self.base, self.iiif = http, base, iiif

    def buscar(self, consulta: str, limite: int = 8) -> list[Candidato]:
        dados = self.http.json(f"{self.base}/artworks/search", {
            "q": consulta, "limit": str(limite), "query[term][is_public_domain]": "true",
            "fields": "id,title,image_id,artist_display,date_display,is_public_domain,thumbnail,credit_line"})
        iiif = (dados.get("config") or {}).get("iiif_url") or self.iiif
        saida: list[Candidato] = []
        for rank, obra in enumerate(dados.get("data") or []):
            if not obra.get("is_public_domain") or not obra.get("image_id"):
                continue
            thumb = obra.get("thumbnail") or {}
            saida.append(Candidato(
                fonte="aic", id_fonte=str(obra["id"]), titulo=obra.get("title", ""),
                url_arquivo=f"{iiif}/{obra['image_id']}/full/1686,/0/default.jpg",
                url_pagina=f"https://www.artic.edu/artworks/{obra['id']}",
                largura=1686, altura=round(1686 * (thumb.get("height") or 1) / (thumb.get("width") or 1)) if thumb else 0,
                mime="image/jpeg", licenca="CC0 (domínio público, Art Institute of Chicago)",
                licenca_categoria="cc0", licenca_url="https://www.artic.edu/open-access",
                autor=texto_limpo(obra.get("artist_display")), credito=obra.get("credit_line") or "",
                descricao=obra.get("date_display") or "", natureza="obra de arte (digitalização do acervo do museu)",
                rank=rank,
            ))
        return saida


def criar_provedores(http: ClienteHTTP, nomes: list[str] | None = None) -> list:
    todos = {"commons": ProvedorCommons(http), "met": ProvedorMet(http), "aic": ProvedorAIC(http)}
    return [todos[n] for n in (nomes or ["commons", "met", "aic"]) if n in todos]
