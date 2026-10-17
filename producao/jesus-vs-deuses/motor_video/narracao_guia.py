"""Narração-guia SINTÉTICA para testes. NÃO É NARRAÇÃO.

Gera ruído com envelope silábico apenas nos intervalos de fala da transcrição (VTT/SRT), para
exercitar o ducking, a mixagem e a verificação de sincronia quando o áudio real da narração não
está disponível. Nunca deve ser usada na produção final.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from . import audio_synth as syn
from .config import ErroProducao
from .script_analyzer import Cue

SR = 48000


def gerar(cues: list[Cue], duracao: float, destino: Path, nivel_db: float = -22.0) -> Path:
    n = int(duracao * SR)
    rng = np.random.default_rng(42)
    x = syn._ruido_banda(n, 250, 3200, rng, 2) * 0.1
    t = np.arange(n, dtype=np.float32) / SR
    silabas = 0.55 + 0.45 * np.sin(2 * np.pi * 4.3 * t) ** 2 * (0.7 + 0.3 * np.sin(2 * np.pi * 0.9 * t + 1))
    env = np.zeros(n, np.float32)
    for c in cues:
        a, b = int(c.ini * SR), min(n, int(c.fim * SR))
        if b > a:
            ramp = min(int(0.03 * SR), (b - a) // 2)
            seg = np.ones(b - a, np.float32)
            if ramp:
                seg[:ramp] = np.linspace(0, 1, ramp)
                seg[-ramp:] = np.linspace(1, 0, ramp)
            env[a:b] = np.maximum(env[a:b], seg)
    voz = (x * env * silabas).astype(np.float32)
    atual = float(np.sqrt(np.mean(voz[env > 0] ** 2)))
    voz *= (10 ** (nivel_db / 20)) / max(atual, 1e-9)
    destino.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                           "-c:a", "pcm_s24le", str(destino)], input=voz.tobytes(), capture_output=True)
    if proc.returncode != 0:
        raise ErroProducao("Falha ao gravar a narração-guia: " + proc.stderr.decode(errors="replace")[-300:])
    return destino
