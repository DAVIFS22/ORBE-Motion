#!/bin/sh
# Monta JUNTAR-VIDEO-WINDOWS.zip (ffmpeg.exe oficial + JUNTAR-PARTES-ffmpeg.bat) para juntar partes MP4 tocáveis
# (as de dividir_para_envio.py) no Windows sem instalar nada. Confere o SHA-256 do FFmpeg antes de empacotar.
# Uso: sh montar_kit_windows.sh PASTA_SAIDA      (o .bat espera nomes BASE_parteNN.mp4; ajuste BASE e NUMS nele se mudar)
set -eu
OUT=$(cd "$1" && pwd); AQUI=$(cd "$(dirname "$0")" && pwd); TMP=$(mktemp -d)
Z=ffmpeg-n8.1-latest-win64-lgpl-8.1.zip; URL=https://github.com/BtbN/FFmpeg-Builds/releases/download/latest
cd "$TMP"
curl -sSL -o checksums.sha256 "$URL/checksums.sha256"
curl -sSL -o "$Z" "$URL/$Z"
grep " $Z\$" checksums.sha256 | sha256sum -c -
unzip -q -j "$Z" "${Z%.zip}/bin/ffmpeg.exe" "${Z%.zip}/LICENSE.txt"
cp "$AQUI/JUNTAR-PARTES-ffmpeg.bat" JUNTAR-PARTES.bat
mv LICENSE.txt LICENCA-FFMPEG.txt
python3 - "$OUT/JUNTAR-VIDEO-WINDOWS.zip" <<'PY'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1], "w", zipfile.ZIP_DEFLATED, compresslevel=9) as f:
    for n in ["JUNTAR-PARTES.bat", "ffmpeg.exe", "LICENCA-FFMPEG.txt"]: f.write(n, n)
PY
rm -rf "$TMP"; ls -la "$OUT/JUNTAR-VIDEO-WINDOWS.zip"
