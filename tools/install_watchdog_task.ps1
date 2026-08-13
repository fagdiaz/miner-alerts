param(
    [string]$TaskName = "MinerAlertsWatchdog",
    [string]$TaskPath = "\MinerAlerts\",
    [string]$ServiceName = "MinerAlerts",
    [switch]$ConfigureServiceRecovery
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonw = Join-Path $repoRoot ".venv\Scripts\pythonw.exe"
$watchdog = Join-Path $repoRoot "tools\monitor_watchdog.py"
$config = Join-Path $repoRoot "app\config.json"

foreach ($required in @($pythonw, $watchdog, $config)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required path not found: $required"
    }
}

$arguments = '"{0}" --config "{1}"' -f $watchdog, $config
$action = New-ScheduledTaskAction -Execute $pythonw -Argument $arguments -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 1)
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount `
    -RunLevel Highest

Register-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Action $action `
    -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null

if ($ConfigureServiceRecovery) {
    $artifactDir = Join-Path $repoRoot "artifacts"
    New-Item -ItemType Directory -Path $artifactDir -Force | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $rollbackPath = Join-Path $artifactDir "service-recovery-before-$stamp.txt"
    (& sc.exe qfailure $ServiceName) | Set-Content -LiteralPath $rollbackPath -Encoding UTF8
    & sc.exe failure $ServiceName "reset=" "86400" `
        "actions=" "restart/60000/restart/60000/restart/300000"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to configure SCM recovery for $ServiceName"
    }
    Write-Output "SCM recovery baseline: $rollbackPath"
}

Write-Output "Scheduled task installed: $TaskPath$TaskName"
