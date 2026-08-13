# Quickstart: V2 Release Stabilization

**Status**: Planned validation procedure; it applies only after prerequisite packages are evidence-closed.

## Preconditions

- Every earlier spec has a final status and evidence.
- No active P0/P1 production incident and an elevated maintenance window exists.

## Static And Automated Validation

```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
& ".\.venv\Scripts\python.exe" -m py_compile app\*.py tools\*.py
Get-Content app\config.example.json -Raw | ConvertFrom-Json | Out-Null
git diff --check
git status --short
```

## Controlled Runtime Validation

1. Record candidate, service, schema, dependency and rollback identities.
2. Run QA command/action, persisted-state startup, liveness, acquisition and auxiliary outage scenarios.
3. Create backup and complete staging restore drill.
4. Restart service once, verify new PID/startup/worker/database logs and read-only commands.
5. Complete 72-hour soak and final seven-day reliability review.
6. Execute final three documentation and secret-hygiene sweeps.

## Evidence To Capture

- Full regression matrix with exact commands.
- Core invariant and QA no-action proof.
- Service activation, PID, mutex, config source, guard and worker logs.
- Backup/restore manifest and report.
- 72-hour and seven-day issue/metric summary.
- Documentation/link/status/date/secret audit and release decision.
