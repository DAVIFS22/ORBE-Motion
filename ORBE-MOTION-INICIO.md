# ORBE Motion — primeira base de desenvolvimento

O ORBE Motion é o nome e a identidade pública desta nova aplicação de motion graphics e composição.

## Estado desta entrega

- Janela principal identificada como **ORBE Motion**.
- Texto de ajuda/tooltip da marca atualizado para **Sobre o ORBE Motion**.
- A arquitetura funcional existente foi mantida para evitar uma renomeação indiscriminada que quebre módulos e dependências.
- Este pacote ainda é uma primeira etapa de rebranding, não uma versão final nem uma compilação validada.

## Compilar no Windows

Requisitos declarados pelo projeto: Rust toolchain compatível com Rust 1.95+ e dependências necessárias para compilar wgpu/eframe.

Na pasta que contém `Cargo.toml`, execute:

```powershell
cargo run --release -p orbe
```

O nome interno do pacote Cargo continua `orbe` nesta etapa para preservar as referências do workspace. A próxima etapa pode migrar o pacote/binário e a identidade visual por partes, validando cada alteração.

## Licenças e proveniência

Esta base inclui código de terceiros sob licenças MIT e Apache-2.0. Preserve `LICENSE-MIT`, `LICENSE-APACHE`, `NOTICE`, `ATTRIBUTION.md` e avisos de componentes/ativos. O nome ORBE Motion identifica a distribuição derivada, mas não apaga autoria ou obrigações de licença.
