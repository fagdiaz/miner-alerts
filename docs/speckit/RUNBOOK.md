# Miner Alerts Validation Runbook

## Planning Boundary

This runbook documents implemented behavior and executable checks. Planned work
belongs in `ROADMAP.md`; estimated implementation and bug-fix windows belong in
`DELIVERY_PLAN.md`.

Current release gate as of 2026-08-13: Spec 030 commit `2afd65e` is deployed and
its Telegram smoke passed. Spec 021 liveness is implemented and activated; its
controlled SCM recovery proof passed and D+1/D+3 observation remains open.

## Baseline Checks

```powershell
git status
git diff --stat
& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py
& ".\\.venv\\Scripts\\python.exe" -m py_compile tools\\miner_diagnostics.py
& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\event_store.py app\\vnish_telemetry.py app\\vnish_logs.py app\\mining_quality.py tools\\incident_report.py tools\\vnish_log_collector.py tools\\operations_dashboard.py
```

## Read-Only Miner Diagnostics

Use this when investigating false alerts, unnecessary reboots, Vnish behavior,
pool issues, hashboard symptoms, or possible power/voltage hints.

Dry run with the example config, no miner network calls:

```powershell
& ".\\.venv\\Scripts\\python.exe" tools\\miner_diagnostics.py --config app\\config.example.json --out diagnostics\\dry-run --dry-run
```

Production snapshot, read-only API 4028 calls:

```powershell
& ".\\.venv\\Scripts\\python.exe" tools\\miner_diagnostics.py --config app\\config.json --out diagnostics\\latest
```

Build a baseline/sweet-spot report from one snapshot or a diagnostics folder:

```powershell
& ".\\.venv\\Scripts\\python.exe" tools\\diagnostics_baseline.py --input diagnostics\\latest\\snapshot.json --out diagnostics\\baseline
```

Optional Docker run for the diagnostics collector only:

```powershell
docker build -f Dockerfile.diagnostics -t miner-alerts-diagnostics .
docker run --rm -v "${PWD}\\app\\config.json:/config/config.json:ro" -v "${PWD}\\diagnostics:/out" miner-alerts-diagnostics
```

Notes:

- The diagnostics collector is read-only.
- The baseline analyzer is read-only and only consumes saved snapshots.
- It does not call Hashcore Toolkit.
- It does not touch `app/state.json`.
- Relative Docker volume syntax can vary by Windows/Docker Desktop configuration.

## Service / Process Restart Policy

Miner Alerts runs as a long-lived Python process. The process reads code and
configuration at startup, so use this policy:

- Documentation-only changes under `.specify/`, `.agents/`, `docs/`, or `specs/`: no service restart required.
- Code changes in `app/miner_monitor.py`: restart the service/process after validation.
- Config changes in `app/config.json`: restart the service/process after validation.
- `app/state.json` manual edits: stop the service first, edit only when needed, then start it again.

Before restart:

```powershell
& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py
git status
```

Restart command depends on how the service was installed. Use the actual Windows
service name or scheduled-task name from the host. Do not run a second manual
monitor while the service instance is active.

For the current NSSM service, run from an elevated PowerShell:

```powershell
Restart-Service -Name MinerAlerts -Force
Get-Service -Name MinerAlerts
```

A `Running` status alone is insufficient: verify a new startup block in the
service log, including PID, config path, mutex acquisition, `qa_mode`, startup
guard and event-store health.

### Monitor Liveness Watchdog

The watchdog is an independent read-only process. It reads the sanitized
heartbeat plus Windows service/process state and can notify Telegram, but it
does not import miner API, state-machine or Hashcore action code.

