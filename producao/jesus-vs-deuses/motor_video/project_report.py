"""Relatório final da produção: o que foi gerado, de onde veio cada imagem e o que ficou pendente."""

from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path

from .config import salvar_json

NOMES_FONTE = {"commons": "Wikimedia Commons", "met": "The Metropolitan Museum of Art (Open Access)",
               "aic": "Art Institute of Chicago (domínio público)", "usuario": "Fornecida pelo usuário"}


def _mmss(s: float) -> str:
    return f"{int(s // 60):02d}:{s % 60:05.2f}"


def escrever_fontes_csv(assets: list[dict], destino: Path):
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["id", "cenas", "arquivo", "fonte", "titulo", "autor", "licenca", "url_pagina", "url_arquivo", "natureza",
                    "largura", "altura"])
        for a in assets:
            w.writerow([a["id"], ",".join(a["cenas"]), a["arquivo_original"], NOMES_FONTE.get(a["fonte"], a["fonte"]), a["titulo"],
                        a["autor"], a["licenca"], a["url_pagina"], a["url_arquivo"], a["natureza"], a["largura"], a["altura"]])


def escrever_creditos(assets: list[dict], destino: Path):
    """Texto de créditos pronto para a descrição do vídeo (atribuição exigida por CC BY / CC BY-SA)."""
    linhas = ["# Créditos das imagens", "",
              "Imagens de acervos abertos usadas no documentário “Jesus contra todos os deuses: por que Jesus é único?”.",
              "Obras de arte aparecem como obras de arte (digitalizações de acervo), não como fotografias da época. "
              "Cenários identificados como “gerados por código” são ilustrações próprias, sem material de terceiros.", ""]
    por_licenca: dict[str, list[dict]] = {}
    for a in assets:
        por_licenca.setdefault(a["licenca"], []).append(a)
    for lic in sorted(por_licenca):
        linhas += [f"## {lic}", ""]
        for a in sorted(por_licenca[lic], key=lambda x: x["titulo"].lower()):
            autor = a["autor"] or "autor não informado"
            linhas.append(f"- “{a['titulo']}” — {autor} — {NOMES_FONTE.get(a['fonte'], a['fonte'])} — {a['url_pagina'] or a['url_arquivo']}")
        linhas.append("")
    if not assets:
        linhas.append("_Nenhuma imagem de terceiros foi usada nesta versão._")
    destino.write_text("\n".join(linhas), encoding="utf-8")


def _secao_3d(ctx: dict, add):
    """Animação 3D: o que foi usado, por quê, quanto custou e como está rotulado."""
    ped = ctx.get("cenas3d") or []
    c3 = ctx.get("config3d") or {}
    add("## Animação 3D (Blender), uso seletivo")
    add("")
    if not ped:
        add(f"Nenhuma cena 3D nesta execução (prioridade {c3.get('prioridade', 0)}; "
            f"{'Blender: ' + ctx['blender'] if ctx.get('blender') else 'Blender não encontrado ou desativado'}). "
            "Os planos usam imagens reais, quando há, ou cenário 2D gerado por código.")
        add("")
        return
    usados = [p for p in ped if p["status"] in ("renderizado", "reaproveitado")]
    seg = sum(p["duracao"] for p in usados)
    total = ctx.get("duracao_video_s") or 1
    add(f"- Blender: {ctx.get('blender') or 'não informado'}; motor {c3.get('motor')}, dispositivo {str(c3.get('dispositivo')).upper()}, "
        f"qualidade \"{c3.get('qualidade')}\", prioridade até P{c3.get('prioridade')}"
        + (f", orçamento de {c3['orcamento_min']:g} min" if c3.get("orcamento_min") else "") + ".")
    add(f"- {len(usados)} clipe(s) usados, {seg:.0f} s no total = {seg / total * 100:.1f}% do vídeo; o resto é imagem real, "
        "arte/cenário 2D, texto e mapas. P1 = abertura, reconstruções e momentos de impacto; P2 = só onde não há imagem real adequada.")
    add("- Todas as cenas 3D são **reconstruções ou representações artísticas** e levam rótulo na tela; os deuses seguem a iconografia de cada "
        "tradição, o Ragnarök é tratado como evento mítico e nenhuma cena mostra Jesus ou afirma a aparência dele.")
    add("")
    add("| Plano | Cena 3D | Prio. | Duração | Situação | Render |")
    add("|---|---|---|---|---|---|")
    for p in sorted(ped, key=lambda x: x["plano_id"]):
        sit = {"renderizado": "renderizado", "reaproveitado": "reaproveitado (cache)", "cortado_orcamento": "cortado (orçamento)",
               "falhou": "FALHOU"}.get(p["status"], p["status"])
        add(f"| `{p['plano_id']}` | {p['cena']} | P{p['prioridade']} | {p['duracao']:.1f} s | {sit} | "
            f"{p['tempo_real_s'] / 60:.1f} min |" if p.get("tempo_real_s") else
            f"| `{p['plano_id']}` | {p['cena']} | P{p['prioridade']} | {p['duracao']:.1f} s | {sit} | |")
    add("")


