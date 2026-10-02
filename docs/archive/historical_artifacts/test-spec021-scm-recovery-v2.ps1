$ErrorActionPreference = "Continue"
$repo = "F:\02-ASIC - mineros\miner-alerts"
$result = "F:\02-ASIC - mineros\miner-alerts\artifacts\test-spec021-scm-recovery-result.txt"
$lines = [System.Collections.Generic.List[string]]::new()
function Record([string]$message) { [void]$lines.Add("$(Get-Date -Format o) $message"); $lines | Set-Content -LiteralPath $result -Encoding UTF8 }
function Snapshot {
    $output = (& sc.exe queryex MinerAlerts) -join "`n"
    $state = "UNKNOWN"; $pidValue = 0
    if ($output -match "(?:STATE|ESTADO)\s*:\s*\d+\s+([A-Z_]+)") { $state = $Matches[1] }
    if ($output -match "PID\s*:\s*(\d+)") { $pidValue = [int]$Matches[1] }
    return @{ State=$state; Pid=$pidValue }
}
try {
    Set-Location -LiteralPath $repo
    $before = Snapshot
    $beforeHb = Get-Content -Raw -LiteralPath (Join-Path $repo "data\monitor_heartbeat.json") | ConvertFrom-Json
    Record "baseline service_state=$($before.State) wrapper_pid=$($before.Pid) monitor_pid=$($beforeHb.pid) tick=$($beforeHb.tick_sequence)"
    & taskkill.exe /PID $before.Pid /T /F | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "taskkill failed exit=$LASTEXITCODE" }
    Record "forced_failure wrapper_pid=$($before.Pid) tree=true"
    $deadline = (Get-Date).AddSeconds(150)
    $recovered = $false
    do {
        Start-Sleep -Seconds 5
        $snap = Snapshot
        Record "poll service_state=$($snap.State) wrapper_pid=$($snap.Pid)"
        if ($snap.State -eq "RUNNING" -and $snap.Pid -gt 0 -and $snap.Pid -ne $before.Pid) { $recovered = $true; break }
    } while ((Get-Date) -lt $deadline)
    if (-not $recovered) { throw "SCM did not recover service within 150s" }
    $hbDeadline = (Get-Date).AddSeconds(90)
    $hbRecovered = $false
    do {
        Start-Sleep -Seconds 3
        try {
            $hb = Get-Content -Raw -LiteralPath (Join-Path $repo "data\monitor_heartbeat.json") | ConvertFrom-Json
            if ($hb.pid -ne $beforeHb.pid -and $hb.last_tick_completed_ts -gt $beforeHb.last_tick_completed_ts) {
                Record "heartbeat_recovered monitor_pid=$($hb.pid) tick=$($hb.tick_sequence)"
                $hbRecovered = $true; break
            }
        } catch {}
    } while ((Get-Date) -lt $hbDeadline)
    if (-not $hbRecovered) { throw "Monitor heartbeat did not recover with a new PID" }
    Record "result=PASS"
    exit 0
} catch {
    Record "result=FAIL error=$($_.Exception.Message)"
    $current = Snapshot
    if ($current.State -ne "RUNNING") {
        Start-Service -Name MinerAlerts
        Record "fallback_start_service=issued"
    }
    exit 1
}
