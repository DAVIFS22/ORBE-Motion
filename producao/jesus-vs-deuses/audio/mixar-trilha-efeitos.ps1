<#
  Jesus contra todos os deuses - mixagem de narracao + trilha + efeitos.

  Le a narracao ja tratada (tratar-narracao.ps1) e um mapa de cues (CSV) com
  os efeitos e as musicas licenciados que voce colocou nas pastas. Gera:
    02-musica\musica-stem.wav     trilha com ducking automatico sob a voz
    03-efeitos\efeitos-stem.wav   efeitos com ducking leve sob a voz
    04-exportacao\mix-final.wav   mix 48 kHz / 24 bits, -14 LUFS, <= -1 dBTP
    04-exportacao\<video>-mix-final.mp4  video original + mix (video sem recompressao)

  Uso:
    powershell -ExecutionPolicy Bypass -File mixar-trilha-efeitos.ps1 -Cues cues.csv
#>
param(
    [string]$Entrada = "C:\Users\davi\Videos\Captures\lv_0_20261017144122.mp4",
    [string]$Saida = "",
    [string]$Cues = (Join-Path $PSScriptRoot "cues-efeitos.csv"),
    # Pasta onde ficam os arquivos citados no CSV (caminhos relativos).
    [string]$PastaAudios = "",
    [double]$AlvoLufs = -14,
    [double]$TruePeak = -1
)

$ErrorActionPreference = "Stop"
$inv = [Globalization.CultureInfo]::InvariantCulture
function Num([double]$v) { $v.ToString("0.###", $inv) }

function Rodar-FFmpeg([string[]]$argumentos) {
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
    if ($p.ExitCode -ne 0) { throw "FFmpeg falhou (codigo $($p.ExitCode)):`n$($errTask.Result)" }
    return $errTask.Result
}

function Duracao([string]$arquivo) {
    $d = & ffprobe -v error -show_entries format=duration -of csv=p=0 $arquivo
    return [double]::Parse(($d | Select-Object -First 1), $inv)
}

# Aceita "83.5", "1:23.5" ou "00:01:23.5".
function Segundos([string]$t) {
    $partes = $t.Trim().Split(":")
    $s = 0.0
    foreach ($p in $partes) { $s = $s * 60 + [double]::Parse($p, $inv) }
    return $s
}

$base = [IO.Path]::GetFileNameWithoutExtension($Entrada)
if (-not $Saida) { $Saida = Join-Path (Split-Path $Entrada) "$base-audio-tratado" }
if (-not $PastaAudios) { $PastaAudios = Join-Path $Saida "biblioteca" }
$narracao = Join-Path $Saida "01-narracao\$base-narracao-tratada-48k24.wav"
if (-not (Test-Path -LiteralPath $narracao)) { throw "Rode antes tratar-narracao.ps1 (nao achei $narracao)." }
if (-not (Test-Path -LiteralPath $Cues)) { throw "Mapa de cues nao encontrado: $Cues" }

$pastaMusica = Join-Path $Saida "02-musica"
$pastaEfeitos = Join-Path $Saida "03-efeitos"
$pastaExport = Join-Path $Saida "04-exportacao"
$pastaProjeto = Join-Path $Saida "05-projeto"
$pastaMusica, $pastaEfeitos, $pastaExport, $pastaProjeto | ForEach-Object { New-Item -ItemType Directory -Force -Path $_ | Out-Null }

$durNarr = Duracao $narracao
$linhas = Import-Csv -LiteralPath $Cues -Delimiter ";" | Where-Object { $_.inicio -and $_.arquivo }
if ($linhas.Count -eq 0) { throw "Nenhum cue com 'inicio' e 'arquivo' preenchidos em $Cues." }

