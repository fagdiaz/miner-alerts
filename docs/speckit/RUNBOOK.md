# Miner Alerts Validation Runbook

## Baseline Checks

```powershell
git status
git diff --stat
& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py
& ".\\.venv\\Scripts\\python.exe" -m py_compile tools\\miner_diagnostics.py
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

## Telegram Alert Policy

Production Telegram notifications should be event-driven by default:

- Startup notification if `notify_startup=true`.
- State changes for LOW, OFFLINE, HASHBOARD and recovery to OK.
- Reboot/restart results and failures.
- Manual command replies.

Hourly degraded status is disabled by default:

```json
"notify_degraded_hourly": false,
"degraded_hourly_seconds": 3600
```

Enable it only if an operator explicitly wants repeated reminders while a miner
is in degraded mode.

## Auto-Reboot Safety Checks

- QA mode with real actions disabled must block manual and automatic real actions.
- Startup guard must prevent auto-reboot during its configured window.
- LOW must be sustained from the current process execution before auto-reboot.
- Cooldown and reboot window limits must be visible in logs when they block action.

## Evidence Rules

Every spec should record:

- Commands executed.
- Runtime mode used: QA or production controlled.
- Telegram commands tested.
- Logs observed.
- Checks blocked or not executed.
