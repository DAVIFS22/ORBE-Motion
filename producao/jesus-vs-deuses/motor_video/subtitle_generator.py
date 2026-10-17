"""Legendas SRT a partir do roteiro (texto correto) e do alinhamento com a transcrição (tempos reais).

Os tempos vêm da transcrição com timestamps (início/fim de cada trecho); dentro de
um trecho, os tempos das palavras são interpolados. Palavras do roteiro sem
correspondência na transcrição não recebem tempo inventado: se um trecho inteiro
não tem tempo (duração nula), ele fica sem legenda e é reportado.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .script_analyzer import Alinhamento

MAX_CARACTERES_LINHA = 42
MAX_LINHAS = 2
MAX_DURACAO = 6.5
MIN_DURACAO = 1.0
FOLGA = 0.04  # intervalo mínimo entre legendas consecutivas


@dataclass
class Legenda:
    ini: float
    fim: float
    texto: str  # com quebra de linha


def _fmt(t: float) -> str:
    t = max(0.0, t)
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _quebrar_linhas(texto: str) -> str:
    if len(texto) <= MAX_CARACTERES_LINHA:
        return texto
    meio = len(texto) / 2
    espacos = [m.start() for m in re.finditer(" ", texto)]
    corte = min(espacos, key=lambda i: abs(i - meio))
    return texto[:corte] + "\n" + texto[corte + 1:]


def gerar(al: Alinhamento, duracao_audio: float, avisos: list[str] | None = None) -> list[Legenda]:
    avisos = avisos if avisos is not None else []
    blocos: list[tuple[int, int]] = []  # (palavra_ini, palavra_fim)
    limite = MAX_CARACTERES_LINHA * MAX_LINHAS
    for fr in al.frases:
        ini = fr.palavra_ini
        cursor = ini
        chars = 0
        for w in range(fr.palavra_ini, fr.palavra_fim):
            tam = len(al.palavras[w]) + 1
            dur_atual = al.t_fim[w] - al.t_ini[ini]
            estourou = chars + tam > limite or dur_atual > MAX_DURACAO
            if estourou and w > ini:
                # prefere quebrar na última vírgula/ponto-e-vírgula do bloco, se houver
                corte = w
                for k in range(w - 1, ini + 2, -1):
                    if al.palavras[k].endswith((",", ";", ":")) and (k + 1 - ini) >= 3:
                        corte = k + 1
                        break
                blocos.append((ini, corte))
                ini = corte
                chars = sum(len(al.palavras[x]) + 1 for x in range(ini, w))
            chars += tam
        blocos.append((ini, fr.palavra_fim))

    legendas: list[Legenda] = []
    for a, b in blocos:
        ini, fim = al.t_ini[a], al.t_fim[b - 1]
        texto = " ".join(al.palavras[a:b])
        if fim - ini < 0.2:
            avisos.append(f"Sem legenda (sem tempo na transcrição): {texto[:70]!r}")
            continue
        legendas.append(Legenda(ini, fim, _quebrar_linhas(texto)))

    # ajustes de duração mínima e ausência de sobreposição
    for i, lg in enumerate(legendas):
        proximo = legendas[i + 1].ini if i + 1 < len(legendas) else duracao_audio
        if lg.fim - lg.ini < MIN_DURACAO:
            lg.fim = min(lg.ini + MIN_DURACAO, proximo - FOLGA)
        lg.fim = min(lg.fim, proximo - FOLGA, duracao_audio)
        if lg.fim <= lg.ini:
            lg.fim = min(lg.ini + 0.3, duracao_audio)
    return [lg for lg in legendas if lg.fim > lg.ini]


def escrever_srt(legendas: list[Legenda], caminho: Path) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    partes = [f"{i}\n{_fmt(lg.ini)} --> {_fmt(lg.fim)}\n{lg.texto}\n" for i, lg in enumerate(legendas, 1)]
    caminho.write_text("\n".join(partes), encoding="utf-8")
    return caminho


def ler_srt(caminho: Path) -> list[Legenda]:
    texto = caminho.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
    saida = []
    for bloco in re.split(r"\n\n+", texto):
        linhas = bloco.split("\n")
        if len(linhas) < 3:
            continue
        m = re.match(r"(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)", linhas[1])
        if not m:
            continue
        v = list(map(int, m.groups()))
        saida.append(Legenda(v[0] * 3600 + v[1] * 60 + v[2] + v[3] / 1000, v[4] * 3600 + v[5] * 60 + v[6] + v[7] / 1000,
                             "\n".join(linhas[2:])))
    return saida


def validar(legendas: list[Legenda], duracao: float) -> list[str]:
    """Problemas encontrados (lista vazia = ok)."""
    erros = []
    for i, lg in enumerate(legendas):
        if lg.fim <= lg.ini:
            erros.append(f"legenda {i + 1}: fim <= início")
        if lg.fim > duracao + 0.05:
            erros.append(f"legenda {i + 1}: termina depois do áudio ({lg.fim:.2f}s)")
        if i and lg.ini < legendas[i - 1].fim - 1e-6:
            erros.append(f"legenda {i + 1}: sobrepõe a anterior")
        if any(len(l) > MAX_CARACTERES_LINHA + 6 for l in lg.texto.split("\n")) or lg.texto.count("\n") >= MAX_LINHAS:
            erros.append(f"legenda {i + 1}: linhas longas demais")
    return erros
