# Auditoria do projeto — visual, 3D, áudio e pipeline

Data: 18/10/2026. Base: código desta pasta e as produções de teste da sessão (linha do tempo completa de 236 planos,
prévia de 100 s com motion, render completo anterior com clipes Blender). Os números abaixo foram **medidos** nesses
arquivos; onde há julgamento visual, ele vem de quadros extraídos e está identificado como tal.

## 1. Como as cenas são construídas

| Etapa | Arquivo | O que faz |
|---|---|---|
| Roteiro → planos | `storyboard_jesus.py`, `storyboard.py` | Cada cena do roteiro vira 1+ planos com fundo, câmera, cor, overlays, transição e efeitos sonoros. |
| Alinhamento | `script_analyzer.py` | Casa o roteiro com as legendas (VTT) da narração. A sincronia é **por frase** (início/fim de cada legenda); não há tempo por palavra. |
| Linha do tempo | `timeline_builder.py` | Planos em segundos absolutos, seções musicais, eventos de áudio, eventos das animações. |
| Fundo de cada plano | `procedural_art.py`, `visual_effects.py` | Imagem (fornecida/baixada), vídeo/clipe 3D, mapa ou cenário gerado por código (15 “motivos”). |
| Câmera 2D | `visual_effects.py` | 9 presets de Ken Burns (zoom, pan, tilt, deriva, respiro, foco). |
| Textos | `text_graphics.py` | Título, capítulo, versículo, rótulo, ponto, lista. |
| Motion graphics | `motion/` (Node + Chromium) | Composições puras do tempo (`window.seek(t)`), renderizadas por `render.mjs` em H.264. |
| 3D | `motion/comps/cena3d_*.js` (Three.js) e `motor_video/cenas3d` (Blender, legado) | Cenas tridimensionais com câmera em trilho. |
| Composição final | `video_renderer.py` | Compõe cada quadro (fundo + câmera + overlays + transições + legendas) e codifica H.264/AAC. |

## 2. Distribuição real dos planos (filme inteiro, 1756 s, 236 planos)

| Medida | Valor | Leitura |
|---|---|---|
| Duração mediana do plano | 6,9 s (máx. 18,2 s) | Sem novidade visual a cada 2–4 s na maior parte do filme. |
| Fundo gerado por código (“motivo”) | 221 planos (94 %) | Só 15 motivos distintos; `luz_dourada` aparece 64 vezes, `pergaminho` 33, `ruinas` 26. |
| Imagens reais | 6 planos (as ilustrações fornecidas) | A busca no Wikimedia Commons é bloqueada pela política de rede do ambiente (HTTP 403 em `commons.wikimedia.org` e `upload.wikimedia.org`). |
| Transição de entrada | dissolve 209 (89 %), dips 26, corte 1 | Fusão usada como solução universal. |
| Câmera | `zoom_in` 80 (34 %), `deriva` 43, `pan_dir` 34 | Movimento repetitivo. |
| Textos sobre a imagem | 33 em 236 planos | Pouca camada editorial. |
| Planos com motion graphics | 19 (130 s, 7,4 % do tempo) | Concentrados nas seções 1–2. Seções 4 (amor), 8 (comparação) e 9 (encerramento): nenhum. |
| Planos com 3D Three.js | 5 (27,5 s, 1,6 %) | Abaixo dos 10–20 % de cenas com destaque 3D pedidos. |

Por seção (planos · mediana · overlays · motion): abertura 8 · 3,8 s · 0 · 2; civilizações 17 · 7,4 s · 2 · 10;
identidade 56 · 6,6 s · 6 · 4; amor 15 · 9,8 s · 4 · 0; morte 24 · 7,7 s · 2 · 1; crucificação 28 · 6,7 s · 5 · 1;
ressurreição 29 · 7,8 s · 3 · 1; comparação 26 · 7,2 s · 8 · 0; encerramento 33 · 6,8 s · 3 · 0.

**Conclusão:** a parte sobre Jesus (seções 3–9, ~1200 s, 70 % do filme) é a mais fraca visualmente: cenários
procedurais repetidos, zoom lento e fusões, quase sem 3D, mapas, diagramas ou tipografia.

## 3. Sistema de animação

- **Python (compositor):** câmera Ken Burns por plano, overlays com entrada/saída, transições (corte, dissolve, dip
  preto/dourado/branco). Determinístico (quadro = função do tempo), paralelizado em blocos de 4 processos.
- **Motion (`motion/`):** composições `deus`, `mapa`, `periodo` e as cenas 3D; GSAP só em timelines pausadas e
  posicionadas por `seek`; `Math.random` substituído por mulberry32; `requestAnimationFrame` neutralizado; quadros
  capturados em qualquer ordem dão o mesmo resultado (testes de contrato em `motion/tests/contrato.test.mjs`).

