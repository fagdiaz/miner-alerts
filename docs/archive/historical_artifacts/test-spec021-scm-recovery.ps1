$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath 'F:\02-ASIC - mineros\miner-alerts'
$resultLines = [System.Collections.Generic.List[string]]::new()
function Add-Evidence([string]$line) { $resultLines.Add("$(Get-Date -Format o) $line") }
function Service-Snapshot {
    $raw = (& sc.exe queryex MinerAlerts) -join "
"
    $state = if ($raw -match '(?:STATE|ESTADO)\s*:\s*\d+\s+([A-Z_]+)') { $Matches[1] } else { 'UNKNOWN' }
    $pid = if ($raw -match 'PID\s*:\s*(\d+)') { [int]$Matches[1] } else { 0 }
    return @{ State=$state; Pid=$pid }
}
$before = Service-Snapshot
$beforeHb = Get-Content -Raw -LiteralPath (Join-Path 'F:\02-ASIC - mineros\miner-alerts' 'data\monitor_heartbeat.json') | ConvertFrom-Json
Add-Evidence "baseline service_state=$($before.State) wrapper_pid=$($before.Pid) monitor_pid=$($beforeHb.pid) tick=$($beforeHb.tick_sequence)"
try {
    & taskkill.exe /PID $before.Pid /T /F | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "taskkill failed exit=$LASTEXITCODE" }
    Add-Evidence "forced_failure wrapper_pid=$($before.Pid) tree=true"

    $deadline = (Get-Date).AddSeconds(150)
    $recovered = $false
    do {
        Start-Sleep -Seconds 5
        $snap = Service-Snapshot
        Add-Evidence "poll service_state=$($snap.State) wrapper_pid=$($snap.Pid)"
        if ($snap.State -eq 'RUNNING' -and $snap.Pid -gt 0 -and $snap.Pid -ne $before.Pid) {
            $recovered = $true
            break
        }
    } while ((Get-Date) -lt $deadline)

    if (-not $recovered) { throw 'SCM did not recover service within 150s' }

    $hbDeadline = (Get-Date).AddSeconds(90)
    $hbRecovered = $false
    do {
        Start-Sleep -Seconds 3
        try {
            $hb = Get-Content -Raw -LiteralPath (Join-Path 'F:\02-ASIC - mineros\miner-alerts' 'data\monitor_heartbeat.json') | ConvertFrom-Json
            if ($hb.pid -ne $beforeHb.pid -and $hb.last_tick_completed_ts -gt $beforeHb.last_tick_completed_ts) {
                $hbRecovered = $true
                Add-Evidence "heartbeat_recovered monitor_pid=$($hb.pid) tick=$($hb.tick_sequence)"
                break
            }
        } catch {}
    } while ((Get-Date) -lt $hbDeadline)
    if (-not $hbRecovered) { throw 'Monitor heartbeat did not recover with a new PID' }
    Add-Evidence 'result=PASS'
} catch {
    Add-Evidence "result=FAIL error=$($_.Exception.Message)"
    $current = Service-Snapshot
    if ($current.State -ne 'RUNNING') {
        Start-Service -Name MinerAlerts
        Add-Evidence 'fallback_start_service=issued'
    }
    $resultLines | Set-Content -LiteralPath 'F:\02-ASIC - mineros\miner-alerts\artifacts\test-spec021-scm-recovery-result.txt' -Encoding UTF8
    throw
}
$resultLines | Set-Content -LiteralPath 'F:\02-ASIC - mineros\miner-alerts\artifacts\test-spec021-scm-recovery-result.txt' -Encoding UTF8
