# Feature Specification: Backup Retention And Restore

**Feature Branch**: `028-backup-retention-restore`

**Created**: 2026-08-13

**Status**: Planned; not implemented

**Input**: Create consistent SQLite backups with manifests and retention, verify integrity, rehearse restoration to staging, and never overwrite live production data automatically.

**Risk Class**: HIGH

**Dependencies**: Stable EventStore schema after Spec 023 and an operator-approved backup destination outside Git

## User Scenarios & Testing

### User Story 1 - Create a trustworthy live backup (Priority: P1)

The operator obtains a consistent database snapshot while monitoring continues.

**Why this priority**: Blind copying a live SQLite file can miss WAL/journal state and create unusable backups.

**Independent Test**: Write concurrently to a fixture database while using the SQLite backup interface and validate the result.

**Acceptance Scenarios**:

1. **Given** the live database is active, **When** a scheduled backup runs, **Then** a consistent destination plus manifest is produced
2. **Given** backup fails, **When** the task exits, **Then** the incomplete output is not promoted and the failure is logged

---

### User Story 2 - Control storage growth (Priority: P1)

Daily, weekly and monthly retention keeps verified recovery points without unbounded disk use.

**Why this priority**: A backup process that fills the host creates a new production failure.

**Independent Test**: Apply retention to dated fixtures and verify protected generations and disk thresholds.

**Acceptance Scenarios**:

1. **Given** old verified backups exceed policy, **When** retention runs, **Then** only eligible generations are removed
2. **Given** free space is below the safety floor, **When** backup begins, **Then** it aborts safely and records the condition

---

### User Story 3 - Prove restoration safely (Priority: P1)

A backup is restored to a staging path, integrity-checked and compared without replacing the live database.

**Why this priority**: A backup is not useful until restoration is rehearsed.

**Independent Test**: Restore a selected backup into an isolated temporary directory and validate schema, integrity and key row counts.

**Acceptance Scenarios**:

1. **Given** a verified backup is selected, **When** restore drill runs, **Then** staging database passes integrity and compatibility checks
2. **Given** a checksum or schema check fails, **When** restore drill runs, **Then** it fails closed and leaves live data untouched

### Edge Cases

- The source uses WAL during backup.
- Disk becomes full mid-backup.
- A backup filename exists.
- Manifest exists but database is missing or altered.
- The restored schema is newer than the current application.
- Retention runs while another backup is active.

## Requirements

### Functional Requirements

- **FR-001**: Live database backup MUST use the SQLite online backup interface or VACUUM INTO, never an uncoordinated file copy.
- **FR-002**: Each completed backup MUST have an immutable manifest with source schema version, size, SHA-256, created time and tool version.
- **FR-003**: Incomplete backups MUST use temporary names and MUST NOT be considered restore candidates.
- **FR-004**: Backup destination MUST be outside Git and MUST NOT contain app/config.json, state.json, tokens or credentials.
- **FR-005**: Retention MUST preserve 14 daily, 8 weekly and 12 monthly verified generations by default.
- **FR-006**: Retention MUST delete only files owned by the backup layout and MUST respect a non-overlap lock.
- **FR-007**: Backup MUST check a configurable minimum free-space floor before and after creation.
- **FR-008**: Restore MUST target a new staging directory and MUST NOT overwrite the live database automatically.
- **FR-009**: Restore validation MUST include SHA-256, PRAGMA integrity_check, schema version and bounded key-table counts.
- **FR-010**: A scheduled task MUST run non-interactively with a bounded duration and visible logs.
- **FR-011**: At least one restore drill MUST pass before the spec can complete.

### Key Entities

- **BackupArtifact**: Consistent SQLite snapshot promoted only after validation.
- **BackupManifest**: Hash, size, schema, timestamp and tool identity.
- **RetentionGeneration**: Daily, weekly or monthly protected recovery point.
- **RestoreDrill**: Staging restore result and compatibility evidence.
- **BackupRun**: Start/end, source, destination, result and reason.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Concurrent-write fixture backups pass integrity and expected row checks.
- **SC-002**: Every promoted backup has a matching SHA-256 manifest.
- **SC-003**: Retention never deletes outside its owned directory and respects 14/8/12 generations.
- **SC-004**: A staging restore drill passes without stopping or altering the live monitor database.
- **SC-005**: Scheduled backup failure is visible and cannot promote a partial file.

## Assumptions

- An operator chooses a local or attached backup destination with adequate free space.
- SQLite EventStore remains the only canonical database in this release.
- Disaster replacement of the live database remains a manual runbook procedure.

## Non-Goals

- Cloud backup provider integration.
- Automatic live database overwrite or failover.
- Backing up app/config.json secrets or state.json.
- Database replication or high availability.