Validate before activation:

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_monitor_liveness tests.test_reboot_safety
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py app\liveness.py tools\monitor_watchdog.py
[void][scriptblock]::Create((Get-Content tools\install_watchdog_task.ps1 -Raw))
```

Run a read-only assessment without sending or consuming incident state:

```powershell
& ".\.venv\Scripts\python.exe" tools\monitor_watchdog.py --config app\config.json --no-notify
Get-Content logs\watchdog.log -Tail 20
```

Set a bounded maintenance lease before an intentional service operation:

```powershell
& ".\.venv\Scripts\python.exe" tools\monitor_watchdog.py --config app\config.json --maintenance-seconds 900 --maintenance-reason "controlled rollout"
```

Install the hidden SYSTEM task and explicitly configure SCM recovery from an
elevated PowerShell. The installer first exports `sc qfailure` under ignored
`artifacts/`:

```powershell
& ".\tools\install_watchdog_task.ps1" -ConfigureServiceRecovery
Restart-Service -Name MinerAlerts -Force
Start-ScheduledTask -TaskPath "\MinerAlerts\" -TaskName "MinerAlertsWatchdog"
Get-ScheduledTaskInfo -TaskPath "\MinerAlerts\" -TaskName "MinerAlertsWatchdog"
sc.exe qfailure MinerAlerts
```

The controlled 2026-08-13 proof terminated the service process tree once. SCM
restarted it after the configured 60-second delay with one new wrapper and one
new monitor PID; the mutex, 600-second startup guard and first-tick heartbeat
were observed, with no miner or Hashcore action.

After the service heartbeat is fresh, clear maintenance explicitly or let the
lease expire:

```powershell
& ".\.venv\Scripts\python.exe" tools\monitor_watchdog.py --config app\config.json --clear-maintenance
```

Rollback removes only the independent task; use the captured SCM artifact to
restore the prior failure-action policy:

```powershell
Unregister-ScheduledTask -TaskPath "\MinerAlerts\" -TaskName "MinerAlertsWatchdog" -Confirm:$false
```

### Telegram Token In Logs

Current source redacts the bot token from Telegram response and exception logs.
If an older `getUpdates` error contains a URL shaped like
`api.telegram.org/bot...`, treat that token as exposed locally:

1. Revoke/regenerate it with BotFather.
2. Update only `telegram.bot_token` in ignored local `app/config.json`.
3. Restart `MinerAlerts` once from elevated PowerShell.
4. Verify the new startup block and Telegram command delivery.

Do not commit, paste or attach the affected log. Preserve or remove it according
to the local incident-retention decision only after token rotation.

## Telegram QA Trace

Use only when validating Telegram command changes:

```powershell
$env:DBG_TELEGRAM="1"
$env:DBG_TELEGRAM_COMMANDS_ONLY="1"
& ".\\.venv\\Scripts\\python.exe" app\\miner_monitor.py
```

Expected trace keywords for commands:

```text
RX
TGQ
SEND_POST
PERF
TG SEND_ERR
TG ENQUEUE_FAIL
TG FALLBACK_SEND
TG DROP chat_mismatch
```

### Delivery Contract

- Cada payload de texto queda limitado a 3900 caracteres. Una respuesta mas
  larga se envia como `Parte N/M`, preservando orden y contenido.
- Las respuestas a comandos usan `is_command=true`: no entran en dedupe ni
  coalescing de notificaciones.
- Con cola llena, un comando usa un envio directo acotado, sin retries, y deja
  `TG QUEUE_BYPASS` seguido de `TG FALLBACK_SEND ok|err|exc`.
- Una notificacion informativa rechazada por presion deja `TG QUEUE_DROP` con
  clase, tipo y motivo, sin copiar el payload al log.
- `TG ENQUEUE_FAIL`, `TG FALLBACK_SEND`, `TG SEND_ERR` y
  `TG DROP chat_mismatch` son evidencia de produccion y no dependen de los
  flags de debug.

Comandos oficiales para acciones confirmadas: `/rb<ID>`, `/reboot_no_ok` y
`/c<code>`. `/help <comando>` muestra la ficha del registro central sin ejecutar
la accion.

## Telegram Alert Policy

Production Telegram notifications should be event-driven by default:

- Startup notification if `notify_startup=true`.
- Irregular episodes for LOW, OFFLINE, or board loss, coalesced across a bounded
  30-second window for all affected miners.
- Persistent reminders at episode ages 5, 10, 15, 30, 60 and 120 minutes, then
  hourly while the condition remains active.
- One concise recovery sequence from OK back to OK, including restart evidence
  when detected. User-facing board loss is rendered as `PLACAS x/y`.
- Reboot/restart results and failures.
- Manual command replies.

Hourly degraded status is disabled by default:

```json
"notify_degraded_hourly": false,
"degraded_hourly_seconds": 3600,
"state_change_coalesce_seconds": 30,
"notify_persistent_outage": true,
"persistent_outage_schedule_seconds": [300, 600, 900, 1800, 3600, 7200],
"persistent_outage_repeat_seconds": 3600
```

The episode reminder is independent from degraded hourly status and stops as
soon as the miner returns to confirmed OK. `/status` renders current response,
rate, and board evidence: healthy evidence under recovery hysteresis is
`RECUPERANDO`, never a positive rate labeled `OFFLINE`.

## Incident History And Restart Intelligence

The monitor keeps a local operational history in SQLite by default. The store is
observational: it records evidence but is never consulted to trigger a reboot or
to bypass QA, startup guard, sustained LOW, cooldown, or reboot-window policy.

Production-safe defaults:

```json
"event_store_enabled": true,
"event_store_path": "data/miner_alerts.db",
"telemetry_sample_seconds": 300,
"telemetry_retention_days": 90,
"event_retention_days": 365,
"decision_retention_days": 180,
"restart_attribution_window_seconds": 900,
"notify_unexpected_restarts": true,
"notify_expected_restarts": false
```

Relative database paths are resolved from the repository root, not the service
working directory. The database, `-wal`, and `-shm` files are local runtime
artifacts ignored by Git.

Restart classifications:

- `unexpected`: uptime reset with no recent successful manual/automatic action.
- `expected_manual`: uptime reset shortly after a successful Telegram action.
- `expected_auto`: uptime reset shortly after a successful auto-reboot.

Unexpected restarts join the active episode after the 30-second grouping window,
with previous/current uptime, attribution and a click-safe `/e<ID>` detail link.
Expected restarts are stored but are not separately notified by default.

Read-only Telegram history:

```text
/events
/events 23
/event 42
/e42
/why
/why 23
```

These commands read local SQLite history only. They do not call API 4028 or
Hashcore Toolkit. `/why` explains the latest recorded auto-reboot result with
LOW duration, cooldown/window evidence, boards, and normalized Vnish telemetry.
`/e<ID>` is an alias for `/event <id>` and includes a bounded chronological
episode timeline with related fleet events.

Startup health log:

```text
EVENT_STORE enabled=true path=<absolute-path> available=true schema=5
```

If storage cannot initialize or a write fails, the monitor logs `EVENT_STORE`
with the operation and exception and continues monitoring. Emergency rollback is
configuration-only: set `"event_store_enabled": false` in local
`app/config.json` and restart the service. Existing monitoring remains active;
history commands reply `Historial no disponible.`

## Vnish Telemetry And Reboot Decision Audit

Schema v3 keeps normalized evidence from the `summary` and `stats` requests already performed
by the monitor. It does not add another stats request and does not store raw ASIC
responses. Available fields include maximum temperature, average chain voltage,
total chain consumption, average frequency, hardware-error counters, fan RPM/PWM,
and conservative diagnostic flags.

`chain_voltage_mv_avg` is hashboard/firmware evidence. It is not AC input voltage
and must not be used alone to diagnose utility/PSU fluctuations. AC input quality
requires a PDU, UPS, smart meter, or an explicitly documented PSU source.

Generate an offline report without loading config or contacting miners:

```powershell
& ".\\.venv\\Scripts\\python.exe" tools\\incident_report.py --db data\\miner_alerts.db --hours 24 --format markdown
& ".\\.venv\\Scripts\\python.exe" tools\\incident_report.py --db data\\miner_alerts.db --hours 168 --miner 23 --format json --out diagnostics\\incident-23.json
```

The report opens SQLite in read-only mode and correlates samples, operational
events, and auto-reboot decisions. It never invokes Hashcore.

## Stability Advisor

The Stability Advisor compares the latest persisted sample with each miner's own
healthy history. It uses robust median/MAD bands and never triggers or authorizes
a restart or reboot.

Production defaults:

```json
"stability_window_hours": 168,
"stability_min_samples": 12,
"stability_stale_seconds": 900
```

At the default five-minute telemetry interval, a miner needs about one hour of
prior healthy evidence before leaving `LEARNING`. Available results are:

- `STABLE`: no meaningful deviation from the learned healthy range.
- `WATCH`: soft drift or a recovered current signal while state hysteresis still
  retains a prior non-OK label.
- `CRITICAL`: current stale/no-response, below-threshold, missing-board, or high
  temperature evidence.
- `LEARNING`: there is not enough healthy history to claim stability.

Read-only Telegram commands:

```text
/health
/health all
/health 23
```

The command queries local SQLite only. It does not call API 4028 or Hashcore.
Hashrate, maximum temperature, chain voltage, chain power, and frequency are
compared when finite evidence exists. Chain voltage remains board-side telemetry;
it is explicitly not AC input voltage.

## Mining Quality Intelligence

Mining Quality compares cumulative counters only between samples from the same
uptime epoch. Counter or uptime regression starts a new learning interval instead
of producing a negative rate or a false fault. Current Vnish chain faults and
non-mining chains remain explicit evidence; known transition/autotune states are
reported as `WATCH` for observation and never trigger an action.

Production advisory defaults:

```json
"quality_window_hours": 24,
"quality_min_intervals": 3,
"quality_reject_warning_percent": 1.0,
"quality_stale_warning_percent": 1.0,
"quality_hw_error_delta_warning": 50,
"quality_no_share_warning_seconds": 900
```

Read-only Telegram commands:

```text
/quality
/quality all
/quality 23
```

The command reads at most 100 local SQLite samples per miner and contacts neither
the miner nor Hashcore. Rejected/stale percentages are interval values derived
from accepted, rejected, and stale deltas; lifetime totals are retained only as
bounded numeric counters. Raw firmware payloads, pool URLs, workers, and secrets
are not persisted.

## Vnish Firmware Log Intelligence

Install the focused synchronous WebSocket client in the project venv:

```powershell
& ".\\.venv\\Scripts\\python.exe" -m pip install -r requirements.txt
```

Run a bounded read-only dry run first:

```powershell
& ".\\.venv\\Scripts\\python.exe" tools\\vnish_log_collector.py `
  --config app\\config.json `
  --dry-run `
  --tabs status `
  --connect-timeout 2 `
  --idle-timeout 1 `
  --max-bytes 262144
