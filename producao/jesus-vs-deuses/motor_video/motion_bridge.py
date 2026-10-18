"""Ponte com o motor de motion graphics (Node + Chromium + Three.js/GSAP): planeja, renderiza e aplica os clipes.

As composições (motion/comps/*.js) são funções puras do tempo: `window.seek(t)` desenha o quadro de t, sem estado entre
quadros. O Node (render.mjs) abre cada composição no Chromium, captura os quadros em qualquer ordem e codifica o clipe
em H.264 yuv420p CRF 16. Os clipes ficam em cache pelo conteúdo do pedido (parâmetros, imagem, código do motor).

Observação: o conector "Frame motion" da conta não estava habilitado nesta sessão (sem ferramentas expostas), então a
renderização usa este motor próprio, que segue o mesmo contrato. A interface `renderizar_clipes` é o ponto de troca.
"""

from __future__ import annotations

import copy
import hashlib
from functools import lru_cache
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import script_analyzer as sa
from .config import Config, ErroProducao, log, salvar_json
from .motion_conteudo import CONTEUDO

PASTA_MOTION = Path(__file__).resolve().parent.parent / "motion"
VERSAO_MOTION = "1.0.0"


class ErroMotion(ErroProducao):
    pass


@dataclass
class Motion:
    node: str
    versao_node: str
    render: Path


