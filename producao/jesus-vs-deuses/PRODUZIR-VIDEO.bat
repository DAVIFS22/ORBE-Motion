@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Jesus contra todos os deuses - Producao do video
rem Arraste a NARRACAO (mp3/wav/mp4) sobre este arquivo, ou de dois cliques e informe o caminho.
rem Requer: Python 3.10+ (pip install numpy pillow), FFmpeg no PATH e, para as cenas 3D, o Blender (ou pip install bpy).
cd /d "%~dp0"

set "NARRACAO=%~1"
if "%NARRACAO%"=="" set /p NARRACAO=Caminho da narracao (mp3, wav ou mp4):
set "NARRACAO=%NARRACAO:"=%"

where ffmpeg >nul 2>nul || (echo FFmpeg nao encontrado no PATH. Instale em https://ffmpeg.org e tente de novo. & goto fim)
where python >nul 2>nul || (echo Python nao encontrado no PATH. & goto fim)

rem Qualidade 3D: teste ^| previa ^| padrao ^| alta  (padrao = 1280x720; alta = 1920x1080, bem mais lento)
if "%QUALIDADE_3D%"=="" set "QUALIDADE_3D=padrao"
rem Maximo de minutos de render 3D (estimados). Vazio = sem limite.
if "%ORCAMENTO_3D%"=="" set "ORCAMENTO_3D=90"

python -m motor_video produzir ^
  --narracao "%NARRACAO%" ^
  --roteiro "entrada\prompt_narracao_e_producao_jesus.txt" ^
  --transcricao "entrada\lv_0_20261017144122.vtt" ^
  --saida "saida\producao" ^
  --prioridade-3d 2 --qualidade-3d %QUALIDADE_3D% --orcamento-3d %ORCAMENTO_3D% ^
  %2 %3 %4 %5 %6 %7 %8 %9

:fim
echo.
echo Para cancelar uma producao em andamento, crie o arquivo CANCELAR.txt dentro da pasta saida\producao.
pause
