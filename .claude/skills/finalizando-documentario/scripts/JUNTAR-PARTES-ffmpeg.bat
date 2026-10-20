@echo off
setlocal EnableExtensions DisableDelayedExpansion
title Juntar o documentario - Jesus contra todos os deuses
set "BASE=JESUS_CONTRA_TODOS_OS_DEUSES_FINAL_1080P"
set "SAIDA=%BASE%.mp4"
set "NUMS=01 02 03 04 05 06 07 08 09 10 11 12 13 14 15"
set "LISTA=lista_juntar_partes.txt"
set "AQUI=%~dp0."
for %%a in ("%AQUI%") do set "AQUI=%%~fa"
set "DL=%USERPROFILE%\Downloads"
for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "(New-Object -ComObject Shell.Application).NameSpace('shell:Downloads').Self.Path" 2^>nul`) do if exist "%%p\" set "DL=%%p"
echo.
echo  ==============================================================
echo    JESUS CONTRA TODOS OS DEUSES  -  juntar as 15 partes do video
echo  ==============================================================
echo.

rem ---- 1. FFmpeg: procura ao lado deste arquivo, na pasta acima, em Downloads ou instalado
set "FF="
for %%d in ("%AQUI%" "%AQUI%\.." "%DL%" "%DL%\JUNTAR-VIDEO-WINDOWS") do if not defined FF if exist "%%~d\ffmpeg.exe" set "FF=%%~fd\ffmpeg.exe"
if not defined FF for /f "delims=" %%p in ('where ffmpeg 2^>nul') do if not defined FF set "FF=%%p"
if not defined FF goto semff

rem ---- 2. Pasta das 15 partes: a que foi arrastada para cima deste arquivo, esta pasta,
rem         a pasta acima, Downloads, Area de Trabalho, Videos
set "PASTA="
if "%~1"=="" goto procura
if exist "%~1\" call :testa "%~f1"
if not defined PASTA call :testa "%~dp1."
:procura
for %%d in ("%AQUI%" "%AQUI%\.." "%DL%" "%USERPROFILE%\Desktop" "%USERPROFILE%\Videos" "%USERPROFILE%\OneDrive\Downloads" "%USERPROFILE%\OneDrive\Desktop") do if not defined PASTA call :testa "%%~fd"
if not defined PASTA goto faltam

rem ---- 3. Lista na ordem 01 a 15 e juncao sem recodificar
cd /d "%PASTA%"
type nul > "%LISTA%" 2>nul
if not exist "%LISTA%" goto semescrita
for %%i in (%NUMS%) do call :linha %%i
echo  As 15 partes foram encontradas em:
echo    %PASTA%
echo.
echo  Juntando SEM perder qualidade (copia direta, sem recodificar)...
echo  Leva de 1 a 3 minutos. NAO feche esta janela.
echo.
"%FF%" -hide_banner -loglevel error -stats -y -f concat -safe 0 -i "%LISTA%" -map 0 -c copy -movflags +faststart "%SAIDA%"
set "ERRO=%errorlevel%"
del "%LISTA%" >nul 2>nul
if not "%ERRO%"=="0" goto falhou
if not exist "%SAIDA%" goto falhou
echo.
echo  ==============================================================
echo    PRONTO. O video completo foi criado:
echo    %PASTA%\%SAIDA%
echo    (29 min 16 s, 1920x1080, cerca de 5,6 GB)
echo  ==============================================================
echo.
echo  Depois de conferir o video, as 15 partes podem ser apagadas.
start "" explorer /select,"%PASTA%\%SAIDA%"
echo.
pause
exit /b 0

rem ---- sub-rotinas -------------------------------------------------------
:testa
if defined PASTA exit /b
set "T=%~f1"
set "N=0"
for %%i in (%NUMS%) do call :conta %%i
if "%N%"=="15" set "PASTA=%T%"
exit /b

:conta
set "ACHOU="
if exist "%T%\%BASE%_parte%1.mp4" set "ACHOU=1"
if not defined ACHOU for %%f in ("%T%\*parte%1*.mp4") do set "ACHOU=1"
if defined ACHOU set /a N+=1
exit /b

:linha
set "ARQ="
if exist "%BASE%_parte%1.mp4" set "ARQ=%BASE%_parte%1.mp4"
if not defined ARQ for %%f in ("*parte%1*.mp4") do if not defined ARQ set "ARQ=%%~nxf"
>> "%LISTA%" echo file '%ARQ%'
exit /b

rem ---- mensagens de erro --------------------------------------------------
:semff
echo  ERRO: nao encontrei o ffmpeg.exe.
echo  Ele vem dentro do JUNTAR-VIDEO-WINDOWS.zip. Extraia o zip e deixe o ffmpeg.exe
echo  na mesma pasta deste arquivo .bat (ou na pasta Downloads).
echo.
pause
exit /b 1

:faltam
echo  ERRO: nao encontrei as 15 partes do video juntas numa mesma pasta.
echo.
echo  Procurei nestas pastas:
echo    %AQUI%
echo    %DL%
echo    %USERPROFILE%\Desktop
echo    %USERPROFILE%\Videos
echo.
echo  Videos .mp4 que existem na pasta Downloads:
dir /b "%DL%\*.mp4" 2>nul
echo.
echo  COMO RESOLVER: coloque as 15 partes numa mesma pasta e ARRASTE essa pasta
echo  com o mouse para cima do arquivo JUNTAR-PARTES.bat (solte em cima dele).
echo.
pause
exit /b 1

:semescrita
echo  ERRO: nao foi possivel gravar na pasta das partes:
echo    %PASTA%
echo  Mova as 15 partes para a pasta Downloads e tente de novo.
echo.
pause
exit /b 1

:falhou
echo.
echo  ERRO: a juncao nao terminou. Causas mais comuns:
echo   - falta espaco no disco (precisa de pelo menos 6 GB livres);
echo   - alguma parte nao foi baixada por completo (baixe-a de novo).
echo.
pause
exit /b 1
