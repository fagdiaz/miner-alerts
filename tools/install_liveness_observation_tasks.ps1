[CmdletBinding()]
param(
    [string]$RecoveryTimestamp = "",
    [string]$TaskPath = "\MinerAlerts\",
    [int]$SafetyDelayMinutes = 5,
    [switch]$DryRun,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

$taskNames = @(
    "MinerAlertsLivenessD1",
    "MinerAlertsLivenessD3"
)

if ($Uninstall) {
    $installedTasks = @(
        Get-ScheduledTask -TaskPath $TaskPath -ErrorAction Stop
    )
    foreach ($taskName in $taskNames) {
        $existing = $installedTasks | Where-Object { $_.TaskName -eq $taskName }
        if ($null -ne $existing) {
            if ($DryRun) {
                Write-Output "DRY-RUN unregister task=$TaskPath$taskName"
            }
            else {
                Unregister-ScheduledTask `
                    -TaskPath $TaskPath `
                    -TaskName $taskName `
                    -Confirm:$false `
                    -ErrorAction Stop
                Write-Output "Unregistered task=$TaskPath$taskName"
            }
        }
    }
    exit 0
}

if ([string]::IsNullOrWhiteSpace($RecoveryTimestamp)) {
    throw "RecoveryTimestamp is required unless -Uninstall is used."
}
if ($SafetyDelayMinutes -lt 1 -or $SafetyDelayMinutes -gt 60) {
    throw "SafetyDelayMinutes must be between 1 and 60."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonw = Join-Path $repoRoot ".venv\Scripts\pythonw.exe"
$observer = Join-Path $repoRoot "tools\observe_liveness.py"
$artifactDir = Join-Path $repoRoot "artifacts"
if (-not (Test-Path -LiteralPath $pythonw -PathType Leaf)) {
    throw "pythonw.exe not found: $pythonw"
}
if (-not (Test-Path -LiteralPath $observer -PathType Leaf)) {
    throw "Observer not found: $observer"
}

try {
    $recovery = [DateTimeOffset]::Parse(
        $RecoveryTimestamp,
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::RoundtripKind
    )
}
catch {
    throw "RecoveryTimestamp must be ISO-8601 with an explicit offset."
}
if (-not [regex]::IsMatch($RecoveryTimestamp, "(?:Z|[+-]\d{2}:\d{2})$")) {
    throw "RecoveryTimestamp must include Z or an explicit UTC offset."
}

$definitions = @(
    [pscustomobject]@{
        Name = $taskNames[0]
        Stage = "d1"
        RequiredSeconds = 86400
    },
    [pscustomobject]@{
        Name = $taskNames[1]
        Stage = "d3"
        RequiredSeconds = 259200
    }
)

$principal = $null
$settings = $null
if (-not $DryRun) {
    New-Item -ItemType Directory -Path $artifactDir -Force | Out-Null
    $principal = New-ScheduledTaskPrincipal `
        -UserId "SYSTEM" `
        -LogonType ServiceAccount `
        -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
        -MultipleInstances IgnoreNew
}

foreach ($definition in $definitions) {
    $runAt = $recovery.AddSeconds($definition.RequiredSeconds).AddMinutes($SafetyDelayMinutes)
    if ($runAt -le [DateTimeOffset]::Now) {
        throw "Refusing elapsed schedule for $($definition.Stage): $($runAt.ToString('o'))"
    }
    $outputPath = Join-Path $artifactDir "spec021-$($definition.Stage)-observation.json"
    $arguments = @(
        ('"{0}"' -f $observer),
        "--stage",
        $definition.Stage,
        "--since",
        ('"{0}"' -f $recovery.ToString("o")),
        "--output",
        ('"{0}"' -f $outputPath)
    ) -join " "
    $plan = [ordered]@{
        task = "$TaskPath$($definition.Name)"
        stage = $definition.Stage
        run_at = $runAt.ToString("o")
        executable = $pythonw
        arguments = $arguments
        working_directory = $repoRoot
        output = $outputPath
    }
    if ($DryRun) {
        [pscustomobject]$plan | ConvertTo-Json -Compress
        continue
    }

    $action = New-ScheduledTaskAction `
        -Execute $pythonw `
        -Argument $arguments `
        -WorkingDirectory $repoRoot
    $trigger = New-ScheduledTaskTrigger -Once -At $runAt.LocalDateTime
    Register-ScheduledTask `
        -TaskPath $TaskPath `
        -TaskName $definition.Name `
        -Action $action `
        -Trigger $trigger `
        -Principal $principal `
        -Settings $settings `
        -Description "Read-only Miner Alerts Spec 021 $($definition.Stage.ToUpperInvariant()) observation" `
        -Force `
        -ErrorAction Stop | Out-Null
    [pscustomobject]$plan | ConvertTo-Json -Compress
}
