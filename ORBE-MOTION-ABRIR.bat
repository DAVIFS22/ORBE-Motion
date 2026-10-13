@echo off
setlocal EnableExtensions
chcp 65001 >nul
title ORBE Motion - Iniciar aplicativo
cd /d "%~dp0"
color 0B

echo ========================================================
echo              ORBE MOTION - INICIAR
echo ========================================================
echo.

where cargo >nul 2>&1
if errorlevel 1 (
  echo [ERRO] Rust/Cargo nao foi encontrado.
  echo Instale o Rust em https://rustup.rs/ e reinicie o Windows.
  goto :erro
)

if not exist "Cargo.toml" (
  echo [ERRO] Cargo.toml nao encontrado.
  echo Extraia a pasta ORBE-Motion inteira e execute este arquivo dentro dela.
  goto :erro
)

echo [1/2] Preparando e compilando o aplicativo para Windows...
echo A primeira execucao pode demorar e baixar dependencias.
echo.
cargo build --release -p orbe-motion
if errorlevel 1 goto :erro

if not exist "target\release\orbe-motion.exe" (
  echo [ERRO] A compilacao terminou, mas orbe-motion.exe nao foi encontrado.
  goto :erro
)

echo.
echo [2/2] Abrindo ORBE Motion...
echo.
start "ORBE Motion" "%~dp0target\release\orbe-motion.exe"
if errorlevel 1 goto :erro
 echo [OK] O aplicativo foi iniciado.
 echo Esta janela pode ser fechada.
 timeout /t 3 /nobreak >nul
exit /b 0

:erro
echo.
echo [FALHA] Nao foi possivel iniciar o ORBE Motion.
echo Leia a mensagem de erro acima e envie uma foto ou copie o texto.
echo.
pause
exit /b 1
