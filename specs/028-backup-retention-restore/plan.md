# Implementation Plan: Backup Retention And Restore

**Branch**: `028-backup-retention-restore` | **Date**: 2026-08-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/028-backup-retention-restore/spec.md`

## Summary

Add a standalone Python backup/restore CLI using sqlite3.Connection.backup, SHA-256 manifests, non-overlap, free-space checks and daily/weekly/monthly retention. Scheduled backups run hidden; restores always target staging and require integrity/schema/count validation.

## Technical Context

**Language/Version**: Python 3.14.x and PowerShell 5.1

**Primary Dependencies**: Python standard library sqlite3, hashlib, shutil and PowerShell ScheduledTasks; no new package

**Storage**: Operator-selected ignored backup root with temp, verified, manifest and restore-staging subdirectories

**Testing**: `unittest`, deterministic fixtures, contract validation, `py_compile`, and controlled runtime evidence

**Target Platform**: Windows 10, Windows service/Scheduled Tasks, local ASIC network

**Project Type**: Standalone backup/restore CLI plus non-interactive scheduled-task installer

**Performance Goals**: Bounded incremental backup with monitor writes continuing and scheduled run under five minutes

**Constraints**: No real secrets or runtime files in Git; no unproved completion; no action authority outside the existing monitor

**Risk Classification**: HIGH - backup concurrency, retention and restore validation directly affect forensic data durability

**Scale/Scope**: Current four-miner fleet with bounded behavior for configured growth

## Constitution Check

- **Production Safety First**: PASS by design; restore never targets the live path and retention is path-guarded and lock-protected.
- **Single Source Of Truth**: PASS; local config/state stay outside Git.
- **Telegram Operational Controls**: PASS; dangerous command confirmation remains unchanged.
- **Auto-Reboot Evidence And Gates**: PASS; existing policy remains authoritative and receives regression coverage.
- **Windows Compatibility**: PASS; validation and rollout are PowerShell/service compatible.
- **Evidence-Based Completion**: PASS by plan; runtime evidence and observation remain mandatory.

## Project Structure

### Documentation

```text
specs/028-backup-retention-restore/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- integration-map.md
|-- contracts/config.md
|-- contracts/backup-restore.md
|-- checklists/requirements.md
|-- tasks.md
`-- evidence.md
```

### Planned Source Scope

```text
tools/event_store_backup.py
tools/install_backup_task.ps1
tests/test_event_store_backup.py
docs/speckit/RUNBOOK.md
.gitignore
app/config.example.json        # only safe non-secret defaults if needed
```

**Structure Decision**: Keep backup and restore outside the monitor. Reuse the SQLite library for consistency instead of copying database/WAL files at filesystem level.

## Phase 0: Research Decisions

See [research.md](research.md) and [integration-map.md](integration-map.md).
SQLite documents the backup API and VACUUM INTO as safe live-copy mechanisms.
A plain database-file copy can be inconsistent with active journal/WAL state.
Integrity checks and staged restore are mandatory evidence.

## Phase 1: Design

- Use sqlite3.Connection.backup with small page batches and bounded sleep.
- Write to a temporary destination, validate, fsync/close, hash and atomically promote with manifest.
- Apply UTC grandfather-father-son retention to the union of newest
  14-day/8-week/12-month verified owned artifacts.
- Install a pythonw.exe scheduled task with non-overlap and execution limit.
- Restore only to an empty staging path and produce a comparison report.
- Require marked roots, resolved-path containment, pre/post free-space checks
  and deterministic dry-run before retention deletion.
- Validate the disabled-by-default local settings in
  [contracts/config.md](contracts/config.md).

## Performance And Resource Design

- SQLite page batches: 256 pages with 50 ms inter-batch sleep when the source is
  busy.
- Overall CLI/task execution limit: five minutes.
- Pre-run free space: configured floor plus twice the current source size.
- Post-run free space: configured floor (1 GiB default).
- Full integrity/schema/count/hash checks precede promotion and restore pass.

## Rollback And Failure Boundary

- Disable/remove the scheduled task; the monitor and source database are unchanged.
- Failed or partial outputs remain temporary and are safe to remove manually.
- No automatic restore path exists, so rollback cannot overwrite production data.
- Retention aborts without deletion on any marker, path, manifest, hash or lock
  ambiguity.

## Post-Design Constitution Check

PASS. No unresolved constitution violation exists. Completion remains conditional on `tasks.md` evidence and the scheduled observation window.
