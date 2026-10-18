# Jesus contra todos os deuses — motor de produção de vídeo

Motor em Python que monta o documentário **a partir da sua narração já gravada**. Ele não gera voz, não altera a
fala e não corta nem acelera palavras: a narração original entra no vídeo com o mesmo tempo, e tudo o mais
(imagens, câmera, 3D, efeitos, música, legendas) é encaixado nela.

## O que ele faz

1. **Entrada** — localiza e valida narração, roteiro e transcrição (`.vtt`/`.srt`); converte a narração para WAV 48 kHz/24 bits sem mexer no original (confere o SHA-256 no fim).
2. **Alinhamento** — liga o roteiro às palavras da transcrição (difflib) e interpola onde a transcrição errou; trechos sem fala no roteiro ficam marcados.
3. **Storyboard e linha do tempo** — 234 cenas ancoradas em frases do roteiro; cada plano guarda início/fim, texto narrado, descrição visual, arquivo, movimento de câmera, efeitos, música, transição, fonte e licença (`04-linha-do-tempo/linha-do-tempo.json`).
4. **Pesquisa de imagens** — Wikimedia Commons, Metropolitan Museum (Open Access) e Art Institute of Chicago. Só entram PD, CC0, CC BY e CC BY-SA; NC/ND, "uso justo", marca d'água e imagens geradas por IA são recusadas. Cada arquivo guarda autor, fonte, licença e hash (sem duplicatas). Imagens suas, na pasta `--imagens`, têm prioridade.
5. **Visual** — Ken Burns com foco seguro, panorâmicas, vinheta, grão leve, título/versículo/mapa/legenda, transições (dissolve, dip to black/gold/white) e uma única graduação de cor. Sem imagem real disponível, a cena usa arte procedural **identificada como tal** no relatório.
6. **3D pontual** — só onde agrega: abertura, reconstruções de templos e aldeias, movimentos de câmera em ambientes históricos e momentos de maior impacto. Duas rotas: **Three.js/WebGL** (cenas `cena3d_*`, padrão; veja "Motion graphics e cenas Three.js") e **Blender** (alternativa; veja "Animação 3D").
7. **Motion graphics por código** (`motion/`, Node + Chromium) — fichas de divindades, mapas animados, linhas do tempo e datas, todos como função pura do tempo (`window.seek(t)`), com informação classificada (fato histórico, tradição mitológica, datação acadêmica, crença religiosa, fonte antiga).
8. **Áudio** — trilha e efeitos **sintetizados por código com a Web Audio API** (`OfflineAudioContext`, WAV PCM; nenhum arquivo de áudio de terceiros) em andamentos por seção, com `beats.json` (grade de batidas planejada + confirmação por onsets) sincronizando cortes, títulos e impactos; ou arquivos licenciados das pastas `--musica`/`--efeitos`; *ducking* sobre a narração, fade-out final, -14 LUFS, pico ≤ -1,5 dBTP, sem clipping. Stems ficam separados em `03-audio/`.
9. **Renderização** — blocos em paralelo → FFmpeg libx264 (1920×1080, 30 ou 24 fps, yuv420p, bt709, CRF 16) + AAC 256 kbps, com progresso, ETA, log, checagem de disco, reaproveitamento de blocos já prontos e limpeza dos temporários. `CANCELAR.txt` na pasta de saída (ou Ctrl+C) interrompe com segurança.
10. **Validação** (`quality_checker`) — decodifica o MP4 inteiro; confere duração, resolução, FPS, trilhas, tela preta/congelada inesperada, silêncio, loudness, **sincronia da narração por correlação cruzada (±20 ms)** e se os quadros batem com a linha do tempo. Se algo reprovar, o resultado é marcado como falha.
11. **Relatório** — `08-relatorio/relatorio-producao.md/.json`, `creditos-imagens.md` e `fontes-imagens.csv`; legendas em `05-legendas/*.srt`.

## Requisitos (Windows)

| Item | Como instalar |
|---|---|
| Python 3.10+ | python.org (marque "Add to PATH") |
| numpy e Pillow | `pip install numpy pillow` |
| FFmpeg + FFprobe | ffmpeg.org (ou `winget install Gyan.FFmpeg`) e confirme `ffmpeg -version` |
| Node.js 18+ e `npm install` em `motion/` | nodejs.org; depois, na pasta `motion`: `npm install` (Three.js, GSAP, Playwright) e `npx playwright install chromium` — para motion graphics, cenas Three.js e trilha Web Audio. Sem isso o motor roda sem motion e usa a síntese NumPy |
| Blender 4.x/5.x **ou** módulo `bpy` | blender.org (instalador) ou `pip install bpy` — só para as cenas Blender (alternativa); sem ele o motor roda normalmente |
| Internet | só para pesquisar imagens; com `--offline` ele usa as suas imagens e a arte procedural |

