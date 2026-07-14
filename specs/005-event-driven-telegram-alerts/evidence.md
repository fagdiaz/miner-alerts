# Evidence: Event-Driven Telegram Alerts

## Local Validation

Passed:

```powershell
& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py tools\\miner_diagnostics.py tools\\diagnostics_baseline.py
& ".\\.venv\\Scripts\\python.exe" -c "import app.miner_monitor as m; print(m.format_state_event('23','OK','LOW',55.0,60.0,3,3,True))"
git diff --check
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force; & ".agents\\skills\\speckit-qa\\scripts\\preflight.ps1" -RunBuilds
```

Observed event-line smoke output:

```text
- 23: OK -> LOW | 55.00 TH/s < 60.00 TH/s
```

Static verification:

- `notify_degraded_hourly` defaults to `false`.
- Existing `degraded_hourly` sender is gated by `notify_degraded_hourly`.
- Manual `/status` still uses `snapshot_ref` and is not changed.
- `STATE_CHANGE` still includes the full current snapshot, now preceded by event lines when available.
- Speckit QA preflight passed with `git-diff-check=PASS`.

## Runtime Validation

Pending after service restart:

- Confirm the bot still answers `/status`.
- Confirm no hourly `degraded_hourly` status is sent unless `notify_degraded_hourly=true` is explicitly configured.
