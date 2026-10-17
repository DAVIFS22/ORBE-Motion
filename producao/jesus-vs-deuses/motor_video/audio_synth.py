"""Síntese de ambiências, efeitos e trilha por código (NumPy).

Tudo aqui é *ambientação cinematográfica sintetizada*: vento, graves, impactos,
whooshes, notas de piano e pads. Nada é apresentado como gravação histórica
de civilizações antigas nem como som do acontecimento bíblico. Arquivos
licenciados fornecidos pelo usuário têm prioridade (ver audio_mixer).

Convenção: funções devolvem float32 (n, 2) normalizado em pico 1.0 (efeitos)
ou RMS ~0.1 (ambiências/trilha); o mixer aplica os ganhos em dB.
"""

from __future__ import annotations

import math

import numpy as np

SR = 48000


# ------------------------------------------------------------ utilidades ---

def midi(n: float) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


NOTAS = {nome: 12 * (o + 1) + i for o in range(0, 8) for i, nome in
         [(0, f"C{o}"), (1, f"C#{o}"), (2, f"D{o}"), (3, f"D#{o}"), (4, f"E{o}"), (5, f"F{o}"),
          (6, f"F#{o}"), (7, f"G{o}"), (8, f"G#{o}"), (9, f"A{o}"), (10, f"A#{o}"), (11, f"B{o}")]}


def f(nome: str) -> float:
    return midi(NOTAS[nome])


def _rng(semente: int) -> np.random.Generator:
    return np.random.default_rng(semente)


def _estereo(m: np.ndarray) -> np.ndarray:
    return np.stack([m, m], axis=1).astype(np.float32)


def _normalizar_pico(x: np.ndarray, pico: float = 1.0) -> np.ndarray:
    m = float(np.abs(x).max())
    return (x * (pico / m)).astype(np.float32) if m > 0 else x.astype(np.float32)


def _normalizar_rms(x: np.ndarray, rms: float = 0.1) -> np.ndarray:
    r = float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))
    return (x * (rms / r)).astype(np.float32) if r > 0 else x.astype(np.float32)


def fade(x: np.ndarray, entrada: float, saida: float) -> np.ndarray:
    n = len(x)
    g = np.ones(n, np.float32)
    ne, ns = min(n, int(entrada * SR)), min(n, int(saida * SR))
    if ne > 0:
        g[:ne] = np.sin(np.linspace(0, math.pi / 2, ne, dtype=np.float32)) ** 2
    if ns > 0:
        g[n - ns:] *= np.cos(np.linspace(0, math.pi / 2, ns, dtype=np.float32)) ** 2
    return x * (g[:, None] if x.ndim == 2 else g)


def _ruido_banda(n: int, f_lo: float, f_hi: float, rng, ordem: int = 2) -> np.ndarray:
    """Ruído passa-banda por FFT em blocos com sobreposição (sqrt-Hann): sem emendas."""
    bloco = 1 << 17
    salto = bloco // 2
    janela = np.sqrt(np.hanning(bloco + 1)[:-1]).astype(np.float32)
    freqs = np.fft.rfftfreq(bloco, 1 / SR)
    with np.errstate(divide="ignore", invalid="ignore"):
        h = 1.0 / np.sqrt(1 + (max(f_lo, 1e-3) / np.maximum(freqs, 1e-3)) ** (2 * ordem))
        h *= 1.0 / np.sqrt(1 + (freqs / f_hi) ** (2 * ordem))
    h[0] = 0
    saida = np.zeros(n + bloco, np.float32)
    for ini in range(0, n + salto, salto):
        ruido = rng.standard_normal(bloco).astype(np.float32)
        bl = np.fft.irfft(np.fft.rfft(ruido) * h, bloco).astype(np.float32) * janela
        fim = min(ini + bloco, len(saida))
        saida[ini:fim] += bl[: fim - ini]
    out = saida[:n]
    s = out.std()
    return out / s if s > 0 else out