## Como rodar

Clique duas vezes em **`PRODUZIR-VIDEO.bat`** e informe o caminho da narração (ou arraste o arquivo sobre ele), ou:

```
python -m motor_video produzir ^
  --narracao "C:\Users\davi\Videos\Captures\lv_0_20261017144122.mp4" ^
  --roteiro entrada\prompt_narracao_e_producao_jesus.txt ^
  --transcricao entrada\lv_0_20261017144122.vtt ^
  --saida saida\producao ^
  --imagens entrada\imagens-fornecidas ^
  --prioridade-3d 2 --qualidade-3d padrao --orcamento-3d 90
```

Resultado: `saida\producao\07-exportacao\jesus-contra-todos-os-deuses.mp4`.

Opções úteis: `--so-motion` (renderiza só os clipes de motion/Three.js e guarda em cache), `--motion-previa` (clipes em 960×540, só para revisão), `--so-revisao N` (gera as folhas de contato da rodada N e para antes de renderizar), `--sem-motion`, `--audio-numpy`, `--previa 60` (só o primeiro minuto, para conferir), `--listar-3d` (mostra as cenas 3D e o tempo estimado, sem renderizar), `--so-3d` (renderiza só o 3D e guarda em cache), `--offline`, `--fps 24`, `--musica PASTA`, `--efeitos PASTA`, `--imagens PASTA` (imagens suas, nomeadas com o id da cena, ex. `c05-nazare_1.jpg`), `--legendas-queimadas`, `--encoder gpu`, `--trabalhadores N`, `--manter-temporarios`. Veja tudo com `python -m motor_video produzir --help`.

A execução pode ser repetida: blocos de vídeo, clipes 3D e imagens já baixadas são reaproveitados enquanto nada mudar.

## Animação 3D (Blender) — uso seletivo

O 3D é a exceção, não a regra (menos de 10% das cenas do storyboard). Cada cena 3D tem uma **prioridade** e um **modo**:

| Prioridade | Quando entra | Exemplos |
|---|---|---|
| **P1** (`sempre`) | abertura, reconstruções e momentos de impacto | templo egípcio (abertura), templo grego, Ragnarök, colina das cruzes, túmulo vazio, aldeia da Judeia |
| **P2** (`sem_imagem`) | só se não houver imagem real adequada para a cena | Rá, Osíris, Anúbis, Zeus, Hades, Odin, relevo egípcio, fiorde nórdico, Mar da Galileia, mapas 3D |
| **P3** | opcional (`--prioridade-3d 3`) | paralaxe 2.5D de fotos reais |

`--prioridade-3d 1|2|3` escolhe até onde ir e `--orcamento-3d MIN` corta, por prioridade, o que ultrapassar o tempo de render estimado (a estimativa vem de um quadro de teste real em cada cena). Qualidades: `teste` (480×270, 4 amostras), `previa` (800×450, 8), `padrao` (1280×720, 32), `alta` (1920×1080, 96) — o clipe sempre é entregue em 1920×1080. Cycles roda em qualquer CPU (`--dispositivo-3d gpu` tenta a GPU e volta para a CPU se não houver). O Blender é detectado sozinho ou informado em `--blender` / variável `MOTOR_BLENDER`.

Toda cena 3D leva um rótulo na tela ("Reconstrução artística em 3D… não é registro histórico" ou "Representação artística estilizada em 3D: Anúbis"). Os deuses são **representações artísticas** da iconografia de cada tradição e o Ragnarök é tratado como evento mítico; **nenhuma cena 3D mostra Jesus** (a crucificação é só uma colina com três cruzes em silhueta, sem violência gráfica, e o túmulo aparece vazio), então nada afirma a aparência dele; as cenas 3D só ilustram o que a narração já diz.

Recursos CC0 do Poly Haven (HDRI/modelos) têm cliente pronto em `motor_video/recursos3d.py` (checksum e registro de licença); as cenas atuais usam céu e objetos gerados por código.

## Motion graphics e cenas Three.js (`motion/`)

