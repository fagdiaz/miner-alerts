<#
.SYNOPSIS
    Installs or manages the Windows Scheduled Task for EventStore SQLite Backup (Spec 028).

.DESCRIPTION
    Configures a hidden, bounded Windows Scheduled Task that executes tools/event_store_backup.py
    using pythonw.exe to prevent console popups.
    Enforces:
    - SYSTEM or Highest privilege execution.
    - MultipleInstances: IgnoreNew (prevents overlapping task runs).
    - ExecutionTimeLimit: 5 minutes (PT5M).
    - Disjoint path verification and lock management.

.PARAMETER Action
    Action to perform: Register, Unregister, Status, RunNow. Default: Status.

.PARAMETER TaskName
    Name of the Scheduled Task. Default: MinerAlerts_EventStore_Backup.

.PARAMETER ConfigPath
    Path to app/config.json to resolve backup paths. Default: app/config.json.

.PARAMETER BackupRoot
    Explicit backup root path override.
#>

[CmdletBinding()]
param(
    [ValidateSet("Register", "Unregister", "Status", "RunNow", "Plan")]
    [string]$Action = "Status",

    [string]$TaskName = "MinerAlerts_EventStore_Backup",
    [string]$ConfigPath = "app\config.json",
    [string]$BackupRoot = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Resolve pythonw.exe
$VenvPythonw = Join-Path $ProjectRoot ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $VenvPythonw)) {
    throw "Required virtualenv pythonw.exe is missing: $VenvPythonw"
}

$BackupScript = Join-Path $ProjectRoot "tools\run_event_store_backup.py"
if (-not [IO.Path]::IsPathRooted($ConfigPath)) { $ConfigPath = Join-Path $ProjectRoot $ConfigPath }
$ConfigPath = [IO.Path]::GetFullPath($ConfigPath)

function Get-TaskStatus {
    param([string]$Name)
    $task = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
    if ($null -eq $task) {
        return [PSCustomObject]@{
            TaskName = $Name
            Exists   = $null
            State    = "NotVisibleOrNotRegistered"
            Note     = "Run Status from an elevated PowerShell to distinguish missing task from access denied."
        }
    }
    $info = Get-ScheduledTaskInfo -TaskName $Name -ErrorAction SilentlyContinue
    return [PSCustomObject]@{
        TaskName       = $Name
        Exists         = $true
        State          = $task.State.ToString()
        LastRunTime    = $info.LastRunTime
        LastTaskResult = $info.LastTaskResult
        NextRunTime    = $info.NextRunTime
    }
}

switch ($Action) {
    "Status" {
        $status = Get-TaskStatus -Name $TaskName
        $status | Format-List
    }

    "Unregister" {
        $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if ($null -ne $existing) {
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
            Write-Host "[OK] Scheduled task '$TaskName' removed successfully."
        } else {
            Write-Host "[INFO] Scheduled task '$TaskName' is not registered."
        }
    }

    { $_ -in "Register", "Plan" } {
        if (-not (Test-Path -LiteralPath $BackupScript)) { throw "Backup runner missing." }
        $ValidatorPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
        $checkRaw = & $ValidatorPython $BackupScript --config $ConfigPath --check
        if ($LASTEXITCODE -ne 0) { throw "Backup configuration validation failed: $checkRaw" }
        $check = $checkRaw | ConvertFrom-Json
        if ($BackupRoot -and [IO.Path]::GetFullPath($BackupRoot) -ne $check.root) {
            throw "BackupRoot differs from config. Align the local backup configuration first."
        }
        $Arguments = "`"$BackupScript`" --config `"$ConfigPath`""
        if ($Action -eq "Plan") {
            [ordered]@{TaskName=$TaskName;Execute=$VenvPythonw;Arguments=$Arguments;
                WorkingDirectory=$ProjectRoot;DailyAt='03:00';Principal='SYSTEM';
                MultipleInstances='IgnoreNew';MaxSeconds=300;Hidden=$true} | ConvertTo-Json
            break
        }
        $TaskAction = New-ScheduledTaskAction -Execute $VenvPythonw -Argument $Arguments -WorkingDirectory $ProjectRoot
        $TaskTrigger = New-ScheduledTaskTrigger -Daily -At "03:00"
        $TaskSettings = New-ScheduledTaskSettingsSet `
            -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
            -MultipleInstances IgnoreNew -StartWhenAvailable -Hidden
        $Principal = New-ScheduledTaskPrincipal -UserId "NT AUTHORITY\SYSTEM" -LogonType ServiceAccount -RunLevel Highest
        Register-ScheduledTask -TaskName $TaskName -Action $TaskAction -Trigger $TaskTrigger `
            -Settings $TaskSettings -Principal $Principal -Force | Out-Null
        Get-TaskStatus -Name $TaskName | Format-List
    }

    "RunNow" {
        Start-ScheduledTask -TaskName $TaskName
        Write-Host "[OK] Triggered immediate run for '$TaskName'."
    }
}