def _secao_motion(ctx: dict, add):
    """Motion graphics (fichas, mapas e linhas do tempo animados): o que foi gerado e o que cada ficha afirma."""
    ped = ctx.get("cenas_motion") or []
    add("## Motion graphics (informações animadas)")
    add("")
    if not ped:
        add("Nenhuma composição de motion nesta execução (" + ("Node/Chromium disponíveis, sem cenas elegíveis" if ctx.get("motion") else
            "Node.js 18+ com 'npm install' em motion/ não disponível") + ").")
        add("")
        return
    usados = [p for p in ped if p["status"] in ("renderizado", "reaproveitado")]
    seg = sum(p["dur_visivel"] for p in usados)
    total = ctx.get("duracao_video_s") or 1
    add(f"- {len(usados)} de {len(ped)} composição(ões) usadas, {seg:.0f} s = {seg / total * 100:.1f}% do vídeo; renderizadas por `window.seek(t)` "
        "(função pura do tempo; mesmos quadros em qualquer ordem), H.264 yuv420p, CRF 16.")
    add("- Cada ficha classifica a informação (fato histórico, tradição mitológica, datação acadêmica, crença religiosa ou fonte antiga). "
        "Datas escritas sem consulta online devem ser conferidas antes da publicação.")
    add("- Ilustrações fornecidas pelo usuário aparecem como ilustrações modernas de origem/licença não verificadas, nunca como arte da antiguidade.")
    add("")
    add("| Plano | Composição | Conteúdo | Duração | Situação |")
    add("|---|---|---|---|---|")
    for p in sorted(ped, key=lambda x: x["plano_id"]):
        add(f"| `{p['plano_id']}` | {p['comp']} | {p['conteudo']} | {p['dur_visivel']:.1f} s | {p['status']}{(' (' + p['detalhe'] + ')') if p.get('detalhe') else ''} |")
    add("")


def _secao_threejs(ctx: dict, add):
    """Cenas 3D feitas por código em Three.js/WebGL: o que são, o que não são e como foram conferidas."""
    ped = [p for p in (ctx.get("cenas_motion") or []) if str(p.get("comp", "")).startswith("cena3d_")]
    if not ped:
        return
    usados = [p for p in ped if p["status"] in ("renderizado", "reaproveitado")]
    add("## Cenas 3D por código (Three.js / WebGL)")
    add("")
    add(f"- {len(usados)} de {len(ped)} cena(s) 3D usadas: geometria real (sólidos de revolução, extrusões, terreno por altura), texturas PBR "
        "procedurais (cor, normal e rugosidade geradas por código com semente fixa), luz solar com sombras, céu e iluminação por imagem, "
        "feixes de luz e poeira, câmera em spline (Catmull-Rom) e tremor de mão determinístico. Renderizadas por `window.seek(t)` em WebGL por software (SwiftShader).")
    add("- **São reconstruções artísticas, não evidência arqueológica**: tipos de arquitetura documentados (salão hipostilo, templo dórico, aldeia de pedra) "
        "combinados por código; inscrições e cores egípcias são estilizadas (não são hieróglifos legíveis), o templo grego não tem policromia nem esculturas, "
        "a paisagem nórdica não é um local real e a aldeia não representa um sítio específico nem pessoas. Cada cena traz esse aviso na tela.")
    add("- Nenhum modelo, textura ou foto externa foi usado nestas cenas (nada a licenciar além das bibliotecas listadas no fim). As cenas Blender continuam disponíveis como alternativa.")
    add("")
    add("| Plano | Cena | Duração | Situação |")
    add("|---|---|---|---|")
    for p in sorted(ped, key=lambda x: x["plano_id"]):
        add(f"| `{p['plano_id']}` | {p['comp']} | {p['dur_visivel']:.1f} s | {p['status']} |")
    add("")


