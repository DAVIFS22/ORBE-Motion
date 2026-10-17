<#
  Jesus contra todos os deuses - tratamento da narracao existente.

  Nao gera voz nova e nao altera o conteudo falado. Nenhum filtro muda o
  tempo do audio (sem cortes, sem time-stretch), entao a versao tratada
  continua sincronizada com o video.

  Uso (PowerShell):
    powershell -ExecutionPolicy Bypass -File tratar-narracao.ps1
    powershell -ExecutionPolicy Bypass -File tratar-narracao.ps1 -Entrada "D:\outro\video.mp4"

  Requer FFmpeg no PATH (winget install Gyan.FFmpeg).
#>
param(
    [string]$Entrada = "C:\Users\davi\Videos\Captures\lv_0_20261017144122.mp4",
    [string]$Saida = "",
    # Alvo da narracao isolada. -16 LUFS deixa folga para musica/efeitos;
    # o mix final (mixar-trilha-efeitos.ps1) entrega -14 LUFS para o YouTube.
    [double]$AlvoLufs = -16,
    [double]$TruePeak = -1.5
)

$ErrorActionPreference = "Stop"
$inv = [Globalization.CultureInfo]::InvariantCulture

function Num([double]$v) { $v.ToString("0.###", $inv) }

function Rodar-FFmpeg([string[]]$argumentos) {
    # FFmpeg escreve analises no stderr; capturamos tudo como texto.
    $psi = New-Object Diagnostics.ProcessStartInfo
    $psi.FileName = "ffmpeg"
    $psi.Arguments = ($argumentos | ForEach-Object {
        if ($_ -match '[\s;,\[\]=]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ }
    }) -join " "
    $psi.UseShellExecute = $false
    $psi.RedirectStandardError = $true
    $psi.RedirectStandardOutput = $true
    $p = [Diagnostics.Process]::Start($psi)
    $errTask = $p.StandardError.ReadToEndAsync()
    $null = $p.StandardOutput.ReadToEnd()
    $p.WaitForExit()
    $log = $errTask.Result
    if ($p.ExitCode -ne 0) { throw "FFmpeg falhou (codigo $($p.ExitCode)):`n$log" }
    return $log
}

function Duracao([string]$arquivo, [string]$stream) {
    $d = & ffprobe -v error -select_streams $stream -show_entries stream=duration -of csv=p=0 $arquivo
    if (-not $d -or $d -eq "N/A") {
        $d = & ffprobe -v error -show_entries format=duration -of csv=p=0 $arquivo
    }
    return [double]::Parse(($d | Select-Object -First 1), $inv)
}

function Analisar([string]$arquivo) {
    $log = Rodar-FFmpeg @("-hide_banner", "-nostats", "-i", $arquivo, "-vn",
        "-af", "astats=measure_perchannel=none,silencedetect=n=-45dB:d=2.5,loudnorm=I=$(Num $AlvoLufs):TP=$(Num $TruePeak):LRA=11:print_format=json",
        "-f", "null", "-")
    $r = @{}
    foreach ($chave in "Peak level dB", "RMS level dB", "Noise floor dB", "Flat factor", "DC offset") {
        $m = [regex]::Matches($log, [regex]::Escape($chave) + ':\s*(-?[\d\.]+|-inf)')
        if ($m.Count -gt 0) {
            $v = $m[$m.Count - 1].Groups[1].Value
            $r[$chave] = if ($v -eq "-inf") { -200.0 } else { [double]::Parse($v, $inv) }
        }
    }
    $json = [regex]::Match($log, '\{[^{}]*"input_i"[^{}]*\}').Value
    $r["loudnorm"] = $json | ConvertFrom-Json
    $silencios = @()
    foreach ($m in [regex]::Matches($log, 'silence_end:\s*([\d\.]+)\s*\|\s*silence_duration:\s*([\d\.]+)')) {
        $fim = [double]::Parse($m.Groups[1].Value, $inv)
        $dur = [double]::Parse($m.Groups[2].Value, $inv)
        $silencios += [pscustomobject]@{ Inicio = $fim - $dur; Duracao = $dur }
    }
    $r["silencios"] = $silencios
    return $r
}

function Tempo([double]$s) { [TimeSpan]::FromSeconds($s).ToString("hh\:mm\:ss\.f") }

# ---------------------------------------------------------------------------
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    throw "FFmpeg nao encontrado. Instale com: winget install Gyan.FFmpeg  (depois reabra o PowerShell)"
}
if (-not (Test-Path -LiteralPath $Entrada)) { throw "Arquivo nao encontrado: $Entrada" }

$base = [IO.Path]::GetFileNameWithoutExtension($Entrada)
if (-not $Saida) { $Saida = Join-Path (Split-Path $Entrada) "$base-audio-tratado" }
$pastas = @{
    original   = Join-Path $Saida "00-original"
    narracao   = Join-Path $Saida "01-narracao"
    exportacao = Join-Path $Saida "04-exportacao"
}
$pastas.Values | ForEach-Object { New-Item -ItemType Directory -Force -Path $_ | Out-Null }