```

Persist normalized events to the configured schema-v5 SQLite store:

```powershell
& ".\\.venv\\Scripts\\python.exe" tools\\vnish_log_collector.py `
  --config app\\config.json `
  --tabs status,miner,autotune,system
```

The CLI opens only `ws://<miner>/api/v1/logs-ws/<tab>`, processes one
miner/tab at a time, uses strict time/byte/event limits, and has no reconnect or
retry loop. Limits retain the newest recognized tail while preserving
chronological order. It stores generated categories and summaries, parsed source
time with clock provenance, and a SHA-256 fingerprint for idempotency. Raw lines,
pool workers, arbitrary firmware payloads, and credentials are neither persisted
nor printed.

Each persisted invocation writes one bounded `collector_runs` health record with
stream success/failure, parsed/inserted/duplicate counts and truncation. It does
not contain raw firmware content.

Read-only Telegram views:

```text
/firmware
/firmware all
/firmware 23
```

The monitor never opens the Vnish WebSocket. Telegram reads SQLite only, and
firmware events cannot change state, notifications, or reboot/restart policy.
Set `vnish_log_utc_offset_hours` only when the firmware clock offset is known;
otherwise `null` records the collector host local timezone as provenance.

Install the separate current-user scheduled task after a dry run:

```powershell
& ".\tools\install_vnish_collector_task.ps1" -WhatIf
& ".\tools\install_vnish_collector_task.ps1" -IntervalMinutes 30
Start-ScheduledTask -TaskPath "\MinerAlerts\" -TaskName "MinerAlertsVnishCollector"
Get-ScheduledTaskInfo -TaskPath "\MinerAlerts\" -TaskName "MinerAlertsVnishCollector"
```

