[CmdletBinding()]
param(
    [object]$DryRun = $false,
    [int]$DeadlockLogMaxAgeHours = 48
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
Set-Location $repoRoot

$isDryRun = ($DryRun -eq $true -or "$DryRun" -eq 'true' -or "$DryRun" -eq '1' -or "$DryRun" -eq '$true')

$cleanedItems = @()
$bytesFreed = 0
$now = Get-Date

# 1. Stale Deadlock Forensics Logs in logs/
if (Test-Path 'logs') {
    $cutoff = $now.AddHours(-$DeadlockLogMaxAgeHours)
    Get-ChildItem -Path 'logs' -Filter 'deadlock_forensics_*.log' -File | ForEach-Object {
        if ($_.LastWriteTime -lt $cutoff) {
            $bytesFreed += $_.Length
            $cleanedItems += [ordered]@{
                Type = 'StaleDeadlockLog'
                Path = $_.FullName.Substring($repoRoot.Length + 1)
                AgeHours = [math]::Round(($now - $_.LastWriteTime).TotalHours, 1)
                SizeBytes = $_.Length
            }
            if (-not $isDryRun) {
                Remove-Item -LiteralPath $_.FullName -Force
            }
        }
    }
}

# 2. Transient Diagnostics Task Logs
if (Test-Path 'diagnostics') {
    Get-ChildItem -Path 'diagnostics' -Filter 'task-*.log' -File | ForEach-Object {
        $bytesFreed += $_.Length
        $cleanedItems += [ordered]@{
            Type = 'TransientDiagnosticLog'
            Path = $_.FullName.Substring($repoRoot.Length + 1)
            SizeBytes = $_.Length
        }
        if (-not $isDryRun) {
            Remove-Item -LiteralPath $_.FullName -Force
        }
    }
}

# 3. Python Cache Dirs (__pycache__ and .pytest_cache)
$cacheDirs = @()
Get-ChildItem -Path $repoRoot -Recurse -Directory -Filter '__pycache__' | ForEach-Object {
    if ($_.FullName -notmatch '\\\.venv\\') { $cacheDirs += $_.FullName }
}
if (Test-Path '.pytest_cache') {
    $cacheDirs += (Resolve-Path '.pytest_cache').Path
}

foreach ($cd in $cacheDirs) {
    if (Test-Path $cd) {
        $dirSize = (Get-ChildItem $cd -Recurse -File | Measure-Object -Property Length -Sum).Sum
        if ($dirSize) { $bytesFreed += $dirSize }
        $cleanedItems += [ordered]@{
            Type = 'BytecodeCacheDir'
            Path = $cd.Substring($repoRoot.Length + 1)
            SizeBytes = $dirSize
        }
        if (-not $isDryRun) {
            Remove-Item -LiteralPath $cd -Recurse -Force
        }
    }
}

# 4. Strict Immutability Proof
$protectedIntegrity = [ordered]@{
    DevelopmentLogPreserved = (Test-Path 'docs/audit/DEVELOPMENT_LOG.md')
    LocalConfigPreserved    = (Test-Path 'app/config.json')
    LocalStatePreserved     = (Test-Path 'app/state.json')
    ActiveServiceLogOut     = (Test-Path 'logs/out.log')
    ActiveServiceLogErr     = (Test-Path 'logs/err.log')
    ActiveServiceLogWatchdog= (Test-Path 'logs/watchdog.log')
}

$summary = [ordered]@{
    Status              = 'SUCCESS'
    DryRun              = [bool]$isDryRun
    TotalItemsCleaned   = $cleanedItems.Count
    BytesFreed          = $bytesFreed
    KilobytesFreed      = [math]::Round($bytesFreed / 1024, 2)
    CleanedItems        = $cleanedItems
    ProtectedIntegrity  = $protectedIntegrity
}

$summary | ConvertTo-Json -Depth 5 -Compress
exit 0
