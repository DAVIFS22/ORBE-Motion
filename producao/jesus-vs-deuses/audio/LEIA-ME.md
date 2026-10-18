# Jesus contra todos os deuses: áudio

Estes scripts rodam no seu Windows com FFmpeg. Eles tratam a narração que já existe sem gerar voz nova, sem cortar palavras e sem mudar a velocidade. Depois mixam trilha e efeitos licenciados com ducking automático.

## 0. Instalar o FFmpeg (uma vez)

```
winget install Gyan.FFmpeg
```

Depois disso, feche e abra o terminal de novo.

## 1. Tratar a narração (MP3 + WAV 24 bits/48 kHz + vídeo sincronizado)

Dê dois cliques em `TRATAR-NARRACAO.bat`. Por padrão, ele usa
`C:\Users\davi\Videos\Captures\lv_0_20261017144122.mp4`. Para tratar outro arquivo, arraste-o sobre o `.bat`.

Os arquivos ficam em `C:\Users\davi\Videos\Captures\lv_0_20261017144122-audio-tratado\`:

| Pasta | Conteúdo |
|---|---|
| `00-original` | Áudio original extraído em **MP3 320 kbps** e WAV. O MP4 original não é alterado. |
| `01-narracao` | Narração tratada em **WAV PCM 24 bits / 48 kHz** e MP3. |
| `04-exportacao` | Vídeo original com o áudio tratado. O vídeo é copiado sem recompressão, então a sincronia é exata. |
| `relatorio-audio.txt` | Análise antes e depois, as decisões tomadas, as pausas longas e a verificação. |

O tratamento se adapta à análise e só aplica o que for necessário:

- **Ruído:** a redução só é aplicada se o piso de ruído for maior que -62 dB. Ela é leve ou moderada, conforme o nível. Um áudio limpo não recebe redução, para evitar som metálico.
- **Clipping:** o `adeclip` só entra se houver clipping real.
- **Correções fixas:** estalos com `adeclick` conservador e graves indesejados com passa-altas de 70 Hz.
- **EQ moderada:** -2,5 dB em 280 Hz contra o som embolado, +2 dB em 3,2 kHz para clareza e +1 dB de "ar".
- **Sibilância e volume:** de-esser e compressão 2,5:1 suave.
- **Loudness:** normalização em duas passagens, em modo linear, que preserva as pausas e a dinâmica. O alvo é -16 LUFS com true peak de no máximo -1,5 dBTP.
- **Pausas:** nada é cortado. Pausas com mais de 2,5 s são listadas no relatório para você conferir se são dramáticas ou acidentais.
- **Verificação:** o script compara a duração do original com a tratada, confere o true peak e procura clipping.

> Se o `lv_0_...mp4` foi exportado do CapCut com a **música já misturada** na voz, não é possível baixar só a música sem separar as fontes antes. Nesse caso, exporte do CapCut a narração sem música. Também é possível separar as fontes antes com uma ferramenta como o Demucs.

## 2. Trilha e efeitos sonoros

1. Coloque os arquivos **licenciados** (WAV ou MP3) em `...-audio-tratado\biblioteca\efeitos\` e `...\biblioteca\musica\`. Use bibliotecas com licença para o projeto, como a Biblioteca de Áudio do YouTube, Epidemic Sound ou Artlist.
2. Abra `cues-efeitos.csv` no Excel. Ele já traz as 9 seções da direção de áudio. Para cada linha que você quiser usar:
   - preencha `inicio` com o momento do vídeo (`83.5`, `1:23.5` ou `00:01:23.5`);
   - confira o nome em `arquivo`.

   Linhas com `inicio` vazio são ignoradas. Os whooshes e impactos já usam arquivos diferentes para não repetir o mesmo som.
3. Rode o script:

   ```
   powershell -ExecutionPolicy Bypass -File mixar-trilha-efeitos.ps1
   ```

O script gera faixas separadas:

- `02-musica\musica-sintetizada.wav`: a música cai cerca de 10 dB enquanto há fala;
- `03-efeitos\efeitos-sintetizados.wav`: os efeitos têm ducking leve;
- `04-exportacao\mix-final-48k24.wav`: o mix final, em -14 LUFS, o padrão do YouTube, com true peak de no máximo -1 dBTP;
- `04-exportacao\...-mix-final.mp4`: o vídeo com o mix final.

Para ajustar o mix, mude `ganho_db` e os fades no CSV e rode o script de novo. Faça a escuta final em fones de ouvido e em alto-falantes comuns.
