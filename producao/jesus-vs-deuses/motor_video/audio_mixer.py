"""Mixagem: narração (original, sem reprocessar) + trilha + efeitos, com ducking.

* Os stems de música e efeitos são montados em Python (sample-accurate, a
  partir dos eventos da linha do tempo) e gravados em WAV 24 bits.
* A mixagem final é feita pelo FFmpeg: `sidechaincompress` usa a própria
  narração para abaixar música (forte) e efeitos (leve) enquanto ela fala.
* A narração só passa por conversão de formato e ganho final linear; nenhum
  filtro de voz é aplicado aqui.
* Sons: arquivos licenciados do usuário (pasta de música/efeitos) têm
  prioridade; na falta deles, usa-se ambientação sintetizada por código.
"""

from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path

import numpy as np

from . import audio_synth as syn
from .config import ErroProducao, executar, log, salvar_json
from .timeline_builder import Timeline

SR = syn.SR
RES_CURVA = 50  # pontos/s das curvas de automação
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}


# ------------------------------------------------------------- medições ---

def decodificar_mono(caminho: Path, taxa: int = 16000) -> np.ndarray:
    """Decodifica qualquer áudio para mono float32 (via FFmpeg)."""
    proc = subprocess.run(["ffmpeg", "-v", "error", "-i", str(caminho), "-vn", "-ac", "1", "-ar", str(taxa),
                           "-f", "f32le", "pipe:1"], capture_output=True)
    if proc.returncode != 0:
        raise ErroProducao(f"Falha ao decodificar {caminho.name}: {proc.stderr.decode(errors='replace')[-300:]}")
    return np.frombuffer(proc.stdout, dtype=np.float32)


