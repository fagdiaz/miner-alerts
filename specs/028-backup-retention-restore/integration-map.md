# Integration Map: Backup, Retention And Staged Restore

## Purpose

Define the exact offline tool boundary, artifact lifecycle and Windows task
behavior before any production database backup is attempted.

## Source Boundary

- The source database path is resolved from local `app/config.json` using the
  same repository-relative policy as EventStore.
- The tool opens the source through SQLite and uses
  `sqlite3.Connection.backup`; it never copies the live `.db`, `-wal` or `-shm`
  files with filesystem commands.
- The monitor remains the only writer and does not import or call the backup
  tool.
- Backup excludes `app/config.json`, `app/state.json`, locks, logs, Telegram
  credentials, miner credentials and Hashcore configuration.

## Planned Files

| File | Responsibility | Prohibited responsibility |
| --- | --- | --- |
| `tools/event_store_backup.py` | backup, manifest, retention dry-run/apply and staging restore CLI | no service stop/start, no live overwrite |
| `tools/install_backup_task.ps1` | validated hidden SYSTEM task with non-overlap and bounded execution | no credential embedding, no visible window |
| `tests/test_event_store_backup.py` | concurrent writes, path guards, retention and restore fixtures | no production DB mutation |
| `docs/speckit/RUNBOOK.md` | operator backup/restore/rollback steps | no secret or real destination in Git |

## Owned Layout

```text
<backup_root>/
|-- .miner-alerts-backup-root-v1
|-- .backup.lock
|-- temporary/
|   `-- .tmp-<backup_id>/
|       `-- miner_alerts.db.partial
|-- verified/
|   `-- <backup_id>/
|       |-- miner_alerts.db
|       `-- manifest.json
|-- reports/
|   `-- <run_id>.json
`-- quarantine/
    `-- <failed_or_stale_name>/

<staging_root>/
`-- <backup_id>-<restore_run_id>/
    |-- miner_alerts.db
    `-- restore-report.json
```

The root marker is mandatory before retention deletes anything. The backup and
staging roots must resolve outside the repository and outside each other. The
live database path cannot equal, contain or be contained by either root.

## Backup Transaction

1. Parse and validate local config and CLI mode.
2. Resolve source/root paths and enforce containment/non-overlap guards.
3. Acquire an exclusive root lock; a concurrent run exits without mutation.
4. Check source existence/schema and pre-run free-space budget.
5. Create a same-root temporary directory and destination SQLite connection.
6. Run `source_connection.backup(destination, pages=256, sleep=0.05)` with an
   overall five-minute deadline enforced by the outer process/task.
7. Close both connections and run full `PRAGMA integrity_check` on the temporary
   destination.
8. Read schema version and exact bounded key-table counts.
9. Compute database size and SHA-256 after close.
10. Write/flush the versioned manifest, then atomically promote the directory
    inside the same volume to `verified/<backup_id>`.
11. Recheck free-space floor, write a sanitized run report, then run retention.
12. Release the lock in `finally`.

Any failure before atomic promotion leaves no restore candidate. Temporary
artifacts are quarantined or reported and are never treated as verified.

## Free-Space Contract

Before backup:

```text
free_bytes >= minimum_free_bytes + (2 * current_source_size_bytes)
```

After promotion and retention:

```text
free_bytes >= minimum_free_bytes
```

The default minimum floor is 1 GiB. Failure is explicit and does not delete an
existing verified generation merely to make the current run pass.

## Retention Algorithm

Retention considers only directories under `verified/` that contain both a
valid manifest and matching database hash. All calendar buckets use UTC:

- daily: newest verified backup in each of the newest 14 distinct UTC dates;
- weekly: newest verified backup in each of the newest 8 distinct ISO weeks;
- monthly: newest verified backup in each of the newest 12 distinct UTC months.

The protected set is the union of all three selections. An artifact may satisfy
multiple buckets. Candidates outside the union are deleted only after a dry-run
plan proves every path resolves below the marked `verified/` root. Temporary,
report, staging and unknown files are never selected by retention.

## Manifest And Identity

The manifest includes only sanitized metadata:

- `manifest_version`, `tool_version`, `backup_id`, `method`;
- UTC start/completion time and duration;
- source schema version and logical source kind (`event_store`), not full path;
- backup file name, size, SHA-256, page size/count;
- `integrity_result` and bounded key-table counts;
- retention policy values used by the run.

`backup_id` is UTC `YYYYMMDDTHHMMSSZ` plus eight random hexadecimal characters.
It is not derived from a local path, miner identity or secret.

## Staging Restore Drill

1. Select a verified artifact by exact backup ID.
2. Revalidate root marker, manifest schema, size and SHA-256.
3. Require a new non-existent staging destination below the configured staging
   root and outside the live/source/backup roots.
4. Copy the closed verified database into that new staging directory.
5. Open the staging copy, run full integrity check, schema compatibility and
   exact key-table count comparison with the manifest.
6. Write a sanitized restore report and close all handles.

There is no command, switch or scheduled path that replaces the live database.
Disaster replacement remains a separate manual maintenance procedure requiring
service stop, independent backup and explicit operator verification.

## Windows Scheduled Task

- `pythonw.exe`, SYSTEM, Highest, hidden, daily local schedule.
- `IgnoreNew`, `StartWhenAvailable`, execution limit five minutes.
- Exact executable, arguments, principal, settings and next-run time are read
  back after registration before success is reported.
- The CLI/root lock is a second non-overlap guard.
- Task failure remains visible in Task Scheduler history and sanitized run
  reports; it never restarts the monitor.

## Activation And Rollback

1. Implement against temporary concurrent-write fixtures.
2. Validate retention only under temporary marked roots.
3. Run one manual production backup to the approved off-repo root.
4. Complete a staging restore drill from that exact artifact.
5. Install the scheduled task only after the drill passes.
6. Observe the next scheduled run and free-space/monitor latency.
7. Roll back by disabling/removing the task; verified backups remain immutable
   and the live database is unchanged.
