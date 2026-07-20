# Quickstart: Incident History And Restart Intelligence

## 1. Syntax And Unit Tests

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py app\event_store.py app\restart_intelligence.py
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py" -v
```

## 2. QA Configuration

Use local `app/config.json` only and do not commit it:

```json
{
  "qa_mode": true,
  "qa_allow_real_actions": false,
  "event_store_enabled": true,
  "event_store_path": "data/miner_alerts.db",
  "telemetry_sample_seconds": 300,
  "restart_attribution_window_seconds": 900,
  "notify_unexpected_restarts": true
}
```

## 3. Telegram QA

```text
/events
/events 23
/event 1
```

Verify deterministic replies, `is_command=True` queue behavior under Telegram
debug flags, and no ASIC/Hashcore calls from these commands.

## 4. Restart Classification Smoke

- Simulate or unit-test an uptime drop without recent actions: expect `unexpected`.
- Simulate a recent manual action: expect `expected_manual`.
- Simulate a recent automatic action: expect `expected_auto`.
- Verify repeated post-reset uptime does not create another incident.

## 5. Safety Regression

- Run QA with real actions blocked.
- Confirm startup guard, sustained LOW, cooldown, reboot window, and max-window logs
  remain unchanged.
- Confirm no event-store read or write invokes `run_hashcore_cli`.

## 6. Production Activation

After validation, restart the Windows service from an elevated PowerShell:

```powershell
Restart-Service -Name MinerAlerts -Force
Start-Sleep -Seconds 3
sc.exe queryex MinerAlerts
```

Then check the startup log for the absolute event-store path and query `/events`.
