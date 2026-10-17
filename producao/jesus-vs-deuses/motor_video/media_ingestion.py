"""Entrada e validação dos arquivos: narração, roteiro, transcrição, trilhas.

Os arquivos originais nunca são alterados: só são lidos. O SHA-256 de cada
original é registrado na entrada e conferido de novo no fim da produção.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config, ErroProducao, PASTAS, executar, exigir_ferramenta, ffprobe_json, log, salvar_json
from .script_analyzer import MARCA_INICIO

EXT_AUDIO = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"}
EXT_VIDEO = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v"}
EXT_MUSICA = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}


@dataclass
class InfoMidia:
    caminho: Path
    duracao: float
    tem_video: bool
    tem_audio: bool
    taxa_amostragem: int | None
    canais: int | None
    codec_audio: str | None
    sha256: str


@dataclass
class Entradas:
    narracao_original: InfoMidia
    narracao_wav: Path  # WAV 48 kHz usado na produção (pode ser o próprio original)
    narracao_tratada: bool
    roteiro: Path
    transcricao: Path | None
    musicas: list[Path] = field(default_factory=list)
    efeitos: list[Path] = field(default_factory=list)
    imagens_usuario: list[Path] = field(default_factory=list)

    def para_dict(self) -> dict:
        o = self.narracao_original
        return {
            "narracao_original": str(o.caminho), "narracao_duracao_s": round(o.duracao, 3),
            "narracao_sha256": o.sha256, "narracao_wav_usado": str(self.narracao_wav),
            "narracao_tratada": self.narracao_tratada,
            "roteiro": str(self.roteiro), "transcricao": str(self.transcricao) if self.transcricao else None,
            "musicas": [str(p) for p in self.musicas], "efeitos": [str(p) for p in self.efeitos],
            "imagens_usuario": [str(p) for p in self.imagens_usuario],
        }


def sha256_arquivo(caminho: Path, bloco: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        while True:
            dados = f.read(bloco)
            if not dados:
                break
            h.update(dados)
    return h.hexdigest()


def sondar(caminho: Path) -> InfoMidia:
    if not caminho.is_file():
        raise ErroProducao(f"Arquivo não encontrado: {caminho}")
    if caminho.stat().st_size == 0:
        raise ErroProducao(f"Arquivo vazio: {caminho}")
    info = ffprobe_json(caminho)
    streams = info.get("streams", [])
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if audio is None:
        raise ErroProducao(f"O arquivo não tem faixa de áudio: {caminho}")
    duracao = float(info.get("format", {}).get("duration") or audio.get("duration") or 0)
    if duracao <= 0:
        raise ErroProducao(f"Não foi possível determinar a duração de: {caminho}")
    return InfoMidia(
        caminho=caminho, duracao=duracao,
        tem_video=any(s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")
                      for s in streams),
        tem_audio=True,
        taxa_amostragem=int(audio["sample_rate"]) if audio.get("sample_rate") else None,
        canais=audio.get("channels"), codec_audio=audio.get("codec_name"),
        sha256=sha256_arquivo(caminho),
    )


# ------------------------------------------------------------ descoberta ---

def _listar(pasta: Path, extensoes: set[str]) -> list[Path]:
    if not pasta or not pasta.is_dir():
        return []
    return sorted(p for p in pasta.rglob("*") if p.is_file() and p.suffix.lower() in extensoes)


def candidatos_narracao(pasta: Path) -> list[Path]:
    """Ordem de preferência: WAV tratado > outro áudio > vídeo com áudio."""
    achados = _listar(pasta, EXT_AUDIO | EXT_VIDEO)
    achados = [p for p in achados if "mix-final" not in p.name.lower() and "-mix-" not in p.name.lower()]

    def chave(p: Path):
        n = p.name.lower()
        return (0 if "narracao-tratada" in n and p.suffix.lower() == ".wav" else
                1 if p.suffix.lower() in EXT_AUDIO else 2, p.name)
    return sorted(achados, key=chave)


def candidatos_roteiro(pasta: Path) -> list[Path]:
    txts = [p for p in _listar(pasta, {".txt", ".md"})]
    com_marca = [p for p in txts if MARCA_INICIO in p.read_text(encoding="utf-8", errors="ignore")]
    return com_marca or sorted(txts, key=lambda p: -p.stat().st_size)


def candidatos_transcricao(pasta: Path) -> list[Path]:
    return _listar(pasta, {".vtt", ".srt"})


def _escolher(candidatos: list[Path], rotulo: str, interativo: bool) -> Path:
    if not candidatos:
        raise ErroProducao(f"Nenhum arquivo de {rotulo} encontrado. Informe o caminho com --{rotulo}.")
    if len(candidatos) == 1 or not interativo:
        if len(candidatos) > 1:
            log().info("Vários arquivos de %s; usando %s (use --interativo para escolher).", rotulo, candidatos[0].name)
        return candidatos[0]
    print(f"\nEscolha o arquivo de {rotulo}:")
    for i, c in enumerate(candidatos, 1):
        print(f"  {i}) {c}")
    while True:
        resp = input("Número: ").strip()
        if resp.isdigit() and 1 <= int(resp) <= len(candidatos):
            return candidatos[int(resp) - 1]


def ingerir(cfg: Config, pasta_entrada: Path | None = None) -> Entradas:
    """Localiza e valida todas as entradas. `pasta_entrada` ativa a detecção automática."""
    exigir_ferramenta("ffmpeg")
    exigir_ferramenta("ffprobe")
    base = pasta_entrada

    narracao = cfg.narracao
    if narracao is None:
        narracao = _escolher(candidatos_narracao(base) if base else [], "narracao", cfg.interativo)
    roteiro = cfg.roteiro
    if roteiro is None:
        roteiro = _escolher(candidatos_roteiro(base) if base else [], "roteiro", cfg.interativo)
    transcricao = cfg.transcricao
    if transcricao is None and base:
        c = candidatos_transcricao(base)
        transcricao = _escolher(c, "transcricao", cfg.interativo) if c else None
    if not roteiro.is_file():
        raise ErroProducao(f"Roteiro não encontrado: {roteiro}")
    if transcricao is not None and not transcricao.is_file():
        raise ErroProducao(f"Transcrição não encontrada: {transcricao}")

    info = sondar(narracao)
    log().info("Narração: %s (%.1fs, %s Hz, %s canais, vídeo=%s)", narracao.name, info.duracao,
               info.taxa_amostragem, info.canais, info.tem_video)

    tratada = "narracao-tratada" in narracao.name.lower()
    pasta_in = cfg.pasta(PASTAS["entrada"])
    wav = _preparar_wav(info, pasta_in)

    return Entradas(
        narracao_original=info, narracao_wav=wav, narracao_tratada=tratada,
        roteiro=roteiro, transcricao=transcricao,
        musicas=_listar(cfg.pasta_musica, EXT_MUSICA) if cfg.pasta_musica else [],
        efeitos=_listar(cfg.pasta_efeitos, EXT_MUSICA) if cfg.pasta_efeitos else [],
        imagens_usuario=_listar(cfg.pasta_imagens, {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"})
        if cfg.pasta_imagens else [],
    )


def _preparar_wav(info: InfoMidia, pasta_in: Path) -> Path:
    """WAV 48 kHz estéreo 24 bits usado como referência temporal.

    Se o original já for um WAV 48 kHz, ele é usado diretamente (sem cópia).
    Caso contrário, o áudio é extraído sem nenhum processamento além de
    conversão de formato; a conversão preserva a duração.
    """
    c = info.caminho
    if c.suffix.lower() == ".wav" and info.taxa_amostragem == 48000 and (info.canais or 0) in (1, 2):
        return c
    destino = pasta_in / f"{c.stem}-narracao-48k24.wav"
    if destino.is_file() and destino.stat().st_mtime >= c.stat().st_mtime and destino.stat().st_size > 1000:
        log().info("Reutilizando narração extraída: %s", destino.name)
        return destino
    log().info("Extraindo a narração para WAV 48 kHz/24 bits (sem filtros)...")
    executar(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", c, "-vn", "-map", "0:a:0",
              "-ar", "48000", "-c:a", "pcm_s24le", destino])
    return destino


def conferir_originais(entradas: Entradas) -> dict:
    """Confere se os arquivos originais continuam idênticos (hash)."""
    resultado = {}
    for rotulo, caminho, esperado in [("narracao", entradas.narracao_original.caminho, entradas.narracao_original.sha256)]:
        atual = sha256_arquivo(caminho)
        resultado[rotulo] = {"arquivo": str(caminho), "inalterado": atual == esperado, "sha256": atual}
    return resultado


def salvar_manifesto(cfg: Config, entradas: Entradas) -> Path:
    destino = cfg.pasta(PASTAS["entrada"]) / "entradas.json"
    salvar_json(destino, entradas.para_dict())
    return destino
