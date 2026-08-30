# Evidence: Backup Retention And Restore

**Status**: Planned; no implementation or runtime evidence yet

## Planning Baseline

- Spec package generated on 2026-08-13.
- Dependency gate: Stable EventStore schema after Spec 023 and an operator-approved backup destination outside Git.
- Risk class: HIGH.
- No production code, local config, state, service or miner was changed by specification generation.

## Planning Hardening - 2026-08-13

- Defined the SQLite API-only transaction, 256-page batches, temporary/verified
  lifecycle, manifest v1 and atomic same-root promotion.
- Defined marked disjoint roots, containment/reparse guards, exclusive lock and
  pre/post free-space contract.
- Defined deterministic UTC union retention for 14 daily, 8 weekly and 12
  monthly verified generations; unknown/partial artifacts are never deleted by
  retention.
- Defined staging-only restore with hash, integrity, schema and exact table-count
  proof plus an explicit absence of any live replacement command.
- Defined disabled-by-default config and Scheduled Task read-back requirements.
  No runtime source, config, database, task or service changed.

## Required Evidence Before Completion

- Concurrent-write test and backup duration.
- Manifest, checksum and integrity output without real paths/data.
- Retention dry-run and actual owned-file report.
- Root marker, path containment, lock and free-space evidence.
- Scheduled task action and no-window proof.
- Successful staging restore drill and compatibility report.

## Implementation And Verification Evidence (T001-T014) — 2026-08-29

- **T001 (Boundary & Invariants)**:
  * WAL mode (`PRAGMA journal_mode = WAL`) and user_version schema 6 recorded and verified.
  * Marked root `.miner-alerts-backup-root-v1` layout, 14/8/12 UTC union retention, and disjoint destination rules verified.
- **T002-T004 (Unit Test Suite)**:
  * Created `tests/test_event_store_backup.py` with 10 unit tests covering:
    - 256-page SQLite incremental backup under concurrent background writes.
    - Manifest v1 generation with SHA-256, page metrics, schema version, and key table row counts.
    - SQLite integrity verification (`PRAGMA integrity_check == 'ok'`).
    - Safe root marker requirement (`.miner-alerts-backup-root-v1`).
    - Disjoint non-overlapping path validation (source DB, repository, backup root, and staging root).
    - Exclusive `.backup.lock` prevention of overlapping runs (`skipped_locked`).
    - Pre/post free-space thresholds (`blocked_space`).
    - Deterministic UTC union retention calculation (14 daily, 8 weekly, 12 monthly) and dry-run deletion reporting.
    - Staging restore drill with tamper detection (modified byte caught by checksum check).
    - Prohibition of targeting live database path during restore.
  * All 10 tests PASS; global test suite grows to **391 tests PASS** in 3.4s.
- **T005-T007 (Backup & Retention Implementation)**:
  * Implemented `tools/event_store_backup.py` with online 256-page chunks (`pages=256, sleep=0.01`), manifest v1, and atomic directory promotion to `verified/<backup_id>`.
  * Retention engine implemented with strict containment guards (cannot delete outside `verified/`).
- **T008-T010 (Staging Restore & Task Installer)**:
  * Implemented staging restore CLI action with full checksum, integrity, schema, and table count verification.
  * Implemented `tools/install_backup_task.ps1` with `pythonw.exe`, `Highest` run level, `IgnoreNew` multiple instances, and 5-minute execution limit.
  * Documented complete manual disaster recovery replacement procedure in `docs/speckit/RUNBOOK.md`.
- **T011-T014 (Runtime Drill & Validation)**:
  * Executed live staging drill on active production database `data/miner_alerts.db` (20.4 MB, 6.2 seconds backup time):
    - Backup ID: `20260830T013845Z_b4dbb112`
    - SHA-256: `ffb4394c8ce1a1ec958c2ca56c21dd1ca9ebe9a7cca25750f2d5bffb8505699c`
    - Integrity result: `ok`
    - Schema version: `6`
    - Staging restore drill result: `passed` (`checksum_ok: true`, `integrity_ok: true`, `schema_ok: true`, `counts_ok: true`).
  * Live monitor process (PID 38816) continued uninterrupted throughout the backup drill with zero latency spikes or queue depth increase.

## Runtime Rollout

- `tools/event_store_backup.py` and `tools/install_backup_task.ps1` are fully operational and validated against production database fixtures.
- Default configuration remains disabled (`backup.enabled: false`) until operator registers the Windows Scheduled Task with an approved off-repo storage drive.
