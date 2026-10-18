"""Trilha e efeitos sintetizados com a Web Audio API (OfflineAudioContext, em Chromium) + grade de batidas (beats.json).

A música é composta em código (motion/audio/partitura.js): um clima por seção do documentário, com andamento próprio
(motion/audio/climas.json), progressão harmônica, motivos recorrentes, pulso rítmico e ostinatos. Nenhum arquivo de áudio,
sample ou gravação é usado. O Node renderiza cada seção em WAV (float32, 48 kHz); aqui os trechos são somados nos stems
`musica-stem.wav` e `efeitos-stem.wav` (mesmo contrato do `audio_mixer.construir_stems`) e a grade de batidas é
planejada a partir da partitura e MEDIDA no áudio renderizado (onsets), nunca suposta.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import time
from pathlib import Path

import numpy as np

from . import audio_mixer as am
from .config import ErroProducao, log, salvar_json
from .motion_bridge import Motion, PASTA_MOTION
from .timeline_builder import Timeline

SR = am.SR
CLIMAS: dict = {k: v for k, v in json.loads((PASTA_MOTION / "audio" / "climas.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}
TIPOS_EFEITO = {"impacto", "whoosh", "nota", "passos", "tecido", "pergaminho", "revelar", "ping", "faixa", "rota"}
XF, CAUDA = 2.5, 6.0


def bpm(clima: str) -> float:
    return float(CLIMAS[clima]["bpm"])


# ------------------------------------------------------------------ grade de batidas ---

def grade_planejada(tl: Timeline, total: float | None = None) -> dict:
    """Grade de batidas definida pela composição: cada seção começa no compasso 1 (4/4) do seu andamento."""
    total = total or tl.duracao_video
    secoes, batidas = [], []
    for i, s in enumerate(tl.secoes):
        ini, fim = s["inicio"], min(s["fim"], total)
        if ini >= total:
            break
        b = bpm(s["musica"])
        passo = 60.0 / b
        n = int(math.ceil((fim - ini) / passo - 1e-9))
        secoes.append({"indice": i, "id": s["secao"], "clima": s["musica"], "bpm": b, "compasso": "4/4", "inicio": round(ini, 4), "fim": round(fim, 4),
                       "compassos": int(math.ceil(n / 4)), "batidas": n})
        for k in range(n):
            batidas.append({"t": round(ini + k * passo, 4), "secao": i, "compasso": k // 4 + 1, "tempo": k % 4 + 1, "forte": k % 4 == 0})
    return {"versao": 1, "origem": "planejada pela partitura (motion/audio/climas.json); a seção 'medicao' vem da análise do áudio renderizado",
            "secoes": secoes, "batidas": batidas, "eventos": []}


def batidas_do_trecho(grade: dict, ini: float, fim: float) -> list[float]:
    return [b["t"] for b in grade["batidas"] if ini - 0.01 <= b["t"] <= fim + 0.01]


def escrever_beats(grade: dict, destino: Path) -> Path:
    salvar_json(destino, grade)
    return destino


# ------------------------------------------------------------------------- render ---

def _executar_node(motion: Motion, spec: dict, pasta_audio: Path, total_secoes: int) -> dict:
    arq = pasta_audio / "audio-spec.json"
    salvar_json(arq, {**spec, "saida": str(spec["saida"])})
    cmd = [motion.node, str(PASTA_MOTION / "audio.mjs"), "--spec", str(arq)]
    t0 = time.monotonic()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1, cwd=str(PASTA_MOTION))
    ultimas: list[str] = []
    try:
        for linha in proc.stdout:
            linha = linha.rstrip()
            if linha.startswith(("SECAO ", "SFX ")):
                log().info("   [áudio] %s", linha)
            elif linha:
                ultimas = (ultimas + [linha])[-10:]
        rc = proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        proc.stdout.close()
    man = spec["saida"] / "manifesto-audio.json"
    if rc != 0 or not man.is_file():
        raise ErroProducao("A síntese de áudio (Web Audio) falhou:\n" + "\n".join(ultimas[-8:]))
    log().info("   [áudio] trilha sintetizada em %.0f s", time.monotonic() - t0)
    return json.loads(man.read_text(encoding="utf-8"))


def construir_stems_web(tl: Timeline, narr: dict, pasta_audio: Path, motion: Motion, limite: float | None = None, grade: dict | None = None) -> dict:
    """Mesmo contrato de `audio_mixer.construir_stems`: devolve {musica, efeitos, fontes}."""
    pasta_audio.mkdir(parents=True, exist_ok=True)
    total = min(tl.duracao_video, limite) if limite else tl.duracao_video
    ref = narr["rms_ativo_db"]
    secoes = []
    for i, s in enumerate(tl.secoes):
        ini, fim = s["inicio"], min(s["fim"], total + 1.5)
        if ini >= total:
            break
        secoes.append({"id": f"{i:02d}-{s['secao']}", "clima": s["musica"], "bpm": bpm(s["musica"]), "ini": ini, "fim": fim,
                       "nivelDb": CLIMAS[s["musica"]]["nivel_db"], "ambiencias": list(s["ambiencia"]), "primeira": i == 0})
    contadores: dict[str, int] = {}
    eventos = []
    for ev in tl.eventos_audio:
        tipo = ev["tipo"]
        if tipo not in TIPOS_EFEITO or ev["t"] >= total:
            continue
        k = contadores.get(tipo, 0)
        contadores[tipo] = k + 1
        eventos.append({"t": round(ev["t"], 4), "tipo": tipo, "variante": k % 4, "dur": ev.get("dur", 0.0)})
    spec = {"saida": pasta_audio / "webaudio", "ref": ref, "xf": XF, "cauda": CAUDA, "janela": 60, "total": total, "secoes": secoes, "eventos": eventos}
    man = _executar_node(motion, spec, pasta_audio, len(secoes))

    N = int(math.ceil(total * SR))
    raw_m, raw_x = pasta_audio / "musica.f32", pasta_audio / "efeitos.f32"
    musica = np.memmap(raw_m, dtype=np.float32, mode="w+", shape=(N, 2))
    efeitos = np.memmap(raw_x, dtype=np.float32, mode="w+", shape=(N, 2))
    usados: list[dict] = []
    for s in man["secoes"]:
        am._somar(musica, am.carregar_audio(Path(s["musica"])), s["inicioAbs"])
        usados.append({"tipo": "musica", "nome": s["clima"], "origem": f"sintetizada por código (Web Audio: osciladores, filtros e envelopes; {s['bpm']:g} BPM, 4/4)",
                       "ini": s["ini"], "fim": s["fim"]})
        if s.get("amb"):
            am._somar(efeitos, am.carregar_audio(Path(s["amb"])), s["inicioAbs"])
            for nome in s["ambiencias"]:
                usados.append({"tipo": "ambiencia", "nome": nome, "origem": "sintetizada por código (ambientação, não é gravação histórica)", "ini": s["ini"], "fim": s["fim"]})
    for x in man["sfx"]:
        am._somar(efeitos, am.carregar_audio(Path(x["arquivo"])), x["inicioAbs"])
    for ev in eventos:
        usados.append({"tipo": ev["tipo"], "t": ev["t"], "origem": "sintetizado por código (Web Audio)", "cena": None})
    pontos_m, pontos_x = am.pontos_automacao(tl, total)
    saida = am.finalizar_stems(tl, total, limite, musica, efeitos, raw_m, raw_x, pontos_m, pontos_x, pasta_audio, usados)
    saida["manifesto"] = man
    return saida


# ------------------------------------------------------------------------- medição ---

def _decodificar(wav: Path, taxa: int) -> np.ndarray:
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(wav), "-ac", "1", "-ar", str(taxa), "-f", "f32le", "-"], capture_output=True)
    if p.returncode != 0:
        raise ErroProducao(f"Não foi possível ler {wav.name} para medir as batidas.")
    return np.frombuffer(p.stdout, np.float32)


def _onsets(x: np.ndarray, taxa: int) -> tuple[np.ndarray, np.ndarray]:
    """Força de onset na banda grave/média-grave (40–400 Hz), onde está o pulso. Devolve (tempos dos picos, envelope de onset)."""
    n = len(x)
    if n < taxa:
        return np.array([]), np.zeros(0)
    X = np.fft.rfft(x.astype(np.float64))
    f = np.fft.rfftfreq(n, 1 / taxa)
    X[(f < 40) | (f > 400)] = 0
    y = np.abs(np.fft.irfft(X, n))
    k = max(1, int(0.02 * taxa))                                   # envelope: média móvel de 20 ms
    env = np.convolve(y, np.ones(k) / k, mode="same")
    d = np.maximum(0.0, np.diff(env, prepend=env[0]))
    k2 = max(1, int(0.012 * taxa))
    ons = np.convolve(d, np.ones(k2) / k2, mode="same")
    lim = np.median(ons) + 4.0 * (np.median(np.abs(ons - np.median(ons))) + 1e-12)
    lim = max(lim, 0.25 * np.percentile(ons, 99.5))
    picos = []
    minimo = int(0.12 * taxa)
    i = 1
    while i < n - 1:
        if ons[i] > lim and ons[i] >= ons[i - 1] and ons[i] >= ons[i + 1]:
            picos.append(i)
            i += minimo
        else:
            i += 1
    return np.array(picos) / taxa, ons


def medir_grade(musica_wav: Path, grade: dict, taxa: int = 8000) -> dict:
    """Confere, no áudio renderizado, se os pulsos da partitura caem onde a grade planejada diz (±60 ms).

    A grade é exata por construção (cada nota é agendada no OfflineAudioContext); a medição verifica, de forma independente,
    que o áudio produzido tem mesmo energia de onset nos instantes dos pulsos e estima o andamento só pelos onsets.
    Preenche `medicao` em cada seção (use depois de `marcos_para_grade`, que traz os pulsos).
    """
    x = _decodificar(musica_wav, taxa)
    for s in grade["secoes"]:
        a, b = int(s["inicio"] * taxa), int(min(s["fim"], len(x) / taxa) * taxa)
        picos, ons = _onsets(x[a:b], taxa)
        picos = picos + s["inicio"]
        pulsos = np.array(s.get("pulsos", []), dtype=float)
        med: dict = {"onsets_detectados": int(len(picos)), "pulsos_planejados": int(len(pulsos))}
        if len(ons) and len(pulsos) >= 4:
            lim = np.median(ons) + 3.0 * (np.median(np.abs(ons - np.median(ons))) + 1e-12)
            lim = max(lim, 0.12 * np.percentile(ons, 99.5))
            w = int(0.06 * taxa)
            achados, desvios = 0, []
            for t in pulsos:
                c = int((t - s["inicio"]) * taxa)
                lo, hi = max(0, c - w), min(len(ons), c + w + 1)
                if hi - lo < 3:
                    continue
                trecho = ons[lo:hi]
                if trecho.max() > lim:
                    achados += 1
                    desvios.append((lo + int(np.argmax(trecho)) - c) / taxa)
            des = np.array(desvios)
            ioi = np.diff(picos)
            ioi = ioi[(ioi > 0.25) & (ioi < 2.0)]
            bpm_med = None
            if len(ioi) >= 3:
                cand = 60.0 / ioi
                ref = s["bpm"]
                cand = np.array([c * 2 ** round(math.log2(ref / c)) if c > 0 else c for c in cand])   # normaliza oitavas (metade/dobro do tempo)
                bpm_med = float(np.median(cand))
            med.update({"cobertura_pulsos": round(achados / len(pulsos), 3),
                        "desvio_medio_ms": round(float(np.mean(des) * 1000), 1) if len(des) else None,
                        "desvio_abs_max_ms": round(float(np.max(np.abs(des)) * 1000), 1) if len(des) else None,
                        "bpm_medido": round(bpm_med, 2) if bpm_med else None})
            med["mensuravel"] = True
            med["confirmada"] = bool(med["cobertura_pulsos"] >= 0.75 and (med["desvio_abs_max_ms"] or 0) <= 60)
        else:
            med["mensuravel"] = False
            med["confirmada"] = False
            med["observacao"] = "menos de 4 pulsos percussivos planejados na seção: grade planejada, sem confirmação por onsets"
        s["medicao"] = med
    return grade


def marcos_para_grade(grade: dict, manifesto: dict):
    """Eventos musicais relevantes (acordes, motivos, sinos, subidas) em tempo absoluto, vindos da partitura.
    Os pulsos percussivos ficam em `secoes[i]["pulsos"]` (usados na medição) e não entram na lista de eventos."""
    for s in manifesto["secoes"]:
        base = s["ini"]
        sec = next((g for g in grade["secoes"] if g["indice"] == s["indice"]), None)
        for m in s.get("marcos", []):
            if m["tipo"] == "pulso":
                if sec is not None:
                    sec.setdefault("pulsos", []).append(round(base + m["t"], 4))
                continue
            grade["eventos"].append({"t": round(base + m["t"], 3), "tipo": m["tipo"], "secao": s["indice"], "compasso": m["compasso"]})
    grade["eventos"].sort(key=lambda e: e["t"])