The task invokes `.venv\Scripts\pythonw.exe` directly with the bounded collector
arguments, so it does not create a PowerShell or console window. It uses
`IgnoreNew` and has a ten-minute execution limit. It is current-user
`Interactive`, so it requires that user to have an active Windows session. It
never starts the monitor or Hashcore. `tools/run_vnish_collector.ps1` remains a
manual diagnostics wrapper only.

Read-only correlated diagnosis:

```text
/diagnose
/diagnose all
/diagnose 23
```

`/diagnose` uses only SQLite and returns bounded signal, quality, fresh firmware,
latest event, reboot-decision and collector-health evidence. Replayed firmware
events outside `diagnosis_firmware_window_hours` are excluded from current
evidence. The command is advisory and cannot execute reboot/restart.

## Local Operations Dashboard

Generate a self-contained read-only dashboard from the same SQLite history:

```powershell
& ".\\.venv\\Scripts\\python.exe" tools\\operations_dashboard.py `
  --db data\\miner_alerts.db `
  --out diagnostics\\dashboard\\index.html `
  --hours 24
```

Open `diagnostics/dashboard/index.html` locally. Regenerate the file whenever a
fresh view is required. The page contains fleet KPIs, one card per miner,
hashrate sparklines, evidence freshness, Vnish metrics, recent incidents, a
bounded Vnish firmware timeline, and auto-reboot decisions. Each card also shows the shared Stability Advisor and
Mining Quality status, interval deltas, baseline, and bounded evidence. It has no action controls, JavaScript, remote assets,
network listener, Telegram token, or miner credentials.

Optional Docker execution keeps this reporting tool isolated from the Windows
service and Hashcore Toolkit:

```powershell
docker build -f Dockerfile.dashboard -t miner-alerts-dashboard .
docker run --rm `
  -v "${PWD}\\data:/data:ro" `
  -v "${PWD}\\diagnostics\\dashboard:/out" `
  miner-alerts-dashboard
```

