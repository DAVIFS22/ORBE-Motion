"""Cenários 3D estáticos (stills) como fundo dos planos: substituem os cenários genéricos gerados por código.

Cada still é um quadro de uma cena Three.js (motion/comps/cena3d_*.js) renderizado uma vez em 2400×1350, sem textos, com o
mesmo motor determinístico dos clipes. O compositor faz o movimento de câmera 2D por cima, como em qualquer imagem. A escolha
depende do contexto (seção do filme + cenário que o storyboard pedia) e gira entre variações para não repetir o mesmo quadro
em planos vizinhos. Todos são RECONSTRUÇÕES ARTÍSTICAS (o crédito na linha do tempo diz isso).

Os stills ficam em cache pelo hash do código da composição e dos parâmetros: só o que mudou é renderizado de novo.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import ErroProducao, log, salvar_json

LARGURA, ALTURA = 2400, 1350


@dataclass(frozen=True)
class Still:
    comp: str
    vista: str
    f: float            # posição no trilho de câmera (0–1)
    seed: int
    descricao: str

    def params(self) -> dict:
        return {"vista": self.vista, "hud": {"desligado": True}}


_GAL = "mar da Galileia (paisagem artística, não é um ponto exato da margem)"
_GOL = "colina das cruzes (reconstrução artística; local exato e forma das cruzes incertos)"
_TUM = "túmulo escavado na rocha do tipo usado na Judeia do século I (reconstrução artística; não é o local histórico)"
_ESC = "rolo e lamparina (composição artística; a escrita do rolo é estilizada, não é um manuscrito real)"
_JUD = "aldeia da Galileia do século I (reconstrução artística; não representa um sítio específico)"
_RUI = "ruínas de um santuário dórico (composição artística genérica; não é um sítio específico)"
_EGI = "salão hipostilo inspirado em Karnak (reconstrução artística; inscrições e cores estilizadas)"
_GRE = "templo dórico inspirado no Templo de Zeus em Olímpia (reconstrução artística; sem policromia nem esculturas)"
_FIO = "fiorde nórdico (paisagem artística; não é um local real nem mostra o evento mitológico)"

_BASE = {   # (comp, vista, descrição) -> posições no trilho; cada posição vira um still diferente (outro ponto de vista)
    "galileia_lago": ("cena3d_galileia", "lago", _GAL, (0.05, 0.25, 0.45, 0.65, 0.85, 1.0)),
    "galileia_margem": ("cena3d_galileia", "margem", _GAL, (0.15, 0.55, 0.95)),
    "galileia_colinas": ("cena3d_galileia", "colinas", _GAL, (0.2, 0.6, 1.0)),
    "galileia_noite": ("cena3d_galileia", "noite", _GAL + ", à noite", (0.05, 0.3, 0.55, 0.8, 1.0)),
    "galileia_colinas_noite": ("cena3d_galileia", "colinas_noite", _GAL + ", à noite, vista da encosta", (0.05, 0.35, 0.65, 1.0)),
    "golgota_tempestade": ("cena3d_golgota", "tempestade", _GOL, (0.2, 0.5, 0.75, 1.0)),
    "golgota_amanhecer": ("cena3d_golgota", "amanhecer", _GOL + ", ao amanhecer", (0.05, 0.25, 0.45, 0.65, 0.85, 1.0)),
    "golgota_distante": ("cena3d_golgota", "distante", _GOL + ", com a muralha ao fundo", (0.2, 0.8)),
    "tumulo_interior": ("cena3d_tumulo", "interior", _TUM, (0.3, 0.7, 1.0)),
    "tumulo_saida": ("cena3d_tumulo", "saida", _TUM, (0.2, 0.6, 1.0)),
    "tumulo_exterior": ("cena3d_tumulo", "exterior", _TUM, (0.15, 0.5, 0.9)),
    "escritos_mesa": ("cena3d_escritos", "mesa", _ESC, (0.1, 0.4, 0.7, 1.0)),
    "escritos_lamparina": ("cena3d_escritos", "lamparina", _ESC, (0.2, 0.6, 1.0)),
    "escritos_rolo": ("cena3d_escritos", "rolo", _ESC, (0.2, 0.6, 1.0)),
    "judeia_viela": ("cena3d_judeia", "viela", _JUD, (0.15, 0.45, 0.75)),
    "judeia_telhados": ("cena3d_judeia", "telhados", _JUD, (0.2, 0.6, 1.0)),
    "grecia_ruinas": ("cena3d_grecia", "ruinas", _RUI, (0.1, 0.35, 0.6, 0.85, 1.0)),
    "egito_salao": ("cena3d_egito", "", _EGI, (0.25, 0.55, 0.85)),
    "grecia_templo": ("cena3d_grecia", "", _GRE, (0.15, 0.5, 0.85)),
    "fiorde": ("cena3d_fiorde", "", _FIO, (0.2, 0.5, 0.8)),
}
STILLS: dict[str, Still] = {f"{nome}_{k}": Still(comp, vista, f, 3 + 2 * k, desc)
                            for nome, (comp, vista, desc, fs) in _BASE.items() for k, f in enumerate(fs)}
VARIACOES = {nome: [f"{nome}_{k}" for k in range(len(v[3]))] for nome, v in _BASE.items()}

# (seção, cenário pedido) -> grupos de stills; (None, cenário) vale para qualquer seção. Cenários ausentes continuam como estão.
_LUZ = {
    "3-identidade": ["galileia_lago", "galileia_colinas_noite", "judeia_telhados", "escritos_lamparina", "galileia_noite"],
    "4-amor": ["galileia_margem", "galileia_colinas", "judeia_viela", "galileia_lago"],
    "5-morte": ["tumulo_interior", "golgota_amanhecer", "escritos_lamparina"],
    "6-crucificacao": ["golgota_tempestade", "golgota_distante", "escritos_mesa"],
    "7-ressurreicao": ["tumulo_saida", "golgota_amanhecer", "galileia_lago"],
    "8-comparacao": ["galileia_noite", "golgota_amanhecer", "tumulo_saida", "escritos_mesa"],
    "9-encerramento": ["galileia_lago", "galileia_colinas_noite", "golgota_amanhecer", "judeia_telhados", "galileia_noite"],
}
_GRUPOS: dict[tuple[str | None, str], list[str]] = {
    **{(s, "luz_dourada"): v for s, v in _LUZ.items()},
    (None, "pergaminho"): ["escritos_mesa", "escritos_rolo", "escritos_lamparina"],
    (None, "cosmos"): ["galileia_colinas_noite", "galileia_noite"],
    (None, "ceu_estrelado"): ["galileia_noite", "galileia_colinas_noite"],
    (None, "mar_galileia"): ["galileia_lago", "galileia_margem", "galileia_colinas"],
    (None, "aldeia"): ["judeia_viela", "judeia_telhados"],
    (None, "cruz_colina"): ["golgota_tempestade", "golgota_distante"],
    (None, "tumulo"): ["tumulo_interior", "tumulo_exterior", "tumulo_saida"],
    (None, "amanhecer"): ["golgota_amanhecer", "galileia_lago"],
    (None, "ruinas"): ["grecia_ruinas"],
    (None, "deserto_egito"): ["egito_salao"],
    ("6-crucificacao", "tempestade"): ["golgota_tempestade"],
    **{(s, "templo_grego"): ["grecia_templo"] for s in ("2-civilizacoes", "2c-grecia")},
    **{(s, "nordico"): ["fiorde"] for s in ("2-civilizacoes", "2d-nordicos")},
    ("2d-nordicos", "tempestade"): ["fiorde"],
    ("6-crucificacao", "roma_judeia"): ["golgota_distante"],
    ("7-ressurreicao", "roma_judeia"): ["golgota_distante"],
}


def _intercalar(grupos: list[str]) -> list[str]:
    """[a0, b0, c0, a1, b1, c1, ...]: alterna os lugares e, dentro de cada lugar, os pontos de vista."""
    listas = [VARIACOES[g] for g in grupos]
    return [l[i] for i in range(max(map(len, listas))) for l in listas if i < len(l)]


MAPA: dict[tuple[str | None, str], list[str]] = {k: _intercalar(v) for k, v in _GRUPOS.items()}
SECOES_JESUS = {"3-identidade", "4-amor", "5-morte", "6-crucificacao", "7-ressurreicao", "8-comparacao", "9-encerramento"}
SECOES_CIVILIZACOES = {"2-civilizacoes", "2b-egito", "2c-grecia", "2d-nordicos"}


def escolher(secao: str, motivo: str, contador: dict) -> str | None:
    """Still para um plano com cenário `motivo` na `secao` (gira entre as variações). Vale para as civilizações e para a parte
    sobre Jesus; a abertura mantém os cenários próprios (céu estrelado, tempestade, cosmos)."""
    if secao not in SECOES_JESUS | SECOES_CIVILIZACOES:                 # a abertura mantém os cenários próprios
        return None
    opcoes = MAPA.get((secao, motivo)) or MAPA.get((None, motivo))
    if not opcoes:
        return None
    k = (secao, motivo)
    i = contador.get(k, 0)
    contador[k] = i + 1
    return opcoes[i % len(opcoes)]


def chave(sid: str, codigo: str) -> str:
    s = STILLS[sid]
    dados = {"comp": s.comp, "params": s.params(), "f": s.f, "seed": s.seed, "w": LARGURA, "h": ALTURA, "codigo": codigo}
    return hashlib.sha1(json.dumps(dados, sort_keys=True).encode()).hexdigest()[:16]


def renderizar(motion, ids: list[str], pasta: Path, pasta_temp: Path, timeout_s: int = 3600) -> dict[str, Path]:
    """Renderiza (ou reaproveita) os stills pedidos; devolve {id: caminho do PNG}."""
    from .motion_bridge import hash_codigo
    pasta.mkdir(parents=True, exist_ok=True)
    pasta_temp.mkdir(parents=True, exist_ok=True)
    caminhos, pendentes = {}, []
    for sid in sorted(set(ids)):
        destino = pasta / f"{sid}-{chave(sid, hash_codigo(STILLS[sid].comp))}.png"
        caminhos[sid] = destino
        if not (destino.is_file() and destino.stat().st_size > 10_000):
            pendentes.append(sid)
    if not pendentes:
        return caminhos
    # todos os stills são tirados no instante T = 1 s: a duração do "clipe" posiciona a câmera no ponto f do trilho (f = T / dur)
    clipes = [{"id": sid, "comp": STILLS[sid].comp, "dur": round(1.0 / max(0.05, STILLS[sid].f), 4), "seed": STILLS[sid].seed,
               "params": STILLS[sid].params(), "saida": str(pasta / f"{sid}.mp4")} for sid in pendentes]
    spec = {"largura": LARGURA, "altura": ALTURA, "fps": 30, "clipes": clipes, "render3d": {"escala": 1.0, "msaa": True}}
    arq = pasta_temp / "stills-3d-spec.json"
    salvar_json(arq, spec)
    saida_png = pasta_temp / "stills-3d"
    cmd = [motion.node, str(motion.render), "--spec", str(arq), "--quadros", "1.0", "--png-dir", str(saida_png)]
    log().info("   [3D] renderizando %d still(s) de cenário (%dx%d)…", len(pendentes), LARGURA, ALTURA)
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path(motion.render).parent), timeout=timeout_s)
    if p.returncode != 0:
        raise ErroProducao("Falha ao renderizar os cenários 3D estáticos:\n" + (p.stdout + p.stderr)[-1500:])
    for sid in pendentes:
        gerado = saida_png / f"{sid}_t001000.png"
        if not gerado.is_file():
            raise ErroProducao(f"Still 3D {sid} não foi gerado.")
        gerado.replace(caminhos[sid])
    return caminhos


def aplicar(tl, motion, pasta: Path, pasta_temp: Path, limite: float | None = None) -> dict:
    """Troca os fundos marcados como still 3D pelos PNGs renderizados. Sem motor de motion, mantém o cenário original.
    Numa prévia (`limite`), só os planos do trecho renderizado ganham still; os demais voltam ao cenário original."""
    marcados = [p for p in tl.planos if p.fundo.get("tipo") == "still3d"]
    if limite is not None:
        for p in marcados:
            if p.inicio >= limite:
                p.fundo = dict(p.fundo["alternativa"])
        marcados = [p for p in marcados if p.inicio < limite]
    if not marcados:
        return {"stills": 0, "planos": 0}
    if motion is None:
        for p in marcados:
            p.fundo = dict(p.fundo["alternativa"])
        return {"stills": 0, "planos": 0, "aviso": "motor de motion indisponível: cenários procedurais mantidos"}
    caminhos = renderizar(motion, [p.fundo["still"] for p in marcados], pasta, pasta_temp)
    for p in marcados:
        sid = p.fundo["still"]
        p.fundo = {"tipo": "imagem", "arquivo": str(caminhos[sid].resolve()), "gerada": True, "still": sid}
        p.fonte = {"origem": "gerada por código (ORBE Motion, cena 3D)", "titulo": STILLS[sid].descricao, "autor": "ORBE Motion (código)",
                   "licenca": "obra própria, sem material de terceiros", "url": "",
                   "natureza": "cena 3D gerada por código: reconstrução artística, não é fotografia nem registro histórico", "gerada_por_codigo": True}
    return {"stills": len({p.fundo["still"] for p in marcados}), "planos": len(marcados)}
