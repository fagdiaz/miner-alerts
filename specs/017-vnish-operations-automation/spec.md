# Feature Specification: Vnish Operations Automation

**Feature Branch**: `codex/017-vnish-operations-automation`

**Created**: 2026-07-20

**Status**: Complete

## Goal

Operationalize Vnish intelligence without adding a permanent worker to the
monitor: retain the newest bounded events, audit collector health, install an
isolated non-overlapping Windows scheduled task, and expose a SQLite-only
`/diagnose` view that combines current telemetry and recent evidence without
authorizing actions.

## User Stories

### US1 - Retain recent firmware evidence

As an operator, I need bounded parsing to retain the newest recognized events,
not the oldest portion of a replayed Vnish buffer.

Acceptance:

1. Line and event limits select the tail while preserving chronological order.
2. Source timestamps are parsed using an explicit clock basis and old replayed
   history cannot masquerade as current evidence.
3. Unknown lines and raw text remain unpersisted.

### US2 - Automate collection safely

As an operator, I need a separate scheduled collection process whose freshness,
successes, failures, truncation and dedupe counts are durable and inspectable.

Acceptance:

1. Every persisted invocation records one bounded collector-run summary.
2. A PowerShell installer creates a current-user scheduled task with
   `IgnoreNew`, bounded one-shot execution and no retries.
3. The task can be inspected with `-WhatIf` before registration.
4. The monitor does not import the WebSocket client or launch the collector.

### US3 - Diagnose without acting

As an operator, I need `/diagnose`, `/diagnose all` and `/diagnose <miner>` to
combine the latest SQLite sample, recent state event, reboot decision, fresh
firmware evidence and collector freshness in one bounded reply.

Acceptance:

1. The command is SQLite-only and always uses command delivery semantics.
2. Firmware evidence is called current only when its parsed source timestamp is
   within the configured diagnostic window.
3. Missing/stale telemetry and stale/missing collection are explicit.
4. The command never calls API 4028, WebSocket, Hashcore or an action function.

## Requirements

- **FR-001**: Parser caps MUST retain newest recognized events in chronological order.
- **FR-002**: Firmware rows MUST carry nullable parsed source epoch plus clock provenance.
- **FR-003**: Schema migration MUST preserve schema-v1 through schema-v4 data.
- **FR-004**: Collector summaries MUST exclude raw firmware content and secrets.
- **FR-005**: Scheduling MUST be separate, current-user scoped, one-shot and non-overlapping.
- **FR-006**: `/diagnose` MUST query SQLite only and produce bounded evidence.
- **FR-007**: No new evidence may trigger state or reboot/restart actions.
- **FR-008**: Existing monitor, Telegram, startup guard and auto-reboot tests MUST pass.

## Success Criteria

- **SC-001**: Tail tests prove the newest event survives both line and event caps.
- **SC-002**: Recollection updates timestamp metadata without duplicate event rows.
- **SC-003**: Collector-run health is available after success, partial failure and dry-run.
- **SC-004**: `/diagnose` excludes old replayed firmware events from current evidence.
- **SC-005**: Full tests, compilation, scheduling dry-run and live read-only smoke pass.

## Non-Goals

- No automatic interpretation of firmware logs as reboot permission.
- No permanent WebSocket thread in the monitor.
- No web action surface, message broker, retry daemon or external database.
