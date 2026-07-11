[CmdletBinding()]
param(
    [string]$FeatureDir,
    [switch]$RunBuilds
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
Set-Location $repoRoot

if (-not $FeatureDir) {
    $featureState = Get-Content -Raw '.specify/feature.json' | ConvertFrom-Json
    $FeatureDir = $featureState.feature_directory
}

$resolvedFeature = (Resolve-Path $FeatureDir).Path
if (-not $resolvedFeature.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Feature directory is outside repository: $resolvedFeature"
}

$requiredFiles = @('spec.md', 'plan.md', 'tasks.md')
$missingFiles = @($requiredFiles | Where-Object {
    -not (Test-Path -LiteralPath (Join-Path $resolvedFeature $_))
})

$tasksPath = Join-Path $resolvedFeature 'tasks.md'
$tasks = if (Test-Path -LiteralPath $tasksPath) { Get-Content -Raw $tasksPath } else { '' }
$scope = [ordered]@{
    Python   = [bool]($tasks -match '(?i)app/|app\\|\.py\b|py_compile|miner_monitor')
    Telegram = [bool]($tasks -match '(?i)telegram|bot|command|confirm|reboot_no_ok|/rb|/c<|polling|getUpdates')
    Reboot   = [bool]($tasks -match '(?i)auto-reboot|reboot|restart|Hashcore|cooldown|startup guard|LOW|qa_')
    Config   = [bool]($tasks -match '(?i)config\.json|config\.example|state\.json|secret|token|chat_id')
    Docs     = [bool]($tasks -match '(?i)docs/|docs\\|README|spec|plan|tasks|evidence|roadmap')
}

$checklistTotal = 0
$checklistOpen = 0
$checklistDirectory = Join-Path $resolvedFeature 'checklists'
if (Test-Path -LiteralPath $checklistDirectory) {
    Get-ChildItem $checklistDirectory -File -Filter '*.md' | ForEach-Object {
        $lines = Get-Content $_.FullName
        $checklistTotal += @($lines | Where-Object { $_ -match '^- \[[ xX]\]' }).Count
        $checklistOpen += @($lines | Where-Object { $_ -match '^- \[ \]' }).Count
    }
}

function Invoke-Gate {
    param([string]$Name, [scriptblock]$Command)
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = (& $Command 2>&1 | Out-String).Trim()
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorAction
    }
    $gateStatus = if ($exitCode -eq 0) { 'PASS' } else { 'FAIL' }
    [ordered]@{
        Name = $Name
        Status = $gateStatus
        ExitCode = $exitCode
        Summary = (($output -split "`r?`n") | Select-Object -Last 6) -join "`n"
    }
}

$gates = @()
$gates += Invoke-Gate 'git-diff-check' { git -c core.autocrlf=false diff --check }

if ($RunBuilds -and $scope.Python) {
    $gates += Invoke-Gate 'python-py-compile' {
        & ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py
    }
}

$dirtyCount = @(git status --short).Count
$failedGates = @($gates | Where-Object { $_.Status -eq 'FAIL' }).Count
$status = if ($missingFiles.Count -or $checklistOpen -or $failedGates) {
    'FAIL'
}
else {
    'PASS'
}

$result = [ordered]@{
    Status = $status
    FeatureDir = $resolvedFeature
    MissingRequiredFiles = $missingFiles
    Checklist = [ordered]@{ Total = $checklistTotal; Open = $checklistOpen }
    Scope = $scope
    DirtyPathCount = $dirtyCount
    Gates = $gates
}

$result | ConvertTo-Json -Depth 6 -Compress
if ($status -eq 'FAIL') { exit 1 }
