# Quickstart: Electrical Source Discovery

**Status**: Planned validation procedure; referenced implementation files do not exist yet.

## Preconditions

- Spec 023 fact contract is stable.
- Operator supplies actual device model/access or accepts a blocked outcome.

## Static And Automated Validation

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_electrical_telemetry tests.test_event_store
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
& ".\.venv\Scripts\python.exe" -m py_compile tools\electrical_discovery.py app\electrical_telemetry.py
Get-Content app\config.example.json -Raw | ConvertFrom-Json | Out-Null
```

## Controlled Runtime Validation

1. Inventory device model, firmware and documented telemetry.
2. Capture sanitized read-only samples or close as blocked.
3. If approved, run the adapter in shadow mode for 72 hours.
4. Compare source time, units, availability and incident windows without actions.

## Evidence To Capture

- Capability matrix and vendor documentation reference.
- Sanitized sample and unit map.
- Read-only operation scan.
- Collector load, timeout and freshness report.
- Explicit supported or blocked decision.