# 1. Original intacto: so lemos o arquivo de entrada; extraimos copias.
$wavOriginal = Join-Path $pastas.original "$base-original-48k24.wav"
$mp3Original = Join-Path $pastas.original "$base-original.mp3"
Write-Host "[1/5] Extraindo audio original (WAV 48 kHz/24 bits e MP3 320 kbps)..."
Rodar-FFmpeg @("-y", "-hide_banner", "-i", $Entrada, "-vn", "-map", "0:a:0", "-ar", "48000", "-c:a", "pcm_s24le", $wavOriginal) | Out-Null
Rodar-FFmpeg @("-y", "-hide_banner", "-i", $Entrada, "-vn", "-map", "0:a:0", "-c:a", "libmp3lame", "-b:a", "320k", $mp3Original) | Out-Null

# 2. Analise do audio completo.
Write-Host "[2/5] Analisando o audio completo..."
$antes = Analisar $wavOriginal
$ln = $antes["loudnorm"]
$ruido = $antes["Noise floor dB"]
$pico = $antes["Peak level dB"]
$clip = ($pico -ge -0.1) -and ($antes["Flat factor"] -gt 0)

# 3. Cadeia de filtros: cada etapa so entra se a analise indicar necessidade.
$filtros = New-Object Collections.Generic.List[string]
$decisoes = New-Object Collections.Generic.List[string]

$filtros.Add("highpass=f=70:poles=2")
$decisoes.Add("Passa-altas 70 Hz: remove ronco/vento grave sem afinar a voz.")

if ([math]::Abs($antes["DC offset"]) -gt 0.001) {
    $filtros.Add("dcshift=$(Num (-$antes['DC offset']))")
    $decisoes.Add("DC offset de $(Num $antes['DC offset']) corrigido.")
}
if ($clip) {
    $filtros.Add("adeclip")
    $decisoes.Add("Clipping detectado (pico $(Num $pico) dBFS, flat factor $(Num $antes['Flat factor'])): adeclip aplicado.")
} else {
    $decisoes.Add("Sem clipping no original (pico $(Num $pico) dBFS).")
}
# Remocao suave de estalos/cliques de boca.
$filtros.Add("adeclick=w=55:o=75:t=3")
$decisoes.Add("Remocao de estalos (adeclick conservador, limiar 3).")

if ($ruido -gt -50) {
    $filtros.Add("afftdn=nr=12:nf=$(Num ([math]::Max($ruido, -80))):tn=1")
    $decisoes.Add("Ruido de fundo alto ($(Num $ruido) dB): reducao de 12 dB com rastreamento.")
} elseif ($ruido -gt -62) {
    $filtros.Add("afftdn=nr=6:nf=$(Num $ruido):tn=1")
    $decisoes.Add("Ruido de fundo moderado ($(Num $ruido) dB): reducao leve de 6 dB.")
} else {
    $decisoes.Add("Ruido de fundo baixo ($(Num $ruido) dB): sem reducao de ruido (evita som metalico).")
}

# EQ moderada: tira embolado, da presenca e um pouco de ar.
$filtros.Add("equalizer=f=280:t=q:w=1.1:g=-2.5")
$filtros.Add("equalizer=f=3200:t=q:w=1.2:g=2")
$filtros.Add("highshelf=f=10000:g=1")
$decisoes.Add("EQ moderada: -2,5 dB em 280 Hz (embolado), +2 dB em 3,2 kHz (inteligibilidade), +1 dB acima de 10 kHz.")

$filtros.Add("deesser=i=0.35:m=0.5:f=0.5:s=o")
$decisoes.Add("De-esser moderado para sibilancias.")

$filtros.Add("acompressor=threshold=-21dB:ratio=2.5:attack=12:release=180:knee=4:makeup=1.5")
$decisoes.Add("Compressao 2,5:1 (ataque 12 ms, release 180 ms) para uniformizar o volume.")

$filtrosAntesNorm = $filtros -join ","

# Normalizacao de loudness em 2 passagens (linear: preserva a dinamica e as pausas).
Write-Host "[3/5] Medindo loudness apos a limpeza (passagem 1 do loudnorm)..."
$medida = Rodar-FFmpeg @("-hide_banner", "-nostats", "-i", $wavOriginal,
    "-af", "$filtrosAntesNorm,loudnorm=I=$(Num $AlvoLufs):TP=$(Num $TruePeak):LRA=11:print_format=json",
    "-f", "null", "-")
$m1 = [regex]::Match($medida, '\{[^{}]*"input_i"[^{}]*\}').Value | ConvertFrom-Json

$cadeia = "$filtrosAntesNorm,loudnorm=I=$(Num $AlvoLufs):TP=$(Num $TruePeak):LRA=11:" +
    "measured_I=$($m1.input_i):measured_TP=$($m1.input_tp):measured_LRA=$($m1.input_lra):" +
    "measured_thresh=$($m1.input_thresh):offset=$($m1.target_offset):linear=true," +
    "alimiter=limit=0.84:attack=5:release=50:level=false:latency=1,aresample=48000"
