"""Codificação e validação de WAV PCM (RIFF/WAVE) sem depender de bibliotecas externas.

O áudio sintetizado é Float32 (-1..1). A exportação para PCM 24 bits é feita aqui, de forma explícita: cabeçalho completo (canais,
taxa, bytes por segundo, alinhamento, tamanhos), quantização com dither TPDF determinístico (semente fixa) e conferência final do
arquivo (formato, duração, integridade). `validar_wav` serve para qualquer WAV do projeto.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

from .config import ErroProducao

BLOCO = 1 << 20


def cabecalho(canais: int, taxa: int, bits: int, quadros: int, float_: bool = False) -> bytes:
    bps = bits // 8
    dados = quadros * canais * bps
    fmt = struct.pack("<HHIIHH", 3 if float_ else 1, canais, taxa, taxa * canais * bps, canais * bps, bits)
    if float_:
        fmt += struct.pack("<H", 0)
    extra = b"fact" + struct.pack("<II", 4, quadros) if float_ else b""
    corpo = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + extra + b"data" + struct.pack("<I", dados)
    return b"RIFF" + struct.pack("<I", len(corpo) + dados) + corpo        # tamanho do RIFF = tudo depois dos 8 primeiros bytes


def escrever_wav(destino: Path, x, taxa: int = 48000, bits: int = 24, dither: bool = True, semente: int = 7) -> dict:
    """Grava `x` (N×canais float32, array ou memmap) como WAV PCM `bits` (16/24) com dither TPDF; devolve o cabeçalho lido de volta."""
    n, canais = x.shape
    destino.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(semente)
    with open(destino, "wb") as f:
        f.write(cabecalho(canais, taxa, bits, n))
        for i in range(0, n, BLOCO):
            b = np.asarray(x[i:i + BLOCO], dtype=np.float64)
            if bits == 24:
                m = 8388607.0
                d = (rng.random(b.shape) - rng.random(b.shape)) if dither else 0.0
                q = np.clip(np.rint(np.clip(b, -1, 1) * m + d), -m - 1, m).astype(np.int32)
                u = np.stack([q & 0xFF, (q >> 8) & 0xFF, (q >> 16) & 0xFF], axis=-1).astype(np.uint8)
                f.write(u.tobytes())
            elif bits == 16:
                d = (rng.random(b.shape) - rng.random(b.shape)) if dither else 0.0
                f.write(np.clip(np.rint(np.clip(b, -1, 1) * 32767.0 + d), -32768, 32767).astype("<i2").tobytes())
            else:
                raise ErroProducao(f"Formato de exportação não suportado: {bits} bits")
    info = ler_cabecalho(destino)
    if info["quadros"] != n or info["canais"] != canais or info["taxa"] != taxa or info["bits"] != bits:
        raise ErroProducao(f"WAV gravado não confere com o pedido: {info}")
    return info


def ler_cabecalho(caminho: Path) -> dict:
    tam = caminho.stat().st_size
    with open(caminho, "rb") as f:
        cab = f.read(12)
        if cab[:4] != b"RIFF" or cab[8:12] != b"WAVE":
            raise ErroProducao(f"{caminho.name} não é um WAV (RIFF/WAVE).")
        fmt = None
        while True:
            c = f.read(8)
            if len(c) < 8:
                raise ErroProducao(f"{caminho.name}: bloco 'data' ausente.")
            nome, n = c[:4], struct.unpack("<I", c[4:])[0]
            if nome == b"fmt ":
                d = f.read(n)
                tag, canais, taxa, byte_rate, alinh, bits = struct.unpack("<HHIIHH", d[:16])
                fmt = {"formato": {1: "PCM", 3: "float", 0xFFFE: "extensível"}.get(tag, str(tag)), "tag": tag, "canais": canais, "taxa": taxa,
                       "byte_rate": byte_rate, "alinhamento": alinh, "bits": bits}
                if n & 1:
                    f.read(1)
            elif nome == b"data":
                dados = n if n < 0xFFFFFFF0 else tam - f.tell()
                fmt.update({"offset": f.tell(), "bytes": dados, "arquivo_bytes": tam, "quadros": dados // max(1, fmt["alinhamento"]), "duracao_s": dados / max(1, fmt["byte_rate"])})
                return fmt
            else:
                f.seek(n + (n & 1), 1)


def validar_wav(caminho: Path, duracao_esperada: float | None = None, taxa: int = 48000, canais: int = 2, bits: int | None = 24,
                tol_s: float = 0.05) -> dict:
    """Confere cabeçalho (taxa, canais, bits, byte rate, alinhamento, tamanhos) e duração; devolve {ok, problemas, info}."""
    probs: list[str] = []
    info: dict = {}
    try:
        info = ler_cabecalho(caminho)
    except (ErroProducao, OSError, struct.error) as e:
        return {"ok": False, "problemas": [str(e)], "info": {}}
    if info["taxa"] != taxa:
        probs.append(f"taxa {info['taxa']} Hz (esperado {taxa})")
    if info["canais"] != canais:
        probs.append(f"{info['canais']} canais (esperado {canais})")
    if bits is not None and info["bits"] != bits:
        probs.append(f"{info['bits']} bits (esperado {bits})")
    if info["alinhamento"] != info["canais"] * info["bits"] // 8 or info["byte_rate"] != info["taxa"] * info["alinhamento"]:
        probs.append("alinhamento/byte rate inconsistentes no cabeçalho")
    if info["offset"] + info["bytes"] > info["arquivo_bytes"]:
        probs.append("arquivo truncado: o bloco 'data' declara mais bytes do que existem")
    if info["bytes"] % max(1, info["alinhamento"]):
        probs.append("tamanho dos dados não é múltiplo do quadro")
    if duracao_esperada is not None and abs(info["duracao_s"] - duracao_esperada) > tol_s:
        probs.append(f"duração {info['duracao_s']:.3f} s (esperado {duracao_esperada:.3f} s)")
    return {"ok": not probs, "problemas": probs, "info": info}
