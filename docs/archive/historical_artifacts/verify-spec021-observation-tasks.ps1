$ErrorActionPreference = "Stop"
$rows = foreach ($name in @("MinerAlertsLivenessD1", "MinerAlertsLivenessD3")) {
    $task = Get-ScheduledTask -TaskPath "\MinerAlerts\" -TaskName $name -ErrorAction Stop
    $info = Get-ScheduledTaskInfo -TaskPath "\MinerAlerts\" -TaskName $name -ErrorAction Stop
    [pscustomobject]@{
        name = $name
        state = [string]$task.State
        run_as = $task.Principal.UserId
        logon_type = [string]$task.Principal.LogonType
        run_level = [string]$task.Principal.RunLevel
        execute = $task.Actions[0].Execute
        arguments = $task.Actions[0].Arguments
        working_directory = $task.Actions[0].WorkingDirectory
        start_boundary = $task.Triggers[0].StartBoundary
        next_run_time = $info.NextRunTime.ToString("o")
        last_task_result = $info.LastTaskResult
        multiple_instances = [string]$task.Settings.MultipleInstances
        start_when_available = $task.Settings.StartWhenAvailable
        execution_time_limit = [string]$task.Settings.ExecutionTimeLimit
    }
}
$rows | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath "F:\02-ASIC - mineros\miner-alerts\artifacts\spec021-observation-tasks.json" -Encoding UTF8