def _secao_batidas(ctx: dict, add):
    b = ctx.get("beats")
    if not b:
        return
    add("### Trilha sintetizada e grade de batidas")
    add("")
    add(f"- Trilha e efeitos gerados por código com a **Web Audio API** (`OfflineAudioContext`: osciladores, filtros, envelopes ADSR, ruído, convolução simples), "
        "exportados em WAV PCM; nenhum arquivo ou amostra de áudio de terceiros. Obra própria; não imita gravações acústicas.")
    add(f"- `beats.json` ({b['planejadas']} batidas planejadas): andamento por seção definido na composição; cortes, revelações e impactos são alinhados a essa grade.")
    for s in b["secoes"]:
        m = s.get("medicao") or {}
        if m.get("mensuravel"):
            add(f"    - {s['id']} ({s['clima']}, {s['bpm']:g} BPM): {m['pulsos_planejados']} pulsos planejados, {m['cobertura_pulsos'] * 100:.0f}% detectados no áudio "
                f"(desvio médio {m['desvio_medio_ms']} ms, máx. {m['desvio_abs_max_ms']} ms; andamento medido {m['bpm_medido']} BPM) → "
                f"{'grade confirmada' if m.get('confirmada') else 'grade NÃO confirmada'}.")
        else:
            add(f"    - {s['id']} ({s['clima']}, {s['bpm']:g} BPM): grade planejada (exata por construção); poucos pulsos percussivos para confirmar por onsets.")
    add("")


def _secao_tecnologias(ctx: dict, add):
    add("## Tecnologias, integração Frame Motion e licenças do código")
    add("")
    add("- **Frame Motion (MCP):** o conector aparecia instalado e autenticado, mas desabilitado na conversa e **sem ferramentas expostas**; por isso **não foi usado** e nada "
        "foi inventado sobre ele. O motor próprio (`motion/`) segue o mesmo contrato determinístico (`window.seek(t)`, sem CSS transitions/timers/rAF/Math.random, "
        "`mulberry32` com semente fixa, saída H.264 yuv420p CRF 16 a 1920×1080, `node render.mjs`). Se o conector for habilitado, as composições podem ser portadas a ele.")
    add("- Bibliotecas fixadas em `motion/package.json`: Three.js 0.170.0 (MIT), GSAP 3.12.5 (licença padrão GreenSock, gratuita), Playwright/Chromium (Apache-2.0), "
        "fontes Cinzel e Inter (SIL OFL 1.1), mapas Natural Earth (domínio público).")
    add("- Texturas, geometrias, trilha e efeitos são gerados por código (obra própria). Ilustrações dos deuses fornecidas pelo usuário têm origem e licença não verificadas "
        "(a de Odin traz a assinatura de Talita Babiresti) e aparecem rotuladas como ilustrações modernas.")
    rev = ctx.get("revisao")
    if rev:
        add(f"- Revisão antes da renderização final: {rev}")
    add("")


