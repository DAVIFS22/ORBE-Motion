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


def _frase(texto, eyebrow=None, nota=None, lado="esq", aspas=False, categoria="religioso"):
    """Tipografia cinética: `texto` usa só palavras ditas na narração, na ordem em que são ditas; "|" quebra a linha e
    *palavra* marca a ênfase. O fundo é o do próprio plano (cenário ou still 3D)."""
    return {"comp": "frase", "exige_imagem": False, "fundo_do_plano": True,
            "remove_overlays": ["versiculo", "capitulo", "ponto", "lista", "titulo"],
            "params": {"texto": texto, "eyebrow": eyebrow, "nota": nota, "lado": lado, "aspas": aspas, "categoria": categoria}}


_CITACAO = "Citação bíblica conforme a narração"
_PONTOS = [{"rotulo": "Eterno", "ref": "João 1"}, {"rotulo": "Criador", "ref": "Colossenses 1"}, {"rotulo": "Amor e serviço", "ref": "Marcos 10:45"},
           {"rotulo": "Reconciliação", "ref": "Romanos 5"}, {"rotulo": "Ressuscitado", "ref": "1 Coríntios 15"}]
_PARAFRASE = "Paráfrase da narração"


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
        "rodape": "Reconstrução artística por código, inspirada no Templo de Zeus em Olímpia. Sem policromia nem esculturas.",
        "anotacoes": [{"pos": [0, 18.5, 31], "texto": "Frontão", "sub": "esculturas não reconstruídas", "t0": 2.4, "t1": 5.6, "lado": "dir", "dy": 70},
                      {"pos": [13.2, 7.5, 30.5], "texto": "Coluna dórica", "sub": "fuste com caneluras", "t0": 3.2, "t1": 5.6, "lado": "dir", "dy": -60}]}},
    "cena3d_fiorde_ragnarok": {"comp": "cena3d_fiorde", "exige_imagem": False, "params": {
        "ficha": {"eyebrow": "Tradições nórdicas · mito", "nome": "Ragnarök", "periodo": "Eddas, séc. XIII d.C.",
                  "categoria": "mitologico", "descricao": ""},
        "rodape": "Paisagem artística por código: não é um local real nem mostra o evento mitológico."}},
    "cena3d_judeia_aldeia": {"comp": "cena3d_judeia", "exige_imagem": False, "params": {
        "ficha": {"eyebrow": "Galileia · século I", "nome": "Nazaré", "periodo": "Pequena aldeia da Galileia",
                  "categoria": "historico", "descricao": ""},
        "rodape": "Reconstrução artística por código de uma aldeia típica da região; não representa um sítio específico nem pessoas."}},

    # ------------------------------------------- cenas 3D da parte sobre Jesus (reconstruções e paisagens artísticas) ---
    "cena3d_galileia_colinas": {"comp": "cena3d_galileia", "exige_imagem": False, "params": {"vista": "colinas",
        "ficha": {"eyebrow": "Galileia · século I", "nome": "Mar da Galileia", "periodo": "Lago de água doce no norte da região",
                  "categoria": "historico", "descricao": ""},
        "rodape": "Paisagem artística por código: não reproduz um ponto exato da margem e não mostra pessoas."}},
    "cena3d_galileia_margem": {"comp": "cena3d_galileia", "exige_imagem": False, "params": {"vista": "margem",
        "ficha": {"eyebrow": "Evangelhos · Galileia", "nome": "Entre pescadores", "periodo": "Marcos 1:16–20", "categoria": "fonte", "descricao": ""},
        "rodape": "Paisagem artística por código; barco na escala do barco do século I achado no lago em 1986. Não mostra pessoas."}},
    "cena3d_galileia_lago": {"comp": "cena3d_galileia", "exige_imagem": False, "params": {"vista": "lago", "hud": {"desligado": True, "rodape": True},
        "ficha": {"nome": "Mar da Galileia", "categoria": "historico"},
        "rodape": "Mar da Galileia — paisagem artística por código."}},
    "cena3d_judeia_telhados": {"comp": "cena3d_judeia", "exige_imagem": False, "params": {"vista": "telhados", "hud": {"desligado": True, "rodape": True},
        "ficha": {"nome": "Aldeia da Galileia", "categoria": "historico"},
        "rodape": "Aldeia do século I — reconstrução artística por código; não representa um sítio específico."}},
    "cena3d_golgota_distante": {"comp": "cena3d_golgota", "exige_imagem": False, "params": {"vista": "distante",
        "ficha": {"eyebrow": "Jerusalém · c. 30–33 d.C.", "nome": "Gólgota", "periodo": "“Perto da cidade” — João 19:20", "categoria": "fonte", "descricao": ""},
        "rodape": "Reconstrução artística por código: a localização exata, o relevo e a forma das cruzes não são conhecidos com certeza. Sem pessoas.",
        "anotacoes": [{"pos": [30, 14.5, -336], "texto": "Muralha da cidade", "sub": "ilustrativa", "t0": 3.6, "t1": 8.6, "lado": "dir", "dy": 80}]}},
    "cena3d_golgota_tempestade": {"comp": "cena3d_golgota", "exige_imagem": False, "params": {"vista": "tempestade", "hud": {"desligado": True, "rodape": True},
        "ficha": {"nome": "Gólgota", "categoria": "fonte"},
        "rodape": "Reconstrução artística por código; forma e local exatos das cruzes incertos."}},
    "cena3d_golgota_amanhecer": {"comp": "cena3d_golgota", "exige_imagem": False, "params": {"vista": "amanhecer", "hud": {"desligado": True, "rodape": True},
        "ficha": {"nome": "Gólgota", "categoria": "fonte"},
        "rodape": "Reconstrução artística por código."}},
    "cena3d_tumulo_exterior": {"comp": "cena3d_tumulo", "exige_imagem": False, "params": {"vista": "exterior",
        "ficha": {"eyebrow": "Jerusalém · manhã do primeiro dia", "nome": "O túmulo", "periodo": "Marcos 16:1–4", "categoria": "fonte", "descricao": ""},
        "rodape": "Reconstrução artística por código de um túmulo escavado na rocha, do tipo usado na Judeia do século I; não é o local histórico.",
        "anotacoes": [{"pos": [1.75, 1.7, 0.45], "texto": "A pedra removida", "sub": "Marcos 16:4", "t0": 2.6, "t1": 5.7, "lado": "dir", "dy": 60}]}},
    "cena3d_tumulo_interior": {"comp": "cena3d_tumulo", "exige_imagem": False, "params": {"vista": "interior", "hud": {"desligado": True, "rodape": True},
        "ficha": {"nome": "O túmulo", "categoria": "fonte"},
        "rodape": "Os panos de linho deixados na câmara (João 20:5–7) — reconstrução artística."}},
    "cena3d_tumulo_saida": {"comp": "cena3d_tumulo", "exige_imagem": False, "params": {"vista": "saida", "hud": {"desligado": True, "rodape": True},
        "ficha": {"nome": "O túmulo", "categoria": "fonte"},
        "rodape": "Reconstrução artística por código."}},
    "cena3d_galileia_margem_sem": {"comp": "cena3d_galileia", "exige_imagem": False, "params": {"vista": "margem", "hud": {"desligado": True, "rodape": True},
        "ficha": {"nome": "Mar da Galileia", "categoria": "historico"},
        "rodape": "Mar da Galileia — paisagem artística por código."}},
    "cena3d_galileia_noite": {"comp": "cena3d_galileia", "exige_imagem": False, "params": {"vista": "noite", "hud": {"desligado": True, "rodape": True},
        "ficha": {"nome": "Mar da Galileia", "categoria": "historico"},
        "rodape": "Céu noturno sobre o mar da Galileia — paisagem artística por código."}},
    "cena3d_egito_retorno": {"comp": "cena3d_egito", "exige_imagem": False, "params": {"hud": {"desligado": True, "rodape": True},
        "ficha": {"nome": "Karnak", "categoria": "historico"},
        "rodape": "Reconstrução artística por código, inspirada no Salão Hipostilo de Karnak."}},
    "cena3d_grecia_respeito": {"comp": "cena3d_grecia", "exige_imagem": False, "params": {"hud": {"desligado": True, "rodape": True},
        "ficha": {"nome": "Olímpia", "categoria": "historico"},
        "rodape": "Reconstrução artística por código, inspirada no Templo de Zeus em Olímpia."}},

    # ----------------------------------------------------------------- diagrama dos cinco pontos (comparação) ---
    **{f"pontos_{i}": {"comp": "pontos", "exige_imagem": False, "fundo_do_plano": True, "remove_overlays": ["ponto", "lista", "capitulo"],
                       "params": {"ativo": i, "palavra_ativa": pal, "itens": _PONTOS, "categoria": "religioso"}}
       for i, pal in [(1, "eterno"), (2, "criador"), (3, "amor"), (4, "reconciliação"), (5, "ressuscitado")]},
    "pontos_todos": {"comp": "pontos", "exige_imagem": False, "fundo_do_plano": True, "remove_overlays": ["ponto", "lista", "capitulo"],
                     "params": {"ativo": 0, "itens": _PONTOS, "titulo": "Cinco pontos", "sub": "o argumento central da fé cristã", "categoria": "religioso"}},

    # ------------------------------------------------------------- tipografia cinética (palavras da narração) ---
    "frase_isaias45": _frase("Eu sou o Senhor, | e não há *outro.*", "Isaías 45:5", _CITACAO, "esq", True),
    "frase_unico": _frase("o único Deus | *verdadeiro*", "Monoteísmo bíblico", _PARAFRASE, "dir"),
    "frase_nao_mais_forte": _frase("não simplesmente | um deus *mais* *forte*", "A fé cristã histórica", _PARAFRASE, "esq"),
    "frase_joao1": _frase("No princípio | era o *Verbo*", "João 1:1", _CITACAO, "esq", True),
    "frase_logos": _frase("o termo grego | *Logos*", "Evangelho de João", "“Verbo” traduz o termo grego Logos", "dir"),
    "frase_joao8": _frase("Antes que Abraão existisse, | *eu* *sou.*", "João 8:58", _CITACAO, "esq", True),
    "frase_col116": _frase("todas as coisas | foram *criadas*", "Colossenses 1:16–17", _PARAFRASE, "dir"),
    "frase_acima_criacao": _frase("acima | da *criação*", "Colossenses 1", _PARAFRASE, "esq"),
    "frase_marcos": _frase("não veio para ser servido, | mas para *servir*", "Marcos 10:45", _CITACAO, "esq"),
    "frase_poder": _frase("O verdadeiro | *poder*", "Na vida de Jesus", _PARAFRASE, "dir"),
    "frase_joao13": _frase("que amem | uns aos *outros*", "João 13:34", _CITACAO, "esq"),
    "frase_carater": _frase("revelação do próprio | *caráter* de Deus", "A particularidade cristã", _PARAFRASE, "dir"),
    "frase_joao11": _frase("Eu sou a *ressurreição* | e a vida", "João 11:25", _CITACAO, "esq", True),
    "frase_palavra_final": _frase("a morte não tem | a palavra *final*", "Na fé cristã", _PARAFRASE, "dir"),
    "frase_venceu": _frase("Ele *venceu* | a morte", "A afirmação cristã", _PARAFRASE, "esq"),
    "frase_isaias53": _frase("o servo | *sofredor*", "Isaías 53", _PARAFRASE, "dir"),
    "frase_romanos": _frase("Cristo morreu | por *nós*", "Romanos 5:8", _PARAFRASE, "esq"),
    "frase_filipenses": _frase("se humilhou | e foi *exaltado*", "Filipenses 2:8–11", _PARAFRASE, "dir"),
    "frase_encontram": _frase("o amor, a justiça, | o perdão e a *redenção*", "A cruz, na fé cristã", _PARAFRASE, "esq"),
    "frase_1cor15_14": _frase("a pregação cristã | é *vazia*", "1 Coríntios 15:14", "“Se Cristo não ressuscitou” — paráfrase da narração", "dir"),
    "frase_permanece": _frase("morreu, ressuscitou | e permanece *vivo*", "A afirmação cristã", _PARAFRASE, "esq"),
    "frase_forca": _frase("não se resume a uma | disputa de *força*", "A resposta bíblica", _PARAFRASE, "dir"),
    "frase_col118": _frase("a *primazia* | em todas as coisas", "Colossenses 1:18", _PARAFRASE, "esq"),
    "frase_diferenca": _frase("a diferença | mais *importante*", None, None, "dir"),
    "frase_acima_poderes": _frase("acima de todos | os *poderes*", "A afirmação da fé cristã", _PARAFRASE, "esq"),
    "frase_pergunta_final": _frase("Quem é Jesus | para *você?*", None, None, "esq"),

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
    # cenas 3D em movimento (parte sobre Jesus e retornos às tradições antigas)
    "c06-ensino": "cena3d_galileia_colinas", "f04-evangelhos": "cena3d_galileia_margem", "k10-doismil": "cena3d_galileia_lago",
    "f10-impuras": "cena3d_judeia_telhados", "h01-centro": "cena3d_golgota_distante", "h05-fracasso": "cena3d_golgota_tempestade",
    "i01-resposta": "cena3d_golgota_amanhecer", "i03-mulheres": "cena3d_tumulo_exterior", "i04-vazio": "cena3d_tumulo_interior",
    "j09b-1cor15": "cena3d_tumulo_saida", "j01-voltar": "cena3d_egito_retorno", "i27-respeito": "cena3d_grecia_respeito",
    "k22-cruz": "cena3d_golgota_amanhecer", "k23-ressurreicao": "cena3d_tumulo_saida", "f16-cruz-maximo": "cena3d_golgota_tempestade",
    "h28-morreu": "cena3d_golgota_tempestade", "k12-sofrimento": "cena3d_galileia_margem_sem", "k32-jornada": "cena3d_galileia_noite",
    "e24-antes": "cena3d_galileia_noite", "e26-nao-criatura": "cena3d_galileia_noite",
    # diagrama dos cinco pontos
    "j05-primeiro": "pontos_1", "j06-segundo": "pontos_2", "j07-terceiro": "pontos_3", "j08-quarto": "pontos_4", "j09-quinto": "pontos_5", "j10-cinco": "pontos_todos",
    # tipografia cinética
    "e02b-isaias-citacao": "frase_isaias45", "e04-unico": "frase_unico", "e06-nao-mais-forte": "frase_nao_mais_forte", "e13-joao-1-1": "frase_joao1",
    "e15-logos": "frase_logos", "e20b-joao-8-58-citacao": "frase_joao8", "e23-col-1-16": "frase_col116", "e27-acima": "frase_acima_criacao",
    "f06-marcos": "frase_marcos", "f08-poder": "frase_poder", "f13-novo-mandamento": "frase_joao13", "f15-particularidade": "frase_carater",
    "g11-ressurreicao-vida": "frase_joao11", "g17-palavra-final": "frase_palavra_final", "g21-venceu": "frase_venceu",
    "h11-isaias53": "frase_isaias53", "h13-romanos": "frase_romanos", "h25-filipenses": "frase_filipenses", "h27-encontram": "frase_encontram",
    "i20-1cor15-14": "frase_1cor15_14", "i28-especifica": "frase_permanece", "j03-forca": "frase_forca", "j15-col118": "frase_col118",
    "k18-diferenca": "frase_diferenca", "k24-acima": "frase_acima_poderes", "k33-pergunta-final": "frase_pergunta_final",
}