def medir_narracao(wav: Path) -> dict:
    """RMS ativo (dBFS), pico e mapa de atividade da fala a 20 Hz."""
    x = decodificar_mono(wav, 16000)
    if len(x) == 0:
        raise ErroProducao("A narração não tem amostras de áudio.")
    jan = 800  # 50 ms
    n = len(x) // jan
    quadros = x[: n * jan].reshape(n, jan)
    rms = np.sqrt((quadros.astype(np.float64) ** 2).mean(axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    limiar = max(db.max() - 35, -60)
    ativo = db > limiar
    rms_ativo = 20 * np.log10(np.sqrt((rms[ativo] ** 2).mean())) if ativo.any() else -40.0
    return {"rms_ativo_db": float(rms_ativo), "pico_db": float(20 * np.log10(np.abs(x).max() + 1e-12)),
            "atividade": ativo, "duracao_s": len(x) / 16000, "resolucao_hz": 16000 / jan}


def loudness(wav: Path, alvo: float = -14.0, tp: float = -1.5) -> dict:
    proc = executar(["ffmpeg", "-hide_banner", "-nostats", "-i", wav, "-af",
                     f"loudnorm=I={alvo}:TP={tp}:LRA=11:print_format=json", "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", proc.stderr)
    if not m:
        raise ErroProducao("Não foi possível medir o loudness do áudio.")
    import json
    return json.loads(m.group(0))


# ----------------------------------------------------- arquivos do usuário ---

def carregar_audio(caminho: Path) -> np.ndarray:
    proc = subprocess.run(["ffmpeg", "-v", "error", "-i", str(caminho), "-vn", "-ac", "2", "-ar", str(SR),
                           "-f", "f32le", "pipe:1"], capture_output=True)
    if proc.returncode != 0:
        raise ErroProducao(f"Falha ao ler {caminho.name}: {proc.stderr.decode(errors='replace')[-300:]}")
    return np.frombuffer(proc.stdout, dtype=np.float32).reshape(-1, 2).copy()


def _achar_usuario(arquivos: list[Path], chave: str) -> Path | None:
    chave = chave.lower()
    for a in arquivos:
        if chave in a.stem.lower().replace("-", "").replace("_", "").replace(" ", ""):
            return a
    return None


def _repetir(x: np.ndarray, dur: float, xf: float = 3.0) -> np.ndarray:
    """Repete `x` com crossfade até cobrir `dur` segundos."""
    n = int(dur * SR)
    if len(x) >= n:
        return x[:n]
    passo = max(len(x) - int(xf * SR), int(SR))
    saida = np.zeros((n, 2), np.float32)
    ini = 0
    while ini < n:
        trecho = syn.fade(x, xf if ini > 0 else 0.0, xf)
        fim = min(n, ini + len(trecho))
        saida[ini:fim] += trecho[: fim - ini]
        ini += passo
    return saida


# --------------------------------------------------------- automação / stems ---

class Curva:
    """Ganho em dB ao longo do tempo (50 pontos/s), com rampas."""

    def __init__(self, duracao: float):
        self.db = np.zeros(int(duracao * RES_CURVA) + 2, np.float32)

    def _i(self, t: float) -> int:
        return int(max(0, min(len(self.db) - 1, round(t * RES_CURVA))))

    def chaves(self, pontos: list[tuple[float, float]]):
        """Define a curva base por pontos (tempo, dB), interpolando linearmente."""
        pontos = sorted(pontos)
        tempos = np.arange(len(self.db), dtype=np.float32) / RES_CURVA
        self.db += np.interp(tempos, [p[0] for p in pontos], [p[1] for p in pontos]).astype(np.float32)

    def somar_local(self, ini: float, fim: float, db_ini: float, db_fim: float, manter: bool = False):
        a, b = self._i(ini), self._i(fim)
        if b <= a:
            return
        self.db[a:b] += np.linspace(db_ini, db_fim, b - a, dtype=np.float32)
        if manter:
            self.db[b:] += db_fim

    def limitar(self, ini: float, fim: float, db: float, entrada: float, saida: float):
        """Força o ganho a no máximo `db` entre ini e fim, com rampas de entrada/saída."""
        a, b = self._i(ini), self._i(fim)
        ra, rb = max(1, int(entrada * RES_CURVA)), max(1, int(saida * RES_CURVA))
        env = np.zeros(len(self.db), np.float32)  # 0 = sem efeito, 1 = limite total
        env[a:b] = 1.0
        env[max(0, a - ra):a] = np.linspace(0, 1, a - max(0, a - ra), dtype=np.float32)
        env[b:b + rb] = np.linspace(1, 0, len(env[b:b + rb]), dtype=np.float32)
        alvo = np.minimum(self.db, db)
        self.db = self.db + env * (alvo - self.db)

    def aplicar(self, memmap, chunk: int = SR * 10):
        n = len(memmap)
        tempos = np.arange(len(self.db), dtype=np.float32) / RES_CURVA
        for ini in range(0, n, chunk):
            fim = min(n, ini + chunk)
            t = np.arange(ini, fim, dtype=np.float32) / SR
            g = 10 ** (np.interp(t, tempos, self.db) / 20)
            memmap[ini:fim] *= g[:, None].astype(np.float32)


def _somar(destino: np.memmap, x: np.ndarray, t0: float):
    i = int(round(t0 * SR))
    if i >= len(destino) or i + len(x) <= 0:
        return
    a = max(0, -i)
    fim = min(len(x), len(destino) - i)
    destino[i + a:i + fim] += x[a:fim]


def _db(x_db: float) -> float:
    return 10 ** (x_db / 20)


def _escalar_rms(x: np.ndarray, rms_db: float) -> np.ndarray:
    r = float(np.sqrt(np.mean(np.square(x[:: 8], dtype=np.float64))))
    return x * (_db(rms_db) / r) if r > 0 else x


def _escalar_pico(x: np.ndarray, pico_db: float) -> np.ndarray:
    m = float(np.abs(x).max())
    return x * (_db(pico_db) / m) if m > 0 else x


def construir_stems(tl: Timeline, narr: dict, pasta_audio: Path, pasta_musicas: list[Path] | None = None,
                    pasta_efeitos: list[Path] | None = None, limite: float | None = None) -> dict:
    """Gera `musica-stem.wav` e `efeitos-stem.wav` (24 bits, 48 kHz) e a lista de fontes usadas.

    `limite` (s) restringe os stems ao início da linha do tempo (modo prévia).
    """
    pasta_audio.mkdir(parents=True, exist_ok=True)
    total = min(tl.duracao_video, limite) if limite else tl.duracao_video
    N = int(math.ceil(total * SR))
    ref = narr["rms_ativo_db"]
    usados: list[dict] = []
    raw_m, raw_x = pasta_audio / "musica.f32", pasta_audio / "efeitos.f32"
    musica = np.memmap(raw_m, dtype=np.float32, mode="w+", shape=(N, 2))
    efeitos = np.memmap(raw_x, dtype=np.float32, mode="w+", shape=(N, 2))
    cm, cx = Curva(total), Curva(total)
    pontos_m: list[tuple[float, float]] = []
    user_m, user_x = pasta_musicas or [], pasta_efeitos or []
    seed = 1

    # ---- música por seção + ambiências ----
    for s in tl.secoes:
        ini, fim = s["inicio"], min(s["fim"], total + 1.5)
        if ini >= total:
            break
        dur = fim - ini
        clima = s["musica"]
        arq = _achar_usuario(user_m, clima)
        nivel_clima = syn.CLIMAS[clima]["nivel_db"]
        alvo_rms = ref - 17 + nivel_clima
        if arq is not None:
            bruto = carregar_audio(arq)
            x = _escalar_rms(_repetir(bruto, dur + 3.0), alvo_rms)
            _somar(musica, syn.fade(x, 3.0, 3.0), ini - 1.5)
            usados.append({"tipo": "musica", "nome": clima, "origem": f"arquivo do usuário: {arq.name}", "ini": ini, "fim": fim})
        else:
            c = syn.CLIMAS[clima]
            troca, xf = c["troca"], 2.5
            k, t0 = 0, ini
            while t0 < fim:
                dseg = troca + 2 * xf
                x = _escalar_rms(syn.segmento_musica(clima, k, dseg, seed), alvo_rms)
                primeiro, ultimo = k == 0, t0 + troca >= fim
                x = syn.fade(x, 3.0 if primeiro else 2 * xf, 3.0 if ultimo else 2 * xf)
                _somar(musica, x, t0 - xf)
                k += 1
                t0 += troca
            usados.append({"tipo": "musica", "nome": clima, "origem": "sintetizada por código (pad/cordas/coro/piano)", "ini": ini, "fim": fim})
        if clima == "encerramento":
            arp = _escalar_pico(syn.arpejo_piano(dur + 2.0, seed), ref - 8)
            _somar(musica, syn.fade(arp, 1.0, 3.0), ini)
        a_db, b_db = {"ressurreicao": (-24.0, 0.0), "comparacao": (-7.0, 0.0), "crucificacao": (0.0, -11.0)}.get(clima, (0.0, 0.0))
        if not pontos_m:
            pontos_m.append((0.0, a_db))
        if dur >= 3.5:
            pontos_m += [(ini + 1.5, a_db), (fim - 1.5, b_db)]
        else:
            pontos_m.append(((ini + fim) / 2, (a_db + b_db) / 2))
        for nome in s["ambiencia"]:
            seed += 1
            arq_amb = _achar_usuario(user_x, nome)
            offset = {"ressonancia_templo": 3.0, "grave_atmosferico": -3.0, "grave_sutil": -3.0, "ambiencia_templo": -1.0}.get(nome, 0.0)
            if arq_amb is not None:
                x = _escalar_rms(_repetir(carregar_audio(arq_amb), dur + 3.0), ref - 27 + offset)
                origem = f"arquivo do usuário: {arq_amb.name}"
            else:
                x = _escalar_rms(syn.ambiencia(nome, dur + 3.0, seed), ref - 27 + offset)
                origem = "sintetizada por código (ambientação, não é gravação histórica)"
            _somar(efeitos, syn.fade(x, 2.5, 2.5), ini - 1.5)
            usados.append({"tipo": "ambiencia", "nome": nome, "origem": origem, "ini": ini, "fim": fim})

    # ---- efeitos pontuais (variando as amostras para não repetir) ----
    contadores: dict[str, int] = {}
    niveis = {"impacto": ref - 4, "whoosh": ref - 9, "nota": ref - 7, "passos": ref - 14, "tecido": ref - 20, "pergaminho": ref - 16}
    for ev in tl.eventos_audio:
        tipo = ev["tipo"]
        if tipo in ("silencio", "musica_nivel", "vento_forte") or ev["t"] >= total:
            continue
        k = contadores.get(tipo, 0)
        contadores[tipo] = k + 1
        arq = _achar_usuario(user_x, tipo)
        if arq is not None:
            x = carregar_audio(arq)
            origem = f"arquivo do usuário: {arq.name}"
            t0 = ev["t"]
        elif tipo == "impacto":
            x, origem, t0 = syn.impacto(k), "sintetizado por código", ev["t"] - syn.PRELUDIO_S
        elif tipo == "whoosh":
            x, origem, t0 = syn.whoosh(k), "sintetizado por código", ev["t"]
        elif tipo == "nota":
            x, origem, t0 = syn.nota_destaque(k), "sintetizado por código (piano)", ev["t"]
        elif tipo == "passos":
            x, origem, t0 = syn.passos(ev.get("dur", 5.0), 40 + k), "sintetizado por código", ev["t"]
        elif tipo == "tecido":
            x, origem, t0 = syn.tecido(60 + k), "sintetizado por código", ev["t"]
        elif tipo == "pergaminho":
            x, origem, t0 = syn.pergaminho(80 + k), "sintetizado por código", ev["t"]
        else:
            continue
        x = _escalar_pico(x, niveis[tipo])
        _somar(efeitos, x, t0)
        usados.append({"tipo": tipo, "t": ev["t"], "origem": origem, "cena": ev.get("cena")})

    pontos_m.append((total, pontos_m[-1][1] if pontos_m else 0.0))
    cm.chaves(pontos_m)
    # ---- automações dos eventos ----
    for ev in tl.eventos_audio:
        t, dur = ev["t"], ev.get("dur", 0.0)
        if ev["tipo"] == "silencio":
            cm.limitar(t, t + dur, -50.0, 0.5, 1.2)
            cx.limitar(t, t + dur, -40.0, 0.5, 1.2)
        elif ev["tipo"] == "musica_nivel":
            modo = ev["modo"]
            if modo == "baixo":
                cm.limitar(t, t + dur, -7.0, 1.5, 2.0)
            elif modo == "some":
                cm.limitar(t, t + dur, -50.0, 2.0, 3.0)
            elif modo == "cresce":
                cm.somar_local(t, t + dur, 0.0, 5.0, manter=True)
    # cauda final: a trilha e os efeitos se retiram com fade-out limpo
    fim_fala = tl.duracao_audio
    if fim_fala < total:
        cm.somar_local(max(0.0, fim_fala - 1.0), total, 0.0, -45.0, manter=True)
        cx.somar_local(max(0.0, fim_fala - 0.5), total, 0.0, -40.0, manter=True)
    elif limite:  # prévia: fade-out curto no corte
        cm.somar_local(total - 1.0, total, 0.0, -30.0, manter=True)
        cx.somar_local(total - 1.0, total, 0.0, -30.0, manter=True)
    cm.aplicar(musica)
    cx.aplicar(efeitos)

    saidas = {}
    for nome, mm, raw in (("musica-stem.wav", musica, raw_m), ("efeitos-stem.wav", efeitos, raw_x)):
        pico = float(np.abs(mm[:: 16]).max())
        if pico > 0.98:  # segurança: evita clip no stem
            mm[:] *= 0.95 / pico
        mm.flush()
        destino = pasta_audio / nome
        executar(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", raw,
                  "-c:a", "pcm_s24le", destino])
        saidas[nome] = destino
        del mm
        raw.unlink(missing_ok=True)
    salvar_json(pasta_audio / "fontes-de-audio.json", usados)
    return {"musica": saidas["musica-stem.wav"], "efeitos": saidas["efeitos-stem.wav"], "fontes": usados}


# ----------------------------------------------------------- mixagem final ---

def mixar(narracao_wav: Path, canais_narracao: int, stem_musica: Path, stem_efeitos: Path, duracao_video: float,
          narr: dict, destino: Path, alvo_lufs: float = -14.0, tp: float = -1.5) -> dict:
    """Mix final em WAV 24 bits/48 kHz: ducking pela própria narração + ganho linear de loudness.

    Uma única passada pesada (sidechain + soma) grava um intermediário em float; o loudness é medido
    com `ebur128` e aplicado como ganho linear simples (sem compressão extra), com limitador de pico.
    """
    ref = narr["rms_ativo_db"]
    limiar_m = _db(ref - 9)   # a música abaixa quando a fala passa deste nível
    limiar_x = _db(ref - 6)
    nar = "pan=stereo|c0=c0|c1=c0" if canais_narracao == 1 else "aformat=channel_layouts=stereo"
    grafo = (
        f"[0:a]{nar},apad=whole_dur={duracao_video:.3f},asplit=3[n1][n2][n3];"
        f"[1:a]aformat=channel_layouts=stereo[m];[2:a]aformat=channel_layouts=stereo[x];"
        f"[m][n1]sidechaincompress=threshold={limiar_m:.5f}:ratio=6:attack=60:release=800:knee=4:makeup=1[md];"
        f"[x][n2]sidechaincompress=threshold={limiar_x:.5f}:ratio=2.5:attack=15:release=300:knee=4:makeup=1[xd];"
        f"[n3][md][xd]amix=inputs=3:normalize=0:duration=longest:dropout_transition=0,aresample={SR}[out]"
    )
    entradas = ["-i", narracao_wav, "-i", stem_musica, "-i", stem_efeitos]
    pre = destino.with_name(destino.stem + "-pre.wav")
    executar(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *entradas, "-filter_complex", grafo, "-map", "[out]",
              "-t", f"{duracao_video:.3f}", "-c:a", "pcm_f32le", "-ar", str(SR), pre])
    proc = executar(["ffmpeg", "-hide_banner", "-nostats", "-i", pre, "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"])
    integ = re.search(r"I:\s+(-?[\d.]+) LUFS", proc.stderr)
    pico = re.search(r"Peak:\s+(-?[\d.]+) dBFS", proc.stderr)
    if not integ or not pico:
        raise ErroProducao("Falha ao medir o loudness do mix.")
    lufs, tp_real = float(integ.group(1)), float(pico.group(1))
    ganho = alvo_lufs - lufs
    ganho_limitado = min(ganho, tp - tp_real) if tp_real + ganho > tp else ganho
    aviso = None
    if ganho_limitado < ganho - 0.05:
        aviso = (f"Para respeitar o pico máximo de {tp} dBTP o ganho foi limitado a {ganho_limitado:+.1f} dB "
                 f"(loudness final ≈ {lufs + ganho_limitado:.1f} LUFS, alvo {alvo_lufs}).")
        log().warning(aviso)
    executar(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", pre, "-af",
              f"volume={ganho_limitado:.3f}dB,alimiter=limit=0.89:level=false:latency=1", "-c:a", "pcm_s24le", "-ar", str(SR), destino])
    pre.unlink(missing_ok=True)
    log().info("Mix: %.1f LUFS (pico real %.1f dBTP) -> ganho %+.2f dB -> alvo %.1f LUFS", lufs, tp_real, ganho_limitado, alvo_lufs)
    return {"entrada": {"input_i": f"{lufs:.1f}", "input_tp": f"{tp_real:.1f}"}, "ganho_db": round(ganho_limitado, 2),
            "alvo_lufs": alvo_lufs, "true_peak_max": tp, "aviso": aviso}
