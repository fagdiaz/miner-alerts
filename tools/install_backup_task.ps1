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
    [ValidateSet("Register", "Unregister", "Status", "RunNow")]
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
    $VenvPythonw = "pythonw.exe"
}

$BackupScript = Join-Path $ProjectRoot "tools\event_store_backup.py"

function Get-TaskStatus {
    param([string]$Name)
    $task = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
    if ($null -eq $task) {
        return [PSCustomObject]@{
            TaskName = $Name
            Exists   = $false
            State    = "NotRegistered"
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

    "Register" {
        if (-not (Test-Path $BackupScript)) {
            throw "Backup script not found at '$BackupScript'."
        }

        # Resolve backup root from config if not provided
        $ResolvedBackupRoot = $BackupRoot
        if ([string]::IsNullOrWhiteSpace($ResolvedBackupRoot) -and (Test-Path $ConfigPath)) {
            try {
                $cfg = Get-Content $ConfigPath -Raw | ConvertFrom-Json
                $ResolvedBackupRoot = $cfg.backup.root
            } catch {
                Write-Verbose "Could not parse backup root from config."
            }
        }

        if ([string]::IsNullOrWhiteSpace($ResolvedBackupRoot)) {
            $ResolvedBackupRoot = Join-Path $ProjectRoot "backups"
        }

        # Arguments: --backup-root <path>
        $Arguments = "`"$BackupScript`" --backup-root `"$ResolvedBackupRoot`" --action backup"

        $TaskAction = New-ScheduledTaskAction -Execute $VenvPythonw -Argument $Arguments -WorkingDirectory $ProjectRoot
        $TaskTrigger = New-ScheduledTaskTrigger -Daily -At "03:00AM"
        $TaskSettings = New-ScheduledTaskSettingsSet `
            -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries `
            -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
            -MultipleInstances IgnoreNew `
            -StartWhenAvailable

        $Principal = New-ScheduledTaskPrincipal -UserId "NT AUTHORITY\SYSTEM" -LogonType ServiceAccount -RunLevel Highest

        try {
            Register-ScheduledTask `
                -TaskName $TaskName `
                -Action $TaskAction `
                -Trigger $TaskTrigger `
                -Settings $TaskSettings `
                -Principal $Principal `
                -Force | Out-Null
            Write-Host "[OK] Scheduled task '$TaskName' registered successfully under SYSTEM."
        } catch {
            Write-Warning "Could not register as SYSTEM (may require Administrator). Falling back to current user."
            Register-ScheduledTask `
                -TaskName $TaskName `
                -Action $TaskAction `
                -Trigger $TaskTrigger `
                -Settings $TaskSettings `
                -RunLevel Highest `
                -Force | Out-Null
            Write-Host "[OK] Scheduled task '$TaskName' registered for current user."
        }

        Get-TaskStatus -Name $TaskName | Format-List
    }

    "RunNow" {
        Start-ScheduledTask -TaskName $TaskName
        Write-Host "[OK] Triggered immediate run for '$TaskName'."
    }
}
