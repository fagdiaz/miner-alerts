# Quickstart: Incident Evidence Fusion

**Status**: Planned validation procedure; referenced implementation files do not exist yet.

## Preconditions

- Spec 022 provides sample authority, quality and timestamps.
- Spec 020 incident references are production-verified.

## Static And Automated Validation

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_evidence_fusion tests.test_event_store tests.test_stability_profile tests.test_mining_quality
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
& ".\.venv\Scripts\python.exe" -m py_compile app\evidence_fusion.py app\event_store.py app\miner_monitor.py tools\operations_dashboard.py
```

## Controlled Runtime Validation

1. Replay sanitized isolated, fleet, board, thermal and unknown incidents.
2. Compare output with raw event, diagnosis and dashboard evidence.
3. Activate read-only detail and inspect D+1/D+3 for unsupported claims.

## Evidence To Capture

- Ruleset and fixture versions.
- Targeted/full tests and migration results.
- Sanitized before/after assessments.
- Query latency and database growth.
- D+1/D+3 confidence-wording review.