Contrato de renderização (testado em `motion/tests/contrato.test.mjs`): cada composição é **função pura do tempo** — `window.loadScene(spec)` e `window.seek(t)`; sem CSS transitions/animations, sem `setTimeout`/`setInterval`, sem `requestAnimationFrame` (neutralizado pelo renderizador), sem `Math.random` (use `mulberry32` com semente fixa em `engine/rng.js`), sem estado acumulado: o mesmo (entrada, instante) produz os **mesmos pixels** em qualquer ordem e a frio. GSAP só é usado com linhas do tempo pausadas, dirigidas por `tl.totalTime(t)`. Saída: `node render.mjs --spec spec.json` → H.264 yuv420p, CRF 16, 1920×1080.

| Composição | O que mostra |
|---|---|
| `deus` | ficha animada com a ilustração fornecida (Zeus, Hades, Odin, Anúbis, Osíris, Rá), local no mapa e categoria da informação |
| `mapa` | mapa que "levanta" em perspectiva, câmera por regiões, rotas e marcadores (Natural Earth, domínio público) |
| `periodo` | linha do tempo animada com períodos, eventos e datas aproximadas |
| `cena3d_abertura` | céu noturno com Via Láctea e silhuetas de três tradições; título tipográfico revelado em sincronia com a grade |
| `cena3d_egito` | salão hipostilo (colunas papiriformes, claristório, feixes de luz, poeira) |
| `cena3d_grecia` | templo dórico 6×13 (fuste canelado, entablamento, frontões, telhado) em luz de fim de tarde |
| `cena3d_fiorde` | paisagem nórdica (relevo procedural, água, floresta instanciada, névoa) |
| `cena3d_judeia` | aldeia de pedra do século I (casas, arcos, banca, panos, oliveiras); vistas `viela` e `telhados` |
| `cena3d_golgota` | colina com três cruzes **vazias** fora dos muros (sem pessoas); vistas `tempestade`, `amanhecer`, `distante` |
| `cena3d_tumulo` | túmulo escavado na rocha, pedra circular rolada, câmara com os panos de linho; vistas `exterior`, `interior`, `saida` |
| `cena3d_galileia` | mar da Galileia: praia de seixos, juncos, barco de pesca do séc. I, redes, névoa; vistas `margem`, `lago`, `colinas`, `noite` |
| `cena3d_escritos` | rolo aberto e lamparina de barro (escrita **estilizada**, não é manuscrito real); vistas `mesa`, `lamparina`, `rolo` |
| `frase` | tipografia cinética: uma frase **literal da narração**, palavra por palavra no instante em que é dita, sobre o fundo do plano |
| `pontos` | diagrama vetorial dos cinco pontos da seção de comparação; o nó acende quando o narrador diz a palavra-chave |

Camadas híbridas: as cenas 3D aceitam `anotacoes` (rótulo 2D + linha-guia vetorial presos a um ponto 3D, projetados a cada quadro — frontão, coluna dórica, muralha, pedra removida) e o modo só-rodapé (`hud: {desligado, rodape}`) que mantém o aviso de reconstrução sem a ficha.

**Stills 3D (`motor_video/fundos3d.py`):** na parte sobre Jesus, os cenários genéricos que o storyboard pedia (luz dourada, pergaminho, cosmos, ruínas…) são trocados por quadros das cenas 3D renderizados uma vez em 2400×1350 (56 variações: outros pontos de vista de cada trilho de câmera), escolhidos pelo contexto da seção e alternados para não repetir em planos vizinhos; o compositor faz o movimento de câmera 2D por cima. Ficam em cache pelo hash do código.

**Ritmo de montagem:** planos com cenário gerado por código duram ~3,6–6,5 s e são cortados nos inícios de frase da narração; o 2º plano de uma cena reenquadra o mesmo cenário mais de perto (corte "punch-in", recorte 1:1 sem perda de resolução). A entrada padrão é **corte seco na fala**; fusão só em mudança de seção ou cena de ritmo lento. A tipografia entra ~0,5 s antes da primeira palavra e, se faltar tempo de leitura, avança até 1,3 s sobre o plano seguinte (corte em L, sem atravessar seções).

As cenas Three.js usam geometria real, texturas PBR **geradas por código** (nenhuma textura/modelo externo), sombras, iluminação por imagem a partir do céu procedural e câmeras em spline Catmull-Rom. São **reconstruções artísticas**: não são evidência arqueológica (as inscrições egípcias são marcas estilizadas, o templo grego não tem policromia nem esculturas, a paisagem nórdica não é um lugar real) e cada uma traz o aviso na tela. Sem GPU, o WebGL roda por software (SwiftShader): conte ~0,5–1 s por quadro em 960×540 e ~2,5–3 s em 1920×1080 com a resolução interna de 75 % (`motion_escala3d`, MSAA ligado; diferença visual medida: PSNR 41,9 dB contra o render cheio).

