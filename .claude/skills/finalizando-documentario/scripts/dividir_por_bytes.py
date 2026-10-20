#!/usr/bin/env python3
"""Divide um arquivo grande em pedaços binários (.001, .002, ...) abaixo do limite de envio e gera JUNTAR_FILME.bat,
que remonta o arquivo IDÊNTICO no Windows só com ferramentas nativas (copy /b + certutil), sem instalar nada.

Os pedaços NÃO tocam sozinhos (são bytes); use quando o objetivo é o arquivo único. Para partes assistíveis use
dividir_para_envio.py. O .bat confere tamanho de cada pedaço e o SHA-256 final do arquivo montado.

Uso:  python3 dividir_por_bytes.py ORIGINAL.mp4 PASTA_SAIDA [--mib 380] [--so-bat] [--parte N]
  --so-bat   gera só o .bat e o PARTES.sha256 (sem gravar pedaços)
  --parte N  grava só o pedaço N (para criar -> conferir -> enviar -> apagar, um por vez, quando falta disco)
"""
import argparse, hashlib, pathlib, sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("original"); ap.add_argument("saida")
    ap.add_argument("--mib", type=int, default=380); ap.add_argument("--so-bat", action="store_true"); ap.add_argument("--parte", type=int)
    a = ap.parse_args()
    orig = pathlib.Path(a.original); out = pathlib.Path(a.saida); out.mkdir(parents=True, exist_ok=True)
    tam, passo = orig.stat().st_size, a.mib * 1024 * 1024
    n = (tam + passo - 1) // passo; nome = orig.name
    pedacos = [f"{nome}.{i:03d}" for i in range(1, n + 1)]
    tams = [passo] * (n - 1) + [tam - passo * (n - 1)]
    hm, hp, linhas = hashlib.sha256(), [], []
    with open(orig, "rb") as f:
        for i, p in enumerate(pedacos, 1):
            h = hashlib.sha256(); restante = tams[i - 1]
            dest = open(out / p, "wb") if (not a.so_bat and (a.parte in (None, i))) else None
            while restante:
                bloco = f.read(min(restante, 8 << 20)); restante -= len(bloco); h.update(bloco); hm.update(bloco)
                if dest: dest.write(bloco)
            if dest: dest.close()
            linhas.append(f"{h.hexdigest()}  {p}")
    (out / "PARTES.sha256").write_text("\n".join(linhas) + "\n")
    H = hm.hexdigest()
    bat = ["@echo off", 'cd /d "%~dp0"', f"echo Conferindo as {n} partes..."]
    for p, s in zip(pedacos, tams):
        bat += [f'if not exist "{p}" (echo ERRO: falta o arquivo {p} & goto fim)',
                f'for %%A in ("{p}") do if not "%%~zA"=="{s}" (echo ERRO: {p} veio incompleto, baixe de novo & goto fim)']
    bat += ["echo Juntando as partes - pode levar alguns minutos...",
            f'copy /b /y {"+".join(pedacos)} "{nome}" >nul',
            "if errorlevel 1 (echo ERRO: falhou ao juntar - falta espaco em disco? & goto fim)",
            "echo Conferindo se ficou identico ao original...",
            f'certutil -hashfile "{nome}" SHA256 | findstr /i "{H}" >nul',
            "if errorlevel 1 (echo ERRO: o arquivo montado nao confere. Baixe as partes de novo. & goto fim)",
            "echo.", f"echo TUDO CERTO: {nome} esta identico ao original.", "echo Pode apagar os arquivos .001 em diante e este .bat.",
            ":fim", "pause"]
    texto = "\r\n".join(bat) + "\r\n"; texto.encode("ascii")          # .bat só com ASCII (sem acentos) e CRLF
    (out / "JUNTAR_FILME.bat").write_bytes(texto.encode("ascii"))
    print(f"{n} partes de até {a.mib} MiB; SHA-256 do original: {H}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
