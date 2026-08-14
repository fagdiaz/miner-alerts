# Quickstart: V2 Release Stabilization

**Status**: Planned validation procedure; it applies only after prerequisite packages are evidence-closed.

## Preconditions

- Every earlier spec has a final status and evidence.
- No active P0/P1 production incident and an elevated maintenance window exists.
- `planned`, `in_progress`, `observation_pending` or generic blocked dependencies
  stop the release before freeze.

## Static And Automated Validation

```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
& ".\.venv\Scripts\python.exe" -m py_compile app\*.py tools\*.py
Get-Content app\config.example.json -Raw | ConvertFrom-Json | Out-Null
git diff --check
git status --short
```

The implementation must additionally generate the deterministic runtime-payload
digest and validate complete R001-R025 rows. Do not substitute `git log`, a clean
status or one aggregate test count for the release manifest.

## Controlled Runtime Validation

1. Record candidate, runtime payload, terminal dependencies, service/task,
   schema/dependency and rollback identities.
2. Run R001-R021 static, QA, action-block, startup, liveness, acquisition and
   accepted/blocked boundary checks.
3. Create backup, complete staging restore and rehearse safe runtime rollback.
4. Activate once, verify R022 identity and R023 read-only/auxiliary isolation.
5. Capture seven continuous daily reports; close R024 after 72 hours and R025
   only after at least 168 hours on the same runtime payload.
6. Execute final three documentation/secret sweeps and generate binary decision.

## Evidence To Capture

- Full regression matrix with exact commands.
- Core invariant and QA no-action proof.
- Service activation, PID, mutex, config source, guard and worker logs.
- Backup/restore manifest and report.
- 72-hour and seven-day issue/metric summary.
- Seven daily observation reports with one unchanged runtime-payload digest.
- Documentation/link/status/date/secret audit and release decision.