**Frame Motion (MCP):** o conector aparecia instalado, mas desabilitado na conversa e sem ferramentas expostas; nada foi inventado sobre ele e **não foi usado**. O motor próprio segue o mesmo contrato e pode ser ligado ao Frame Motion se o conector for habilitado.

## Trilha sonora (Web Audio) e `beats.json`

`motion/audio/` sintetiza, por seção do filme, música em 4/4 a partir de `composicao.json` (tonalidade, compasso, motivos, progressões, movimentos e intensidades por clima, cadência final IV–V–I): pads e cordas por síntese aditiva/subtrativa, coro, sub-grave, pulso percussivo, ostinatos, motivos recorrentes, sinos e *risers*, em barramentos por família (graves, harmonia, melodia, percussão, efeitos) com EQ e compressão moderadas e limitador no master; mais efeitos (impacto, whoosh, revelar, ping, rota…) calibrados contra o nível da narração. Efeitos leves que cairiam sobre uma palavra vão para a pausa mais próxima (até ±0,35 s) ou ficam 6 dB mais baixos. Tudo em `OfflineAudioContext`, gravado como WAV PCM 24 bits com dither (codificação própria em `audio/wav.mjs` e `motor_video/audio_wav.py`). É obra própria, **não imita gravações acústicas** e não usa amostras. As seções ficam em cache (`03-audio/cache-webaudio/`) e são sintetizadas em paralelo; `--so-audio` gera só o áudio.

`03-audio/relatorio-audio.md` mede cada faixa (narração original, música, efeitos, fundo após ducking, mix): LUFS, LRA, true peak, picos, clipping, subgraves, emendas entre seções, clareza da voz (razão voz/fundo na banda 300–3400 Hz só nos quadros com fala) e a cauda final; `formas-de-onda.png` e `espectrograma-mix.png` mostram o mesmo visualmente. Medição do filme inteiro nesta máquina: mix −14,0 LUFS, true peak −3,6 dBTP, clareza p5 19,3 dB, 14 emendas sem suspeita, cauda final a −109 dBFS.

`03-audio/beats.json` traz: andamento e compassos por seção, **todas as batidas** (`t`, compasso, tempo, forte), os marcos musicais (acordes, temas, sinos, *risers*) e a medição feita no áudio renderizado — os pulsos que a partitura agendou são procurados como onsets (±60 ms): `cobertura_pulsos`, desvio em ms, andamento medido e `confirmada`. Seções sem pulso percussivo suficiente ficam como "grade planejada, sem confirmação" em vez de fingir medição. Cortes, títulos, revelações e impactos de motion/3D se alinham a essa grade (tolerância 220 ms).

## Revisão antes da renderização final

1. `python -m motor_video produzir ... --so-revisao 1` gera, em `09-revisao/rodada-01/`, **um quadro por batida relevante** (entradas de plano, seções, eventos sonoros, meio e fim das animações e os dois primeiros segundos) compostos pelo mesmo compositor do vídeo final, em folhas de contato rotuladas com tempo, compasso:tempo, plano e níveis de áudio (mix/música/efeitos em dBFS), mais `metricas.json` (variedade visual, sincronia dos cortes com a grade, energia da abertura).
2. Quem revisa olha as folhas e registra, com `python -m motor_video avaliar --saida ... --rodada 1 --arquivo notas.json`, notas de 1 a 10 em: qualidade do 3D, qualidade da animação 2D, movimento/composição de câmera, integração 2D-3D, clareza em telas pequenas, variedade/originalidade, coerência histórica, sincronização com a narração, desempenho/estabilidade e impacto nos 2 primeiros segundos — no geral e, opcionalmente, por cena representativa (`"cenas": {...}`, com `"n/a"` quando a categoria não se aplica). O comando **recusa** notas sem justificativa, sem as folhas vistas como evidência ou (se alguma nota < 8) sem os 3 piores problemas.
3. Corrige-se, gera-se a rodada seguinte e repete-se até todas as notas serem ≥ 8; só então se renderiza o vídeo final. O histórico fica em `09-revisao/AVALIACAO.md`.

## Estrutura da pasta de saída

