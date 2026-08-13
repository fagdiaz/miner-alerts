# Feature Specification: Fleet Restart Notification Stability

**Feature Branch**: `codex/018-fleet-restart-notification-stability`

**Created**: 2026-07-21

**Status**: Complete; activated by the verified Spec 019 service rollout

## User Scenarios & Testing

### User Story 1 - Understand fleet restarts without alert flood (Priority: P1)

As the operator, I need closely timed miner restarts to be reported as one
bounded fleet incident instead of multiple per-miner alerts plus transient boot
state messages.

**Why this priority**: The 2026-07-21 incident produced overlapping alerts while
all four miners were recovering, obscuring the actual event.

**Independent Test**: Feed multiple restart detections inside the configured
window and verify one fleet notification plus one post-recovery summary while
all state changes remain logged and persisted.

**Acceptance Scenarios**:

1. **Given** two or more restart detections inside the coalescing window, **When** notifications flush, **Then** Telegram receives one fleet incident listing all affected miners and incident links.
2. **Given** miners transition through OFFLINE, HASHBOARD, LOW and OK during restart recovery, **When** the quiet window is active, **Then** transient Telegram state-change messages are suppressed but logs, persistence and state-machine updates continue.
3. **Given** the quiet window ends, **When** the next monitor tick completes, **Then** Telegram receives one current fleet recovery summary.

### User Story 2 - Avoid false certainty about restart cause (Priority: P1)

As the operator, I need restart alerts to distinguish lack of monitor attribution
from proof that a reboot was unexpected.

**Why this priority**: A firmware update or external power/control action is not
recorded as a Hashcore action and was incorrectly titled as definitively
unexpected.

**Independent Test**: Render an unattributed restart and verify that the message
states no registered monitor action was found without claiming a proven cause.

**Acceptance Scenarios**:

1. **Given** an uptime reset with no recent manual or auto action, **When** the incident is formatted, **Then** it is titled as an unattributed restart and retains uptime and event evidence.
2. **Given** a recent registered action, **When** the incident is formatted, **Then** existing expected-manual or expected-auto attribution remains unchanged.

### User Story 3 - Keep scheduled collection unobtrusive (Priority: P2)

As the Windows operator, I need the read-only Vnish collector to run without
opening an interactive PowerShell window and at a bounded cadence.

**Why this priority**: The current scheduled action uses an interactive account
without hidden-window arguments, causing visible console windows.

**Independent Test**: Inspect the generated scheduled action and verify hidden
PowerShell execution, non-overlap and a 30-minute default interval.

**Acceptance Scenarios**:

1. **Given** the scheduled collector is installed, **When** it runs, **Then** its PowerShell process is requested hidden and remains non-overlapping.
2. **Given** no interval override, **When** the task is installed, **Then** its default cadence is 30 minutes.

### Edge Cases

- A single restart remains a bounded individual notification after the coalescing window.
- Additional restart detections extend the recovery quiet window without losing incident IDs.
- Notification suppression never changes state, action eligibility, cooldowns, persistence or Hashcore execution.
- Collector failures remain recorded as collector-run health and never trigger miner actions.

## Requirements

### Functional Requirements

- **FR-001**: Closely timed restart notifications MUST be coalesced into one bounded fleet message when at least two miners are affected.
- **FR-002**: Restart recovery MUST suppress only Telegram state-change delivery during a bounded window; monitor logs, state transitions, persistence and action policy MUST remain unchanged.
- **FR-003**: The operator MUST receive one current-state recovery summary when the quiet window expires after suppressed transitions.
- **FR-004**: A restart without a recent registered action MUST be described as unattributed, not as proof of an unexpected cause.
- **FR-005**: Expected manual and automatic restart attribution MUST remain unchanged.
- **FR-006**: Notification coalescing and recovery quiet durations MUST have safe production defaults and be configurable.
- **FR-007**: The scheduled collector MUST request hidden PowerShell execution and retain non-overlap and bounded execution.
- **FR-008**: The scheduled collector default interval MUST be 30 minutes.
- **FR-009**: Auto-reboot, manual actions, state-machine transitions, startup guard, cooldowns and polling offset MUST remain unchanged.

### Key Entities

- **Pending restart notification**: In-memory bounded evidence for one detected uptime reset, including miner, detection time, event ID and rendered evidence.
- **Recovery quiet window**: In-memory deadline controlling only Telegram state-change delivery after a restart detection.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Four restart detections spread across three minutes produce one fleet restart notification rather than four individual restart notifications.
- **SC-002**: Boot transitions during a ten-minute recovery window produce no intermediate Telegram state-change messages and one final summary.
- **SC-003**: Every suppressed transition remains present in local logs and operational history.
- **SC-004**: No test or source diff changes auto-reboot decisions, Hashcore invocation, polling offset or state transition conditions.
- **SC-005**: The scheduled task action contains hidden-window execution and defaults to a 30-minute interval.

## Assumptions

- Immediate all-miner OFFLINE notification remains useful and may precede uptime-reset confirmation.
- Delaying restart attribution by up to three minutes is acceptable because signal-loss alerts remain immediate.
- The collector is read-only; this feature changes its operator UX and cadence, not its data contract.
