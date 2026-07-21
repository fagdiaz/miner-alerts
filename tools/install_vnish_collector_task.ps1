[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "Medium")]
param(
    [ValidateRange(5, 1440)]
    [int]$IntervalMinutes = 15,
    [string]$TaskName = "MinerAlertsVnishCollector",
    [string]$TaskPath = "\MinerAlerts\"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$runner = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "run_vnish_collector.ps1")).Path
$powershell = (Get-Command powershell.exe -ErrorAction Stop).Source
$arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$runner`""
$target = "$TaskPath$TaskName"

if ($WhatIfPreference) {
    $null = $PSCmdlet.ShouldProcess($target, "Register Vnish read-only collector")
    return
}

$action = New-ScheduledTaskAction `
    -Execute $powershell `
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
        -Description "Bounded read-only Vnish log collection for Miner Alerts" `
        -Force | Out-Null
    Write-Output "VNISH_TASK registered=$TaskPath$TaskName interval_minutes=$IntervalMinutes"
}