def _modulacao(n: int, freq: float, rng, profundidade: float = 0.5) -> np.ndarray:
    """Modulação lenta e aleatória em [1-prof, 1] (pontos de controle suavizados; barata)."""
    passo = max(1, int(SR / max(freq, 1e-3) / 2))
    pontos = rng.random(n // passo + 3).astype(np.float32)
    x = np.arange(n, dtype=np.float32) / passo
    i = x.astype(np.int64)
    f = x - i
    f = f * f * (3 - 2 * f)
    m = pontos[i] * (1 - f) + pontos[i + 1] * f
    m = (m - m.min()) / max(m.max() - m.min(), 1e-6)
    return ((1 - profundidade) + profundidade * m).astype(np.float32)


def _alocar(dur: float) -> int:
    return max(1, int(round(dur * SR)))


# ---------------------------------------------------------------- ambiências ---

def vento(dur: float, intensidade: float = 0.5, semente: int = 1, brilho: float = 1.0, rampa: tuple[float, float] | None = None):
    """Vento suave/profundo; `rampa=(a,b)` varia a intensidade ao longo da duração."""
    n = _alocar(dur)
    saida = np.zeros((n, 2), np.float32)
    rng = _rng(semente * 10)
    corpo = _ruido_banda(n, 90, 700 * brilho, rng, 2)
    ar = _ruido_banda(n, 500, 2600 * brilho, rng, 2) * 0.35
    raj = _modulacao(n, 0.18, rng, 0.65) ** 1.4
    mono = (corpo + ar * raj) * raj
    saida[:, 0] = mono
    saida[:, 1] = np.roll(mono, 531) * _modulacao(n, 0.11, rng, 0.2)  # canal R defasado: decorrelação barata
    saida = _normalizar_rms(saida, 0.1)
    g = np.full(n, intensidade, np.float32)
    if rampa:
        g = np.linspace(rampa[0], rampa[1], n, dtype=np.float32)
    return (saida * g[:, None]).astype(np.float32)


def grave(dur: float, nota: str = "E1", semente: int = 2, batimento: float = 0.12):
    """Grave atmosférico: dois senos próximos (batimento lento) + quinta, com swell."""
    n = _alocar(dur)
    t = np.arange(n, dtype=np.float32) / SR
    f0 = f(nota)
    rng = _rng(semente)
    sw = _modulacao(n, 0.07, rng, 0.45)
    x = (np.sin(2 * math.pi * f0 * t) + np.sin(2 * math.pi * (f0 * 1.0 + batimento) * t + 0.7)
         + 0.45 * np.sin(2 * math.pi * f0 * 1.5 * t + 1.9) + 0.18 * np.sin(2 * math.pi * f0 * 2 * t)) * sw
    return _normalizar_rms(_estereo(x), 0.1)


def ressonancia_templo(dur: float, semente: int = 3):
    """Ressonâncias distantes e raras (tons graves com cauda longa); ambientação, não gravação."""
    n = _alocar(dur)
    saida = np.zeros((n, 2), np.float32)
    rng = _rng(semente)
    t_evento = 2.0
    base = [f("E2"), f("B2"), f("G2"), f("D3")]
    while t_evento < dur - 4:
        fr = base[int(rng.integers(0, len(base)))]
        ln = _alocar(min(7.0, dur - t_evento))
        t = np.arange(ln, dtype=np.float32) / SR
        x = (np.sin(2 * math.pi * fr * t) + 0.4 * np.sin(2 * math.pi * fr * 2.01 * t) + 0.2 * np.sin(2 * math.pi * fr * 3.02 * t))
        x *= np.exp(-t / 2.2) * (1 - np.exp(-t / 0.35))
        i = int(t_evento * SR)
        pan = rng.uniform(0.3, 0.7)
        saida[i:i + ln, 0] += x * pan
        saida[i:i + ln, 1] += x * (1 - pan)
        t_evento += rng.uniform(7, 14)
    return _normalizar_rms(saida, 0.1) if saida.any() else saida


def passaros(dur: float, semente: int = 4, densidade: float = 0.12):
    """Cantos de passaros estilizados (chilros curtos), raros e discretos."""
    n = _alocar(dur)
    saida = np.zeros((n, 2), np.float32)
    rng = _rng(semente)
    t_evento = rng.uniform(2, 6)
    while t_evento < dur - 1:
        base = rng.uniform(2400, 4200)
        for k in range(int(rng.integers(2, 5))):
            ln = _alocar(0.09)
            t = np.arange(ln, dtype=np.float32) / SR
            fr = base * (1 + 0.25 * np.sin(2 * math.pi * 14 * t) + 0.35 * t / 0.09)
            x = np.sin(2 * math.pi * np.cumsum(fr) / SR) * np.hanning(ln)
            i = int((t_evento + k * 0.14) * SR)
            if i + ln < n:
                pan = rng.uniform(0.2, 0.8)
                saida[i:i + ln, 0] += x * pan
                saida[i:i + ln, 1] += x * (1 - pan)
        t_evento += rng.uniform(1 / densidade * 0.6, 1 / densidade * 1.6)
    return _normalizar_pico(saida, 1.0) if saida.any() else saida


def aldeia(dur: float, semente: int = 5):
    base = vento(dur, 0.8, semente, brilho=0.8)
    return (base * 0.9 + passaros(dur, semente) * 0.12).astype(np.float32)


def natureza_discreta(dur: float, semente: int = 6):
    return (vento(dur, 0.55, semente, brilho=1.1) * 0.9 + passaros(dur, semente + 1, 0.07) * 0.08).astype(np.float32)


BEDS = {
    "vento_profundo": lambda d, s: vento(d, 0.7, s, brilho=0.7),
    "vento_suave": lambda d, s: vento(d, 0.5, s, brilho=0.9),
    "vento_ruinas": lambda d, s: vento(d, 0.6, s, brilho=1.3),
    "vento_deserto": lambda d, s: vento(d, 0.6, s, brilho=1.5),
    "vento_crescente": lambda d, s: vento(d, 0.5, s, brilho=1.1, rampa=(0.35, 1.0)),
    "ambiencia_templo": lambda d, s: grave(d, "A1", s, 0.08) * 0.8 + vento(d, 0.25, s, brilho=0.5) * 0.6,
    "ressonancia_templo": lambda d, s: ressonancia_templo(d, s),
    "grave_atmosferico": lambda d, s: grave(d, "E1", s),
    "grave_sutil": lambda d, s: grave(d, "D1", s, 0.09),
    "aldeia": lambda d, s: aldeia(d, s),
    "natureza_discreta": lambda d, s: natureza_discreta(d, s),
}


def ambiencia(nome: str, dur: float, semente: int = 1) -> np.ndarray:
    if nome not in BEDS:
        raise KeyError(f"Ambiência desconhecida: {nome}")
    return BEDS[nome](dur, semente).astype(np.float32)


# ------------------------------------------------------------------ efeitos ---

def impacto(variante: int = 0, com_preludio: bool = True) -> np.ndarray:
    """Impacto grave e suave (sub + corpo), com curto prelúdio opcional.

    O ponto de impacto fica em `PRELUDIO_S` segundos do início do arquivo.
    """
    rng = _rng(100 + variante)
    pre = PRELUDIO_S if com_preludio else 0.0
    dur = pre + 3.4
    n = _alocar(dur)
    t = np.arange(n, dtype=np.float32) / SR
    ti = t - pre
    f_ini, f_fim = [(62, 38), (55, 34), (70, 42), (48, 30)][variante % 4]
    fr = f_fim + (f_ini - f_fim) * np.exp(-np.maximum(ti, 0) / 0.18)
    fase = 2 * math.pi * np.cumsum(fr) / SR
    corpo = np.sin(fase) * np.exp(-np.maximum(ti, 0) / (0.9 + 0.15 * (variante % 3))) * (ti >= 0)
    ruido = _ruido_banda(n, 50, 380, rng, 2) * np.exp(-np.maximum(ti, 0) / 0.22) * (ti >= 0) * 0.55
    x = corpo + ruido
    if com_preludio:
        sw = _ruido_banda(n, 150, 900, rng, 2) * ((t / pre) ** 2.5) * (t < pre) * 0.18
        x = x + sw
    x = x * (1 - np.exp(-t / 0.004))
    return _estereo(_normalizar_pico(x, 1.0))


PRELUDIO_S = 0.7


def whoosh(variante: int = 0) -> np.ndarray:
    """Passagem de ar discreta; as variantes mudam direção, duração e timbre."""
    rng = _rng(200 + variante)
    dur = [1.1, 1.4, 0.9, 1.25][variante % 4]
    n = _alocar(dur)
    saida = np.zeros((n, 2), np.float32)
    sobe = variante % 2 == 0
    base = [_ruido_banda(n, 180, 3600, rng, 2) for _ in range(2)]
    t = np.linspace(0, 1, n, dtype=np.float32)
    # a "cor" varre o espectro: mistura ruído grave e agudo com pesos que variam no tempo
    grave_ = _ruido_banda(n, 120, 700, rng, 2)
    agudo = _ruido_banda(n, 1400, 5200, rng, 2)
    peso = t if sobe else 1 - t
    env = np.abs(np.sin(math.pi * t)) ** 2.2
    for c in range(2):
        x = (grave_ * (1 - peso) + agudo * peso * 0.8 + base[c] * 0.3) * env
        saida[:, c] = x
    saida[:, 0] *= 0.9 if sobe else 1.0
    saida[:, 1] *= 1.0 if sobe else 0.9
    return _normalizar_pico(saida, 1.0)


def nota_piano(freq: float, dur: float = 4.5, brilho: float = 1.0, semente: int = 0) -> np.ndarray:
    """Nota de piano sintetizada (parciais com leve inarmonicidade e decaimentos distintos)."""
    n = _alocar(dur)
    t = np.arange(n, dtype=np.float32) / SR
    x = np.zeros(n, np.float32)
    B = 0.00035
    for k in range(1, 11):
        fk = freq * k * math.sqrt(1 + B * k * k)
        if fk > 9000:
            break
        amp = (1.0 / k ** 1.15) * (brilho ** (k - 1))
        tau = 2.6 / (1 + 0.55 * (k - 1))
        x += amp * np.sin(2 * math.pi * fk * t + k) * np.exp(-t / tau)
    ataque = 1 - np.exp(-t / 0.004)
    rng = _rng(300 + semente)
    martelo = _ruido_banda(n, 500, 3000, rng, 2) * np.exp(-t / 0.02) * 0.05
    x = (x * ataque + martelo) * np.minimum(1.0, (dur - t) / 0.5)
    return _estereo(_normalizar_pico(x, 1.0))


def nota_destaque(variante: int = 0) -> np.ndarray:
    """Nota sutil para destacar uma passagem (João 1:1, Colossenses 1...): quinta aberta em piano suave."""
    pares = [("D4", "A4"), ("A3", "E4"), ("F#3", "C#4"), ("G3", "D4")]
    a, b = pares[variante % len(pares)]
    n1, n2 = nota_piano(f(a), 5.0, 0.85, variante), nota_piano(f(b), 5.0, 0.8, variante + 1)
    saida = np.zeros((max(len(n1), len(n2) + int(0.18 * SR)), 2), np.float32)
    saida[: len(n1)] += n1
    saida[int(0.18 * SR): int(0.18 * SR) + len(n2)] += n2 * 0.7
    return _normalizar_pico(saida, 1.0)


def passos(dur: float, semente: int = 7, intervalo: float = 0.62) -> np.ndarray:
    """Passos discretos em piso de pedra (ambientação estilizada)."""
    n = _alocar(dur)
    saida = np.zeros((n, 2), np.float32)
    rng = _rng(semente)
    t_passo = 0.0
    lado = 0
    while t_passo < dur - 0.3:
        ln = _alocar(0.22)
        t = np.arange(ln, dtype=np.float32) / SR
        ruido = _ruido_banda(ln, 140, 1100, rng, 2) * np.exp(-t / 0.045)
        toque = np.sin(2 * math.pi * rng.uniform(80, 120) * t) * np.exp(-t / 0.05)
        x = (ruido * 0.7 + toque * 0.9) * rng.uniform(0.75, 1.0)
        i = int(t_passo * SR)
        pan = 0.35 if lado == 0 else 0.65
        ln_ef = min(ln, n - i)
        saida[i:i + ln_ef, 0] += x[:ln_ef] * (1 - pan)
        saida[i:i + ln_ef, 1] += x[:ln_ef] * pan
        t_passo += intervalo * rng.uniform(0.9, 1.12)
        lado ^= 1
    return _normalizar_pico(saida, 1.0)


def tecido(semente: int = 8) -> np.ndarray:
    rng = _rng(semente)
    n = _alocar(0.9)
    t = np.linspace(0, 1, n, dtype=np.float32)
    x = _ruido_banda(n, 1800, 7000, rng, 2) * np.sin(math.pi * t) ** 2 * _modulacao(n, 9, rng, 0.6)
    return _normalizar_pico(_estereo(x), 1.0)


def pergaminho(semente: int = 9) -> np.ndarray:
    rng = _rng(semente)
    n = _alocar(0.9)
    t = np.linspace(0, 1, n, dtype=np.float32)
    x = _ruido_banda(n, 1200, 6500, rng, 2) * np.sin(math.pi * t) ** 3 * 0.5
    for _ in range(14):
        i = int(rng.uniform(0.05, 0.85) * n)
        ln = int(0.004 * SR)
        x[i:i + ln] += rng.uniform(0.4, 1.0) * np.hanning(ln) * rng.choice([-1, 1])
    return _normalizar_pico(_estereo(x), 1.0)


# ----------------------------------------------------------------- trilha ---

def _pad_segmento(freqs: list[float], dur: float, rng, timbre: str = "pad", brilho: float = 1.0,
                  vibrato: float = 0.0) -> np.ndarray:
    n = _alocar(dur)
    t = np.arange(n, dtype=np.float32) / SR
    saida = np.zeros((n, 2), np.float32)
    vib = 1 + vibrato * np.sin(2 * math.pi * 5.1 * t + rng.uniform(0, 6)) if vibrato else 1.0
    for fr in freqs:
        for voz, desafino in enumerate([-0.0018, 0.0, 0.0021]):
            fase0 = rng.uniform(0, 2 * math.pi)
            pan = 0.5 + (voz - 1) * 0.28
            f_voz = fr * (1 + desafino)
            x = np.zeros(n, np.float32)
            if timbre == "pad":
                parciais = [(1, 1.0), (2, 0.35 * brilho), (3, 0.14 * brilho), (4, 0.06 * brilho)]
            elif timbre == "cordas":
                parciais = [(k, 1.0 / k ** 0.95 * (brilho ** (k - 1))) for k in range(1, 11)]
            else:  # coro: formantes de "ah" (≈ 700 e 1150 Hz)
                parciais = []
                for k in range(1, 14):
                    fk = f_voz * k
                    amp = 1.0 / k ** 0.8 * (math.exp(-((fk - 700) / 260) ** 2) + 0.55 * math.exp(-((fk - 1150) / 300) ** 2) + 0.05)
                    parciais.append((k, amp))
            for k, amp in parciais:
                if f_voz * k > 12000:
                    break
                ph = 2 * math.pi * np.cumsum(f_voz * k * vib) / SR if vibrato else 2 * math.pi * f_voz * k * t
                x += amp * np.sin(ph + fase0 * k)
            saida[:, 0] += x * (1 - pan)
            saida[:, 1] += x * pan
    return saida


CLIMAS = {
    # progressão: lista de acordes (notas), troca em segundos, timbre, brilho, vibrato
    "misterio": dict(acordes=[["D2", "A2", "D3", "F3"], ["A#1", "F2", "A#2", "D3"], ["G1", "D2", "G2", "A#2"], ["A1", "E2", "A2", "C#3"]],
                     troca=16, timbre="pad", brilho=0.8, vibrato=0.0, nivel_db=0.0),
    "civilizacoes": dict(acordes=[["D2", "A2", "D3", "D#3"], ["A1", "E2", "A2", "A#2"], ["G1", "D2", "G2", "G#2"], ["D2", "A2", "C3", "D3"]],
                         troca=18, timbre="pad", brilho=0.9, vibrato=0.0, nivel_db=-1.0),
    "identidade": dict(acordes=[["D3", "F#3", "A3", "E4"], ["B2", "F#3", "B3", "D4"], ["G2", "D3", "G3", "B3"], ["A2", "E3", "A3", "C#4"]],
                       troca=14, timbre="pad", brilho=1.2, vibrato=0.0, nivel_db=-1.0),
    "contemplativa": dict(acordes=[["C3", "G3", "D4", "E4"], ["A2", "E3", "A3", "C4"], ["F2", "C3", "F3", "G3"], ["G2", "D3", "G3", "B3"]],
                          troca=16, timbre="pad", brilho=0.9, vibrato=0.0, nivel_db=-3.0),
    "morte": dict(acordes=[["E1", "B1", "E2", "C3"], ["E1", "B1", "F#2", "C3"], ["D1", "A1", "D2", "A#2"]],
                  troca=20, timbre="pad", brilho=0.6, vibrato=0.0, nivel_db=-2.0),
    "crucificacao": dict(acordes=[["D2", "A2", "D3", "D#3"], ["A#1", "F2", "A#2", "B2"], ["D2", "A2", "C3", "D#3"]],
                         troca=18, timbre="cordas", brilho=0.55, vibrato=0.0025, nivel_db=-3.0),
    "ressurreicao": dict(acordes=[["D3", "A3", "F#4", "D5"], ["G2", "D3", "B3", "G4"], ["A2", "E3", "C#4", "A4"], ["D3", "A3", "F#4", "A4"]],
                         troca=12, timbre="cordas+coro", brilho=0.7, vibrato=0.003, nivel_db=0.0),
    "comparacao": dict(acordes=[["D2", "A2", "D3", "F3"], ["A#1", "F2", "A#2", "D3"], ["F2", "C3", "F3", "A3"], ["A1", "E2", "A2", "C#3"]],
                       troca=12, timbre="cordas", brilho=0.6, vibrato=0.002, nivel_db=-1.0),
    "encerramento": dict(acordes=[["D3", "A3", "E4", "F#4"], ["G2", "D3", "A3", "B3"], ["B2", "F#3", "B3", "D4"], ["A2", "E3", "A3", "C#4"]],
                         troca=14, timbre="pad", brilho=1.0, vibrato=0.0, nivel_db=-3.0),
}


def segmento_musica(clima: str, indice: int, dur: float, semente: int = 1) -> np.ndarray:
    """Segmento de `dur` s do acorde `indice` da progressão do clima (RMS ~0.1)."""
    c = CLIMAS[clima]
    acorde = [f(n) for n in c["acordes"][indice % len(c["acordes"])]]
    rng = _rng(semente * 977 + indice)
    timbre = c["timbre"]
    if timbre == "cordas+coro":
        x = _pad_segmento(acorde, dur, rng, "cordas", c["brilho"], c["vibrato"]) * 0.7 + \
            _pad_segmento(acorde[1:], dur, rng, "coro", 1.0, 0.0025) * 0.55
    else:
        x = _pad_segmento(acorde, dur, rng, timbre, c["brilho"], c["vibrato"])
    # respiração lenta de volume
    n = len(x)
    x = x * (_modulacao(n, 0.09, rng, 0.25))[:, None]
    return _normalizar_rms(x, 0.1)


def arpejo_piano(dur: float, semente: int = 1, densidade: float = 0.22) -> np.ndarray:
    """Notas esparsas de piano (pentatônica de Ré maior) para o encerramento."""
    n = _alocar(dur)
    saida = np.zeros((n, 2), np.float32)
    rng = _rng(500 + semente)
    notas = ["D4", "E4", "F#4", "A4", "B4", "D5", "A3", "F#3"]
    t_evento = 0.5
    while t_evento < dur - 1:
        nt = nota_piano(f(notas[int(rng.integers(0, len(notas)))]), 5.0, 0.8, int(rng.integers(0, 50)))
        i = int(t_evento * SR)
        ln = min(len(nt), n - i)
        saida[i:i + ln] += nt[:ln] * rng.uniform(0.55, 1.0)
        t_evento += rng.uniform(1 / densidade * 0.7, 1 / densidade * 1.5)
    return saida
