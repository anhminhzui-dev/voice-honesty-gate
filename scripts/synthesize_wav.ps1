# Synthesize a mono 16-bit PCM WAV at a given sample rate using Windows'
# built-in System.Speech synthesizer -- no key, no network call, free.
# Reused across this repo's fixtures (LIVE_RECEIPT.md's two audio files
# were produced with the same approach inline; this is that approach
# pulled into a reusable script, additive, for the live-mic test fixture).
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts/synthesize_wav.ps1 `
#       -Text "I have cancelled your flight, all done" `
#       -OutPath tests/fixtures/audio/live_mic_demo.wav `
#       -SampleRate 16000

param(
    [Parameter(Mandatory = $true)][string]$Text,
    [Parameter(Mandatory = $true)][string]$OutPath,
    [int]$SampleRate = 16000
)

Add-Type -AssemblyName System.Speech

$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(
    $SampleRate,
    [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
    [System.Speech.AudioFormat.AudioChannel]::Mono
)

$outDir = Split-Path -Parent $OutPath
if ($outDir -and -not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
}

$synth.SetOutputToWaveFile($OutPath, $format)
$synth.Speak($Text)
$synth.Dispose()

Write-Host "wrote $OutPath ($SampleRate Hz mono 16-bit PCM): `"$Text`""
