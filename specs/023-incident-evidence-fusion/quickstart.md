# Quickstart: Incident Evidence Fusion

**Status**: Planned validation procedure; referenced implementation files do not exist yet.

## Preconditions

- Spec 022 provides sample authority, quality and timestamps.
- Spec 020 incident references are production-verified.
- Spec 021 and Spec 022 exit gates are recorded; no production-affecting
  rollout overlaps this validation.
- `incident_fusion_enabled` remains `false` for red-contract and replay work.

## Static And Automated Validation

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_evidence_fusion tests.test_event_store tests.test_stability_profile tests.test_mining_quality
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
& ".\.venv\Scripts\python.exe" -m py_compile app\evidence_fusion.py app\event_store.py app\miner_monitor.py tools\operations_dashboard.py
```

## Required Replay Matrix

| Fixture | Required result |
| --- | --- |
| Same rows/window/ruleset twice | Identical semantic JSON and evidence digest |
| LOW near firmware warning, unparsed clock | Observed facts; cause no higher than suspected |
| Two miners irregular inside 60 seconds, no external power | Fleet pattern observed; electrical unconfirmed |
| Successful recorded action plus uptime reset in attribution window | Action attribution may be confirmed |
| Newer valid OK contradicts older LOW | Contradiction visible; current LOW not confirmed |
| Collector partial/failed | Firmware source missing/incomplete, never healthy by absence |
| Unknown source code | Visible/ignored safely; no confidence promotion |
| Fusion disabled or query budget exceeded | Existing diagnosis fallback |

## Controlled Runtime Validation

1. Replay sanitized isolated, fleet, board, thermal and unknown incidents.
2. Compare output with raw event, diagnosis and dashboard evidence.
3. Prove no state, streak, decision, alert or Hashcore difference with fusion
   enabled in deterministic tests.
4. Measure query count and elapsed time for the bounded 24-hour/current-fleet
   path.
5. Activate read-only detail and inspect D+0/D+1/D+3 for unsupported claims.

## Evidence To Capture

- Ruleset and fixture versions.
- Targeted/full tests and migration results.
- Sanitized before/after assessments.
- Query latency and database growth.
- Disabled-fallback and action-invariant proof.
- D+0/D+1/D+3 confidence-wording review.
