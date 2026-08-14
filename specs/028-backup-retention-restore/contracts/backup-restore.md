# Contract: SQLite Backup And Staged Restore

## Backup Result States

- `verified`: SQLite backup completed, integrity/schema/count checks passed,
  file closed, hash/manifest written and directory atomically promoted.
- `failed`: run ended before promotion; no restore candidate exists.
- `skipped_locked`: another run owns the exclusive lock.
- `blocked_space`: pre/post free-space contract failed.
- `blocked_path`: root/source/staging containment contract failed.

Only `verified` artifacts participate in retention or restore.

## Manifest V1

```text
manifest_version: 1
tool_version
backup_id
method: sqlite_connection_backup
started_ts / completed_ts / duration_seconds
source_kind: event_store
source_schema_version
database_file: miner_alerts.db
size_bytes / sha256
page_size / page_count
integrity_result: ok
table_counts: finite allowlisted map
retention: daily=14, weekly=8, monthly=12
```

No absolute path, config value, address, credential, state payload or source row
is stored in the manifest.

## Key-Table Count Allowlist

The manifest and restore drill compare only known durable tables present in the
source schema, including:

- `telemetry_samples`;
- `operational_events`;
- `reboot_decisions`;
- `firmware_events`;
- `collector_runs`;
- additive assessment tables introduced by Spec 023 when present.

Unknown future tables do not silently disappear: schema compatibility must be
reviewed before restore approval.

## Path Safety

- Backup root requires `.miner-alerts-backup-root-v1`.
- Every mutation uses resolved absolute paths and verifies containment beneath
  an owned subdirectory.
- Source DB, repository, backup root and staging root cannot overlap.
- Symlink/reparse traversal outside the owned root is rejected.
- Retention never accepts arbitrary glob/path input from a manifest.
- Restore destination must not exist and cannot be the live database path.

## Retention

- Select newest per distinct UTC day/week/month.
- Protect the union of 14 daily, 8 weekly and 12 monthly generations.
- Validate manifest/hash before selection.
- Produce a deterministic dry-run list before deletion.
- Delete only verified artifact directories that are not protected and remain
  below the marked root.
- If any candidate fails validation or containment, fail the retention run
  without deleting candidates.

## Restore Approval

A staging drill passes only when all are true:

- manifest version supported;
- database size and SHA-256 match;
- `PRAGMA integrity_check` returns exactly `ok`;
- schema version is supported by the current code;
- every allowlisted table count matches the manifest;
- destination is a new path outside production.

The report is evidence of recoverability, not authorization to replace the live
database.

## Failure And Safety Contract

- No blind live file copy.
- No config/state/secret backup.
- No automatic live restore or service control.
- No deletion outside a marked owned root.
- No overlapping runs.
- Any ambiguous path, schema, lock, hash or integrity result fails closed.
