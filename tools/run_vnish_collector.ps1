[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$Tabs = "status,miner,autotune,system",
    [int]$MaxBytes = 1048576,
    [int]$MaxEvents = 1000
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}
$resolvedRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$python = Join-Path $resolvedRoot ".venv\Scripts\python.exe"
$collector = Join-Path $resolvedRoot "tools\vnish_log_collector.py"
$config = Join-Path $resolvedRoot "app\config.json"

foreach ($required in @($python, $collector, $config)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required file not found: $required"
    }
}

Push-Location $resolvedRoot
try {
    & $python $collector `
        --config $config `
        --tabs $Tabs `
        --connect-timeout 3 `
        --idle-timeout 1 `
        --max-bytes $MaxBytes `
        --max-lines 20000 `
        --max-events $MaxEvents
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