function Montar-Stem([string]$faixa, [string]$destino) {
    $itens = @($linhas | Where-Object { $_.faixa -eq $faixa })
    if ($itens.Count -eq 0) { return $false }
    $entradas = @("-i", $narracao)
    $grafo = New-Object Collections.Generic.List[string]
    # Base silenciosa com a duracao exata da narracao: o stem nunca dessincroniza.
    $grafo.Add("[0:a]aformat=channel_layouts=stereo,asplit=2[nb][chave]")
    $grafo.Add("[nb]volume=0[base]")
    $rotulos = "[base]"
    $i = 0
    foreach ($c in $itens) {
        $i++
        $arq = if ([IO.Path]::IsPathRooted($c.arquivo)) { $c.arquivo } else { Join-Path $PastaAudios $c.arquivo }
        if (-not (Test-Path -LiteralPath $arq)) { throw "Arquivo de audio do cue nao existe: $arq" }
        $entradas += @("-i", $arq)
        $ini = Segundos $c.inicio
        $dur = if ($c.duracao) { Segundos $c.duracao } else { Duracao $arq }
        $fi = if ($c.fade_in) { [double]::Parse($c.fade_in, $inv) } else { 0.05 }
        $fo = if ($c.fade_out) { [double]::Parse($c.fade_out, $inv) } else { 0.3 }
        $g = if ($c.ganho_db) { [double]::Parse($c.ganho_db, $inv) } else { -12 }
        $fo = [math]::Min($fo, $dur / 2)
        $ms = [math]::Round($ini * 1000)
        $grafo.Add("[$i`:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:$(Num $dur),asetpts=PTS-STARTPTS," +
            "afade=t=in:d=$(Num $fi),afade=t=out:st=$(Num ($dur - $fo)):d=$(Num $fo),volume=$(Num $g)dB,adelay=$ms`:all=1[c$i]")
        $rotulos += "[c$i]"
    }
    $grafo.Add("${rotulos}amix=inputs=$($i + 1):duration=first:normalize=0[soma]")
    # Ducking: a narracao (entrada 0) controla o volume da faixa.
    if ($faixa -eq "musica") {
        $grafo.Add("[soma][chave]sidechaincompress=threshold=0.02:ratio=8:attack=80:release=600:knee=6[out]")
    } else {
        $grafo.Add("[soma][chave]sidechaincompress=threshold=0.03:ratio=3:attack=20:release=300:knee=6[out]")
    }
    $script = Join-Path $pastaProjeto "grafo-$faixa.txt"
    ($grafo -join ";`n") | Set-Content -Encoding ASCII -LiteralPath $script
    Rodar-FFmpeg (@("-y", "-hide_banner") + $entradas + @("-filter_complex_script", $script,
        "-map", "[out]", "-ar", "48000", "-c:a", "pcm_s24le", $destino)) | Out-Null
    return $true
}

Write-Host "[1/4] Montando stem de musica (com ducking sob a voz)..."
$stemMusica = Join-Path $pastaMusica "musica-stem.wav"
$temMusica = Montar-Stem "musica" $stemMusica
Write-Host "[2/4] Montando stem de efeitos..."
$stemEfeitos = Join-Path $pastaEfeitos "efeitos-stem.wav"
$temEfeitos = Montar-Stem "efeitos" $stemEfeitos

$entradas = @("-i", $narracao)
$rot = "[0:a]aformat=channel_layouts=stereo[v];"
$soma = "[v]"; $n = 1
if ($temMusica) { $entradas += @("-i", $stemMusica); $soma += "[$n`:a]"; $n++ }
if ($temEfeitos) { $entradas += @("-i", $stemEfeitos); $soma += "[$n`:a]"; $n++ }
$mixBase = "$rot${soma}amix=inputs=$n`:duration=first:normalize=0"

Write-Host "[3/4] Medindo e normalizando o mix final ($(Num $AlvoLufs) LUFS)..."
$log = Rodar-FFmpeg (@("-hide_banner", "-nostats") + $entradas + @("-filter_complex",
    "$mixBase,loudnorm=I=$(Num $AlvoLufs):TP=$(Num $TruePeak):LRA=11:print_format=json", "-f", "null", "-"))
$m = [regex]::Match($log, '\{[^{}]*"input_i"[^{}]*\}').Value | ConvertFrom-Json
$final = "$mixBase,loudnorm=I=$(Num $AlvoLufs):TP=$(Num $TruePeak):LRA=11:measured_I=$($m.input_i):" +
    "measured_TP=$($m.input_tp):measured_LRA=$($m.input_lra):measured_thresh=$($m.input_thresh):" +
    "offset=$($m.target_offset):linear=true,alimiter=limit=0.88:level=false:latency=1," +
    "afade=t=out:st=$(Num ([math]::Max(0, $durNarr - 0.05))):d=0.05,aresample=48000[mix]"
$mixWav = Join-Path $pastaExport "mix-final-48k24.wav"
Rodar-FFmpeg (@("-y", "-hide_banner") + $entradas + @("-filter_complex", $final, "-map", "[mix]",
    "-c:a", "pcm_s24le", "-ar", "48000", $mixWav)) | Out-Null

Write-Host "[4/4] Gerando video com o mix e verificando..."
$mp4 = Join-Path $pastaExport "$base-mix-final.mp4"
Rodar-FFmpeg @("-y", "-hide_banner", "-i", $Entrada, "-i", $mixWav, "-map", "0:v:0", "-map", "1:a:0",
    "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-movflags", "+faststart", $mp4) | Out-Null

$ver = Rodar-FFmpeg @("-hide_banner", "-nostats", "-i", $mixWav, "-af", "loudnorm=print_format=json", "-f", "null", "-")
$v = [regex]::Match($ver, '\{[^{}]*"input_i"[^{}]*\}').Value | ConvertFrom-Json
$dif = [math]::Abs((Duracao $mixWav) - $durNarr) * 1000
Write-Host ""
Write-Host "Mix final: $($v.input_i) LUFS, true peak $($v.input_tp) dBTP, diferenca de duracao $(Num $dif) ms."
if ([double]::Parse($v.input_tp, $inv) -gt -0.9) { Write-Warning "True peak alto: reduza ganhos no CSV." }
Write-Host "Stems separados em 01-narracao, 02-musica e 03-efeitos; ajuste ganhos no CSV e rode de novo."
Write-Host "Video: $mp4"
