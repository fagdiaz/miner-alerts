# Miner Alerts Speckit Guide

This folder is the operating manual for structured improvements in Miner Alerts.
Use it to plan and audit small production-safe changes: quick wins, false alert fixes,
auto-reboot safety, Telegram bot UX, delivery diagnostics, and release hygiene.

## Workflow

1. Specify the problem in `specs/<number>-<name>/spec.md`.
2. Plan the technical approach in `plan.md`.
3. Break work into checkable tasks in `tasks.md`.
4. Implement only the scoped change.
5. Record evidence in `evidence.md`.
6. Add a completion entry to `docs/audit/DEVELOPMENT_LOG.md`.

## Active Feature

The active feature is declared in `.specify/feature.json`.

Current active feature:

```text
specs/009-vnish-hashboard-detection
```

## Commands And Validation

Use Windows PowerShell commands by default.

```powershell
& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py
& ".\\.venv\\Scripts\\python.exe" -m py_compile tools\\miner_diagnostics.py
& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\event_store.py app\\vnish_telemetry.py tools\\incident_report.py
git status
git diff
```

For Telegram work, prefer controlled QA validation:

```powershell
$env:DBG_TELEGRAM="1"
$env:DBG_TELEGRAM_COMMANDS_ONLY="1"
```

## Technology Decisions

Use `docs/speckit/TECHNOLOGY_STRATEGY.md` before adding new frameworks,
services, databases, dashboards or containers.

## Safety Rules

- Do not commit `app/config.json`, `app/state.json`, tokens, chat IDs, or logs.
- Do not change auto-reboot behavior without explicit evidence.
- Do not bypass Telegram confirmation for reboot/restart actions.
- Do not treat `py_compile` as proof of runtime behavior.
- Restart the running service/process after code or `app/config.json` changes; docs-only changes do not require restart.
