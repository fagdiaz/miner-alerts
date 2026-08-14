# Quickstart: Backup Retention And Restore

**Status**: Planned validation procedure; referenced implementation files do not exist yet.

## Preconditions

- Spec 023 schema is stable.
- Backup destination is approved, writable, ignored and has adequate capacity.
- Backup and staging roots are absolute, off-repo, disjoint and contain no live
  database/config/state path.
- `backup.enabled` remains false until the manual backup and restore drill pass.

## Static And Automated Validation

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_event_store_backup tests.test_event_store
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
& ".\.venv\Scripts\python.exe" -m py_compile tools\event_store_backup.py
[void][scriptblock]::Create((Get-Content tools\install_backup_task.ps1 -Raw))
```

## Controlled Runtime Validation

1. Back up a concurrently written fixture and validate it.
2. Run retention dry-run/apply against a temporary marked tree with daily,
   weekly, monthly, unknown, malformed and path-escape fixtures.
3. Prove pre/post free-space, lock and five-minute failure paths.
4. Execute one manual production DB backup to the approved destination.
5. Restore that exact artifact to a new staging directory and verify hash,
   integrity, schema and allowlisted counts.
6. Install/read back the hidden task only after the drill passes.
7. Observe the next scheduled run and disk growth.

## Evidence To Capture

- Concurrent-write test and backup duration.
- Manifest, checksum and integrity output without real paths/data.
- Retention dry-run and actual owned-file report.
- Root marker, path containment, lock and free-space evidence.
- Scheduled task action and no-window proof.
- Successful staging restore drill and compatibility report.
