# Feature Specification: Monitor Liveness Watchdog

**Feature Branch**: `021-monitor-liveness-watchdog`

**Created**: 2026-08-13

**Status**: Activated / Observation Pending

**Input**: Detect a dead or stalled monitor independently, distinguish service, process, tick and worker freshness, and recover safely without creating a second monitor or miner-action authority.

**Risk Class**: HIGH

**Dependencies**: Spec 020 production activation, smoke and initial soak

## User Scenarios & Testing

### User Story 1 - Detect a stalled monitor (Priority: P1)

An operator is notified when the Windows service is running but completed fleet ticks stop progressing.

**Why this priority**: A running process can be hung and cannot report its own failure.

**Independent Test**: Freeze heartbeat progress while keeping a fake service alive and verify one bounded liveness incident.

**Acceptance Scenarios**:

1. **Given** a fresh heartbeat exists, **When** its completed-tick age crosses the stale threshold, **Then** the watchdog reports a stalled monitor with age and service state
2. **Given** the heartbeat remains stale, **When** the watchdog runs repeatedly, **Then** notifications are deduplicated and later reminded at the documented cadence

---

### User Story 2 - Recover service failures safely (Priority: P1)

Windows service recovery restarts a failed monitor while startup guard and mutex prevent unsafe or duplicate actions.

**Why this priority**: Process death must not leave monitoring absent, but recovery cannot bypass current safety gates.

**Independent Test**: Stop a QA instance unexpectedly and verify one replacement PID, mutex ownership and startup guard without Hashcore execution.

**Acceptance Scenarios**:

1. **Given** the service process exits unexpectedly, **When** Windows recovery runs, **Then** exactly one replacement process starts
2. **Given** a replacement process starts, **When** its first ticks run, **Then** persisted LOW history cannot trigger an immediate reboot

---

### User Story 3 - Inspect liveness health (Priority: P2)

The operator can inspect process, tick, Telegram poller/sender and Vnish collector freshness without exposing secrets.

**Why this priority**: Diagnosis must distinguish a miner outage from a monitor subsystem outage.

**Independent Test**: Render synthetic healthy, stale and missing component states.

**Acceptance Scenarios**:

1. **Given** all components are fresh, **When** health is queried, **Then** each component reports healthy with bounded age
2. **Given** one timestamp is missing, **When** health is queried, **Then** that component reports unknown or stale, never healthy

### Edge Cases

- Heartbeat file is missing, partially written or has an unsupported version.
- System clock moves backwards or forwards.
- Watchdog runs during an intentional maintenance stop.
- Telegram is unavailable while the monitor is stale.
- Service recovery starts while the previous process still owns the mutex.

## Requirements

### Functional Requirements

- **FR-001**: The monitor MUST atomically publish a versioned heartbeat after each completed fleet tick.
- **FR-002**: The heartbeat MUST include PID, process start, tick sequence/time, Telegram worker freshness, queue depth and collector freshness without secrets.
- **FR-003**: An independent watchdog MUST classify service stopped, process missing, heartbeat missing, tick stale and worker stale separately.
- **FR-004**: The watchdog MUST NOT import or call miner, state-machine or Hashcore action code.
- **FR-005**: Repeated detections MUST be deduplicated, reminded on a bounded cadence and closed on recovery.
- **FR-006**: Windows service failure actions MUST be inspected, configured explicitly and recorded as evidence.
- **FR-007**: A replacement monitor MUST still acquire the existing mutex and enforce persisted-state sanitization plus startup guard.
- **FR-008**: Intentional maintenance suppression MUST be bounded and expire automatically.
- **FR-009**: Clock anomalies MUST be explicit and MUST NOT turn stale evidence healthy.
- **FR-010**: Heartbeat and watchdog state files MUST be ignored by Git and contain no credentials.

### Key Entities

- **MonitorHeartbeat**: Atomic versioned snapshot of process and subsystem progress.
- **LivenessAssessment**: Independent classification with timestamps, ages and reason codes.
- **MaintenanceLease**: Bounded local suppression record for intentional service work.
- **LivenessIncident**: Deduplicated open, reminder and recovery state owned only by the watchdog.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A simulated hung process is detected within 120 seconds while the process still exists.
- **SC-002**: A simulated failure starts exactly one replacement monitor and no duplicate mutex owner.
- **SC-003**: No watchdog test can invoke Hashcore or alter a miner.
- **SC-004**: Every liveness alert identifies the failing component and evidence age.
- **SC-005**: Malformed, missing and clock-skew evidence fails safe with an explicit log trail.

## Assumptions

- MinerAlerts is managed by Windows SCM through NSSM or an equivalent service wrapper.
- The watchdog can run once per minute as a non-interactive Scheduled Task.
- Telegram credentials remain only in local config and are read solely for watchdog notification.

## Non-Goals

- Replacing API 4028 polling.
- Creating another monitoring loop or automatic miner-action authority.
- Remote web administration of the Windows service.
