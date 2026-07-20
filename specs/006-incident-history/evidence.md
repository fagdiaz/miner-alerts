# Evidence: Incident History And Restart Intelligence

## Implemented Scope

- SQLite schema v1 with WAL, indexes, locking, retention, and safe failures.
- Five-minute bounded telemetry samples by default.
- Durable state transitions, restart incidents, and action outcomes.
- Existing uptime reset classified as `expected_manual`, `expected_auto`, or
  `unexpected` without changing detection criteria.
- Dedicated unexpected-restart Telegram notification.
- Read-only `/events`, `/events <miner>`, and `/event <id>` commands.
- Production-safe config defaults and database artifact ignores.

## Deterministic Validation

Passed on 2026-07-20:

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py app\event_store.py app\restart_intelligence.py tools\miner_diagnostics.py tools\diagnostics_baseline.py
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py" -v
& ".\.venv\Scripts\python.exe" -m json.tool app\config.example.json
git diff --check
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force; & ".agents\skills\speckit-qa\scripts\preflight.ps1" -RunBuilds
```

Observed:

- Python compilation: PASS.
- Unit tests: 19/19 PASS.
- Config example JSON parse: PASS.
- Git diff check: PASS; only expected CRLF conversion warnings.
- Speckit QA: `Status=PASS`, Python/Telegram/Reboot/Config/Docs scopes detected.
- QA guard test confirmed `subprocess.run` is not called when
  `qa_mode=true` and `qa_allow_real_actions=false`.
- Store tests confirmed reopen persistence, newest-first/filter queries,
  90/365-day retention behavior, 20 concurrent writes, and safe initialization
  failure.
- Static gate check confirmed startup guard, sustained LOW, cooldown, reboot
  window, max-window, and QA block remain present.

## Git Hygiene

`git check-ignore -v` confirmed:

- `app/config.json` ignored.
- `app/state.json` ignored.
- `data/miner_alerts.db`, `-wal`, and `-shm` ignored.

No real config, state, database, logs, diagnostics, or cache artifacts are part of
the feature diff.

## Runtime Validation

Before activation, Windows service `MinerAlerts` was `RUNNING` as `LocalSystem`
with PID `32092`.

Restart attempts from the Codex process were blocked by Windows service ACLs:

```text
Restart-Service: No se puede abrir el servicio MinerAlerts en el equipo '.'.
NSSM restart: OpenService(): Acceso denegado.
```

The service remained `RUNNING` with PID `32092`; it was not killed or left in a
partial state. Runtime activation remains blocked until an elevated PowerShell
runs the restart.

Post-start checks still pending:

- New PID and `RUNNING` status.
- `EVENT_STORE enabled=true ... available=true schema=1` startup log.
- `/events` deterministic reply.
- `/selftest` includes `History=OK`.

Activation command:

```powershell
Restart-Service -Name MinerAlerts -Force
Start-Sleep -Seconds 3
sc.exe queryex MinerAlerts
```
