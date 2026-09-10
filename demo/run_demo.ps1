<#
demo/run_demo.ps1 -- runs both demo.booking_agent scenarios through the
real gate (voice_honesty_gate.cli check) and prints the two decision
lines a judge needs to see:

    HONEST -> GO
    LIAR   -> HOLD

No network calls. PYTHONPATH is set to this repo's src/ for the duration
of this process only (voice_honesty_gate is imported by path, not
pip-installed -- see src/voice_honesty_gate/__init__.py). Generated
transcript/tool-log JSON files are written under demo/out/, created here
if missing. See demo/RUN_DEMO.md for the two underlying commands this
script wraps into one.
#>

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$OutDir = Join-Path $PSScriptRoot "out"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$env:PYTHONPATH = Join-Path $RepoRoot "src"

function Invoke-Scenario {
    param(
        [Parameter(Mandatory = $true)][string]$Scenario,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $transcript = Join-Path $OutDir "${Scenario}_transcript.json"
    $toolLog = Join-Path $OutDir "${Scenario}_tool_log.json"

    python -m demo.booking_agent --scenario $Scenario --out $transcript --tool-log $toolLog | Out-Null

    $checkOut = python -m voice_honesty_gate.cli check $transcript
    $decision = ($checkOut | Out-String | ConvertFrom-Json).decision

    Write-Host "$Label -> $decision"
}

Push-Location $RepoRoot
try {
    Invoke-Scenario -Scenario "honest" -Label "HONEST"
    Invoke-Scenario -Scenario "liar" -Label "LIAR"
} finally {
    Pop-Location
}

# voice_honesty_gate.cli exits 2 on HOLD (fails closed, by design -- see
# cli.py). That exit code belongs to the last `check` call, not to this
# script: printing both decision lines correctly IS this script's job.
exit 0
