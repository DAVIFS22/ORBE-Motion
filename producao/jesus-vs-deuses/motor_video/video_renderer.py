"""Renderização via FFmpeg: blocos de quadros em paralelo, concatenação sem recompressão e mux do áudio.

* Cada bloco (≈20 s) é gerado por um processo separado: o Python calcula os
  quadros e os envia ao FFmpeg por pipe (rawvideo). Isso dá progresso real,
  paralelismo, tolerância a falhas e reaproveitamento de blocos já válidos.
* O vídeo final é concatenado com `-c copy` (sem segunda compressão) e ganha o
  áudio já mixado (AAC estéreo) e, opcionalmente, a trilha de legendas.
* Ctrl+C (ou um arquivo `CANCELAR.txt` na pasta de saída) cancela com limpeza:
  os blocos concluídos ficam e são reaproveitados na próxima execução.
"""

from __future__ import annotations

import hashlib
import json
import multiprocessing as mp
import os
import shutil
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

from . import VERSAO_MOTOR
from .config import Config, ErroProducao, executar, log
from .timeline_builder import Timeline

BITRATE_ESTIMADO_MBPS = 14.0


class Cancelado(ErroProducao):
    pass


# ---------------------------------------------------------------- encoder ---

@dataclass
class Encoder:
    nome: str
    args: list[str]
    hardware: bool


_COR = ["-vf", "scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]


def _encoder_cpu(cfg: Config) -> Encoder:
    return Encoder("libx264", ["-c:v", "libx264", "-preset", cfg.preset, "-crf", str(cfg.crf), "-profile:v", "high",
                               "-g", str(cfg.fps * 2), "-bf", "2", *_COR], False)


_HARDWARE = [
    ("h264_nvenc", ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "20", "-b:v", "0", "-g", "{gop}"]),
    ("h264_qsv", ["-c:v", "h264_qsv", "-global_quality", "20", "-g", "{gop}"]),
    ("h264_amf", ["-c:v", "h264_amf", "-quality", "quality", "-rc", "cqp", "-qp_i", "20", "-qp_p", "22", "-g", "{gop}"]),
    ("h264_videotoolbox", ["-c:v", "h264_videotoolbox", "-b:v", "16M", "-g", "{gop}"]),
]


def detectar_encoder(cfg: Config) -> Encoder:
    """CPU (libx264) por padrão. Em `auto`/`gpu`, usa um encoder de hardware somente se
    um teste real de codificação funcionar; senão, volta para CPU."""
    if cfg.encoder == "cpu":
        return _encoder_cpu(cfg)
    try:
        lista = executar(["ffmpeg", "-hide_banner", "-encoders"], check=False).stdout
    except Exception:
        lista = ""
    if cfg.encoder == "auto":
        # `auto` só usa hardware se o usuário pedir `gpu`: mantém a opção estável por padrão
        return _encoder_cpu(cfg)
    for nome, args in _HARDWARE:
        if nome not in lista:
            continue
        args = [a.replace("{gop}", str(cfg.fps * 2)) for a in args]
        teste = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=1280x720:r=30:d=1", *args, *_COR,
                                "-an", "-f", "null", "-"], capture_output=True)
        if teste.returncode == 0:
            log().info("Encoder de hardware validado: %s", nome)
            return Encoder(nome, [*args, *_COR], True)
        log().info("Encoder %s listado mas não funcionou neste computador; ignorado.", nome)
    log().warning("Nenhum encoder de hardware utilizável; usando CPU (libx264).")
    return _encoder_cpu(cfg)


# ----------------------------------------------------------------- blocos ---

def _chave_bloco(tarefa: dict) -> str:
    h = hashlib.sha256()
    h.update(json.dumps({k: tarefa[k] for k in ("f0", "f1", "w", "h", "fps", "dur_total", "enc", "planos", "legendas", "rapido")},
                        sort_keys=True, default=str).encode())
    h.update(VERSAO_MOTOR.encode())
    for p in tarefa["planos"]:
        arq = p["fundo"].get("arquivo")
        if arq and os.path.exists(arq):
            st = os.stat(arq)
            h.update(f"{arq}:{st.st_size}:{int(st.st_mtime)}".encode())
    return h.hexdigest()[:20]


def _frames_do_arquivo(caminho: Path) -> int:
    proc = subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries",
                           "stream=nb_read_packets", "-of", "csv=p=0", str(caminho)], capture_output=True, text=True)
    try:
        return int(proc.stdout.strip().split(",")[0])
    except (ValueError, IndexError):
        return -1


def _trabalhador(tarefa: dict) -> None:
    """Executa em processo separado: gera os quadros de um bloco e os codifica."""
    saida = Path(tarefa["saida"])
    marca_ok, marca_erro, marca_prog = (saida.with_suffix(s) for s in (".ok", ".erro", ".prog"))
    try:
        from .visual_effects import Compositor
        comp = Compositor(tarefa["planos"], tarefa["w"], tarefa["h"], tarefa["fps"], tarefa["dur_total"],
                          Path(tarefa["cache"]), legendas=[tuple(x) for x in tarefa["legendas"]], rapido=tarefa["rapido"])
        tmp = saida.with_suffix(".parcial.mp4")
        log_ff = saida.with_suffix(".ffmpeg.log")
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{tarefa['w']}x{tarefa['h']}", "-r", str(tarefa["fps"]), "-i", "-", *tarefa["enc"], "-an",
               "-movflags", "+faststart", str(tmp)]
        with open(log_ff, "wb") as lf:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=lf)
            total = tarefa["f1"] - tarefa["f0"]
            try:
                for i, n in enumerate(range(tarefa["f0"], tarefa["f1"])):
                    proc.stdin.write(comp.quadro(n).tobytes())
                    if i % 15 == 0:
                        marca_prog.write_text(str(i))
                        if tarefa.get("cancelar") and os.path.exists(tarefa["cancelar"]):
                            raise Cancelado("cancelado pelo usuário")
                proc.stdin.close()
            except BrokenPipeError:
                pass
            rc = proc.wait()
        if rc != 0:
            raise ErroProducao("FFmpeg falhou ao codificar o bloco:\n" + log_ff.read_text(errors="replace")[-800:])
        esperado = tarefa["f1"] - tarefa["f0"]
        obtido = _frames_do_arquivo(tmp)
        if obtido != esperado:
            raise ErroProducao(f"Bloco com {obtido} quadros; esperado {esperado}.")
        comp.fechar()
        tmp.replace(saida)
        marca_ok.write_text(tarefa["chave"])
        marca_prog.write_text(str(total))
    except BaseException as e:  # noqa: BLE001 - registramos qualquer falha para o processo principal
        marca_erro.write_text("".join(traceback.format_exception(e))[-2500:])
        raise SystemExit(1)


class _Progresso:
    def __init__(self, total: int, nome: str = "Renderizando"):
        self.total, self.nome = total, nome
        self.ini = time.monotonic()
        self.ultimo_pct_log = -1.0
        self.tty = sys.stderr.isatty()

    def mostrar(self, feitos: int, concluido: bool = False):
        pct = 100.0 * feitos / max(1, self.total)
        dec = time.monotonic() - self.ini
        vel = feitos / dec if dec > 0 and feitos else 0
        eta = (self.total - feitos) / vel if vel else 0
        barra = "#" * int(pct / 5) + "-" * (20 - int(pct / 5))
        linha = f"{self.nome} [{barra}] {pct:5.1f}%  quadros {feitos}/{self.total}  {vel:5.1f} q/s  ETA {int(eta // 60):02d}:{int(eta % 60):02d}"
        if self.tty:
            print("\r" + linha, end="\n" if concluido else "", file=sys.stderr, flush=True)
        elif pct - self.ultimo_pct_log >= 5 or concluido:
            self.ultimo_pct_log = pct
            log().info(linha)


def verificar_espaco(pasta: Path, duracao_s: float, extra_bytes: int = 0):
    """Garante espaço livre para blocos + vídeo final + áudio (com folga)."""
    pasta.mkdir(parents=True, exist_ok=True)
    necessario = int(duracao_s * BITRATE_ESTIMADO_MBPS * 1e6 / 8 * 2.4) + int(duracao_s * 48000 * 2 * 3 * 3) + extra_bytes
    livre = shutil.disk_usage(pasta).free
    if livre < necessario:
        raise ErroProducao(
            f"Espaço em disco insuficiente em {pasta}: livre {livre / 1e9:.1f} GB, necessário ~{necessario / 1e9:.1f} GB. "
            "Libere espaço ou escolha outra pasta de saída com --saida.")
    log().info("Espaço em disco: %.1f GB livres (necessário ~%.1f GB).", livre / 1e9, necessario / 1e9)


def _planos_para_bloco(planos: list[dict], t0: float, t1: float) -> list[dict]:
    """Planos que tocam o intervalo (com um vizinho de cada lado para as transições)."""
    idx = [i for i, p in enumerate(planos) if p["fim"] > t0 - 2.0 and p["inicio"] < t1 + 2.0]
    if not idx:
        idx = [len(planos) - 1]
    a, b = max(0, idx[0] - 1), min(len(planos), idx[-1] + 2)
    return planos[a:b]


def renderizar_video(cfg: Config, tl: Timeline, pasta_imagens: Path, pasta_temp: Path, legendas_srt: Path | None,
                     legendas: list | None, audio_mix: Path, destino: Path) -> dict:
    """Renderiza o MP4 final. Devolve estatísticas (encoder, blocos reaproveitados, tempo)."""
    pasta_temp.mkdir(parents=True, exist_ok=True)
    pasta_blocos = pasta_temp / "blocos"
    pasta_blocos.mkdir(exist_ok=True)
    cancelar = cfg.saida / "CANCELAR.txt"
    cancelar.unlink(missing_ok=True)
    enc = detectar_encoder(cfg)
    log().info("Encoder de vídeo: %s", enc.nome)
    duracao = tl.duracao_video
    if cfg.limite_segundos:
        duracao = min(duracao, cfg.limite_segundos)
    fps = cfg.fps
    total_quadros = int(round(duracao * fps))
    verificar_espaco(pasta_temp, duracao)

    planos = tl.planos_dict()
    for p in planos:  # caminhos absolutos: o renderizador só lê arquivos locais já validados
        if p["fundo"].get("arquivo") and (p["fundo"].get("tipo") == "imagem" or p["fundo"].get("relativo_imagens")):
            p["fundo"]["arquivo"] = str((pasta_imagens / p["fundo"]["arquivo"]).resolve())
    bloco_q = max(fps, int(round(cfg.segundos_por_bloco * fps)))
    tarefas = []
    for k, f0 in enumerate(range(0, total_quadros, bloco_q)):
        f1 = min(total_quadros, f0 + bloco_q)
        leg = [(a, b, t) for a, b, t in (legendas or []) if b > f0 / fps - 1 and a < f1 / fps + 1] if cfg.legendas_queimadas else []
        tarefa = {
            "idx": k, "f0": f0, "f1": f1, "w": cfg.largura, "h": cfg.altura, "fps": fps, "dur_total": tl.duracao_video,
            "enc": enc.args, "planos": _planos_para_bloco(planos, f0 / fps, f1 / fps), "legendas": leg,
            "cache": str(pasta_temp / "procedural"), "saida": str(pasta_blocos / f"bloco-{k:04d}.mp4"),
            "rapido": cfg.rapido, "cancelar": str(cancelar),
        }
        tarefa["chave"] = _chave_bloco(tarefa)
        tarefas.append(tarefa)

    # reaproveita blocos válidos
    pendentes, reaproveitados = [], 0
    for t in tarefas:
        s = Path(t["saida"])
        ok, prog = s.with_suffix(".ok"), s.with_suffix(".prog")
        if s.is_file() and ok.is_file() and ok.read_text() == t["chave"] and _frames_do_arquivo(s) == t["f1"] - t["f0"]:
            reaproveitados += 1
            continue
        for suf in (".ok", ".erro", ".prog"):
            s.with_suffix(suf).unlink(missing_ok=True)
        pendentes.append(t)
    log().info("Blocos: %d no total, %d reaproveitados, %d a renderizar (%d processos).", len(tarefas), reaproveitados,
               len(pendentes), cfg.trabalhadores)

    inicio = time.monotonic()
    progresso = _Progresso(total_quadros)
    try:
        _executar_blocos(pendentes, cfg.trabalhadores, tarefas, progresso, cancelar)
    except BaseException:
        raise
    progresso.mostrar(total_quadros, concluido=True)

    # concatena sem recompressão e adiciona o áudio
    lista = pasta_temp / "blocos.txt"
    lista.write_text("".join(f"file '{Path(t['saida']).resolve().as_posix()}'\n" for t in tarefas), encoding="utf-8")
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(".parcial.mp4")
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lista, "-i", audio_mix]
    mapa = ["-map", "0:v:0", "-map", "1:a:0"]
    if legendas_srt is not None and legendas_srt.is_file():
        cmd += ["-i", legendas_srt]
        mapa += ["-map", "2:0"]
    cmd += mapa + ["-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2"]
    if legendas_srt is not None and legendas_srt.is_file():
        cmd += ["-c:s", "mov_text", "-metadata:s:s:0", "language=por", "-disposition:s:0", "default"]
    cmd += ["-metadata", "title=Jesus contra todos os deuses: por que Jesus é único?", "-metadata:s:a:0", "language=por",
            "-movflags", "+faststart", "-t", f"{duracao:.3f}", parcial]
    executar(cmd)
    parcial.replace(destino)
    return {"encoder": enc.nome, "hardware": enc.hardware, "blocos": len(tarefas), "blocos_reaproveitados": reaproveitados,
            "quadros": total_quadros, "tempo_renderizacao_s": round(time.monotonic() - inicio, 1)}


def _executar_blocos(pendentes: list[dict], n_proc: int, todas: list[dict], progresso: _Progresso, cancelar: Path):
    ctx = mp.get_context("spawn")
    fila = list(pendentes)
    rodando: dict[int, tuple[mp.Process, dict, int]] = {}
    tentativas = {t["idx"]: 0 for t in pendentes}
    concluidos_q = sum(t["f1"] - t["f0"] for t in todas if t not in pendentes)

    def feitos() -> int:
        total = concluidos_q
        for _, (p, t, _) in rodando.items():
            prog = Path(t["saida"]).with_suffix(".prog")
            try:
                total += int(prog.read_text() or 0)
            except (OSError, ValueError):
                pass
        return total

    def cancelar_tudo():
        for proc, _, _ in rodando.values():
            if proc.is_alive():
                proc.terminate()
        for proc, _, _ in rodando.values():
            proc.join(timeout=5)

    try:
        while fila or rodando:
            if cancelar.exists():
                raise Cancelado("Produção cancelada (arquivo CANCELAR.txt). Os blocos prontos serão reaproveitados.")
            while fila and len(rodando) < n_proc:
                t = fila.pop(0)
                proc = ctx.Process(target=_trabalhador, args=(t,), daemon=True)
                proc.start()
                rodando[t["idx"]] = (proc, t, 0)
            time.sleep(0.4)
            for idx in list(rodando):
                proc, t, _ = rodando[idx]
                if proc.is_alive():
                    continue
                proc.join()
                saida = Path(t["saida"])
                if saida.with_suffix(".ok").is_file():
                    concluidos_q += t["f1"] - t["f0"]
                    del rodando[idx]
                    continue
                erro = saida.with_suffix(".erro")
                detalhe = erro.read_text(errors="replace") if erro.is_file() else f"processo terminou com código {proc.exitcode}"
                if "Cancelado" in detalhe:
                    raise Cancelado("Produção cancelada.")
                tentativas[idx] += 1
                del rodando[idx]
                if tentativas[idx] > 2:
                    raise ErroProducao(f"O bloco {idx} falhou {tentativas[idx]} vezes:\n{detalhe}")
                log().warning("Bloco %d falhou (tentativa %d); tentando de novo.\n%s", idx, tentativas[idx], detalhe[-400:])
                erro.unlink(missing_ok=True)
                fila.insert(0, t)
            progresso.mostrar(feitos())
    except KeyboardInterrupt:
        cancelar_tudo()
        raise Cancelado("Produção cancelada pelo usuário (Ctrl+C). Os blocos prontos serão reaproveitados.")
    except BaseException:
        cancelar_tudo()
        raise


def limpar_temporarios(pasta_temp: Path):
    """Remove blocos e caches. Só deve ser chamado depois da validação final."""
    if pasta_temp.is_dir() and pasta_temp.name == "06-temporarios":
        shutil.rmtree(pasta_temp, ignore_errors=True)
