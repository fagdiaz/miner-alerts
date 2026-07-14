# Implementation Plan: Event-Driven Telegram Alerts

## Approach

Make the existing degraded hourly reminder opt-in and improve existing
`STATE_CHANGE` text without changing core monitoring logic.

## Design

- Add config keys:
  - `notify_degraded_hourly`
  - `degraded_hourly_seconds`
- Gate the existing degraded hourly sender behind `notify_degraded_hourly`.
- Add concise event lines to state-change Telegram messages.
- Leave `snapshot_ref` and `/status` unchanged.

## Validation

```powershell
& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py tools\\miner_diagnostics.py tools\\diagnostics_baseline.py
```