def localizar_motion() -> Motion | None:
    """Node + dependências instaladas (npm install em motion/) + Chromium utilizável; None se algo faltar."""
    node = shutil.which("node")
    if not node:
        log().info("Node.js não encontrado: motion graphics desativados (instale em nodejs.org).")
        return None
    try:
        ver = subprocess.run([node, "-v"], capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.match(r"v(\d+)", ver)
    if not m or int(m.group(1)) < 18:
        log().info("Node.js %s é antigo (precisa da versão 18 ou mais nova): motion graphics desativados.", ver)
        return None
    if not (PASTA_MOTION / "node_modules" / "playwright-core").is_dir():
        log().info("Dependências do motion ausentes: rode 'npm install' em %s.", PASTA_MOTION)
        return None
    try:
        r = subprocess.run([node, str(PASTA_MOTION / "render.mjs"), "--sonda"], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if "SONDA_OK" not in r.stdout:
        log().info("O Chromium não iniciou para o motion (%s). Veja 'npx playwright install chromium'.", (r.stderr or r.stdout)[-200:].strip())
        return None
    return Motion(node, ver, PASTA_MOTION / "render.mjs")


_ENGINE_3D = {"arq.js", "cena3d.js", "base3d.js", "tex.js"}


@lru_cache(maxsize=None)
def hash_codigo(comp: str | None = None) -> str:
    """Hash do código que afeta os pixels de uma composição (render, engine, a própria composição, dados, fontes).

    Mudar o código de uma cena 3D não invalida os clipes 2D e vice-versa; o código de áudio nunca invalida clipes de vídeo.
    Sem `comp`, abrange tudo (usado em testes)."""
    h = hashlib.sha1()
    for sub in ("render.mjs", "film.html", "package.json"):
        h.update((PASTA_MOTION / sub).read_bytes())
    tres_d = bool(comp) and comp.startswith("cena3d_")
    for d in ("engine", "comps", "data", "fonts"):
        for arq in sorted((PASTA_MOTION / d).glob("*")):
            if not arq.is_file():
                continue
            if comp:
                if d == "engine" and not tres_d and arq.name in _ENGINE_3D:
                    continue                                    # composições 2D não dependem do kit Three.js
                if d == "comps" and arq.stem != comp:
                    continue                                    # cada composição só depende do próprio arquivo (index.js só lista nomes)
            h.update(arq.name.encode())
            h.update(arq.read_bytes())
    return h.hexdigest()[:10]


@dataclass
class PedidoMotion:
    plano_id: str
    conteudo: str
    comp: str
    dur_visivel: float          # duração do plano
    t0: float                   # pré-rolagem: metade da transição de entrada
    t1: float                   # pós-rolagem: metade da transição de saída
    params: dict = field(default_factory=dict)
    imagem: str | None = None   # caminho absoluto da imagem usada pela composição
    seed: int = 1
    prioridade: int = 1
    status: str = "pendente"    # pendente | renderizado | reaproveitado | falhou
    clipe: str | None = None
    eventos: list = field(default_factory=list)
    tempo_real_s: float = 0.0
    detalhe: str = ""
    chave: str = ""

    @property
    def dur_clipe(self) -> float:
        return self.dur_visivel + self.t0 + self.t1


def semente(plano_id: str) -> int:
    return int(hashlib.sha1(("motion|" + plano_id).encode()).hexdigest()[:6], 16) % 9973 + 1


def tempo_da_palavra(al: sa.Alinhamento, ini: float, fim: float, palavra: str) -> float | None:
    """Instante (s) em que a palavra é dita dentro de [ini, fim], pelo alinhamento roteiro × transcrição."""
    alvo = sa.normalizar(palavra)
    for w, t in zip(al.normalizadas, al.t_ini):
        if w == alvo and ini - 0.05 <= t <= fim:
            return t
    return None


def linhas_da_frase(texto: str, plano, al: sa.Alinhamento | None) -> tuple[list[list[dict]], int]:
    """Quebra a frase ("|" = nova linha, *palavra* = ênfase) e dá a cada palavra o instante em que é dita no plano
    (busca em ordem no alinhamento). Palavra não encontrada fica 0,3 s depois da anterior. Devolve (linhas, n_sincronizadas)."""
    toks = [(li, tok) for li, trecho in enumerate(texto.split("|")) for tok in trecho.split()]
    alvos = [sa.normalizar(tok.strip("*")) for _, tok in toks]
    # ocorrências de cada palavra dentro do plano; escolhe a sequência crescente mais compacta (programação dinâmica).
    # Pular uma palavra curta ("o", "a", "e") custa pouco: ela não é casada com uma ocorrência distante; palavras de conteúdo
    # quase nunca são puladas, mesmo quando a frase junta trechos não contíguos da fala.
    occ = [[ti for w, ti in zip(al.normalizadas, al.t_ini) if w == a and plano.inicio - 0.05 <= ti <= plano.fim] if al is not None and a else []
           for a in alvos]
    estados = {None: (0.0, [])}                      # último instante escolhido -> (custo, escolhas)
    for a, o in zip(alvos, occ):
        PULO = 1.2 if len(a) <= 2 else 8.0
        novos: dict = {}
        for ult, (custo, esc) in estados.items():
            cand = [(custo + PULO, ult, esc + [None])]
            cand += [(custo + (ti - ult if ult is not None else 0.0), ti, esc + [ti]) for ti in o if ult is None or ti > ult]
            for c, u, e in cand:
                if u not in novos or c < novos[u][0]:
                    novos[u] = (c, e)
        estados = novos
    escolha = min(estados.values(), key=lambda v: v[0])[1]
    tempos = [None if ti is None else ti - plano.inicio for ti in escolha]
    for i in range(len(tempos)):                      # palavra sem ocorrência: logo antes da seguinte encontrada, ou depois da anterior
        if tempos[i] is None:
            prox = next((tempos[j] for j in range(i + 1, len(tempos)) if tempos[j] is not None), None)
            ant = tempos[i - 1] if i > 0 else None
            tempos[i] = max(0.0, prox - 0.25) if prox is not None and (ant is None or prox - 0.25 > ant) else (ant + 0.3 if ant is not None else 0.35)
    linhas: list[list[dict]] = []
    for (li, tok), t in zip(toks, tempos):
        while len(linhas) <= li:
            linhas.append([])
        enfase = len(tok) > 2 and tok.startswith("*") and tok.endswith("*")
        linhas[li].append({"txt": tok.strip("*"), "t": round(t, 3), **({"enfase": True} if enfase else {})})
    return [l for l in linhas if l], sum(1 for ti in escolha if ti is not None)


def montar_params(conteudo_id: str, plano, al: sa.Alinhamento | None, batidas: list[float]) -> dict:
    """Parâmetros finais da composição: conteúdo + sincronia com a fala + batidas relativas ao início do plano."""
    params = copy.deepcopy(CONTEUDO[conteudo_id]["params"])
    for i, a in enumerate(params.get("atributos") or []):
        t = tempo_da_palavra(al, plano.inicio, plano.fim, a["palavra"]) if al is not None else None
        a["t"] = round((t - plano.inicio) if t is not None else 1.4 + 0.9 * i, 3)
    if params.get("palavra_ativa"):
        t = tempo_da_palavra(al, plano.inicio, plano.fim, params.pop("palavra_ativa")) if al is not None else None
        params["t_ativo"] = round((t - plano.inicio) if t is not None else min(1.2, plano.duracao * 0.4), 3)
    if params.get("texto"):
        linhas, achadas = linhas_da_frase(params.pop("texto"), plano, al)
        params["linhas"] = linhas
        params["sincronia"] = {"palavras": sum(len(x) for x in linhas), "no_alinhamento": achadas}
        # corte interno para um enquadramento mais fechado quando a segunda linha começa (se houver tempo para os dois)
        if len(linhas) >= 2 and plano.duracao >= 5.0 and 1.6 <= linhas[1][0]["t"] <= plano.duracao - 1.6:
            dx = -210 if params.get("lado") == "dir" else 210              # mais perto, e o assunto continua longe do texto
            params["camera"] = {"corte": {"t": linhas[1][0]["t"], "s": 1.34, "x": dx, "y": 24}}
    params["batidas"] = [round(b - plano.inicio, 4) for b in batidas if plano.inicio - 0.01 <= b <= plano.fim + 0.01]
    return params


def chave_pedido(p: PedidoMotion, fps: int, largura: int, altura: int, sha_imagem: str | None, codigo: str) -> str:
    dados = {"comp": p.comp, "dur": round(p.dur_visivel, 3), "t0": round(p.t0, 3), "t1": round(p.t1, 3), "params": p.params, "seed": p.seed,
             "fps": fps, "w": largura, "h": altura, "img": sha_imagem, "codigo": codigo, "v": VERSAO_MOTION}
    return hashlib.sha1(json.dumps(dados, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()[:16]


def _sha(caminho: str | None) -> str | None:
    if not caminho:
        return None
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()[:16]


def renderizar_clipes(m: Motion, pedidos: list[PedidoMotion], cfg: Config, pasta_clipes: Path, pasta_temp: Path, fps: int,
                      progresso=None) -> None:
    """Renderiza (ou reaproveita do cache) os clipes dos pedidos. Atualiza status/clipe/eventos de cada pedido."""
    pasta_clipes.mkdir(parents=True, exist_ok=True)
    pasta_temp.mkdir(parents=True, exist_ok=True)
    L, A = cfg.motion_largura, cfg.motion_altura
    pendentes: list[PedidoMotion] = []
    ativos: dict[str, str] = {}
    for p in pedidos:
        p.chave = chave_pedido(p, fps, L, A, _sha(p.imagem), hash_codigo(p.comp) + (f"|e{cfg.motion_escala3d}" if p.comp.startswith('cena3d') else ''))
        destino = pasta_clipes / f"{p.conteudo}-{p.chave}.mp4"
        meta = Path(str(destino) + ".json")
        if destino.is_file() and destino.stat().st_size > 5_000 and meta.is_file():
            p.status, p.clipe = "reaproveitado", str(destino)
            p.eventos = json.loads(meta.read_text(encoding="utf-8")).get("eventos", [])
            continue
        pendentes.append(p)
    if not pendentes:
        return
    clipes = []
    for p in pendentes:
        params = copy.deepcopy(p.params)
        if p.imagem:
            chave_img = "img_" + re.sub(r"[^A-Za-z0-9_-]", "_", p.plano_id)       # sem '#', '/' etc.: vai na URL da página
            ativos[chave_img] = str(Path(p.imagem).resolve())
            params["imagem"] = f"/ativo/{chave_img}"
        clipes.append({"id": p.plano_id, "comp": p.comp, "dur": round(p.dur_clipe, 4), "dur_visivel": round(p.dur_visivel, 4), "t0": round(p.t0, 4),
                       "seed": p.seed, "params": params, "saida": str(pasta_clipes / f"{p.conteudo}-{p.chave}.mp4")})
    spec = {"largura": L, "altura": A, "fps": fps, "crf": cfg.motion_crf, "preset": cfg.motion_preset, "assets": ativos, "clipes": clipes,
            "render3d": {"escala": cfg.motion_escala3d, "msaa": True}}      # 3D: resolução interna (75 % com MSAA ≈ igual ao cheio, ~1,6× mais rápido)
    arq_spec = pasta_temp / "motion-spec.json"
    salvar_json(arq_spec, spec)
    cmd = [m.node, str(m.render), "--spec", str(arq_spec), "--workers", str(cfg.motion_trabalhadores), "--cancelar", str(cfg.saida / "CANCELAR.txt")]
    log().debug("motion: %s", " ".join(cmd))
    t0 = time.monotonic()
    por_id = {p.plano_id: p for p in pendentes}
    ultimas: list[str] = []
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1, cwd=str(PASTA_MOTION))
    falhas: dict[str, str] = {}
    cancelado = False
    try:
        for linha in proc.stdout:
            linha = linha.rstrip()
            mm = re.match(r"PROGRESSO (.+) (\d+)/(\d+)$", linha)
            if mm:
                if progresso:
                    progresso(mm.group(1), int(mm.group(2)), int(mm.group(3)))
                continue
            if linha.startswith("CLIPE_PRONTO "):
                pid = linha[len("CLIPE_PRONTO "):]
                p = por_id.get(pid)
                if p:
                    destino = pasta_clipes / f"{p.conteudo}-{p.chave}.mp4"
                    p.status, p.clipe = "renderizado", str(destino)
                    meta = Path(str(destino) + ".json")
                    p.eventos = json.loads(meta.read_text(encoding="utf-8")).get("eventos", []) if meta.is_file() else []
                    p.tempo_real_s = time.monotonic() - t0
                continue
            if linha.startswith("FALHOU "):
                pid, _, msg = linha[len("FALHOU "):].partition(": ")
                falhas[pid] = msg
                continue
            if linha == "CANCELADO":
                cancelado = True
            if linha:
                ultimas = (ultimas + [linha])[-12:]
        rc = proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        proc.stdout.close()
    if cancelado or rc == 130:
        raise ErroMotion("Renderização de motion cancelada (CANCELAR.txt).")
    for pid, msg in falhas.items():
        por_id[pid].status, por_id[pid].detalhe = "falhou", msg[:300]
    if rc != 0 and not falhas:
        raise ErroMotion("O renderizador de motion falhou:\n" + "\n".join(ultimas[-8:]))
    sem = [p.plano_id for p in pendentes if p.status not in ("renderizado", "falhou")]
    if sem:
        raise ErroMotion(f"Clipes de motion não gerados: {', '.join(sem)}\n" + "\n".join(ultimas[-6:]))


def descrever(pedidos: list[PedidoMotion]) -> str:
    linhas = [f"Motion graphics: {len(pedidos)} cena(s) selecionada(s)"]
    for p in sorted(pedidos, key=lambda x: x.plano_id):
        linhas.append(f"  {p.plano_id:26s} {p.comp:8s} {p.dur_visivel:5.1f}s  {p.status}  {p.detalhe}")
    return "\n".join(linhas)