## 4. 3D

- **Blender (legado, `motor_video/cenas3d`):** 17 clipes no render anterior (templos, colina das cruzes, túmulo
  vazio, aldeia, lago da Galileia, Ragnarök, deuses). Quadros extraídos mostram geometria muito simples (cubos, esfera
  como pedra do túmulo, colina lisa), céu estourado e pouca textura: **qualidade abaixo da direção pedida**.
- **Three.js (novo):** kit de arquitetura (`engine/arq.js`: colunas dóricas com estrias e êntase, colunas papiriformes,
  pilones, obeliscos, casas, oliveiras instanciadas, terreno), texturas procedurais (`engine/tex.js`), céu com
  dispersão/nuvens/estrelas, IBL do próprio céu, sombras, poeira em GPU, feixes de luz, câmera em spline. Cenas: abertura,
  Egito (Karnak), Grécia (Olímpia), fiorde nórdico, aldeia da Galileia. Qualidade claramente superior ao Blender legado.
- **Custo medido (SwiftShader, 4 núcleos, 1920×1080):** ~4,6 s/quadro com MSAA em resolução cheia; ~2,7 s/quadro com
  resolução interna de 75 % e MSAA (diferença visual mínima: PSNR 41,9 dB contra o render cheio, sem serrilhado
  visível). Isso limita quantos segundos de 3D cabem num render completo; a resolução interna agora é configurável
  (`spec.render3d = {escala, msaa}`).

## 5. Linha do tempo × narração

- Planos começam e terminam em fronteiras de frase das legendas; eventos de motion trazem o instante dentro do clipe.
- Não há tempo por palavra (o VTT tem frases de 3–6 s). Tipografia cinética deve sincronizar pela frase e distribuir
  palavras proporcionalmente — e dizer isso.
- `alinhamento.json` registra lacunas (trechos do roteiro sem fala correspondente), que não recebem cenas próprias.

## 6. Frame Motion (MCP)

O conector “Frame motion” aparece como conectado na conta, mas **não está habilitado nesta conversa** (nenhuma ferramenta
exposta). Não foi usado e nenhum método dele foi inventado. O motor próprio segue o mesmo contrato (render por código,
determinístico) e `motion_bridge.renderizar_clipes` é o ponto de troca caso o conector seja habilitado.

## 7. Pipeline de quadros, áudio e MP4

Quadros: Python compõe (PIL/NumPy) e envia ao FFmpeg (libx264, CRF 16, yuv420p, 1920×1080, 30 fps). Clipes de motion e
3D chegam como MP4 H.264 CRF 16 e entram como “vídeo” do plano. Áudio: narração original (inalterada) + música e efeitos
sintetizados por Web Audio (`OfflineAudioContext`), mixados no FFmpeg com ducking multibanda; AAC 256 kb/s 48 kHz no MP4.
Controle de qualidade (`quality_checker.py`): fluxos, contagem de quadros, quadros amostrados × linha do tempo, áudio.

## 8. Pontos fracos (prioridade)

1. Parte de Jesus (seções 3–9) sem 3D, sem diagramas e com cenário procedural repetido.
2. Fusão em 89 % das entradas e `zoom_in` em 34 % dos planos.
3. Planos longos (mediana 6,9 s) sem acontecimentos internos sincronizados com a fala.
4. Clipes 3D do Blender fracos (túmulo e colina das cruzes especialmente).
5. Pouca tipografia editorial e nenhum diagrama comparativo na seção de comparação.

## 9. O que reaproveitar

Motor determinístico (`render.mjs`), kit 3D Three.js, céu/atmosfera, composições `deus`/`mapa`/`periodo`, ficha/HUD
(`engine/ficha.js`, `base3d.js`), compositor Python, ciclo de revisão (`revisao.py`), todo o áudio.

## 10. Plano de evolução (etapas)

- **A** Auditoria (este documento).
- **B** Sistema editorial 2D: tipografia cinética sincronizada por frase; diagrama comparativo; transições por corte
  na fala e variedade de câmera.
- **C** Novas cenas Three.js para a parte de Jesus: colina das cruzes e túmulo vazio (substituindo os clipes Blender),
  mar da Galileia; variantes de câmera das cenas existentes.
- **D** Híbridos: rótulos e linhas vetoriais projetados sobre o 3D.
- **E** Distribuição: 10–20 % dos planos com destaque 3D; motion também nas seções 4, 8 e 9.
- **F** Ciclo de QC (folhas de contato, notas 1–10 em 9 categorias, corrigir as 3 piores, repetir até ≥ 8).
- **G** Render completo, validação do MP4 e relatório final.
