# Data Model: Backup Retention And Restore

## BackupArtifact

- `backup_id`: UTC timestamp plus eight random hexadecimal characters.
- `database_path`: Relative artifact path only.
- `created_ts`: Snapshot completion.
- `size_bytes / sha256`: Integrity identity.
- `schema_version`: Compatibility.
- `status`: verified; non-promoted temporary/failed outputs are not artifacts.

## BackupManifest

- `manifest_version`: Format compatibility.
- `tool_version`: Producer.
- `source_fingerprint`: Secret-free source identity.
- `table_counts`: Bounded key-table verification counts.
- `integrity_result`: SQLite check result.
- `page_size / page_count`: Bounded database shape.
- `retention`: Policy values applied by the run.

## BackupRun

- `run_id / started_ts / completed_ts / duration_seconds`.
- `result`: verified, failed, skipped_locked, blocked_space or blocked_path.
- `backup_id`: only when promotion succeeds.
- `free_bytes_before / free_bytes_after`: Capacity evidence.
- `reason_code`: Stable sanitized result without exception payload/path.

## RetentionGeneration

- `backup_id / created_utc`.
- `daily_bucket / iso_week_bucket / monthly_bucket`.
- `protected_by`: One or more of daily, weekly, monthly.
- `candidate_action`: keep or delete.

## RestoreDrill

- `backup_id`: Selected source.
- `staging_path`: New isolated destination.
- `checksum_ok / integrity_ok / schema_ok`: Validation gates.
- `count_comparison`: Expected table evidence.
- `result / completed_ts`: Pass or failure.

## Invariants

- Only verified artifacts enter retention generations.
- Retention cannot resolve outside the backup root.
- Retention selects only valid manifest/hash pairs under a marked verified root.
- Restore destination cannot equal or contain the live database path.
- Backup/staging/repository/source roots cannot overlap in either direction.
- No artifact includes config/state secrets.
