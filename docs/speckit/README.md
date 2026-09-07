# Miner Alerts Speckit Guide

This folder is the operating manual for structured improvements in Miner Alerts.
Use it to plan and audit production-safe changes: false-alert fixes, monitor
availability, auto-reboot safety, diagnostics, Telegram UX and observability.

## Document Map

- `ROADMAP.md`: prioritized capabilities, dependencies and decision gates.
- `SPEC_PROGRAM.md`: definitive Spec 001-030 sequence, architecture boundaries,
  risk classes and shared Definition of Done.
- `DELIVERY_PLAN.md`: implementation, observation and bug-fix calendar.
- `TECHNOLOGY_STRATEGY.md`: adoption rules for polling, WebSockets, Docker,
  Prometheus/Grafana, FastAPI, MQTT and OpenTelemetry.
- `INTERFACE_STRATEGY.md`: Telegram, static dashboard, Grafana and interface boundaries.
- `HASHCORE_TOOLKIT_STRATEGY.md`: current action boundary and capability inventory.
- `MINER_DIAGNOSTICS.md`: evidence model used before intervention.
- `V3_EXPANSION_PLAN.md`: strategic roadmap for Telegram Max, predictive health, and V3 capabilities.
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

Current certified release:

```text
specs/029-v2-release-stabilization (Release v2.0.0 Certified & Tagged)
```

All 30 specifications in the program (Specs 001 to 030) are 100% completed,
verified with evidence, and closed. Production runtime has operated continuously
for over 267 hours without interruption under PID 38816.

Historical Specs 001-005 were early foundation artifacts superseded by Specs
006-030.

## Commands And Validation

Use Windows PowerShell commands by default.

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py
& ".\.venv\Scripts\python.exe" -c "import unittest, os; loader = unittest.TestLoader(); suite = unittest.TestSuite(); [suite.addTests(loader.discover('tests', pattern=f)) for f in os.listdir('tests') if f.startswith('test_') and f.endswith('.py')]; runner = unittest.TextTestRunner(verbosity=0); res = runner.run(suite); print(f'PASS: {res.testsRun} tests, failures={len(res.failures)}, errors={len(res.errors)}')"
& ".\.venv\Scripts\python.exe" tools\release_audit.py --check-only
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
