$ErrorActionPreference = 'Stop'
Write-Host 'ORBE Motion - verificacao local' -ForegroundColor Cyan
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
  Write-Error 'Cargo nao encontrado. Instale Rust via rustup e reabra o terminal.'
  exit 1
}
Write-Host "Rust:" -ForegroundColor Cyan
rustc --version
cargo --version
Write-Host "1/4 cargo fmt" -ForegroundColor Cyan
cargo fmt --all -- --check
Write-Host "2/4 cargo check" -ForegroundColor Cyan
cargo check --workspace --all-targets
Write-Host "3/4 testes" -ForegroundColor Cyan
cargo test --workspace
Write-Host "4/4 build release" -ForegroundColor Cyan
cargo build --release -p orbe
Write-Host 'Verificacoes concluidas. Ainda execute testes manuais de interface, importacao e renderizacao.' -ForegroundColor Green
