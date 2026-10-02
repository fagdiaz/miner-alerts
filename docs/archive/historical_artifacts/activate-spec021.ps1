$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath 'F:\02-ASIC - mineros\miner-alerts'
& '.\tools\install_watchdog_task.ps1' -ConfigureServiceRecovery
Restart-Service -Name MinerAlerts -Force
Start-Sleep -Seconds 8
Start-ScheduledTask -TaskPath '\MinerAlerts\' -TaskName 'MinerAlertsWatchdog'
Start-Sleep -Seconds 5
@(
  "activated_at=$(Get-Date -Format o)"
  "service=$((Get-Service -Name MinerAlerts).Status)"
  "task=$((Get-ScheduledTask -TaskPath '\MinerAlerts\' -TaskName 'MinerAlertsWatchdog').State)"
  "task_last_result=$((Get-ScheduledTaskInfo -TaskPath '\MinerAlerts\' -TaskName 'MinerAlertsWatchdog').LastTaskResult)"
  (& sc.exe queryex MinerAlerts)
  (& sc.exe qfailure MinerAlerts)
) | Set-Content -LiteralPath 'F:\02-ASIC - mineros\miner-alerts\artifacts\activate-spec021-result.txt' -Encoding UTF8
