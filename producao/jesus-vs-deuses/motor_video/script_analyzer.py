"""Análise do roteiro e da transcrição com timestamps.

A transcrição (VTT/SRT) vem de reconhecimento de fala e contém erros de
grafia ("Zeus-Udan", "Colocense Zoom"). O texto correto é o do roteiro; a
transcrição fornece apenas os tempos. As duas são alinhadas palavra a palavra
(difflib sobre palavras normalizadas) e o tempo de cada palavra do roteiro é:

* o tempo do trecho da transcrição em que ela foi reconhecida (interpolado
  dentro do cue, pois o VTT só traz tempos por cue); ou
* interpolado entre as âncoras vizinhas, quando a palavra não foi reconhecida.

Trechos longos do roteiro sem correspondência são reportados: podem ser
partes não narradas ou falhas do reconhecimento de fala.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

MARCA_INICIO = "INÍCIO DA NARRAÇÃO COMPLETA"
MARCA_FIM = "FIM DA NARRAÇÃO COMPLETA"


class ErroRoteiro(ValueError):
    """Roteiro ou transcrição inválidos."""


@dataclass(frozen=True)
class Cue:
    ini: float
    fim: float
    texto: str


@dataclass
class Frase:
    idx: int
    texto: str
    palavra_ini: int  # índice (inclusivo) na lista de palavras do roteiro
    palavra_fim: int  # índice (exclusivo)
    paragrafo: int


@dataclass
class Alinhamento:
    palavras: list[str]  # palavras do roteiro, como escritas
    normalizadas: list[str]
    t_ini: list[float]
    t_fim: list[float]
    reconhecida: list[bool]  # True quando a palavra casou com a transcrição
    frases: list[Frase]
    duracao_transcricao: float
    lacunas: list[dict] = field(default_factory=list)

    @property
    def cobertura(self) -> float:
        if not self.reconhecida:
            return 0.0
        return sum(self.reconhecida) / len(self.reconhecida)

    def tempo_frase(self, frase: Frase) -> tuple[float, float]:
        return self.t_ini[frase.palavra_ini], self.t_fim[frase.palavra_fim - 1]


# ----------------------------------------------------------------- texto ---

def normalizar(palavra: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", palavra)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"[^0-9a-z]", "", sem_acento.lower())


def tokenizar(texto: str) -> list[str]:
    """Palavras como escritas (pontuação colada é mantida para exibição)."""
    return [p for p in texto.split() if normalizar(p)]


def extrair_narracao(texto_arquivo: str) -> str:
    """Devolve só o texto narrado: entre as marcas de início e fim, se existirem."""
    linhas = texto_arquivo.splitlines()
    ini = next((i for i, l in enumerate(linhas) if MARCA_INICIO in l), None)
    fim = next((i for i, l in enumerate(linhas) if MARCA_FIM in l), None)
    if ini is not None and fim is not None and fim > ini:
        linhas = linhas[ini + 1:fim]
    elif ini is not None:
        linhas = linhas[ini + 1:]
    texto = "\n".join(linhas).strip()
    if not texto:
        raise ErroRoteiro("O roteiro não contém texto de narração.")
    return texto


_FIM_FRASE = re.compile(r"(?<=[.!?…])[\"”’)]*\s+")


def dividir_frases(texto: str) -> tuple[list[str], list[Frase]]:
    """Divide em frases; devolve (palavras, frases) com índices de palavras."""
    palavras: list[str] = []
    frases: list[Frase] = []
    for p_idx, paragrafo in enumerate(l.strip() for l in texto.splitlines()):
        if not paragrafo:
            continue
        # "João 1:1." não deve ser quebrado em "João 1:" + "1.": só quebramos
        # depois de .!?… seguidos de espaço.
        for pedaco in _FIM_FRASE.split(paragrafo):
            pedaco = pedaco.strip()
            if not pedaco:
                continue
            tokens = tokenizar(pedaco)
            if not tokens:
                continue
            ini = len(palavras)
            palavras.extend(tokens)
            frases.append(Frase(len(frases), pedaco, ini, len(palavras), p_idx))
    if not palavras:
        raise ErroRoteiro("Nenhuma palavra encontrada no roteiro.")
    return palavras, frases


# ------------------------------------------------------------ transcrição ---

_TEMPO = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})")


def _segundos(trecho: str) -> float:
    m = _TEMPO.fullmatch(trecho.strip())
    if not m:
        raise ErroRoteiro(f"Tempo inválido na transcrição: {trecho!r}")
    h, mi, s, ms = m.groups()
    return int(h or 0) * 3600 + int(mi) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def parse_transcricao(texto: str) -> list[Cue]:
    """Lê VTT ou SRT (tempos mm:ss.mmm, hh:mm:ss.mmm ou com vírgula)."""
    cues: list[Cue] = []
    linhas = texto.replace("\r\n", "\n").replace("﻿", "").split("\n")
    i = 0
    while i < len(linhas):
        if "-->" in linhas[i]:
            esq, dir_ = linhas[i].split("-->", 1)
            dir_ = dir_.strip().split()[0]
            ini, fim = _segundos(esq), _segundos(dir_)
            corpo: list[str] = []
            i += 1
            while i < len(linhas) and linhas[i].strip():
                corpo.append(linhas[i].strip())
                i += 1
            conteudo = " ".join(corpo).strip()
            if conteudo and fim >= ini:
                cues.append(Cue(ini, fim, conteudo))
        else:
            i += 1
    if not cues:
        raise ErroRoteiro("Nenhum cue com tempo foi encontrado na transcrição.")
    for a, b in zip(cues, cues[1:]):
        if b.ini + 1e-6 < a.ini:
            raise ErroRoteiro(f"Transcrição fora de ordem perto de {b.ini:.2f}s.")
    return cues


# ---------------------------------------------------------------- alinhar ---

def _palavras_da_transcricao(cues: list[Cue]):
    norm, t_ini, t_fim = [], [], []
    for cue in cues:
        tokens = [normalizar(p) for p in cue.texto.split()]
        tokens = [t for t in tokens if t]
        n = len(tokens)
        for k, tok in enumerate(tokens):
            norm.append(tok)
            t_ini.append(cue.ini + (cue.fim - cue.ini) * k / n)
            t_fim.append(cue.ini + (cue.fim - cue.ini) * (k + 1) / n)
    return norm, t_ini, t_fim


def alinhar(texto_narracao: str, cues: list[Cue], min_lacuna: int = 8) -> Alinhamento:
    palavras, frases = dividir_frases(texto_narracao)
    norm_r = [normalizar(p) for p in palavras]
    norm_t, ti_t, tf_t = _palavras_da_transcricao(cues)
    if not norm_t:
        raise ErroRoteiro("A transcrição não contém palavras.")

    casador = SequenceMatcher(None, norm_r, norm_t, autojunk=False)
    n = len(palavras)
    t_ini: list[float | None] = [None] * n
    t_fim: list[float | None] = [None] * n
    reconhecida = [False] * n
    for a, b, tam in casador.get_matching_blocks():
        for k in range(tam):
            t_ini[a + k] = ti_t[b + k]
            t_fim[a + k] = tf_t[b + k]
            reconhecida[a + k] = True

    fim_total = cues[-1].fim
    _interpolar(palavras, t_ini, t_fim, fim_total)
    al = Alinhamento(
        palavras=palavras, normalizadas=norm_r,
        t_ini=[float(x) for x in t_ini], t_fim=[float(x) for x in t_fim],
        reconhecida=reconhecida, frases=frases, duracao_transcricao=fim_total,
    )
    al.lacunas = _lacunas(al, min_lacuna)
    return al


def _interpolar(palavras, t_ini, t_fim, fim_total):
    """Preenche palavras sem correspondência proporcionalmente ao nº de letras."""
    n = len(palavras)
    i = 0
    while i < n:
        if t_ini[i] is not None:
            i += 1
            continue
        j = i
        while j < n and t_ini[j] is None:
            j += 1
        inicio = t_fim[i - 1] if i > 0 else 0.0
        fim = t_ini[j] if j < n else fim_total
        if fim < inicio:
            fim = inicio
        pesos = [max(1, len(normalizar(palavras[k]))) for k in range(i, j)]
        total = sum(pesos)
        acc = 0
        for k, peso in zip(range(i, j), pesos):
            t_ini[k] = inicio + (fim - inicio) * acc / total
            acc += peso
            t_fim[k] = inicio + (fim - inicio) * acc / total
        i = j


def _lacunas(al: Alinhamento, minimo: int) -> list[dict]:
    lacunas = []
    n = len(al.palavras)
    i = 0
    while i < n:
        if al.reconhecida[i]:
            i += 1
            continue
        j = i
        while j < n and not al.reconhecida[j]:
            j += 1
        if j - i >= minimo:
            dur = al.t_fim[j - 1] - al.t_ini[i]
            palavras_por_s = (j - i) / dur if dur > 0 else float("inf")
            lacunas.append({
                "palavra_ini": i, "palavra_fim": j, "palavras": j - i,
                "t_ini": round(al.t_ini[i], 3), "t_fim": round(al.t_fim[j - 1], 3),
                "palavras_por_segundo": round(palavras_por_s, 2),
                # fala natural ~2,5 a 3 palavras/s; muito acima disso, o trecho
                # provavelmente não foi narrado (ou não foi transcrito).
                "suspeita_nao_narrado": palavras_por_s > 4.5,
                "texto": " ".join(al.palavras[i:min(j, i + 14)]) + (" …" if j - i > 14 else ""),
            })
        i = j
    return lacunas


# -------------------------------------------------------- busca de âncoras ---

def localizar_ancora(al: Alinhamento, ancora: str, a_partir_de: int = 0) -> int:
    """Índice da palavra do roteiro onde `ancora` (frase) começa, após `a_partir_de`."""
    alvo = [normalizar(p) for p in ancora.split()]
    alvo = [t for t in alvo if t]
    if not alvo:
        raise ErroRoteiro("Âncora vazia.")
    m = len(alvo)
    for i in range(max(0, a_partir_de), len(al.normalizadas) - m + 1):
        if al.normalizadas[i:i + m] == alvo:
            return i
    raise ErroRoteiro(f"Âncora não encontrada no roteiro (após a palavra {a_partir_de}): {ancora!r}")


def tempo_confiavel(al: Alinhamento, palavra_idx: int, janela: int = 4) -> tuple[float, bool]:
    """Tempo de início da palavra; `True` se houver palavras reconhecidas perto dela.

    Se a âncora cair numa lacuna (trecho não reconhecido), devolve o tempo da
    próxima palavra reconhecida e `False`.
    """
    fim = min(len(al.palavras), palavra_idx + janela)
    if sum(al.reconhecida[palavra_idx:fim]) >= max(1, (fim - palavra_idx) // 2):
        return al.t_ini[palavra_idx], True
    for k in range(palavra_idx, len(al.palavras)):
        if al.reconhecida[k]:
            return al.t_ini[k], False
    return al.duracao_transcricao, False


def texto_entre(al: Alinhamento, t_ini: float, t_fim: float) -> str:
    """Texto do roteiro cujas palavras começam em [t_ini, t_fim)."""
    ini = next((i for i, t in enumerate(al.t_ini) if t >= t_ini - 1e-6), len(al.palavras))
    fim = next((i for i, t in enumerate(al.t_ini) if t >= t_fim - 1e-6), len(al.palavras))
    return " ".join(al.palavras[ini:fim])


def alinhar_proporcional(texto_narracao: str, duracao: float) -> Alinhamento:
    """ÚLTIMO RECURSO (sem transcrição): distribui as palavras pela duração, proporcionalmente às letras.

    É uma estimativa, não um alinhamento real: ignora pausas e variações de ritmo. O relatório
    registra que a sincronia cena/narração é aproximada nesse modo.
    """
    palavras, frases = dividir_frases(texto_narracao)
    pesos = [max(1, len(normalizar(p))) + 1 for p in palavras]
    total = sum(pesos)
    t_ini, t_fim, acc = [], [], 0
    for p in pesos:
        t_ini.append(duracao * acc / total)
        acc += p
        t_fim.append(duracao * acc / total)
    return Alinhamento(
        palavras=palavras, normalizadas=[normalizar(p) for p in palavras], t_ini=t_ini, t_fim=t_fim,
        reconhecida=[False] * len(palavras), frases=frases, duracao_transcricao=duracao,
        lacunas=[{"palavra_ini": 0, "palavra_fim": len(palavras), "palavras": len(palavras), "t_ini": 0.0,
                  "t_fim": duracao, "palavras_por_segundo": round(len(palavras) / duracao, 2),
                  "suspeita_nao_narrado": False, "texto": "(tempos estimados proporcionalmente: sem transcrição)"}],
    )
