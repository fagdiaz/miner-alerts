# Data Model: Backup Retention And Restore

## BackupArtifact

- `backup_id`: Timestamp plus random/sequence identity.
- `database_path`: Relative artifact path only.
- `created_ts`: Snapshot completion.
- `size_bytes / sha256`: Integrity identity.
- `schema_version`: Compatibility.
- `status`: temporary, verified or failed.

## BackupManifest

- `manifest_version`: Format compatibility.
- `tool_version`: Producer.
- `source_fingerprint`: Secret-free source identity.
- `table_counts`: Bounded key-table verification counts.
- `integrity_result`: SQLite check result.

## RestoreDrill

- `backup_id`: Selected source.
- `staging_path`: New isolated destination.
- `checksum_ok / integrity_ok / schema_ok`: Validation gates.
- `count_comparison`: Expected table evidence.
- `result / completed_ts`: Pass or failure.

## Invariants

- Only verified artifacts enter retention generations.
- Retention cannot resolve outside the backup root.
- Restore destination cannot equal or contain the live database path.
- No artifact includes config/state secrets.
