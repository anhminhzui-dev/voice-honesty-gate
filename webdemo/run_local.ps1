<#
.SYNOPSIS
    Run the voice-honesty-gate Gradio demo locally (no deployment).

.DESCRIPTION
    Installs gradio if it is not already present, then launches
    webdemo/app.py from the repo root so its own sys.path wiring to src/
    (and relay-gate, via voice_honesty_gate/__init__.py) resolves exactly
    as it does under pytest and the CLI.

    Does NOT deploy anywhere, create any account, or push anything -- see
    README_SPACE.md for the actual Hugging Face Space deploy steps, which
    stay manual and Founder-gated.

.EXAMPLE
    powershell -File webdemo/run_local.ps1
#>

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

python -c "import gradio" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "gradio not found -- installing from webdemo/requirements.txt ..."
    python -m pip install -r webdemo/requirements.txt
}

if (-not (Test-Path "M:/AGENT_VAULT/secrets/assemblyai.key") -and -not $env:ASSEMBLYAI_API_KEY) {
    Write-Host "NOTE: no AssemblyAI key found (checked ASSEMBLYAI_API_KEY env var and M:/AGENT_VAULT/secrets/assemblyai.key)."
    Write-Host "      The Run button and example buttons will show an ERROR until one is present."
}

Write-Host "Starting Gradio demo -- Ctrl+C to stop."
python webdemo/app.py
