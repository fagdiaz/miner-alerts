# Quickstart: Backup Retention And Restore

**Status**: Planned validation procedure; referenced implementation files do not exist yet.

## Preconditions

- Spec 023 schema is stable.
- Backup destination is approved, writable, ignored and has adequate capacity.

## Static And Automated Validation

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_event_store_backup tests.test_event_store
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
& ".\.venv\Scripts\python.exe" -m py_compile tools\event_store_backup.py
[void][scriptblock]::Create((Get-Content tools\install_backup_task.ps1 -Raw))
```

## Controlled Runtime Validation

1. Back up a concurrently written fixture and validate it.
2. Run retention against a temporary dated generation tree.
3. Install and execute the hidden task once against production DB to the approved destination.
4. Restore that backup to staging and run integrity, schema and count checks.
5. Observe the next scheduled run and disk growth.

## Evidence To Capture

- Concurrent-write test and backup duration.
- Manifest, checksum and integrity output without real paths/data.
- Retention dry-run and actual owned-file report.
- Scheduled task action and no-window proof.
- Successful staging restore drill and compatibility report.
