# Evidence: Mining Quality Intelligence

## Status

Implementation and local validation complete. Production activation remains
deferred until the controlled end-of-day service restart.

## Discovery

- Fresh read-only API 4028 collection: 4/4 miners responded, 3/3 boards each.
- Current rates: 94.059-98.685 TH/s.
- Summary counters and Vnish chain state/fault fields are present.
- Local Hashcore Toolkit wrapper exists; `version`, `--help`, and documented help
  calls were read-only and no action command was issued.
- Windows service `MinerAlerts` remained `Running` and was not restarted.

## Test-First Evidence

- `python -m unittest tests.test_mining_quality -v` initially failed with
  `ModuleNotFoundError: app.mining_quality`.
- After the pure analyzer existed, command/default/persistence tests remained red
  until `/quality`, schema-v3 columns, and config defaults were wired.
- Dashboard tests then failed on missing `quality` view-model/render output before
  the shared analyzer integration.

## Validation

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\mining_quality.py app\event_store.py app\miner_monitor.py app\stability_profile.py app\vnish_telemetry.py tools\operations_dashboard.py
& ".\.venv\Scripts\python.exe" -m unittest tests.test_mining_quality tests.test_event_store tests.test_operations_dashboard -v
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -v
& ".\.venv\Scripts\python.exe" -c "import json,pathlib; json.loads(pathlib.Path('app/config.example.json').read_text(encoding='utf-8'))"
git diff --check
```

Results:

- 27 targeted tests: PASS.
- 80 full-suite tests: PASS.
- Python compilation and config JSON parse: PASS.
- `git diff --check`: PASS.
- Speckit preflight with builds: PASS, requirements checklist 16/16.
- Pure analyzer benchmark over 2,000 input rows (bounded to 100): 4.974 ms.
- Static inspection: state-machine and auto-reboot sections are byte-equivalent
  to commit `9b8e793`; quality helper/analyzer contain no miner IO or action call.

## Live Read-Only Evidence

Two sanitized API 4028 captures 761-762 seconds apart were compared locally:

- S19JPRO-23: accepted +82, rejected +0, stale +0, HW +0 -> `stable`.
- S19JPRO-24: accepted +54, rejected +0, stale +0, HW +0 -> `stable`.
- S19JPRO-25: accepted +61, rejected +0, stale +0, HW +0 -> `stable`.
- S19JPRO-26: accepted +94, rejected +0, stale +0, HW +0 -> `stable`.

No chain fault or non-mining chain was observed. The captures and generated SQLite
fixture/HTML remain under ignored `diagnostics/` paths.

## Dashboard

- Native HTML generation against a schema-v2 fixture: PASS (backward-compatible
  `LEARNING` quality output).
- Native HTML generation against the two live schema-v3 snapshots: PASS; four
  `QUALITY STABLE` cards with interval deltas.
- Docker image `miner-alerts-dashboard:quality-qa`: build PASS.
- Docker read-only generation against the existing fixture: PASS.

## Runtime Boundary

- `Get-Service MinerAlerts`: `Running`, `Automatic`.
- `data/miner_alerts.db` does not exist yet because the running service has not
  loaded specs 006-013.
- Telegram `/quality` runtime validation is explicitly deferred until the final
  controlled service restart; no second monitor instance was started.
