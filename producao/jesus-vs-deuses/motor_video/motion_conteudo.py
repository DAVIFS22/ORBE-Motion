"""Conteúdo informativo das cenas de motion graphics (textos, datas, lugares e fontes).

Regras editoriais:
- Cada ficha diz de que ORDEM é a informação: fato histórico, tradição mitológica, datação acadêmica, crença religiosa
  ou fonte antiga (categorias do `ficha.js`). Não se mistura tradição religiosa com fato histórico.
- Datas só entram quando são amplamente aceitas; as incertas levam "c." (circa) ou a faixa. Sem acesso à internet nesta
  produção, tudo vem de conhecimento geral e DEVE ser conferido antes da publicação (ver `VERIFICAR` abaixo).
- Ilustrações fornecidas pelo usuário são modernas e de origem/licença não verificadas; nunca são apresentadas como
  arte da antiguidade (o rodapé de cada ficha diz isso).
- Locais mitológicos (Cabo Tênaro, Monte Olimpo) são marcados como tradição, não como local histórico comprovado.

Cada entrada: {"comp": "deus"|"mapa"|"periodo", "exige_imagem": bool, "params": {...}, "sync": {...}}.
`params` segue o contrato de cada composição em motion/comps/*.js; `sync` pede tempos de palavras da narração.
"""

from __future__ import annotations

VERIFICAR = ("Datas e atribuições desta lista foram escritas sem consulta online. Conferir com fontes acadêmicas "
             "antes de publicar (principalmente as marcadas como datação acadêmica).")

_ILUSTRACAO = "Ilustração moderna fornecida pelo projeto, de origem não verificada: não é obra da antiguidade."


def _local(nome, lon, lat, lon0, lat0, larg0, larg1, regiao=None, nilo=False):
    d = {"nome": nome, "lon": lon, "lat": lat, "lon0": lon0, "lat0": lat0, "larg0": larg0, "larg1": larg1, "nilo": nilo}
    if regiao:
        d["regiao"] = regiao
    return d


