# Feature Specification: Read-Only Operations Dashboard

**Feature Branch**: `011-operations-dashboard`
**Created**: 2026-07-20
**Status**: Complete

## Problem

Telegram is effective for alerts and controlled actions, but it is not suitable
for comparing fleet trends, recent incidents, and reboot decisions at a glance.
The new SQLite history contains this evidence but currently requires commands or
raw reports. The operator needs a local visual surface that cannot execute miner
actions or expose a network service.

## User Scenarios & Testing

### User Story 1 - Review Fleet Health At A Glance (Priority: P1)

As the operator, I need one local page with the latest state, hashrate, boards,
temperature, freshness, and recent trend for every miner.

**Acceptance Scenarios**:

1. A database with samples produces one ordered card per miner.
2. Each card distinguishes healthy, degraded, offline, hashboard, and stale evidence.
3. Missing optional Vnish fields display as unavailable without failing generation.

### User Story 2 - Correlate Incidents And Reboot Decisions (Priority: P1)

As the operator, I need recent incidents and automatic reboot decisions in the
same report so I can understand what happened before touching a miner.

**Acceptance Scenarios**:

1. Recent state/restart events are shown newest first.
2. Reboot blocks and outcomes include miner, reason, signal, and timestamp.
3. `fleet_incident` and `high_temperature` are visually distinguishable from executed actions.

### User Story 3 - Generate Safely And Reproducibly (Priority: P2)

As the operator, I need a deterministic command that reads SQLite without writes
and emits a portable HTML file that can be opened locally or generated in Docker.

**Acceptance Scenarios**:

1. The tool opens SQLite read-only and never loads Telegram/miner config.
2. Output is a self-contained responsive HTML document with no remote assets.
3. Missing database or incompatible schema produces a clear error instead of partial corruption.

### Edge Cases

- Empty but valid database.
- Missing optional schema-v2 telemetry columns.
- Stale latest sample.
- Null/non-finite numeric values.
- Miner names or summaries containing HTML special characters.
- Database path containing spaces on Windows.

## Requirements

- **FR-001**: The dashboard MUST be generated from the existing SQLite store in read-only mode.
- **FR-002**: It MUST show current fleet counts and one card per miner with state, rate, board count, temperature, sample age, and bounded hashrate trend when available.
- **FR-003**: It MUST show bounded recent event and reboot-decision timelines.
- **FR-004**: All database text MUST be HTML escaped.
- **FR-005**: Output MUST be self-contained and usable without JavaScript, external fonts, CDNs, or a running server.
- **FR-006**: The generator MUST NOT import or execute monitor startup, Telegram, API 4028, or Hashcore code paths.
- **FR-007**: The generator MUST NOT mutate SQLite, runtime config, state, logs, or miner devices.
- **FR-008**: Query and output sizes MUST be bounded by a configurable time window and row limits.
- **FR-009**: The primary Windows command and an optional Docker execution path MUST be documented.
- **FR-010**: Generated dashboards and databases MUST remain ignored by Git.
- **FR-011**: The running Windows service MUST not be restarted during implementation.

## Key Entities

- **Miner Card**: Latest sample plus bounded hashrate history and latest decision.
- **Fleet Summary**: Counts of miners by current condition and recent event/action totals.
- **Incident Timeline**: Recent persisted operational events.
- **Decision Timeline**: Recent automatic reboot evaluations and outcomes.

## Success Criteria

- **SC-001**: A representative SQLite fixture generates valid HTML containing all expected miner cards and timelines.
- **SC-002**: Malicious-looking text is escaped and never appears as executable markup.
- **SC-003**: The generator performs zero database writes and zero network calls.
- **SC-004**: Empty and partial-compatible databases produce a useful page or clear error deterministically.
- **SC-005**: Existing 51 monitor tests remain green and the service remains running unchanged.

## Assumptions

- The dashboard is local operational evidence, not a public web application.
- Refresh means regenerating the file; live streaming and write actions are out of scope.
- SQLite remains the source of historical truth and Telegram remains the control surface.
