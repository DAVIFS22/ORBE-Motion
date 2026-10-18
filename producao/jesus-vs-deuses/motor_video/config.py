"""Configuração da produção e utilitários comuns (logs, processos, caminhos)."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


class ErroProducao(RuntimeError):
    """Erro esperado, com mensagem compreensível para o usuário."""


@dataclass
class Config:
    saida: Path
    narracao: Path | None = None
    roteiro: Path | None = None
    transcricao: Path | None = None
    pasta_musica: Path | None = None
    pasta_efeitos: Path | None = None
    pasta_imagens: Path | None = None  # imagens fornecidas pelo usuário
    storyboard: Path | None = None  # storyboard alternativo (JSON)

    largura: int = 1920
    altura: int = 1080
    fps: int = 30
    crf: int = 16
    preset: str = "fast"
    encoder: str = "auto"  # auto | cpu | gpu
    trabalhadores: int = max(1, (os.cpu_count() or 2) - 1)
    segundos_por_bloco: float = 20.0

    offline: bool = False
    legendas_queimadas: bool = False
    limite_segundos: float | None = None  # renderiza só o início (prévia)
    loudness_alvo: float = -14.0
    manter_temporarios: bool = False
    plano_alvo_s: float = 11.0  # duração-alvo de cada plano (varia por cena)
    creditos_na_tela: bool = True
    interativo: bool = False
    cauda_final_s: float = 2.5  # pausa curta + fade-out depois da última palavra
    rapido: bool = False  # amostragem bilinear (testes); o padrão é bicúbica
    validacao: bool = False  # narração-guia sintética: o resultado é só uma validação do motor
    nome_saida: str = "jesus-contra-todos-os-deuses"
    # animação 3D (Blender): pontual, por prioridade e com orçamento de tempo de renderização
    prioridade_3d: int = 2          # 0 = sem 3D; 1 = só P1; 2 = P1 + P2 quando faltar imagem real; 3 = tudo
    qualidade_3d: str = "previa"    # teste | previa | padrao | alta
    orcamento_3d_min: float | None = None  # minutos de render 3D (estimados); None = sem limite
    dispositivo_3d: str = "cpu"     # cpu | gpu (gpu cai para cpu se não houver GPU utilizável)
    motor_3d: str = "CYCLES"        # CYCLES | BLENDER_EEVEE
    blender: Path | None = None     # executável do Blender ou Python com o módulo bpy
    so_3d: bool = False             # renderiza apenas as cenas 3D e para
    listar_3d: bool = False         # mostra o plano 3D (com estimativas) e para
    # motion graphics (Node + Chromium; composições determinísticas window.seek(t))
    motion: bool = True             # usa as cenas de motion quando Node/Chromium estiverem disponíveis
    motion_largura: int = 1920
    motion_altura: int = 1080
    motion_crf: int = 16
    motion_preset: str = "medium"
    motion_trabalhadores: int = 3
    so_motion: bool = False         # renderiza apenas os clipes de motion e para
    revisao_rodada: int | None = None   # gera as folhas de contato por batida da rodada N (09-revisao/) e para antes da renderização
    audio_web: bool = True          # trilha e efeitos com a Web Audio API (OfflineAudioContext); False = síntese NumPy anterior

    def para_dict(self) -> dict:
        d = asdict(self)
        return {k: (str(v) if isinstance(v, Path) else v) for k, v in d.items()}

    # pastas do projeto -------------------------------------------------
    def pasta(self, nome: str) -> Path:
        p = self.saida / nome
        p.mkdir(parents=True, exist_ok=True)
        return p


PASTAS = {
    "entrada": "00-entrada",
    "roteiro": "01-roteiro",
    "imagens": "02-imagens",
    "audio": "03-audio",
    "timeline": "04-linha-do-tempo",
    "legendas": "05-legendas",
    "temp": "06-temporarios",
    "export": "07-exportacao",
    "relatorio": "08-relatorio",
    "logs": "logs",
}


def configurar_log(saida: Path) -> tuple[logging.Logger, Path]:
    pasta = saida / PASTAS["logs"]
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / f"producao-{datetime.now():%Y%m%d-%H%M%S}.log"
    log = logging.getLogger("motor_video")
    log.setLevel(logging.DEBUG)
    for h in list(log.handlers):
        log.removeHandler(h)
    fh = logging.FileHandler(arquivo, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(fh)
    log.addHandler(ch)
    return log, arquivo


def log() -> logging.Logger:
    return logging.getLogger("motor_video")


def exigir_ferramenta(nome: str) -> str:
    caminho = shutil.which(nome)
    if not caminho:
        raise ErroProducao(
            f"'{nome}' não foi encontrado no PATH. Instale o FFmpeg "
            "(Windows: winget install Gyan.FFmpeg) e reabra o terminal."
        )
    return caminho


def executar(args: list[str], *, timeout: float | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Executa um programa externo e devolve stdout/stderr como texto."""
    log().debug("exec: %s", " ".join(map(str, args)))
    proc = subprocess.run(
        [str(a) for a in args], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )
    if check and proc.returncode != 0:
        cauda = "\n".join(proc.stderr.strip().splitlines()[-12:])
        raise ErroProducao(f"{Path(str(args[0])).name} falhou (código {proc.returncode}):\n{cauda}")
    return proc


def ffprobe_json(caminho: Path) -> dict:
    exigir_ferramenta("ffprobe")
    proc = executar(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", caminho])
    return json.loads(proc.stdout or "{}")


def salvar_json(caminho: Path, dados) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(caminho)


def ler_json(caminho: Path):
    return json.loads(caminho.read_text(encoding="utf-8"))