CONTEUDO: dict[str, dict] = {
    # ------------------------------------------------------------------ divindades (ilustração fornecida) ---
    "deus_osiris": {"comp": "deus", "exige_imagem": True, "params": {
        "fundoPlaca": "papiro", "variante": "A", "fantasma": "Egito",
        "ficha": {"eyebrow": "Egito antigo · morte e renovação", "nome": "Osíris", "periodo": "Atestado desde o séc. XXIV a.C.",
                  "categoria": "mitologico", "descricao": "Associado à morte, à renovação e ao mundo dos mortos.",
                  "descricaoCurta": "Deus da morte e da renovação."},
        "rodape": _ILUSTRACAO + " Datação: Textos das Pirâmides.",
        "local": _local("Abidos", 31.919, 26.185, 25.0, 33.0, 56, 9, {"nome": "Egito", "lon": 30.3, "lat": 27.6}, nilo=True)}},
    "deus_anubis": {"comp": "deus", "exige_imagem": True, "params": {
        "fundoPlaca": "papiro", "variante": "B", "fantasma": "Egito",
        "ficha": {"eyebrow": "Egito antigo · ritos funerários", "nome": "Anúbis", "periodo": "Atestado desde o Reino Antigo (c. 2686–2181 a.C.)",
                  "categoria": "mitologico", "descricao": "Ligado aos ritos funerários e à proteção dos falecidos; retratado com cabeça de chacal.",
                  "descricaoCurta": "Protetor dos falecidos."},
        "rodape": _ILUSTRACAO,
        "local": _local("Saqqara", 31.216, 29.871, 25.0, 34.0, 56, 9, {"nome": "Egito", "lon": 30.3, "lat": 27.6}, nilo=True)}},
    "deus_ra": {"comp": "deus", "exige_imagem": True, "params": {
        "fundoPlaca": "papiro", "variante": "A", "fantasma": "Rá",
        "ficha": {"eyebrow": "Egito antigo · divindade solar", "nome": "Rá", "periodo": "Culto solar em Heliópolis",
                  "categoria": "mitologico", "descricao": "Divindade solar, retratada com cabeça de falcão e disco solar.",
                  "descricaoCurta": "Divindade solar egípcia."},
        "rodape": _ILUSTRACAO,
        "local": _local("Heliópolis", 31.305, 30.129, 25.0, 34.0, 56, 9, {"nome": "Egito", "lon": 30.3, "lat": 27.6}, nilo=True)}},
    "deus_zeus": {"comp": "deus", "exige_imagem": True, "params": {
        "fundoPlaca": "escuro", "variante": "B", "fantasma": "Grécia",
        "ficha": {"eyebrow": "Grécia antiga · rei dos deuses", "nome": "Zeus", "periodo": "Nome atestado em tabuletas micênicas (séc. XIV–XIII a.C.)",
                  "categoria": "mitologico", "descricao": "Soberano do Olimpo, deus do céu e do trovão na religião grega.",
                  "descricaoCurta": "Soberano do Olimpo."},
        "rodape": "Ilustração moderna em estilo de quadrinhos, fornecida pelo projeto, de origem não verificada.",
        "local": _local("Monte Olimpo", 22.358, 40.086, 20.0, 38.5, 40, 7, {"nome": "Grécia", "lon": 22.2, "lat": 39.0})}},
    "deus_hades": {"comp": "deus", "exige_imagem": True, "params": {
        "fundoPlaca": "branco", "variante": "A", "fantasma": "Grécia",
        "ficha": {"eyebrow": "Grécia antiga · mundo dos mortos", "nome": "Hades", "periodo": "Já aparece em Homero (Ilíada, séc. VIII a.C.)",
                  "categoria": "mitologico", "descricao": "Na mitologia grega, governa o mundo dos mortos; Cérbero é seu cão guardião.",
                  "descricaoCurta": "Senhor do mundo dos mortos."},
        "rodape": "Ilustração fornecida pelo projeto (autoria e licença não verificadas). O Cabo Tênaro é uma das entradas lendárias do mundo dos mortos; não há local real do Hades.",
        "local": _local("Cabo Tênaro", 22.484, 36.388, 20.0, 38.0, 40, 7, {"nome": "Grécia", "lon": 22.2, "lat": 39.0})}},
    "deus_odin": {"comp": "deus", "exige_imagem": True, "params": {
        "fundoPlaca": "escuro", "variante": "A", "fantasma": "Nórdicos",
        "ficha": {"eyebrow": "Tradições nórdicas · divindade central", "nome": "Odin", "periodo": "Fontes escritas: Eddas, séc. XIII d.C.",
                  "categoria": "mitologico", "descricao": "Chefe dos Æsir na mitologia nórdica, ligado à sabedoria, à poesia, à guerra e aos mortos.",
                  "descricaoCurta": "Divindade central do panteão nórdico."},
        "rodape": "Ilustração: Talita Babiresti (assinatura visível na obra). Autorização de uso não verificada.",
        "local": _local("Gamla Uppsala", 17.633, 59.897, 14.0, 58.0, 46, 10, {"nome": "Escandinávia", "lon": 14.5, "lat": 62.0})}},
    "deus_odin_atributos": {"comp": "deus", "exige_imagem": True, "params": {
        "fundoPlaca": "escuro", "variante": "B", "fantasma": "Odin",
        "ficha": {"eyebrow": "Tradições nórdicas · o que as fontes dizem", "nome": "Odin", "periodo": "Eddas, séc. XIII d.C.",
                  "categoria": "mitologico", "descricao": ""},
        "atributos": [{"texto": "Sabedoria", "palavra": "sabedoria"}, {"texto": "Poesia", "palavra": "poesia"}, {"texto": "Guerra", "palavra": "guerra"}],
        "rodape": "Ilustração: Talita Babiresti (assinatura visível na obra). Autorização de uso não verificada.",
        "local": _local("Gamla Uppsala", 17.633, 59.897, 14.0, 58.0, 46, 10, {"nome": "Escandinávia", "lon": 14.5, "lat": 62.0})}},

    # ------------------------------------------------------------------------------------------- mapas ---
    "mapa_egito_centros": {"comp": "mapa", "exige_imagem": False, "params": {
        "camera": [{"f": 0, "lon": 31.4, "lat": 29.0, "larg": 19}, {"f": 0.42, "lon": 31.9, "lat": 26.6, "larg": 14}, {"f": 0.74, "lon": 32.4, "lat": 25.0, "larg": 12}, {"f": 1, "lon": 31.6, "lat": 27.2, "larg": 20}],
        "tiltIni": 0, "tiltFim": 44, "fTilt": [0.02, 0.2], "nilo": True,
        "regioes": [{"nome": "Egito", "lon": 28.2, "lat": 27.2, "f": 0.12, "tam": 110}],
        "locais": [{"nome": "Heliópolis", "sub": "culto a Rá", "lon": 31.305, "lat": 30.129, "f": 0.2},
                   {"nome": "Abidos", "sub": "culto a Osíris", "lon": 31.919, "lat": 26.185, "f": 0.46},
                   {"nome": "Elefantina", "sub": "culto a Khnum", "lon": 32.887, "lat": 24.086, "f": 0.72}],
        "rotas": [],
        "ficha": {"eyebrow": "Mapa · Egito antigo", "nome": "Muitos deuses", "periodo": "Centros de culto ao longo do Nilo", "categoria": "historico",
                  "descricao": "Cada região tinha divindades principais e templos próprios."},
        "rodape": "Mapa: Natural Earth (domínio público). Centros de culto: localização aproximada."}},
    "mapa_mundo_antigo": {"comp": "mapa", "exige_imagem": False, "params": {
        "camera": [{"f": 0, "lon": 20, "lat": 44, "larg": 84}, {"f": 0.3, "lon": 30.5, "lat": 29.0, "larg": 24}, {"f": 0.55, "lon": 23.5, "lat": 38.5, "larg": 16},
                   {"f": 0.78, "lon": 17.6, "lat": 57.5, "larg": 26}, {"f": 1, "lon": 20, "lat": 45, "larg": 78}],
        "tiltIni": 0, "tiltFim": 42, "fTilt": [0.02, 0.2],
        "regioes": [{"nome": "Egito", "lon": 28.5, "lat": 26.0, "f": 0.22, "tam": 90, "ate": 0.5}, {"nome": "Grécia", "lon": 22.0, "lat": 39.6, "f": 0.46, "tam": 60, "ate": 0.74},
                    {"nome": "Escandinávia", "lon": 15.5, "lat": 62.5, "f": 0.7, "tam": 90, "ate": 0.96}],
        "locais": [{"nome": "Mênfis", "sub": "Egito antigo", "lon": 31.25, "lat": 29.85, "f": 0.3}, {"nome": "Atenas", "sub": "Grécia antiga", "lon": 23.727, "lat": 37.984, "f": 0.55},
                   {"nome": "Gamla Uppsala", "sub": "tradições nórdicas", "lon": 17.633, "lat": 59.897, "f": 0.78}],
        "rotas": [],
        "ficha": {"eyebrow": "Mapa · o mundo antigo", "nome": "Tradições antigas", "periodo": "Egito, Grécia e Escandinávia", "categoria": "historico",
                  "descricao": "Povos diferentes, deuses diferentes e histórias próprias."},
        "rodape": "Mapa: Natural Earth (domínio público). Localizações aproximadas."}},
    "mapa_judeia_romana": {"comp": "mapa", "exige_imagem": False, "params": {
        "camera": [{"f": 0, "lon": 16.0, "lat": 40.0, "larg": 62}, {"f": 0.52, "lon": 27.0, "lat": 36.0, "larg": 38}, {"f": 0.82, "lon": 35.2, "lat": 32.2, "larg": 7.5}, {"f": 1, "lon": 35.2, "lat": 32.0, "larg": 5.6}],
        "tiltIni": 0, "tiltFim": 40, "fTilt": [0.02, 0.2],
        "regioes": [{"nome": "Império Romano", "lon": 17.0, "lat": 39.0, "f": 0.08, "tam": 62, "ate": 0.55}],
        "locais": [{"nome": "Roma", "sub": "capital do Império", "lon": 12.496, "lat": 41.903, "f": 0.14},
                   {"nome": "Jerusalém", "sub": "Judeia", "lon": 35.214, "lat": 31.768, "f": 0.7},
                   {"nome": "Nazaré", "sub": "Galileia", "lon": 35.297, "lat": 32.700, "f": 0.8}],
        "rotas": [],
        "ficha": {"eyebrow": "Mapa · século I", "nome": "Judeia e Galileia", "periodo": "Território sob domínio romano", "categoria": "historico",
                  "descricao": "Uma região pequena, no extremo leste do Mediterrâneo."},
        "rodape": "Mapa: Natural Earth (domínio público). Localizações aproximadas."}},
    "mapa_belem": {"comp": "mapa", "exige_imagem": False, "params": {
        "camera": [{"f": 0, "lon": 35.0, "lat": 31.6, "larg": 14}, {"f": 0.35, "lon": 35.2, "lat": 31.8, "larg": 3.4}, {"f": 0.7, "lon": 35.25, "lat": 32.2, "larg": 4.4}, {"f": 1, "lon": 35.25, "lat": 32.1, "larg": 5.6}],
        "tiltIni": 0, "tiltFim": 40, "fTilt": [0.02, 0.2],
        "regioes": [],
        "locais": [{"nome": "Belém", "sub": "nascimento, segundo os Evangelhos", "lon": 35.203, "lat": 31.705, "f": 0.3},
                   {"nome": "Nazaré", "sub": "infância, segundo os Evangelhos", "lon": 35.297, "lat": 32.700, "f": 0.62}],
        "rotas": [],
        "ficha": {"eyebrow": "Mapa · Judeia e Galileia", "nome": "Belém", "periodo": "Cidade da Judeia, perto de Jerusalém", "categoria": "religioso",
                  "descricao": "Segundo Mateus e Lucas, Jesus nasceu em Belém e cresceu em Nazaré."},
        "rodape": "Mapa: Natural Earth (domínio público). Localizações aproximadas."}},

    # ------------------------------------------------------- cenas 3D (Three.js/WebGL), reconstruções artísticas ---
    "cena3d_abertura_titulo": {"comp": "cena3d_abertura", "exige_imagem": False, "remove_overlays": ["titulo"], "params": {
        "hud": {"desligado": True}, "titulo": {"linha1": "JESUS", "linha2": "CONTRA TODOS", "linha3": "OS DEUSES", "sub": "Por que Jesus é único?"},
        "ficha": {"nome": "Jesus contra todos os deuses", "categoria": "historico"},
        "rodape": "Abertura: paisagem noturna artística por código (obelisco e colunas egípcias, templo dórico, círculo de pedras); não é um local real."}},
    "cena3d_egito_karnak": {"comp": "cena3d_egito", "exige_imagem": False, "params": {
        "ficha": {"eyebrow": "Egito antigo · Karnak", "nome": "134 colunas", "periodo": "Séc. XIII a.C. · Seti I e Ramsés II",
                  "categoria": "historico", "descricao": ""},
        "rodape": "Reconstrução artística por código, inspirada no Salão Hipostilo de Karnak. Inscrições e cores são estilizadas."}},
    "cena3d_grecia_olimpia": {"comp": "cena3d_grecia", "exige_imagem": False, "params": {
        "ficha": {"eyebrow": "Grécia antiga · Olímpia", "nome": "Templo de Zeus", "periodo": "c. 470–457 a.C. · ordem dórica",
                  "categoria": "historico", "descricao": ""},
        "rodape": "Reconstrução artística por código, inspirada no Templo de Zeus em Olímpia. Sem policromia nem esculturas."}},
    "cena3d_fiorde_ragnarok": {"comp": "cena3d_fiorde", "exige_imagem": False, "params": {
        "ficha": {"eyebrow": "Tradições nórdicas · mito", "nome": "Ragnarök", "periodo": "Eddas, séc. XIII d.C.",
                  "categoria": "mitologico", "descricao": ""},
        "rodape": "Paisagem artística por código: não é um local real nem mostra o evento mitológico."}},
    "cena3d_judeia_aldeia": {"comp": "cena3d_judeia", "exige_imagem": False, "params": {
        "ficha": {"eyebrow": "Galileia · século I", "nome": "Nazaré", "periodo": "Pequena aldeia da Galileia",
                  "categoria": "historico", "descricao": ""},
        "rodape": "Reconstrução artística por código de uma aldeia típica da região; não representa um sítio específico nem pessoas."}},

    # ------------------------------------------------------------------------ linhas do tempo e datas ---
    "periodo_tradicoes": {"comp": "periodo", "exige_imagem": False, "params": {
        "janela": [{"f": 0, "a": -3600, "b": 1500}, {"f": 1, "a": -3300, "b": 1400}],
        "periodos": [{"nome": "Egito antigo · c. 3100–30 a.C.", "ini": -3100, "fim": -30, "lane": 0, "f": 0.16},
                     {"nome": "Grécia antiga · c. 800–146 a.C.", "ini": -800, "fim": -146, "lane": 1, "f": 0.34},
                     {"nome": "Religião nórdica · Era Viking, 793–1066", "ini": 793, "fim": 1066, "lane": 2, "f": 0.52, "curto": "Era Viking"}],
        "eventos": [{"nome": "Pirâmide de Gizé", "sub": "", "ano": -2560, "aprox": True, "f": 0.2, "nivel": 0},
                    {"nome": "Partenon", "sub": "construção iniciada", "ano": -447, "f": 0.38, "nivel": 1},
                    {"nome": "Codex Regius", "sub": "Edda Poética", "ano": 1270, "aprox": True, "f": 0.58, "nivel": 0}],
        "ficha": {"eyebrow": "Linha do tempo · tradições antigas", "nome": "Épocas diferentes", "periodo": "Cada tradição, em seu tempo e lugar", "categoria": "historico", "descricao": ""},
        "rodape": "Datas aproximadas, segundo a historiografia corrente. Faixas são recortes didáticos."}},
    "periodo_crucificacao": {"comp": "periodo", "exige_imagem": False, "params": {
        "janela": [{"f": 0, "a": -10, "b": 80}, {"f": 1, "a": 8, "b": 52}],
        "periodos": [{"nome": "Tibério, imperador · 14–37 d.C.", "ini": 14, "fim": 37, "lane": 0, "f": 0.2, "curto": "Tibério"},
                     {"nome": "Pôncio Pilatos, prefeito da Judeia · 26–36 d.C.", "ini": 26, "fim": 36, "lane": 1, "f": 0.34, "foco": True, "curto": "Pilatos"}],
        "eventos": [{"nome": "Crucificação de Jesus", "sub": "", "ano": 31, "data": "entre 30 e 33 d.C.", "f": 0.52, "nivel": 0, "foco": True}],
        "ficha": {"eyebrow": "Judeia romana · fonte antiga", "nome": "Sob Pilatos", "periodo": "Tácito, Anais 15.44 (c. 116 d.C.)", "categoria": "fonte",
                  "descricao": "O historiador romano Tácito registra que Cristo foi executado sob Pôncio Pilatos, no reinado de Tibério."},
        "rodape": "Datas aproximadas, segundo a historiografia corrente."}},
    "periodo_joao": {"comp": "periodo", "exige_imagem": False, "params": {
        "janela": [{"f": 0, "a": -10, "b": 130}, {"f": 1, "a": 10, "b": 120}],
        "periodos": [{"nome": "Vida de Jesus · c. 4 a.C.–30 d.C.", "ini": -4, "fim": 30, "lane": 0, "f": 0.16, "curto": "Jesus"},
                     {"nome": "Evangelho de João · c. 90–110 d.C.", "ini": 90, "fim": 110, "lane": 1, "f": 0.5, "foco": True, "curto": "João"}],
        "eventos": [{"nome": "Crucificação", "sub": "", "ano": 31, "data": "c. 30–33 d.C.", "f": 0.3, "nivel": 0},
                    {"nome": "Evangelho de João", "sub": "", "ano": 100, "data": "c. 90–110 d.C.", "f": 0.58, "nivel": 1, "foco": True}],
        "ficha": {"eyebrow": "Evangelho de João · datação", "nome": "João 1:1", "periodo": "Texto escrito décadas depois dos fatos", "categoria": "academico",
                  "descricao": "A maioria dos estudiosos data o Evangelho de João entre c. 90 e 110 d.C."},
        "rodape": "Datação segundo a maioria dos estudiosos; há debate acadêmico."}},
    "periodo_paulo": {"comp": "periodo", "exige_imagem": False, "params": {
        "janela": [{"f": 0, "a": 20, "b": 80}, {"f": 1, "a": 24, "b": 68}],
        "periodos": [{"nome": "Cartas de Paulo · c. 50–60 d.C.", "ini": 50, "fim": 60, "lane": 0, "f": 0.4, "foco": True, "curto": "Paulo"}],
        "eventos": [{"nome": "Crucificação", "sub": "", "ano": 31, "data": "c. 30–33 d.C.", "f": 0.16, "nivel": 0},
                    {"nome": "1 Coríntios", "sub": "", "ano": 55, "data": "c. 53–57 d.C.", "f": 0.52, "nivel": 1, "foco": True}],
        "ficha": {"eyebrow": "1 Coríntios 15 · fonte antiga", "nome": "A tradição de Paulo", "periodo": "Carta escrita c. 53–57 d.C.", "categoria": "fonte",
                  "descricao": "Paulo diz transmitir o que ele mesmo recebeu: Cristo morreu, foi sepultado e ressuscitou ao terceiro dia."},
        "rodape": "Estudiosos em geral consideram a fórmula anterior à própria carta. Datas aproximadas."}},
}