Mount the complete `data` directory so SQLite can read WAL/SHM sidecars when the
monitor is running. Docker is optional; the native PowerShell command is the
primary Windows path. `data/` and `diagnostics/` are ignored by Git.

## Auto-Reboot Safety Checks

- QA mode with real actions disabled must block manual and automatic real actions.
- Startup guard must prevent auto-reboot during its configured window.
- LOW must be sustained from the current process execution before auto-reboot.
- The current tick must have `responded=true` and a finite hashrate below threshold; no-response, missing/non-finite rate, or a recovered rate resets the sustained LOW timer.
- A current Vnish maximum temperature at or above `auto_reboot_max_temp_c` blocks automatic action when `auto_reboot_thermal_guard_enabled` is true.
- A current Vnish chain transition blocks automatic action when `auto_reboot_firmware_transition_guard_enabled` is true. The sustained-LOW timer restarts, so LOW must persist for a full interval after tuning/startup ends; manual confirmed actions are unchanged.
- If at least `auto_reboot_fleet_guard_min_affected` miners were degraded in the latest fresh completed tick, `auto_reboot_fleet_guard_enabled` blocks a reboot cascade as `fleet_incident`.
- Fleet evidence expires after `max(60, poll_seconds * 2)`; stale evidence is ignored.
- Thermal/fleet interlocks use existing summary/stats responses and never add miner IO.
- Cooldown and reboot window limits must be visible in logs when they block action.

Production-safe defaults:

```json
{
  "auto_reboot_thermal_guard_enabled": true,
  "auto_reboot_max_temp_c": 85.0,
  "auto_reboot_fleet_guard_enabled": true,
  "auto_reboot_fleet_guard_min_affected": 2,
  "auto_reboot_firmware_transition_guard_enabled": true
}
```

Expected evidence:

```text
[AUTO-REBOOT] blocked_by=high_temperature miner=... max_temp_c=... limit_c=85.0
[AUTO-REBOOT] blocked_by=firmware_transition miner=... transitioning_chains=... low_timer_reset=true
[AUTO-REBOOT] blocked_by=fleet_incident miner=... affected_count=... min_affected=2 ...
```

Use `/why` or `/why <miner>` to inspect the durable reason. A fleet block means
only that degradation was simultaneous; it does not prove a pool, network, or
power root cause. Manual confirmed actions remain available and unchanged.

## Evidence Rules

Every spec should record:

- Commands executed.
- Runtime mode used: QA or production controlled.
- Telegram commands tested.
- Logs observed.
- Checks blocked or not executed.
