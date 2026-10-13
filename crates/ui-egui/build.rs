//! Build script do ORBE Motion.
//! Não depende de arquivos externos de colaboradores ou modelos.

use std::path::PathBuf;

fn main() {
    println!("cargo:rerun-if-changed=build.rs");

    let out_dir = match std::env::var_os("OUT_DIR") {
        Some(dir) => PathBuf::from(dir),
        None => {
            println!("cargo:warning=OUT_DIR não está definido.");
            return;
        }
    };

    let output_file = out_dir.join("credits.rs");

    let generated_code = r#"
pub static TOTAL_COMMITS: u64 = 0;
pub static CONTRIBUTORS: &[Contributor] = &[];
pub static MODELS: &[Model] = &[];
"#;

    if let Err(error) = std::fs::write(&output_file, generated_code) {
        println!(
            "cargo:warning=Não foi possível gerar {}: {}",
            output_file.display(),
            error
        );
    }
}