def gerar(ctx: dict, pasta: Path) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    assets = ctx["assets"]
    escrever_fontes_csv(assets, pasta / "fontes-imagens.csv")
    escrever_creditos(assets, pasta / "creditos-imagens.md")
    salvar_json(pasta / "relatorio-producao.json", ctx)

    qc = ctx.get("qc") or {}
    aprovado = qc.get("aprovado", False)
    tl = ctx["timeline"]
    L: list[str] = []
    add = L.append
    add("# Relatório de produção: Jesus contra todos os deuses")
    add("")
    add(f"Gerado em {datetime.now():%d/%m/%Y %H:%M} pelo motor de vídeo versão {ctx['versao']}.")
    add("")
    if ctx.get("validacao"):
        add("> **ATENÇÃO: este é um vídeo de VALIDAÇÃO do motor.** A narração real não estava disponível neste ambiente; "
            "foi usada uma narração-guia sintética (ruído com o ritmo da fala, sem palavras), só para exercitar a "
            "sincronia, a mixagem e as verificações. Para o vídeo final, rode o motor com o arquivo de narração real.")
        add("")
    add("## Resultado")
    add("")
    add(f"- **Situação:** {'APROVADO em todas as verificações' if aprovado else 'NÃO APROVADO: veja as verificações abaixo'}")
    if ctx.get("video"):
        add(f"- **Vídeo:** `{ctx['video']}` ({ctx['video_mb']:.1f} MB, {_mmss(ctx['duracao_video_s'])}, "
            f"{ctx['cfg']['largura']}x{ctx['cfg']['altura']} a {ctx['cfg']['fps']} fps)")
    add(f"- **Legendas (SRT):** `{ctx.get('srt')}` ({ctx.get('n_legendas', 0)} legendas)")
    add(f"- **Créditos das imagens:** `{pasta / 'creditos-imagens.md'}`  |  **Fontes (CSV):** `{pasta / 'fontes-imagens.csv'}`")
    add(f"- **Linha do tempo:** `{ctx.get('timeline_json')}`")
    add(f"- **Log:** `{ctx.get('log')}`")
    add("")
    add("## Entradas")
    add("")
    e = ctx["entradas"]
    add(f"- Narração: `{e['narracao_original']}` ({e['narracao_duracao_s']:.1f} s; SHA-256 `{e['narracao_sha256'][:16]}…`)"
        + (" (já tratada: não foi reprocessada)" if e.get("narracao_tratada") else " (usada como está: sem filtros de voz)"))
    add(f"- Roteiro: `{e['roteiro']}`")
    add(f"- Transcrição com tempos: `{e['transcricao']}`" if e.get("transcricao") else "- Transcrição: **não fornecida**: tempos estimados proporcionalmente (sincronia aproximada)")
    add(f"- Voz nova gerada: **não** (a narração existente é a referência temporal; nenhuma voz foi sintetizada).")
    al = ctx["alinhamento"]
    add(f"- Alinhamento roteiro × transcrição: {al['cobertura'] * 100:.1f}% das {al['palavras']} palavras reconhecidas; "
        f"{len(al['lacunas'])} trecho(s) do roteiro sem correspondência.")
    for lac in al["lacunas"]:
        suspeita = " (provavelmente não narrado/não transcrito)" if lac.get("suspeita_nao_narrado") else ""
        add(f"    - {_mmss(lac['t_ini'])}: {lac['palavras']} palavras{suspeita}: “{lac['texto']}”")
    add("")
    add("## Linha do tempo")
    add("")
    add(f"- {tl['cenas']} cenas, {tl['planos']} planos: {tl['planos_com_imagem']} com imagem baixada e licenciada, "
        f"{tl.get('planos_video', 0)} com filmagem licenciada, {tl.get('planos_3d', 0)} com animação 3D (Blender), {tl.get('planos_motion', 0)} com motion graphics e "
        f"{tl['planos_gerados']} com cenário 2D gerado por código (alternativa quando não há imagem).")
    for a in ctx.get("avisos", []):
        add(f"- Aviso: {a}")
    add("")
    _secao_3d(ctx, add)
    _secao_motion(ctx, add)
    _secao_threejs(ctx, add)
    add("## Imagens e licenças")
    add("")
    cont = Counter(a["fonte"] for a in assets)
    if assets:
        add("Imagens baixadas e validadas: " + ", ".join(f"{NOMES_FONTE.get(k, k)}: {v}" for k, v in cont.items()) + ".")
    else:
        add("**Nenhuma imagem de terceiros foi baixada nesta execução.** " + (ctx.get("rede") or ""))
    add("")
    if ctx["pendencias"]:
        cenas_pend = {p["cena"] for p in ctx["pendencias"]}
        add(f"### Pendências ({len(cenas_pend)} cena(s) sem imagem adequada; {len(ctx['pendencias'])} consulta(s) sem resultado)")
        add("")
        add("Nessas cenas foi usado um cenário gerado por código (ilustração estilizada, **não** fotografia). "
            "Rode de novo com acesso à internet, ou coloque imagens próprias em uma pasta e use `--imagens`.")
        add("")
        for p in ctx["pendencias"][:60]:
            add(f"- `{p['cena']}`: {p['motivo']}")
        if len(ctx["pendencias"]) > 60:
            add(f"- … e mais {len(ctx['pendencias']) - 60} (veja o JSON).")
        add("")
    if ctx["falhas_download"]:
        add(f"### Candidatos descartados ({len(ctx['falhas_download'])})")
        add("")
        motivos = Counter(f["motivo"].split(":")[0][:60] for f in ctx["falhas_download"])
        for m, n in motivos.most_common(8):
            add(f"- {n}× {m}")
        add("")
    add("## Áudio")
    add("")
    au = ctx["audio"]
    add(f"- Narração: nível ativo {au['narracao_rms_db']:.1f} dBFS, pico {au['narracao_pico_db']:.1f} dBFS.")
    add(f"- Mix final: {au.get('mix_lufs', '?')} LUFS (alvo {au.get('alvo_lufs')} LUFS), true peak máx. {au.get('true_peak')} dBTP; "
        "a música abaixa sob a fala (sidechain), os efeitos têm ducking leve; fade-out limpo no final.")
    usos = Counter((f["tipo"], f["origem"]) for f in au["fontes"])
    for (tipo, origem), n in sorted(usos.items()):
        add(f"    - {tipo}: {n}× {origem}")
    add("- Todos os sons desta versão são ambientação sintetizada por código ou arquivos fornecidos pelo usuário; "
        "nenhum é apresentado como gravação histórica nem como som do acontecimento bíblico.")
    add("")
    _secao_batidas(ctx, add)
    add("## Renderização")
    add("")
    r = ctx.get("render") or {}
    add(f"- Encoder: {r.get('encoder')} ({'hardware' if r.get('hardware') else 'CPU'}); {r.get('blocos')} blocos "
        f"({r.get('blocos_reaproveitados', 0)} reaproveitados); {r.get('quadros')} quadros em {r.get('tempo_renderizacao_s')} s.")
    add(f"- Movimento de câmera calculado por código (zoom, panorâmica, Ken Burns) com foco protegido; transições: "
        f"{', '.join(f'{k} ({v})' for k, v in tl['transicoes'].items())}.")
    if r.get("blocos") and r.get("blocos_reaproveitados") == r.get("blocos"):
        add("- Todos os blocos já estavam prontos (execução anterior com os mesmos planos): o tempo acima é só o de concatenar e "
            "conferir; o tempo de renderização original consta no log da primeira execução.")
    add("- Paralaxe 2.5D de fotos reais: disponível como cena 3D de prioridade 3 (`--prioridade-3d 3`); só se aplica a fotos baixadas. "
        "Detecção de rostos usa OpenCV se instalado, senão um mapa de saliência.")
    add("")
    _secao_tecnologias(ctx, add)
    add("## Verificações")
    add("")
    for i in qc.get("itens", []):
        marca = {"ok": "OK", "aviso": "AVISO", "falha": "FALHA"}[i["status"]]
        add(f"- **{marca}**: {i['nome']}: {i['detalhe']}")
    add("")
    add("## Tempo gasto por etapa")
    add("")
    for k, v in ctx["tempos"].items():
        add(f"- {k}: {v:.1f} s")
    add("")
    add("## Como reproduzir")
    add("")
    add("```")
    add(ctx["comando"])
    add("```")
    destino = pasta / "relatorio-producao.md"
    destino.write_text("\n".join(L) + "\n", encoding="utf-8")
    return destino
