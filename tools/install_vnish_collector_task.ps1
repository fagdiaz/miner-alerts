[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "Medium")]
param(
    [ValidateRange(5, 1440)]
    [int]$IntervalMinutes = 30,
    [string]$TaskName = "MinerAlertsVnishCollector",
    [string]$TaskPath = "\MinerAlerts\"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$pythonw = (Resolve-Path -LiteralPath (Join-Path $repoRoot ".venv\Scripts\pythonw.exe")).Path
$collector = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "vnish_log_collector.py")).Path
$config = (Resolve-Path -LiteralPath (Join-Path $repoRoot "app\config.json")).Path
$arguments = (
    "`"$collector`" --config `"$config`" " +
    "--tabs status,miner,autotune,system " +
    "--connect-timeout 3 --idle-timeout 1 " +
    "--max-bytes 1048576 --max-lines 20000 --max-events 1000"
)
$target = "$TaskPath$TaskName"

if ($WhatIfPreference) {
    $null = $PSCmdlet.ShouldProcess($target, "Register Vnish read-only collector")
    return
}

$action = New-ScheduledTaskAction `
    -Execute $pythonw `
    -Argument $arguments `
    -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
$principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Limited

if ($PSCmdlet.ShouldProcess($target, "Register Vnish read-only collector")) {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -TaskPath $TaskPath `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Description "Bounded read-only Vnish log collection for Miner Alerts (no console)" `
        -Force | Out-Null
    Write-Output "VNISH_TASK registered=$TaskPath$TaskName interval_minutes=$IntervalMinutes"
}