```
00-entrada/        narração convertida (WAV 48k/24) e relatório de entradas
01-roteiro/        alinhamento roteiro↔tempos
02-imagens/        originais + trabalho + manifesto (fonte, autor, licença, hash)
03-audio/          stems de música e efeitos, mix final, beats.json, webaudio/ (WAV por seção)
04-linha-do-tempo/ linha-do-tempo.json, clipes-3d/ (Blender) e clipes-motion/ (motion/Three.js), em cache
05-legendas/       SRT
06-temporarios/    blocos de vídeo (apagados ao final, salvo --manter-temporarios)
07-exportacao/     MP4 final
08-relatorio/      relatório, créditos e CSV de fontes
09-revisao/        folhas de contato por batida, métricas e avaliações de cada rodada
logs/              log detalhado de cada execução
```

## Tempos medidos (referência)

Execução completa de 29:16 de vídeo, em uma máquina de 4 núcleos, sem GPU: 17 clipes 3D em qualidade `teste` ≈ 35 min (só na primeira vez; depois ficam em cache), áudio ≈ 3,5 min, renderização do vídeo (libx264, preset fast, CRF 19 nessa medição; o padrão agora é CRF 16, ~30% maior, 4 processos) ≈ 40 min, validação completa ≈ 10 min. O MP4 final teve ≈ 670 MB. Qualidades 3D maiores multiplicam o tempo do 3D: use `--listar-3d` para ver a estimativa antes e `--orcamento-3d` para limitar.

## Testes

```
python -m unittest discover -s testes -t .
```

Cobrem: tipografia sincronizada com a fala, ritmo de montagem (cortes, reenquadramento, transições), stills 3D, acomodação dos efeitos à fala, análise e alinhamento, storyboard/timeline, pesquisa e licenças (servidor HTTP simulado, incluindo 429, queda de rede e hosts bloqueados), efeitos visuais, mixagem/ducking/loudness, renderização completa em baixa resolução, o validador (que precisa **reprovar** vídeo preto, curto ou dessincronizado), ingestão, relatório e CLI. `test_blender.py` renderiza quadros e clipes reais se o Blender for encontrado (defina `MOTOR_BLENDER`) e é pulado caso contrário.

## Limites que você precisa conhecer

- **Imagens reais dependem de internet** (Commons, Met, AIC). Offline, ou quando a rede bloqueia esses sites, o motor usa arte procedural/3D e lista no relatório cada cena que ficou **sem imagem real** ("pendências"). Para trocar uma delas, coloque a imagem em `--imagens` com o id da cena.
- **Áudio sintetizado ≠ gravação.** Ambiências e efeitos gerados por código não são apresentados como registros históricos. Para um resultado de estúdio, ponha música e efeitos licenciados em `--musica` / `--efeitos`.
- **Cenas Three.js em CPU são lentas**: sem GPU o WebGL roda por software; os 25 planos 3D em movimento deste filme (≈ 160 s) levam ~3 h em 1080p numa máquina de 4 núcleos (reaproveitados do cache depois). `--motion-previa` renderiza em 960×540 para revisar.
- **Síntese de seções longas é lenta**: o tempo de render do `OfflineAudioContext` cresce mais que a duração (60 s de música ≈ 40 s; 120 s ≈ 150 s; a seção de 289 s levou ~17 min). O cache e o paralelismo evitam repetir isso; dividir as seções em blocos é a melhoria pendente.
- **A qualidade do 3D acompanha a máquina.** Em CPU, `teste`/`previa` servem para conferir e `padrao`/`alta` pedem horas; com GPU e Cycles o tempo cai bastante. As cenas 3D são ilustrações procedurais, não modelos de museu.
- A validação automática cobre arquivo, sincronia, quadros e áudio; **a revisão humana** (assistir e ouvir de fone) continua sendo necessária antes de publicar.
- **Datas e fatos das fichas** foram escritos de conhecimento geral, sem consulta online (a produção rodou sem internet): confira em fonte acadêmica antes de publicar (veja `motor_video/motion_conteudo.py`, constante `VERIFICAR`).
- **Ilustrações dos deuses fornecidas por você** têm origem/licença não verificadas (a de Odin traz a assinatura de Talita Babiresti): obtenha autorização antes de publicar; elas aparecem rotuladas como ilustrações modernas, nunca como arte antiga.
- A trilha sintetizada nunca foi ouvida por uma pessoa nesta produção: foi conferida só por medições (níveis, espectro, picos, onsets). Ouça antes de publicar.
- Os créditos CC BY/CC BY-SA aparecem no relatório e, se não desligar com `--sem-creditos-na-tela`, em pequeno na tela.
