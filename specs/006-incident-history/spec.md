# Feature Specification: Incident History And Restart Intelligence

**Feature Branch**: `006-incident-history`

**Created**: 2026-07-20

**Status**: Implemented; Windows service activation pending elevated restart

**Input**: User description: "Persist operational history, detect and explain unwanted miner restarts, improve Telegram evidence, and establish a database foundation without changing monitoring or reboot policy."

## User Scenarios & Testing

### User Story 1 - Detect Unexpected Restarts (Priority: P1)

As the operator, I want a specific alert when a miner restarts without a recent
manual or automatic action, so I can distinguish an unwanted restart from a
normal state transition and investigate it immediately.

**Why this priority**: A generic LOW/OK transition does not explain whether the
miner process or device restarted. Missing that distinction hides production
incidents and can lead to unnecessary follow-up reboots.

**Independent Test**: Feed a sequence where miner uptime drops from a stable
value to a startup value without a recent recorded action. The system records
one unexpected-restart incident and produces one evidence-rich alert without
executing any action.

**Acceptance Scenarios**:

1. **Given** a miner with stable uptime and no recent reboot/restart action, **When** its reported uptime resets, **Then** an `unexpected` restart incident is recorded and Telegram identifies the miner, uptime evidence, current signal, and incident identifier.
2. **Given** a miner with a recent successful manual action, **When** its uptime resets inside the attribution window, **Then** the incident is classified as an expected manual restart rather than unexpected.
3. **Given** a miner with a recent successful auto-reboot, **When** its uptime resets inside the attribution window, **Then** the incident is classified as an expected automatic restart.
4. **Given** an incident is recorded, **When** the monitor evaluates auto-reboot policy, **Then** the database record does not add, remove, or bypass any existing action gate.

---

### User Story 2 - Preserve Operational Evidence (Priority: P1)

As the operator, I want miner samples and meaningful events preserved across
service restarts, so I can reconstruct what happened before an alert or reboot.

**Why this priority**: The current JSON state is optimized for runtime continuity,
not incident analysis. Durable evidence is required to correlate symptoms over
time and reduce false conclusions.

**Independent Test**: Record telemetry and events, close and reopen storage, and
verify the same records remain queryable while runtime state behavior is unchanged.

**Acceptance Scenarios**:

1. **Given** the event store is enabled, **When** the monitor receives normal samples, **Then** it retains bounded snapshots at the configured interval rather than every polling tick.
2. **Given** a state transition, restart detection, or reboot action result, **When** it occurs, **Then** a normalized event is stored with timestamp, miner identity, signal evidence, and classification data.
3. **Given** the process restarts, **When** storage initializes again, **Then** previous history remains readable.
4. **Given** storage is unavailable or corrupt, **When** a write fails, **Then** monitoring continues and an actionable error is logged without executing a reboot.

---

### User Story 3 - Query Incidents From Telegram (Priority: P2)

As the operator, I want to inspect recent events and one incident from Telegram,
so I can diagnose a restart from my phone without opening runtime files.

**Why this priority**: Telegram is the current operational interface and provides
the shortest path from alert to evidence.

**Independent Test**: Populate local event history and verify `/events`,
`/events <miner>`, and `/event <id>` return deterministic read-only responses.

**Acceptance Scenarios**:

1. **Given** stored events exist, **When** `/events` is sent, **Then** the bot returns a compact newest-first list with incident identifiers.
2. **Given** a valid miner token, **When** `/events <miner>` is sent, **Then** only matching miner events are returned.
3. **Given** a valid event identifier, **When** `/event <id>` is sent, **Then** the bot returns evidence and classification for that event.
4. **Given** storage is disabled, an identifier is invalid, or no records match, **When** a history command is sent, **Then** the bot always replies clearly and performs no miner I/O.

---

### User Story 4 - Control Retention And Operations (Priority: P3)

As the operator, I want bounded retention and visible storage health, so the
history remains useful without growing indefinitely or silently failing.

**Why this priority**: Long-running Windows services need predictable local disk
usage and clear evidence when persistence is unavailable.

**Independent Test**: Insert records older than configured retention, run cleanup,
and verify only expired records are removed and current records remain.

**Acceptance Scenarios**:

1. **Given** records older than retention, **When** scheduled cleanup runs, **Then** expired samples and events are removed using their independent retention limits.
2. **Given** storage initializes, **When** the service starts, **Then** logs identify whether the event store is enabled and its absolute path without exposing secrets.
3. **Given** the event store is disabled by configuration, **When** the monitor runs, **Then** existing monitoring and Telegram commands continue except history commands report storage unavailable.

### Edge Cases

- Uptime is missing, non-numeric, unchanged, or increases normally.
- The service was stopped while a miner restarted, so detection occurs on the first tick after startup.
- A stored action timestamp is slightly ahead of the wall clock.
- Manual and automatic action timestamps both fall inside the attribution window.
- A repeated poll observes the same post-restart uptime.
- Storage path is relative, parent directories do not exist, or the database is temporarily locked.
- A Telegram event query uses an unknown miner or non-numeric event identifier.
- Retention cleanup runs while Telegram reads history.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST preserve the existing uptime-drop detection criteria as the source signal for restart detection.
- **FR-002**: The system MUST classify each detected restart as expected-manual, expected-auto, or unexpected using recent successful action timestamps and a configurable attribution window.
- **FR-003**: The system MUST record every detected restart exactly once per observed uptime reset with previous uptime, current uptime, miner state, hashrate, threshold, classification, and available related-action evidence.
- **FR-004**: The system MUST notify unexpected restarts independently of state-change notification timing when restart notifications are enabled.
- **FR-005**: The system MUST NOT use historical records as a trigger for manual or automatic reboot/restart actions.
- **FR-006**: The system MUST persist bounded telemetry samples at a configurable interval with miner identity, response status, state, hashrate, board count, and uptime.
- **FR-007**: The system MUST persist normalized state transitions and reboot action outcomes when they occur.
- **FR-008**: The system MUST retain event history across monitor and Windows service restarts.
- **FR-009**: Storage failures MUST be isolated from the monitoring loop and MUST produce an actionable log.
- **FR-010**: The system MUST provide deterministic read-only Telegram commands for recent events, miner-filtered events, and event detail.
- **FR-011**: History command replies MUST use command delivery semantics and MUST NOT perform live ASIC or Hashcore I/O.
- **FR-012**: The system MUST apply independent configurable retention periods to telemetry samples and operational events.
- **FR-013**: Storage initialization MUST log enabled/disabled status and the absolute storage path without logging secrets.
- **FR-014**: Shared configuration documentation MUST use production-safe defaults and MUST NOT modify or expose the real runtime configuration.
- **FR-015**: Existing state machine transitions, startup guard, sustained-LOW gate, cooldown, reboot window, QA guardrails, and confirmation flows MUST remain behaviorally unchanged.

### Key Entities

- **Telemetry Sample**: A bounded point-in-time observation of one miner's signal, state, board count, response status, and uptime.
- **Operational Event**: A durable, normalized occurrence such as a state transition, detected restart, or action outcome.
- **Restart Classification**: The interpretation of an uptime reset based on recent successful manual/automatic actions and timing evidence.
- **Storage Health**: Initialization and failure evidence for the local operational history store.

## Success Criteria

### Measurable Outcomes

- **SC-001**: An unexpected uptime reset produces a dedicated operator alert within one completed polling cycle.
- **SC-002**: In deterministic tests, 100% of restart cases with a qualifying recent action are classified as expected and 100% without one are classified as unexpected.
- **SC-003**: Replaying the same post-restart sample does not create a duplicate restart incident.
- **SC-004**: At least 90 days of five-minute telemetry for the current four-miner deployment remains below 250,000 sample rows.
- **SC-005**: Recent-event and event-detail Telegram queries return from local history without miner-network calls and complete within two seconds under the expected deployment size.
- **SC-006**: A simulated storage write failure does not stop a monitoring iteration or invoke Hashcore.
- **SC-007**: Existing auto-reboot and manual-confirmation validation scenarios produce the same action decisions before and after this feature.

## Assumptions

- Miner uptime reported by API 4028 remains the strongest currently available evidence of a miner-process/device restart.
- Successful manual and automatic action timestamps already maintained by the monitor are valid attribution evidence.
- A 15-minute default attribution window is sufficient to associate an uptime reset with a recent action and is configurable.
- Telemetry sampling defaults to five minutes, sample retention to 90 days, and event retention to 365 days.
- The local history store is observability infrastructure only; dashboard and Vnish raw-log ingestion remain follow-up specs.
- The Windows service account can create and write under the repository-local `data/` directory.
