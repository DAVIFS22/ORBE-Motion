"""Ponte com o Blender: localiza o Blender, planeja (prioridade + orçamento), renderiza e converte as cenas 3D em clipes.

O Blender roda em outro processo e produz uma sequência de quadros PNG; o FFmpeg codifica o clipe
(sem filtros 2D para "fingir" 3D). Os clipes ficam em cache pelo conteúdo do pedido: se nada mudou, nada é
renderizado de novo, e um render interrompido continua do último quadro pronto.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from .cenas3d import VERSAO_CENAS3D
from .config import Config, ErroProducao, executar, log, salvar_json

SCRIPT = Path(__file__).parent / "cenas3d" / "renderizar.py"

QUALIDADES = {  # resolução e amostras de render; fps = taxa de render (o clipe é levado ao FPS do projeto)
    "teste": dict(largura=480, altura=270, amostras=4, rebotes=2, fps=12),
    "previa": dict(largura=800, altura=450, amostras=8, rebotes=3, fps=15),
    "padrao": dict(largura=1280, altura=720, amostras=32, rebotes=4, fps=24),
    "alta": dict(largura=1920, altura=1080, amostras=96, rebotes=6, fps=30),
}
FPS_ESTIMADO_SEG_POR_QUADRO_REF = 3.0  # só usado se não houver medição


class ErroBlender(ErroProducao):
    pass


@dataclass
class Blender:
    tipo: str  # "executavel" (blender -b) | "python" (módulo bpy)
    caminho: str
    versao: str = ""

    def comando(self, args: list[str], script: Path = SCRIPT) -> list[str]:
        if self.tipo == "executavel":
            return [self.caminho, "-b", "--factory-startup", "-noaudio", "--python", str(script), "--", *args]
        return [self.caminho, str(script), "--", *args]


# ------------------------------------------------------------------ localizar ---

def _testar(tipo: str, caminho: str) -> Blender | None:
    try:
        if tipo == "python":
            proc = subprocess.run([caminho, "-c", "import bpy; print('VER', bpy.app.version_string)"], capture_output=True, text=True, timeout=90)
        else:
            proc = subprocess.run([caminho, "-b", "--factory-startup", "--python-expr", "import bpy; print('VER', bpy.app.version_string)"],
                                  capture_output=True, text=True, timeout=90)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r"VER (\S.*)", proc.stdout)
    return Blender(tipo, caminho, m.group(1).strip()) if (proc.returncode == 0 and m) else None


def _candidatos(explicito: Path | None) -> list[tuple[str, str]]:
    c: list[tuple[str, str]] = []

    def add(caminho):
        if caminho and os.path.exists(str(caminho)):
            nome = Path(str(caminho)).name.lower()
            c.append(("executavel" if nome.startswith("blender") else "python", str(caminho)))

    add(explicito)
    add(os.environ.get("MOTOR_BLENDER"))
    add(shutil.which("blender"))
    if sys.platform.startswith("win"):
        for raiz in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
            base = Path(raiz) / "Blender Foundation"
            if base.is_dir():
                for d in sorted(base.glob("Blender*"), reverse=True):
                    add(d / "blender.exe")
    elif sys.platform == "darwin":
        add("/Applications/Blender.app/Contents/MacOS/Blender")
    else:
        add("/usr/bin/blender")
        add("/snap/bin/blender")
    # o próprio Python, se tiver o módulo bpy instalado (pip install bpy)
    c.append(("python", sys.executable))
    return c


def localizar_blender(explicito: Path | None = None) -> Blender | None:
    """Primeiro Blender utilizável (executável ou Python com bpy), ou None."""
    vistos = set()
    for tipo, caminho in _candidatos(explicito):
        if caminho in vistos:
            continue
        vistos.add(caminho)
        b = _testar(tipo, caminho)
        if b:
            log().info("Blender encontrado: %s (%s, versão %s)", b.caminho, b.tipo, b.versao)
            return b
    return None


# ----------------------------------------------------------------- pedidos 3D ---

@dataclass
class Pedido3D:
    plano_id: str
    cena: str
    duracao: float          # segundos de clipe necessários (plano + metade das transições)
    prioridade: int
    modo: str
    params: dict = field(default_factory=dict)
    rotulo: str = ""
    semente: int = 7
    estimativa_s: float = 0.0
    status: str = "pendente"   # pendente | selecionado | cortado_orcamento | renderizado | reaproveitado | falhou
    tempo_real_s: float = 0.0
    clipe: str | None = None
    detalhe: str = ""
    params_render: dict = field(default_factory=dict)


def semente_da_cena(plano_id: str) -> int:
    return int(hashlib.sha1(plano_id.encode()).hexdigest()[:6], 16) % 9973 + 1


def _hash_cenas() -> str:
    """Hash do código das cenas 3D: alterar uma cena invalida os clipes em cache."""
    h = hashlib.sha1()
    for arq in sorted(SCRIPT.parent.glob("*.py")):
        h.update(arq.read_bytes())
    return h.hexdigest()[:10]


def chave_clipe(p: Pedido3D, qualidade: str, fps_projeto: int, motor: str) -> str:
    q = QUALIDADES[qualidade]
    dados = {"cena": p.cena, "dur": round(p.duracao, 2), "params": p.params, "q": q, "fps": fps_projeto, "semente": p.semente,
             "motor": motor, "v": VERSAO_CENAS3D, "codigo": _hash_cenas()}
    return hashlib.sha1(json.dumps(dados, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _executar_blender(b: Blender, args: list[str], destino_quadros: Path, total: int, progresso=None, cancelar: Path | None = None) -> float:
    """Roda o script de cena e acompanha o progresso. Devolve segundos por quadro (média)."""
    cmd = b.comando(args)
    log().debug("blender: %s", " ".join(cmd))
    t0 = time.monotonic()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)
    ultimas: list[str] = []
    feitos = 0
    concluido = False
    try:
        for linha in proc.stdout:
            linha = linha.rstrip()
            if linha == "CONCLUIDO":
                concluido = True
            if linha.startswith("PROGRESSO"):
                m = re.match(r"PROGRESSO (\d+)/(\d+)", linha)
                if m:
                    feitos = int(m.group(1))
                    if progresso:
                        progresso(feitos, int(m.group(2)))
            elif linha and not re.search(r"CUEW|HIPEW|Deprecat|use_nodes", linha):
                ultimas.append(linha)
                ultimas = ultimas[-14:]
            if cancelar is not None and cancelar.exists():
                raise ErroBlender("Render 3D cancelado (CANCELAR.txt).")
        rc = proc.wait()
    finally:
        if proc.poll() is None:  # cancelamento, Ctrl+C ou erro: não deixa o Blender rodando
            proc.kill()
            proc.wait()
        proc.stdout.close()
    if rc != 0 or not concluido:
        raise ErroBlender("O Blender falhou ao renderizar a cena:\n" + "\n".join(ultimas[-10:]))
    return (time.monotonic() - t0) / max(1, feitos)


def _codificar(quadros: Path, fps_render: int, fps_projeto: int, n: int, destino: Path):
    """PNGs -> MP4 (H.264, 1920x1080, bt709). Se o render foi em FPS menor, interpola por mistura de quadros."""
    filtros = []
    if fps_render != fps_projeto:
        filtros.append(f"framerate=fps={fps_projeto}:scene=100")
    filtros.append("scale=1920:1080:flags=lanczos:in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p")
    tmp = destino.with_suffix(".parcial.mp4")
    executar(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-framerate", str(fps_render), "-i", quadros / "quadro_%05d.png",
              "-vf", ",".join(filtros), "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-colorspace", "bt709", "-color_primaries", "bt709",
              "-color_trc", "bt709", "-color_range", "tv", "-an", "-movflags", "+faststart", tmp])
    tmp.replace(destino)


def renderizar_pedido(b: Blender, p: Pedido3D, cfg: Config, pasta_clipes: Path, pasta_temp: Path, fps_projeto: int, progresso=None,
                      base_imagens: Path | None = None) -> Path:
    q = QUALIDADES[cfg.qualidade_3d]
    params = dict(p.params)
    if params.pop("_relativo_imagens", False) and base_imagens is not None and params.get("imagem"):
        params["imagem"] = str((base_imagens / params["imagem"]).resolve())
    p.params_render = params
    chave = chave_clipe(p, cfg.qualidade_3d, fps_projeto, cfg.motor_3d)
    destino = pasta_clipes / f"{p.cena}-{chave}.mp4"
    if destino.is_file() and destino.stat().st_size > 10_000:
        p.status, p.clipe = "reaproveitado", str(destino)
        return destino
    quadros = pasta_temp / "3d" / f"{p.cena}-{chave}"
    quadros.mkdir(parents=True, exist_ok=True)
    n = max(2, int(round(p.duracao * q["fps"])))
    args = ["--cena", p.cena, "--saida", str(quadros), "--duracao", f"{n / q['fps']:.4f}", "--fps", str(q["fps"]),
            "--largura", str(q["largura"]), "--altura", str(q["altura"]), "--amostras", str(q["amostras"]),
            "--rebotes", str(q["rebotes"]), "--motor", cfg.motor_3d, "--dispositivo", cfg.dispositivo_3d.upper(),
            "--semente", str(p.semente), "--params", json.dumps(params)]
    t0 = time.monotonic()
    _executar_blender(b, args, quadros, n, progresso, cfg.saida / "CANCELAR.txt")
    prontos = len(list(quadros.glob("quadro_*.png")))
    if prontos != n:
        raise ErroBlender(f"A cena {p.cena} gerou {prontos} quadros; esperado {n}.")
    _codificar(quadros, q["fps"], fps_projeto, n, destino)
    shutil.rmtree(quadros, ignore_errors=True)
    p.tempo_real_s = time.monotonic() - t0
    p.status, p.clipe = "renderizado", str(destino)
    return destino


# ---------------------------------------------------------------- planejamento ---

def medir_cena(b: Blender, cena: str, cfg: Config, pasta_temp: Path, cache: dict, params: dict | None = None) -> float:
    """Segundos por quadro de uma cena na qualidade escolhida (um quadro de teste; resultado em cache)."""
    q = QUALIDADES[cfg.qualidade_3d]
    chave = f"{cena}|{cfg.qualidade_3d}|{cfg.dispositivo_3d}|{cfg.motor_3d}"
    if chave in cache:
        return cache[chave]
    saida = pasta_temp / "3d" / f"_medida-{cena}"
    shutil.rmtree(saida, ignore_errors=True)
    args = ["--cena", cena, "--saida", str(saida), "--duracao", "1", "--fps", "1", "--largura", str(q["largura"]), "--altura", str(q["altura"]),
            "--amostras", str(q["amostras"]), "--rebotes", str(q["rebotes"]), "--motor", cfg.motor_3d, "--dispositivo",
            cfg.dispositivo_3d.upper(), "--quadro", "0.5", "--params", json.dumps(params or {})]
    t0 = time.monotonic()
    try:
        _executar_blender(b, args, saida, 1)
        seg = time.monotonic() - t0
    except ErroBlender as e:
        log().warning("Não foi possível medir a cena %s: %s", cena, str(e)[:200])
        seg = FPS_ESTIMADO_SEG_POR_QUADRO_REF * (q["largura"] / 800) ** 2
    shutil.rmtree(saida, ignore_errors=True)
    cache[chave] = max(0.5, seg - 1.5)  # desconta a inicialização do Blender
    return cache[chave]


def planejar(pedidos: list[Pedido3D], cfg: Config, b: Blender | None, pasta_temp: Path, cache_path: Path) -> list[Pedido3D]:
    """Escolhe quais cenas 3D renderizar: menor prioridade primeiro, respeitando o orçamento de tempo."""
    q = QUALIDADES[cfg.qualidade_3d]
    cache = json.loads(cache_path.read_text()) if cache_path.is_file() else {}
    for p in pedidos:
        seg_q = medir_cena(b, p.cena, cfg, pasta_temp, cache, p.params) if b is not None else FPS_ESTIMADO_SEG_POR_QUADRO_REF
        p.estimativa_s = seg_q * max(2, int(round(p.duracao * q["fps"]))) + 20.0  # + abertura do Blender e codificação
    salvar_json(cache_path, cache)
    ordenados = sorted(pedidos, key=lambda p: (p.prioridade, 0))
    acumulado = 0.0
    orcamento = cfg.orcamento_3d_min * 60 if cfg.orcamento_3d_min else None
    for p in ordenados:
        if orcamento is not None and acumulado + p.estimativa_s > orcamento:
            p.status = "cortado_orcamento"
            p.detalhe = f"estimativa {p.estimativa_s / 60:.1f} min excede o orçamento de {cfg.orcamento_3d_min:g} min"
            continue
        p.status = "selecionado"
        acumulado += p.estimativa_s
    return pedidos


def descrever_plano(pedidos: list[Pedido3D], cfg: Config) -> str:
    q = QUALIDADES[cfg.qualidade_3d]
    linhas = [f"Plano de cenas 3D: qualidade '{cfg.qualidade_3d}' ({q['largura']}x{q['altura']}, {q['amostras']} amostras, {q['fps']} fps de render), "
              f"dispositivo {cfg.dispositivo_3d.upper()}, motor {cfg.motor_3d}"]
    tot = 0.0
    for p in sorted(pedidos, key=lambda p: (p.prioridade, p.plano_id)):
        marca = {"selecionado": "[x]", "cortado_orcamento": "[ ]"}.get(p.status, "[?]")
        linhas.append(f"  {marca} P{p.prioridade} {p.plano_id:28s} {p.cena:18s} {p.duracao:5.1f}s  ~{p.estimativa_s / 60:5.1f} min  {p.detalhe}")
        if p.status == "selecionado":
            tot += p.estimativa_s
    linhas.append(f"  Total estimado das cenas selecionadas: {tot / 60:.1f} min")
    return "\n".join(linhas)
