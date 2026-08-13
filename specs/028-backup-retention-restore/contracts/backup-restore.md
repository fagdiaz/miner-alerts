# Contract: SQLite Backup And Staged Restore

## Purpose

Define consistent backup promotion, retention safety and non-destructive restore proof.

## Inputs

- Live SQLite path read from local config.
- Operator-selected backup root and retention/free-space parameters.

## Outputs

- Verified database plus manifest.
- Retention report.
- Staging restore validation report.

## Failure And Safety Contract

- No blind live file copy.
- No live overwrite.
- Path guards, non-overlap and free-space checks are mandatory.

## Compatibility

- Backup records schema version.
- Restore rejects unsupported newer schema until application compatibility is proven.