$decisoes.Add("Loudness: $(Num $AlvoLufs) LUFS integrado, true peak <= $(Num $TruePeak) dBTP, limitador com compensacao de latencia.")

$wavTratado = Join-Path $pastas.narracao "$base-narracao-tratada-48k24.wav"
$mp3Tratado = Join-Path $pastas.narracao "$base-narracao-tratada.mp3"
Write-Host "[4/5] Aplicando o tratamento e exportando WAV 48 kHz / 24 bits..."
Rodar-FFmpeg @("-y", "-hide_banner", "-i", $wavOriginal, "-af", $cadeia, "-ar", "48000", "-c:a", "pcm_s24le", $wavTratado) | Out-Null
Rodar-FFmpeg @("-y", "-hide_banner", "-i", $wavTratado, "-c:a", "libmp3lame", "-b:a", "320k", $mp3Tratado) | Out-Null

# Video com o audio tratado: video copiado sem recompressao, audio AAC.
$temVideo = (& ffprobe -v error -select_streams v -show_entries stream=index -of csv=p=0 $Entrada) -ne $null
$mp4Tratado = Join-Path $pastas.exportacao "$base-audio-tratado.mp4"
if ($temVideo) {
    Rodar-FFmpeg @("-y", "-hide_banner", "-i", $Entrada, "-i", $wavTratado,
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
        "-ar", "48000", "-movflags", "+faststart", $mp4Tratado) | Out-Null
}

# 5. Verificacao.
Write-Host "[5/5] Verificando o resultado..."
$depois = Analisar $wavTratado
$durOrig = Duracao $wavOriginal "a:0"
$durTrat = Duracao $wavTratado "a:0"
$difMs = [math]::Abs($durOrig - $durTrat) * 1000
$lnD = $depois["loudnorm"]

$problemas = @()
if ([double]::Parse($lnD.input_tp, $inv) -gt -1.0) { $problemas += "True peak acima de -1 dBTP ($($lnD.input_tp))." }
if ($depois["Flat factor"] -gt 0) { $problemas += "Possivel clipping (flat factor $(Num $depois['Flat factor']))." }
if ($difMs -gt 25) { $problemas += "Duracao mudou $(Num $difMs) ms: verificar sincronia." }

$relatorio = Join-Path $Saida "relatorio-audio.txt"
$linhas = @(
    "RELATORIO DE TRATAMENTO - $base",
    "Gerado em $(Get-Date -Format 'yyyy-MM-dd HH:mm')",
    "",
    "ORIGINAL (intacto em: $Entrada)",
    "  Loudness integrado : $($ln.input_i) LUFS",
    "  True peak          : $($ln.input_tp) dBTP",
    "  Faixa dinamica LRA : $($ln.input_lra) LU",
    "  Pico amostral      : $(Num $pico) dBFS",
    "  Piso de ruido      : $(Num $ruido) dB",
    "",
    "DECISOES"
) + ($decisoes | ForEach-Object { "  - $_" }) + @(
    "",
    "TRATADO",
    "  Loudness integrado : $($lnD.input_i) LUFS",
    "  True peak          : $($lnD.input_tp) dBTP",
    "  Faixa dinamica LRA : $($lnD.input_lra) LU",
    "  Piso de ruido      : $(Num $depois['Noise floor dB']) dB",
    "  Duracao original   : $(Num $durOrig) s | tratada: $(Num $durTrat) s (diferenca $(Num $difMs) ms)",
    "",
    "PAUSAS LONGAS (> 2,5 s abaixo de -45 dB) - nada foi cortado; revise se sao intencionais:"
)
if ($antes["silencios"].Count -eq 0) { $linhas += "  nenhuma" }
foreach ($s in $antes["silencios"]) { $linhas += "  $(Tempo $s.Inicio)  ($(Num $s.Duracao) s)" }
$linhas += ""
$linhas += "VERIFICACAO AUTOMATICA"
if ($problemas.Count -eq 0) { $linhas += "  OK: sem clipping, true peak dentro do limite, duracao preservada." }
else { $linhas += ($problemas | ForEach-Object { "  ATENCAO: $_" }) }
$linhas += ""
$linhas += "Faca a escuta final em fones de ouvido e em alto-falantes comuns."
$linhas += ""
$linhas += "Cadeia FFmpeg aplicada:"
$linhas += "  $cadeia"
$linhas | Set-Content -Encoding UTF8 -LiteralPath $relatorio

Write-Host ""
Write-Host "Pronto. Arquivos em: $Saida"
Write-Host "  MP3 original      : $mp3Original"
Write-Host "  WAV tratado       : $wavTratado"
Write-Host "  MP3 tratado       : $mp3Tratado"
if ($temVideo) { Write-Host "  Video sincronizado: $mp4Tratado" }
Write-Host "  Relatorio         : $relatorio"
if ($problemas.Count -gt 0) { Write-Warning ($problemas -join " ") }
