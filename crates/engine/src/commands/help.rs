//! ORBE Motion help commands. External/community destinations are intentionally omitted.

use serde_json::{Value, json};
use super::{CommandSpec, always};
use crate::{Result, Session, cmd};

fn docs(s: &mut Session, p: &Value) -> Result<Value> {
    let page = match p.get("page").and_then(Value::as_str).unwrap_or("help") {
        "scripting" => "docs/control-protocol.md",
        "expressions" => "docs/expressions.md",
        "effects" => "docs/effects.md",
        "agents" => "docs/agents.md",
        _ => "README.md",
    };
    super::frontend(s, "help.openLocalDocs", &json!({"page":page}))
}

pub fn specs() -> Vec<CommandSpec> {
    vec![
        cmd!("help.docs", "ORBE Motion Help...", [], Some("F1"), "{page?: help|scripting|expressions|effects|agents}", always, docs),
        cmd!("help.inAppTutorials", "In-App Tutorials...", ["Help"], None, "{} → Home screen Learn tab", always, |s, p| super::frontend(s, "help.inAppTutorials", p)),
    ]
}
