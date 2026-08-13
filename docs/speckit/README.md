# Miner Alerts Speckit Guide

This folder is the operating manual for structured improvements in Miner Alerts.
Use it to plan and audit production-safe changes: false-alert fixes, monitor
availability, auto-reboot safety, diagnostics, Telegram UX and observability.

## Document Map

- `ROADMAP.md`: prioritized capabilities, dependencies and decision gates.
- `SPEC_PROGRAM.md`: definitive Spec 021-029 sequence, architecture boundaries,
  risk classes and shared Definition of Done.
- `DELIVERY_PLAN.md`: estimated implementation, observation and bug-fix calendar.
- `TECHNOLOGY_STRATEGY.md`: adoption rules for polling, WebSockets, Docker,
  Prometheus/Grafana, FastAPI, MQTT and OpenTelemetry.
- `INTERFACE_STRATEGY.md`: Telegram, static dashboard and conditional local UI.
- `HASHCORE_TOOLKIT_STRATEGY.md`: current action boundary and inventory plan.
- `MINER_DIAGNOSTICS.md`: evidence model used before intervention.
- `RUNBOOK.md`: commands and checks for the system that exists today.

Roadmap documents may describe planned work. The runbook must only describe
implemented behavior or clearly label a procedure as planned.

## Workflow

1. Specify the problem in `specs/<number>-<name>/spec.md`.
2. Plan the technical approach in `plan.md`.
3. Break work into checkable tasks in `tasks.md`.
4. Implement only the scoped change.
5. Record evidence in `evidence.md`.
6. Add a completion entry to `docs/audit/DEVELOPMENT_LOG.md`.

## Active Feature

The active feature is declared in `.specify/feature.json`.

Current active feature and release gate:

```text
specs/020-episode-alerts
```

The Spec 020 implementation is committed and pushed as `e502ab9`. Its controlled
service restart and runtime smoke remain open; do not treat merge state as
production activation.

Specs 021-029 are complete planning packages but are not active or implemented.
Historical Specs 001-005 are early foundation artifacts and partly superseded by
Specs 006-020. Their unchecked tasks are not the delivery queue; `SPEC_PROGRAM.md`
and `ROADMAP.md` govern new work.

## Commands And Validation

Use Windows PowerShell commands by default.

```powershell
& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py
& ".\\.venv\\Scripts\\python.exe" -m py_compile tools\\miner_diagnostics.py
& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\event_store.py app\\vnish_telemetry.py app\\reboot_safety.py tools\\incident_report.py
& ".\\.venv\\Scripts\\python.exe" -m py_compile tools\\operations_dashboard.py
& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\stability_profile.py
git status
git diff
```

For Telegram work, prefer controlled QA validation:

```powershell
$env:DBG_TELEGRAM="1"
$env:DBG_TELEGRAM_COMMANDS_ONLY="1"
```

## Planning And Technology Decisions

Use `SPEC_PROGRAM.md` for sequence/dependencies, `ROADMAP.md` for priority/status,
and `DELIVERY_PLAN.md` to reserve
implementation plus stabilization time. Use `TECHNOLOGY_STRATEGY.md` before
adding frameworks, services, databases, dashboards, protocols or containers.

## Safety Rules

- Do not commit `app/config.json`, `app/state.json`, tokens, chat IDs, or logs.
- Do not change auto-reboot behavior without explicit evidence.
- Do not bypass Telegram confirmation for reboot/restart actions.
- Do not treat `py_compile` as proof of runtime behavior.
- Restart the running service/process after code or `app/config.json` changes; docs-only changes do not require restart.
