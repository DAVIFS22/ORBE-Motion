---
name: finalizando-documentario
description: Use quando for preciso produzir, retomar ou entregar o MP4 final de um documentário do motor_video (producao/jesus-vs-deuses) — render longo interrompido ou contêiner reiniciado, arquivo .parcial.mp4, vídeo maior que o limite de envio de 400 MiB, usuário pedindo partes de 500 MB ou juntar partes no Windows, thumbnail/capa, título, descrição e capítulos do YouTube, ou git push recusado com 403.
---

# Finalizando o documentário (motor_video → MP4 entregue)

## Visão geral
O motor renderiza clipes com cache por hash do código, compõe, codifica e **valida** o MP4 sozinho. O trabalho é: rodar o comando certo, retomar sem perder cache, e entregar um arquivo de 5–6 GB por um canal de **400 MiB por arquivo**.

## 1. Produzir ou retomar o MP4 final
```bash
cd producao/jesus-vs-deuses
python3 -m motor_video produzir --narracao NARRACAO.mp3 --roteiro entrada/prompt_narracao_e_producao_jesus.txt \
  --transcricao entrada/NARRACAO.vtt --imagens entrada/imagens-fornecidas --saida SAIDA --prioridade-3d 0 --offline > final.log 2>&1
```
| Flag | No vídeo final |
|---|---|
| `--validacao` | **Nunca** com narração real (põe aviso de "narração sintética" no relatório) |
| `--motion-previa` | Não (clipes 960×540) |
| `--so-revisao N` | Não (para antes de renderizar o vídeo) |

- Rode com `run_in_background` e `timeout: 7200000`. Se o processo morrer (limite de 2 h ou contêiner reiniciado): apague `SAIDA/04-linha-do-tempo/clipes-motion/*.parcial.mp4` e rode **o mesmo comando** — clipes prontos vêm do cache; perde-se só o que estava em andamento.
- Acompanhe com Monitor: `grep -E "^==|PRODUÇÃO|ERRO|Traceback|FALHOU|100%\)"` no log.
- Pronto quando o log diz `PRODUÇÃO CONCLUÍDA E VALIDADA` → `SAIDA/07-exportacao/*.mp4`, relatório em `08-relatorio/`. Precisa de ~9 GB livres; temporários são apagados no sucesso.
- Ritmo: 3D ≈ 2 s/quadro sozinho, ≈ 4 s com a fila 2D junto; vídeo final ≈ 16 quadros/s.
- **Não edite `motion/comps` nem `motion/engine` com um render rodando**: cada página do Chromium carrega as composições uma vez e o hash do cache é calculado no início. Edite antes de lançar. Mudar `engine/` invalida todos os clipes; mudar uma comp invalida só os clipes dela.

## 2. Validar além do automático
Tire quadros do começo/meio/fim (`ffmpeg -ss T -i FINAL.mp4 -frames:v 1`), monte uma folha e **olhe**. Confira com ffprobe: 1920×1080, H.264 yuv420p, AAC, duração ≥ narração.

## 3. Entregar (SendUserFile: 400 MiB por arquivo; 500 MB = 476,8 MiB → recusado)
Mova o master para `ENTREGA/` e ponha `ENTREGA/` em `.git/info/exclude`.

| Objetivo do usuário | Ferramenta |
|---|---|
| Um arquivo único no PC (padrão) | `python3 scripts/dividir_por_bytes.py MASTER.mp4 SAIDA` → pedaços `.001…` + `JUNTAR_FILME.bat` (copy /b + certutil SHA-256, nada a instalar). Pouco disco: `--parte N` cria um por vez (criar → conferir com `PARTES.sha256` → enviar → apagar). |
| Assistir cada parte | `python3 scripts/dividir_para_envio.py MASTER.mp4 SAIDA` (cortes em keyframe, ≤375 MiB, confere a soma de quadros) + `sh scripts/montar_kit_windows.sh SAIDA` (zip com ffmpeg.exe oficial + .bat que procura as partes na pasta, na pasta acima, em Downloads e aceita arrastar a pasta). |

Diga antes de enviar: limite real, número de partes, que o .bat junta com dois cliques ("Mais informações → Executar assim mesmo").

## 4. Thumbnail
Kit em `producao/jesus-vs-deuses/capa/` (placa 3D `placa-spec.json` + `montar.mjs` sobre `capa.html`) — reproduz a capa entregue pixel a pixel. Teste a leitura em 168×94. Não use ilustrações de licença não verificada.

## 5. Título, descrição e capítulos
`python3 scripts/capitulos_youtube.py SAIDA/04-linha-do-tempo/linha-do-tempo.json` (00:00 primeiro, ≥10 s cada). Na descrição: referências citadas, que as cenas 3D são reconstruções artísticas, créditos (Natural Earth, autores de ilustrações).

## 6. git push 403
Sem permissão de escrita do app: não repita o push. `git bundle create ENTREGA/commits.bundle origin/main..BRANCH`, envie e passe `git fetch ARQ.bundle BRANCH:BRANCH && git push -u origin BRANCH`.

## Erros comuns
| Erro | Correção |
|---|---|
| `.bat` diz que faltam as 15 partes | "Extrair Tudo" cria subpasta; use o .bat que procura pastas ou arraste a pasta das partes sobre ele |
| `!` some do texto do .bat | Com `EnableDelayedExpansion`, não use `!` em `echo` |
| .bat quebra | Só ASCII, CRLF, lista explícita 01…N (curinga não garante ordem) |
| Partes de 500 MB | Excedem 400 MiB; use ≤380 MiB |
| Sol fora do lugar na placa 3D | A cúpula do céu é centrada na origem; centralize-a na câmera |
