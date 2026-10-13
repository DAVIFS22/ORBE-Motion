@echo off
setlocal EnableExtensions
chcp 65001 >nul
title ORBE Motion - Verificação técnica
cd /d "%~dp0"
color 0B

echo ========================================================
echo             ORBE MOTION - VERIFICACAO
echo ========================================================
echo.

echo [1/4] Verificando se o Rust/Cargo esta instalado...
where cargo >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Cargo nao foi encontrado no PATH.
    echo Instale o Rust pelo site oficial: https://rustup.rs/
    echo Depois feche e abra novamente esta janela.
    goto :fim_erro
)
cargo --version
echo.

echo [2/4] Verificando formatacao do codigo...
cargo fmt --all -- --check
if errorlevel 1 (
    echo [AVISO] A verificacao de formatacao encontrou diferencas.
    set "FORMAT_WARN=1"
) else (
    echo [OK] Formatacao verificada.
)
echo.

echo [3/4] Verificando compilacao do workspace...
cargo check --workspace
if errorlevel 1 goto :erro_compilacao
echo [OK] cargo check concluido.
echo.

echo [4/4] Executando testes do workspace...
cargo test --workspace
if errorlevel 1 goto :erro_testes

echo.
echo ========================================================
echo VERIFICACAO CONCLUIDA: compilacao e testes passaram.
if defined FORMAT_WARN echo ATENCAO: revise tambem a formatacao indicada acima.
echo ========================================================
goto :fim

:erro_compilacao
echo.
echo [FALHA] A compilacao falhou. Copie a mensagem de erro completa.
goto :fim_erro

:erro_testes
echo.
echo [FALHA] Um ou mais testes falharam. Copie a mensagem completa.
goto :fim_erro

:fim_erro
echo.
echo Nenhum arquivo foi alterado por este verificador.
:fim
echo.
echo Pressione qualquer tecla para fechar esta janela.
pause >nul
endlocal
