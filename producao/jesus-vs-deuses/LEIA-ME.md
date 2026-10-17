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
6. **3D pontual (Blender)** — só onde agrega: abertura, reconstruções de templos e cidades, movimentos de câmera em ambientes históricos e momentos de maior impacto. Veja "Animação 3D" abaixo.
7. **Áudio** — ambiências e efeitos sintetizados por código (vento, drones, impactos, whooshes, passos…) ou arquivos licenciados das pastas `--musica`/`--efeitos`; *ducking* sobre a narração, fade-out final, -14 LUFS, pico ≤ -1,5 dBTP, sem clipping. Stems de música e efeitos ficam separados em `03-audio/`.
8. **Renderização** — blocos em paralelo → FFmpeg libx264 (1920×1080, 30 ou 24 fps, yuv420p, bt709) + AAC 256 kbps, com progresso, ETA, log, checagem de disco, reaproveitamento de blocos já prontos e limpeza dos temporários. `CANCELAR.txt` na pasta de saída (ou Ctrl+C) interrompe com segurança.
9. **Validação** (`quality_checker`) — decodifica o MP4 inteiro; confere duração, resolução, FPS, trilhas, tela preta/congelada inesperada, silêncio, loudness, **sincronia da narração por correlação cruzada (±20 ms)** e se os quadros batem com a linha do tempo. Se algo reprovar, o resultado é marcado como falha.
10. **Relatório** — `08-relatorio/relatorio-producao.md/.json`, `creditos-imagens.md` e `fontes-imagens.csv`; legendas em `05-legendas/*.srt`.

## Requisitos (Windows)

| Item | Como instalar |
|---|---|
| Python 3.10+ | python.org (marque "Add to PATH") |
| numpy e Pillow | `pip install numpy pillow` |
| FFmpeg + FFprobe | ffmpeg.org (ou `winget install Gyan.FFmpeg`) e confirme `ffmpeg -version` |
| Blender 4.x/5.x **ou** módulo `bpy` | blender.org (instalador) ou `pip install bpy` — só para as cenas 3D; sem ele o motor roda normalmente sem 3D |
| Internet | só para pesquisar imagens; com `--offline` ele usa as suas imagens e a arte procedural |

## Como rodar

Clique duas vezes em **`PRODUZIR-VIDEO.bat`** e informe o caminho da narração (ou arraste o arquivo sobre ele), ou:

```
python -m motor_video produzir ^
  --narracao "C:\Users\davi\Videos\Captures\lv_0_20261017144122.mp4" ^
  --roteiro entrada\prompt_narracao_e_producao_jesus.txt ^
  --transcricao entrada\lv_0_20261017144122.vtt ^
  --saida saida\producao ^
  --prioridade-3d 2 --qualidade-3d padrao --orcamento-3d 90
```

Resultado: `saida\producao\07-exportacao\jesus-contra-todos-os-deuses.mp4`.

Opções úteis: `--previa 60` (só o primeiro minuto, para conferir), `--listar-3d` (mostra as cenas 3D e o tempo estimado, sem renderizar), `--so-3d` (renderiza só o 3D e guarda em cache), `--offline`, `--fps 24`, `--musica PASTA`, `--efeitos PASTA`, `--imagens PASTA` (imagens suas, nomeadas com o id da cena, ex. `c05-nazare_1.jpg`), `--legendas-queimadas`, `--encoder gpu`, `--trabalhadores N`, `--manter-temporarios`. Veja tudo com `python -m motor_video produzir --help`.

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

## Estrutura da pasta de saída

```
00-entrada/        narração convertida (WAV 48k/24) e relatório de entradas
01-roteiro/        alinhamento roteiro↔tempos
02-imagens/        originais + trabalho + manifesto (fonte, autor, licença, hash)
03-audio/          stems de música e efeitos, mix final
04-linha-do-tempo/ linha-do-tempo.json e clipes-3d/ (cache)
05-legendas/       SRT
06-temporarios/    blocos de vídeo (apagados ao final, salvo --manter-temporarios)
07-exportacao/     MP4 final
08-relatorio/      relatório, créditos e CSV de fontes
logs/              log detalhado de cada execução
```

## Testes

```
python -m unittest discover -s testes -t .
```

Cobrem: análise e alinhamento, storyboard/timeline, pesquisa e licenças (servidor HTTP simulado, incluindo 429, queda de rede e hosts bloqueados), efeitos visuais, mixagem/ducking/loudness, renderização completa em baixa resolução, o validador (que precisa **reprovar** vídeo preto, curto ou dessincronizado), ingestão, relatório e CLI. `test_blender.py` renderiza quadros e clipes reais se o Blender for encontrado (defina `MOTOR_BLENDER`) e é pulado caso contrário.

## Limites que você precisa conhecer

- **Imagens reais dependem de internet** (Commons, Met, AIC). Offline, ou quando a rede bloqueia esses sites, o motor usa arte procedural/3D e lista no relatório cada cena que ficou **sem imagem real** ("pendências"). Para trocar uma delas, coloque a imagem em `--imagens` com o id da cena.
- **Áudio sintetizado ≠ gravação.** Ambiências e efeitos gerados por código não são apresentados como registros históricos. Para um resultado de estúdio, ponha música e efeitos licenciados em `--musica` / `--efeitos`.
- **A qualidade do 3D acompanha a máquina.** Em CPU, `teste`/`previa` servem para conferir e `padrao`/`alta` pedem horas; com GPU e Cycles o tempo cai bastante. As cenas 3D são ilustrações procedurais, não modelos de museu.
- A validação automática cobre arquivo, sincronia, quadros e áudio; **a revisão humana** (assistir e ouvir de fone) continua sendo necessária antes de publicar.
- Os créditos CC BY/CC BY-SA aparecem no relatório e, se não desligar com `--sem-creditos-na-tela`, em pequeno na tela.