COMPOSICOES = {"deus", "mapa", "periodo", "frase", "pontos", "cena3d_abertura", "cena3d_egito", "cena3d_grecia", "cena3d_fiorde", "cena3d_judeia",
               "cena3d_golgota", "cena3d_tumulo", "cena3d_galileia", "cena3d_escritos"}


def validar_conteudo():
    """Levanta ValueError se alguma entrada estiver incoerente (usada nos testes)."""
    for k, v in CONTEUDO.items():
        if v["comp"] not in COMPOSICOES:
            raise ValueError(f"{k}: composição desconhecida {v['comp']!r}")
        if v["comp"] == "pontos":
            if not v["params"].get("itens"):
                raise ValueError(f"{k}: diagrama sem itens")
            continue
        if v["comp"] == "frase":
            txt = v["params"].get("texto") or ""
            if not txt.strip() or len(txt.replace("|", " ").split()) > 9:
                raise ValueError(f"{k}: a frase deve ter de 1 a 9 palavras")
            if v["params"].get("categoria") not in ("historico", "mitologico", "academico", "religioso", "fonte"):
                raise ValueError(f"{k}: categoria inválida")
            continue
        f = v["params"].get("ficha")
        if not f or not f.get("nome") or not f.get("categoria"):
            raise ValueError(f"{k}: ficha sem nome/categoria")
        if f["categoria"] not in ("historico", "mitologico", "academico", "religioso", "fonte"):
            raise ValueError(f"{k}: categoria inválida {f['categoria']!r}")
    for cena, cid in POR_CENA.items():
        if cid not in CONTEUDO:
            raise ValueError(f"cena {cena}: conteúdo {cid!r} inexistente")
