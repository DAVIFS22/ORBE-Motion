"""Estrutura do storyboard: cenas ancoradas em frases do roteiro.

Cada cena começa na palavra do roteiro indicada por `ancora` (o tempo vem do
alinhamento com a transcrição) e termina onde a próxima começa. O conteúdo
visual é escolhido pela descrição da cena, não ao acaso: as consultas de
imagem descrevem o que está sendo narrado naquele instante.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import ErroProducao
from .procedural_art import MOTIVOS
from .visual_effects import GRADES, PRESETS

TRANSICOES = {"corte", "dissolve", "dip_black", "dip_gold", "dip_white"}
RITMOS = {"rapido": 6.0, "normal": 11.0, "lento": 16.0}
TIPOS_SFX = {"impacto", "whoosh", "nota", "passos", "tecido", "pergaminho", "vento_forte", "silencio", "pulso"}


@dataclass
class Cena:
    id: str
    secao: str
    ancora: str
    descricao: str
    consultas: list[dict] = field(default_factory=list)
    motivo: str = "ceu_estrelado"  # alternativa gerada por código
    camera: tuple[str, ...] = ("zoom_in",)
    cor: str = "neutro"
    ritmo: str = "normal"
    transicao: str = "dissolve"
    overlays: list[dict] = field(default_factory=list)
    sfx: list[str] = field(default_factory=list)
    foco: list[float] | None = None
    mapa: bool = False
    lugar: str | None = None
    arquivos: list[str] = field(default_factory=list)  # títulos exatos do Commons (opcional)
    musica: str | None = None  # "baixo" | "normal" | "cresce" | "some"

    def validar(self):
        if self.motivo not in MOTIVOS:
            raise ErroProducao(f"Cena {self.id}: motivo desconhecido {self.motivo!r}")
        if self.transicao not in TRANSICOES:
            raise ErroProducao(f"Cena {self.id}: transição desconhecida {self.transicao!r}")
        if self.ritmo not in RITMOS:
            raise ErroProducao(f"Cena {self.id}: ritmo desconhecido {self.ritmo!r}")
        if self.cor not in GRADES:
            raise ErroProducao(f"Cena {self.id}: cor desconhecida {self.cor!r}")
        for c in self.camera:
            if c not in PRESETS:
                raise ErroProducao(f"Cena {self.id}: movimento de câmera desconhecido {c!r}")
        for s in self.sfx:
            if s.split(":")[0] not in TIPOS_SFX:
                raise ErroProducao(f"Cena {self.id}: efeito desconhecido {s!r}")
        if not self.ancora.strip():
            raise ErroProducao(f"Cena {self.id}: âncora vazia")


def _consulta(texto: str) -> dict:
    """'m:crucifixion' (só Met), 'a:Rembrandt Christ' (todos), padrão: só Commons."""
    mapa = {"c": ["commons"], "m": ["met"], "a": ["commons", "met", "aic"], "i": ["aic"]}
    if len(texto) > 2 and texto[1] == ":" and texto[0] in mapa:
        return {"q": texto[2:].strip(), "fontes": mapa[texto[0]]}
    return {"q": texto.strip(), "fontes": ["commons"]}


def C(id, secao, ancora, desc, q=(), motivo="ceu_estrelado", cam=("zoom_in",), cor="neutro", ritmo="normal",
      trans="dissolve", ov=(), sfx=(), foco=None, mapa=False, lugar=None, arquivos=(), musica=None) -> Cena:
    return Cena(id=id, secao=secao, ancora=ancora, descricao=desc, consultas=[_consulta(x) for x in q],
                motivo=motivo, camera=(cam,) if isinstance(cam, str) else tuple(cam), cor=cor, ritmo=ritmo,
                transicao=trans, overlays=list(ov), sfx=list(sfx), foco=foco, mapa=mapa, lugar=lugar,
                arquivos=list(arquivos), musica=musica)


# Overlays ---------------------------------------------------------------

def CAP(texto, linha2=None, atraso=0.6, dur=4.8):
    return {"tipo": "capitulo", "texto": texto, "linha2": linha2, "atraso": atraso, "duracao": dur}


def VERS(ref, citacao=None, nota=None, atraso=0.5, dur=None):
    d = {"tipo": "versiculo", "referencia": ref, "citacao": citacao, "nota": nota, "atraso": atraso}
    if dur:
        d["duracao"] = dur
    return d


def PONTO(n, rotulo, atraso=0.8, dur=5.0):
    return {"tipo": "ponto", "numero": n, "rotulo": rotulo, "atraso": atraso, "duracao": dur}


def TITULO(texto, sub=None, atraso=0.4, dur=None):
    d = {"tipo": "titulo", "texto": texto, "subtitulo": sub, "atraso": atraso}
    if dur:
        d["duracao"] = dur
    return d


def LISTA(titulo, itens, atraso=0.4, dur=None):
    d = {"tipo": "lista", "titulo": titulo, "itens": itens, "atraso": atraso}
    if dur:
        d["duracao"] = dur
    return d


@dataclass
class Secao:
    id: str
    musica: str  # clima musical (ver audio_synth)
    ambiencia: list[str]
    descricao: str = ""


def carregar(caminho=None) -> tuple[list[Cena], dict[str, Secao]]:
    """Storyboard embutido ou, com `caminho`, um JSON alternativo."""
    if caminho:
        import json
        from pathlib import Path
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
        cenas = [Cena(**{**c, "camera": tuple(c.get("camera", ("zoom_in",)))}) for c in dados["cenas"]]
        secoes = {k: Secao(id=k, **v) for k, v in dados["secoes"].items()}
    else:
        from .storyboard_jesus import CENAS, SECOES
        cenas, secoes = CENAS, SECOES
    ids = set()
    for c in cenas:
        c.validar()
        if c.id in ids:
            raise ErroProducao(f"Id de cena duplicado: {c.id}")
        ids.add(c.id)
        if c.secao not in secoes:
            raise ErroProducao(f"Cena {c.id}: seção desconhecida {c.secao!r}")
    return cenas, secoes
