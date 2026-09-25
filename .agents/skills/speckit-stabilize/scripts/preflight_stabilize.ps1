[CmdletBinding()]
param(
    [string]$FeatureDir = '',
    [object]$RunTests = $true,
    [object]$CheckFleet = $true
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
Set-Location $repoRoot

$shouldRunTests = ($RunTests -eq $true -or "$RunTests" -eq 'true' -or "$RunTests" -eq '1' -or "$RunTests" -eq '$true')
$shouldCheckFleet = ($CheckFleet -eq $true -or "$CheckFleet" -eq 'true' -or "$CheckFleet" -eq '1' -or "$CheckFleet" -eq '$true')

# 1. Resolve Active Feature
if (-not $FeatureDir) {
    if (Test-Path -LiteralPath '.specify/feature.json') {
        try {
            $featureState = Get-Content -Raw '.specify/feature.json' | ConvertFrom-Json
            $FeatureDir = $featureState.feature_directory
        }
        catch {
            $FeatureDir = 'specs/066-cold-boot-grace'
        }
    }
    else {
        $FeatureDir = 'specs/066-cold-boot-grace'
    }
}

$resolvedFeature = if (Test-Path -LiteralPath $FeatureDir) { (Resolve-Path $FeatureDir).Path } else { $null }

# 2. Gate Runner Helper
function Invoke-StabilizationGate {
    param(
        [string]$Name,
        [scriptblock]$Command,
        [string]$Severity = 'P0'
    )
    $output = ''
    $isFail = $false
    try {
        $res = & $Command 2>&1
        $output = ($res | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) {
            $isFail = $true
        }
    }
    catch {
        $output = $_.Exception.Message
        $isFail = $true
    }

    $gateStatus = if ($isFail) { 'FAIL' } else { 'PASS' }
    [ordered]@{
        Name     = $Name
        Status   = $gateStatus
        Severity = $Severity
        Summary  = (($output -split "`r?`n") | Where-Object { $_.Trim() } | Select-Object -Last 4) -join "`n"
    }
}

$gates = @()

# Gate 1: Git Diff & Cleanliness Check
$gates += Invoke-StabilizationGate 'git-diff-check' {
    git -c core.autocrlf=false diff --check
} -Severity 'P1'

# Gate 2: Local Runtime Secrets & Untracked Config Gate
$gates += Invoke-StabilizationGate 'secret-leak-and-untracked-configs' {
    $trackedFiles = git ls-files
    $leaks = @()
    if ($trackedFiles -contains 'app/config.json') { $leaks += 'app/config.json is tracked in git!' }
    if ($trackedFiles -contains 'app/state.json') { $leaks += 'app/state.json is tracked in git!' }
    
    # Check git diff for hardcoded bot tokens or raw secrets
    $diffText = git diff HEAD
    if ($diffText -match '(?i)bot_token["\s:]+["''][0-9]{8,}:[a-zA-Z0-9_-]{30,}["'']') {
        $leaks += 'Hardcoded Telegram bot_token detected in git diff!'
    }
    if ($leaks.Count -gt 0) {
        throw ($leaks -join '; ')
    }
} -Severity 'P0'

# Gate 3: Python Syntax Compilation on all modified and core files
$gates += Invoke-StabilizationGate 'python-syntax-compilation' {
    $pyFiles = @('app/miner_monitor.py')
    $modifiedPy = git status --short | Select-String '\.py$' | ForEach-Object {
        $_.Line.Substring(3).Trim()
    }
    if ($modifiedPy) { $pyFiles += $modifiedPy }
    $pyFiles = $pyFiles | Select-Object -Unique
    
    foreach ($pf in $pyFiles) {
        if (Test-Path -LiteralPath $pf) {
            & ".\.venv\Scripts\python.exe" -m py_compile $pf
            if ($LASTEXITCODE -ne 0) {
                throw "Syntax error in $pf"
            }
        }
    }
} -Severity 'P0'

# Gate 4: Config Alignment Check (config.json vs config.example.json)
$gates += Invoke-StabilizationGate 'config-example-alignment' {
    if ((Test-Path 'app/config.json') -and (Test-Path 'app/config.example.json')) {
        & ".\.venv\Scripts\python.exe" -c @"
import json, sys
try:
    c = json.load(open('app/config.json'))
    ex = json.load(open('app/config.example.json'))
    missing = [k for k in c.keys() if k not in ex and not k.startswith('_comment')]
    if missing:
        print(f'Missing keys in config.example.json: {missing}')
        sys.exit(1)
    sys.exit(0)
except Exception as e:
    print(f'Error verifying config alignment: {e}')
    sys.exit(1)
"@
        if ($LASTEXITCODE -ne 0) { throw "Config alignment check failed" }
    }
} -Severity 'P2'

# Gate 5: Pytest Test Suite
if ($shouldRunTests) {
    $gates += Invoke-StabilizationGate 'pytest-regression-suite' {
        & ".\.venv\Scripts\python.exe" -m pytest -q
        if ($LASTEXITCODE -ne 0) { throw "Pytest regression failures detected" }
    } -Severity 'P0'
}

# Gate 6: Windows NSSM Service Health
$gates += Invoke-StabilizationGate 'windows-nssm-service-health' {
    $svcRaw = (nssm status MinerAlerts 2>&1 | Out-String)
    $svcClean = ($svcRaw -replace "`0", "").Trim()
    if ($svcClean -notmatch 'SERVICE_RUNNING') {
        throw "MinerAlerts service is not RUNNING ($svcClean)"
    }
} -Severity 'P1'

# Gate 7: Live Fleet Connectivity Check (Socket 4028 / API)
if ($shouldCheckFleet) {
    $gates += Invoke-StabilizationGate 'fleet-live-connectivity' {
        & ".\.venv\Scripts\python.exe" -c @"
import socket, json, sys
miners = ['192.168.100.23', '192.168.100.24', '192.168.100.25', '192.168.100.26']
failed = []
for ip in miners:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect((ip, 4028))
        s.sendall(json.dumps({'command': 'summary'}).encode('utf-8'))
        d = s.recv(1024)
        s.close()
        if not d: failed.append(ip)
    except Exception:
        failed.append(ip)
if failed:
    print(f'ASIC API unreachable on: {failed}')
    sys.exit(1)
sys.exit(0)
"@
        if ($LASTEXITCODE -ne 0) { throw "Fleet connectivity check failed" }
    } -Severity 'P1'
}

# Gate 8: SpecKit DoD Compliance (Tasks & Development Log)
$gates += Invoke-StabilizationGate 'speckit-dod-compliance' {
    $errors = @()
    if ($resolvedFeature -and (Test-Path (Join-Path $resolvedFeature 'tasks.md'))) {
        $taskLines = Get-Content (Join-Path $resolvedFeature 'tasks.md')
        $openTasks = @($taskLines | Where-Object { $_ -match '^- \[ \]' }).Count
        if ($openTasks -gt 0) {
            $errors += "Feature has $openTasks open incomplete task(s) in tasks.md"
        }
    }
    
    if (Test-Path 'docs/audit/DEVELOPMENT_LOG.md') {
        $todayStr = (Get-Date).ToString('yyyy-MM-dd')
        $topLog = (Get-Content 'docs/audit/DEVELOPMENT_LOG.md' -TotalCount 25) -join "`n"
        if ($topLog -notmatch $todayStr) {
            $errors += "DEVELOPMENT_LOG.md lacks an entry with today's date ($todayStr)"
        }
    }
    
    if ($errors.Count -gt 0) {
        throw ($errors -join '; ')
    }
} -Severity 'P2'

# Final Assessment
$failedGates = @($gates | Where-Object { $_.Status -eq 'FAIL' })
$overallStatus = if ($failedGates.Count -eq 0) { 'PASS' } else { 'FAIL' }

$report = [ordered]@{
    Status       = $overallStatus
    Timestamp    = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    FeatureDir   = $resolvedFeature
    TotalGates   = $gates.Count
    FailedCount  = $failedGates.Count
    Gates        = $gates
}

$report | ConvertTo-Json -Depth 6
if ($overallStatus -eq 'FAIL') {
    exit 1
}
exit 0
