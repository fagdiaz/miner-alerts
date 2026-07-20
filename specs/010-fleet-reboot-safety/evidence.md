# Evidence: Fleet-Aware Auto-Reboot Safety

**Status**: Implementation and local validation complete  
**Service activation**: Deferred to the controlled end-of-day restart.

## Baseline

- Existing order: current valid LOW -> startup guard -> sustained LOW -> cooldown -> window -> QA -> Hashcore.
- Vnish telemetry is already parsed from the same `stats` response; no new IO is required.
- SQLite decision records already support arbitrary result strings and structured details.

## Validation

### Test-First Evidence

The targeted suite initially failed with `ModuleNotFoundError` for
`app.reboot_safety`, proving the new contract was not satisfied by pre-existing
code. After implementation:

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_reboot_safety tests.test_event_store -v
```

Result: PASS, 19 targeted tests.

### Syntax And Full Suite

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py app\reboot_safety.py app\event_store.py app\vnish_telemetry.py tools\incident_report.py
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -v
```

Result: PASS, 51 tests. Coverage proves:

- one LOW candidate with healthy peers remains eligible for existing gates;
- two affected miners block with `fleet_incident`;
- missing or older-than-60s completed fleet evidence is ignored;
- a temperature at the 85 C limit blocks with `high_temperature`;
- missing, malformed, NaN, or infinite temperature does not fabricate a block;
- disabling either interlock preserves previous eligibility;
- interlocks are applied after startup/sustained LOW and before cooldown/window/QA/Hashcore;
- `/why` renders affected miners, snapshot age, observed temperature, and limit.

### Sanitized Production Baseline

The latest read-only diagnostics snapshot reports four miners with 3/3 boards,
92.851-101.265 TH/s, and maximum observed temperatures of 72-81 C. None reaches
the default 85 C thermal block. No live miner call was added or executed by this
spec.

### Repository And QA

- Pre-implementation Speckit HIGH-risk preflight with builds: PASS.
- Post-implementation Speckit HIGH-risk preflight with builds: PASS.
- `git diff --check`: PASS; only expected CRLF conversion warnings were emitted.
- `app/config.json` and `app/state.json`: untouched.

## Safety Comparison

- State transitions and hysteresis are unchanged.
- Existing action order is preserved with two no-action gates inserted between
  sustained LOW and cooldown.
- Manual Telegram reboot/restart/confirm is unchanged.
- Polling offset, network requests, Hashcore arguments, and persistence fields are unchanged.
- Fleet evidence expires after `max(60, poll_seconds * 2)` and cannot block indefinitely.

## Runtime

`MinerAlerts` remains running on the pre-change process. No service restart or
second monitor process was attempted.
