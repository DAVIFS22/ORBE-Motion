#!/usr/bin/env python3
"""Divide um MP4 em partes tocáveis, SEM recodificar, cada uma abaixo de um limite de tamanho (ex.: 400 MiB do envio).

Os cortes caem em keyframes, escolhidos pelo tamanho real dos pacotes (ffprobe), então nenhuma parte passa do limite.
Verifica no fim: soma dos quadros de vídeo das partes == quadros do original, e cada parte demuxa sem erro.

Uso:  python3 dividir_para_envio.py ORIGINAL.mp4 PASTA_SAIDA [--limite-mib 375] [--prefixo NOME] [--so-planejar]
"""
import argparse, csv, io, pathlib, subprocess, sys

def pacotes(arq):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "packet=stream_index,pts_time,size,flags", "-of", "csv=p=0", arq],
                         capture_output=True, text=True, check=True).stdout
    pk = [(float(r[1]), int(r[0]), int(r[2]), "K" in r[3]) for r in csv.reader(io.StringIO(out)) if len(r) >= 4 and r[1] not in ("", "N/A")]
    return sorted(pk)

def cortes(pk, limite):
    res, acc, ultimo_k, acc_no_k = [], 0, 0.0, 0
    for t, s, sz, k in pk:
        if s == 0 and k:
            ultimo_k, acc_no_k = t, acc
        acc += sz
        if acc > limite and ultimo_k > (res[-1] if res else 0):
            res.append(ultimo_k); acc -= acc_no_k
    return res

def quadros(arq):
    return int(subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v", "-show_entries", "stream=nb_read_packets",
                               "-of", "csv=p=0", arq], capture_output=True, text=True, check=True).stdout.strip())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("original"); ap.add_argument("saida")
    ap.add_argument("--limite-mib", type=float, default=375.0, help="margem abaixo do limite real (400 MiB) para o contêiner MP4")
    ap.add_argument("--prefixo", default=None); ap.add_argument("--so-planejar", action="store_true")
    a = ap.parse_args()
    orig = pathlib.Path(a.original).resolve(); saida = pathlib.Path(a.saida); prefixo = a.prefixo or orig.stem
    c = cortes(pacotes(str(orig)), a.limite_mib * 1024 * 1024)
    print(f"{len(c) + 1} partes; cortes (s): {', '.join(f'{x:.3f}' for x in c)}")
    if a.so_planejar:
        return 0
    saida.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(orig), "-map", "0", "-c", "copy", "-f", "segment",
                    "-segment_times", ",".join(f"{x:.3f}" for x in c), "-segment_format", "mp4", "-segment_format_options", "movflags=+faststart",
                    "-reset_timestamps", "1", "-segment_start_number", "1", str(saida / f"{prefixo}_parte%02d.mp4")], check=True)
    partes = sorted(saida.glob(f"{prefixo}_parte*.mp4")); soma = 0; ok = True
    for p in partes:
        mib = p.stat().st_size / 2**20; n = quadros(str(p)); soma += n
        erro = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-map", "0", "-c", "copy", "-f", "null", "-"], capture_output=True, text=True).stderr.strip()
        ok &= (mib < a.limite_mib + 20) and not erro
        print(f"{p.name}  {mib:6.1f} MiB  {n} quadros  {'ERRO: ' + erro[:80] if erro else 'íntegra'}")
    total = quadros(str(orig)); ok &= soma == total
    print(f"quadros: partes {soma} / original {total} -> {'OK' if ok else 'FALHOU'}")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
