# Research: Backup Retention And Restore

## Baseline Findings

- SQLite backup API creates a consistent snapshot while allowing other clients to continue between page batches.
- Blind file copies can be inconsistent when transactions or WAL/journal files exist.
- PRAGMA integrity_check validates low-level consistency but must be combined with checksum/schema/application checks.
- Current retention settings prune data inside SQLite but do not create disaster-recovery copies.

## Decisions

1. Use Python sqlite3 backup API for live snapshots.
2. Use SHA-256 manifests and atomic promotion.
3. Default retention to 14 daily, 8 weekly and 12 monthly verified backups.
4. Require staging restore and never automate production replacement.
5. Use a marked owned-root layout, resolved containment and union-based UTC GFS
   retention rather than age/glob deletion.
6. Combine Scheduled Task `IgnoreNew` with a CLI exclusive lock; ambiguity
   fails closed.
7. Require pre-run floor plus twice source size and post-run minimum-free proof.

## Rejected Or Deferred Alternatives

- Copy-Item of the live .db alone because it can omit transaction state.
- Backing up config/state because they contain secrets or ephemeral action state.
- Automatic restore on startup because corruption/mismatch could overwrite recoverable data.
- Network filesystem destination without a verified locking/durability contract.
- Retention based only on file names/mtime because unknown or partial files can
  be selected or deleted incorrectly.
- Restoring by copying directly over the live path because service/file state
  and compatibility require a separate maintenance decision.

## External Validation Sources

- SQLite online backup: https://www.sqlite.org/backup.html
- SQLite corruption-safe backup guidance: https://www.sqlite.org/howtocorrupt.html
- SQLite integrity check: https://www.sqlite.org/pragma.html#pragma_integrity_check
- Python sqlite3 backup: https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup
