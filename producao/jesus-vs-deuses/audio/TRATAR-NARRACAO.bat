@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Jesus contra todos os deuses - Tratamento da narracao
rem Arraste um video/audio sobre este arquivo, ou de dois cliques para usar o caminho padrao.
if "%~1"=="" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tratar-narracao.ps1"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tratar-narracao.ps1" -Entrada "%~1"
)
echo.
pause
