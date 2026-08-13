# Feature Specification: Adaptive Acquisition Resilience

**Feature Branch**: `022-adaptive-acquisition`

**Created**: 2026-08-13

**Status**: Planned; not implemented

**Input**: Make API 4028 acquisition fresher and resilient with bounded concurrency, explicit quality and diagnostic recovery probes while preserving authoritative 30-second state and action semantics.

**Risk Class**: HIGH

**Dependencies**: Spec 021 liveness rollout and D+1 review

## User Scenarios & Testing

### User Story 1 - Bounded authoritative fleet sampling (Priority: P1)

Slow or unavailable miners no longer age every peer sample.

**Why this priority**: Sequential slow IO can delay trustworthy fleet alerts.

**Independent Test**: Use deterministic fast, slow and timeout endpoints and prove one bounded result per miner and epoch.

**Acceptance Scenarios**:

1. **Given** one miner times out, **When** an authoritative epoch runs, **Then** peer results complete within the epoch deadline
2. **Given** all miners are healthy, **When** epochs repeat, **Then** each miner gets exactly one authoritative sample per epoch

---

### User Story 2 - Explicit sample quality (Priority: P1)

Every sample identifies authority, age, validity and failure reason.

**Why this priority**: Ambiguous no-data and stale reuse create false conclusions.

**Independent Test**: Normalize finite, non-finite, partial, late and timeout fixtures.

**Acceptance Scenarios**:

1. **Given** rate is invalid, **When** it is normalized, **Then** quality is invalid and cannot be healthy/actionable
2. **Given** only a prior value exists, **When** status is rendered, **Then** it is historical with age, never a current success

---

### User Story 3 - Fast read-only recovery visibility (Priority: P2)

Optional 10-second diagnostic probes can show recovery without advancing state or action timers.

**Why this priority**: Visibility may be faster than control semantics, but safety must not accelerate.

**Independent Test**: Interleave diagnostic probes and prove state streaks, low_since_ts and action decisions do not change.

**Acceptance Scenarios**:

1. **Given** a LOW episode is active, **When** a diagnostic probe sees healthy rate, **Then** read-only views may show it but confirmed state waits for authoritative evidence
2. **Given** diagnostic probes fail repeatedly, **When** actions are evaluated, **Then** only authoritative samples affect the decision

### Edge Cases

- A request completes after its epoch deadline.
- A diagnostic request overlaps an authoritative request.
- A route failure affects the full fleet.
- Summary responds but stats is partial.
- The host resumes after sleep and missed epochs.

## Requirements

### Functional Requirements

- **FR-001**: The acquisition layer MUST define one authoritative fleet epoch using the existing 30-second default.
- **FR-002**: Each configured miner MUST produce exactly one authoritative valid, invalid, timeout or error envelope per epoch.
- **FR-003**: Requests MAY use bounded concurrency and staggering, but late results MUST NOT leak into later epochs.
- **FR-004**: Every result MUST include source, authority, observation time, latency, validity and reason code.
- **FR-005**: Only authoritative results MAY update streaks, episodes, sustained-LOW timers or action evaluation.
- **FR-006**: Diagnostic probes MUST be non-authoritative and MUST NOT mutate action or state counters.
- **FR-007**: Per-miner in-flight exclusion MUST prevent overlapping requests.
- **FR-008**: Authoritative outage checks MUST NOT back off beyond their epoch.
- **FR-009**: Fleet transport failures MUST remain distinguishable from individual failures.
- **FR-010**: Telegram offset, state thresholds, hysteresis and action gates MUST remain unchanged.
- **FR-011**: Bounded acquisition health MUST be available for later metrics export.

### Key Entities

- **AcquisitionEpoch**: Fleet cycle identity, deadline and completeness.
- **MinerSampleEnvelope**: Normalized authoritative or diagnostic result with provenance.
- **PollHealth**: Bounded latency, failure and freshness summary.
- **InFlightLease**: Per-miner overlap prevention state.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A five-second timeout does not delay successful peers beyond seven seconds in deterministic tests.
- **SC-002**: Every epoch yields exactly one authoritative envelope per miner.
- **SC-003**: No diagnostic fixture changes state streaks, low_since_ts or action decisions.
- **SC-004**: All late, non-finite and partial fixtures are explicitly classified.
- **SC-005**: Normal request count remains within the documented per-miner budget.

## Assumptions

- API 4028 remains the authoritative request/response health source.
- A small bounded executor is sufficient for the current fleet.
- Diagnostic probes are optional and independently disabled.

## Non-Goals

- Changing threshold, hysteresis, LOW duration, cooldown or reboot windows.
- Replacing Telegram getUpdates polling.
- Continuous WebSocket health acquisition.