# Cena do storyboard -> conteúdo
POR_CENA: dict[str, str] = {
    "b04-odin": "deus_odin", "d03-osiris": "deus_osiris", "d04-anubis": "deus_anubis", "d05-ra": "deus_ra",
    "d08-zeus": "deus_zeus", "g05-hades": "deus_hades", "d10-nordicas": "deus_odin_atributos",
    "b01-egito": "mapa_egito_centros", "d01-mundo": "mapa_mundo_antigo", "c01-seculos": "mapa_judeia_romana", "e18-belem": "mapa_belem",
    "b05-diferentes": "periodo_tradicoes", "a01-titulo": "cena3d_abertura_titulo", "a03-templos": "cena3d_egito_karnak", "b02-grecia": "cena3d_grecia_olimpia",
    "d11-ragnarok": "cena3d_fiorde_ragnarok", "c05-nazare": "cena3d_judeia_aldeia", "h02-romano": "periodo_crucificacao", "e14-declaracoes": "periodo_joao", "i13-paulo": "periodo_paulo",
}

COMPOSICOES = {"deus", "mapa", "periodo", "cena3d_abertura", "cena3d_egito", "cena3d_grecia", "cena3d_fiorde", "cena3d_judeia"}


def validar_conteudo():
    """Levanta ValueError se alguma entrada estiver incoerente (usada nos testes)."""
    for k, v in CONTEUDO.items():
        if v["comp"] not in COMPOSICOES:
            raise ValueError(f"{k}: composição desconhecida {v['comp']!r}")
        f = v["params"].get("ficha")
        if not f or not f.get("nome") or not f.get("categoria"):
            raise ValueError(f"{k}: ficha sem nome/categoria")
        if f["categoria"] not in ("historico", "mitologico", "academico", "religioso", "fonte"):
            raise ValueError(f"{k}: categoria inválida {f['categoria']!r}")
    for cena, cid in POR_CENA.items():
        if cid not in CONTEUDO:
            raise ValueError(f"cena {cena}: conteúdo {cid!r} inexistente")
