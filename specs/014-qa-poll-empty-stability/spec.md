# Feature Specification: QA Poll-Empty Stability

**Feature Branch**: `codex/014-qa-poll-empty-stability`

**Created**: 2026-07-20

**Status**: Complete

**Input**: Prevent the Telegram polling worker from referencing command-local variables when a QA poll returns no updates, without changing polling, routing, or production behavior.

## User Scenarios & Testing

### User Story 1 - Idle QA polling remains healthy (Priority: P1)

As an operator validating Telegram in QA, I need empty `getUpdates` batches to remain a normal idle condition so the polling worker does not enter exception backoff because no command was handled.

**Why this priority**: Idle polling is the common state. A scope error in this path can repeatedly degrade command reception and obscure the actual Telegram signal.

**Independent Test**: Inspect the polling worker and execute a regression test proving the empty-batch logging path references only variables defined for every poll.

**Acceptance Scenarios**:

1. **Given** QA mode and an empty Telegram result, **When** the worker records `POLL_EMPTY`, **Then** it does not reference command-specific variables or raise an exception.
2. **Given** a non-empty result, **When** the worker advances the update reference, **Then** the existing offset calculation and command dispatch remain unchanged.
3. **Given** production mode, **When** polling is idle, **Then** no new production log or behavior is introduced.

### Edge Cases

- The process has never handled a command, so `action` and `cmd_start` have never been bound.
- A previous update happened to bind similarly named locals; idle behavior must not depend on stale loop-local values.
- Debug Telegram logging is disabled; the removal must not affect the normal polling sleep.

## Requirements

### Functional Requirements

- **FR-001**: Empty Telegram batches MUST remain a successful polling outcome in QA.
- **FR-002**: The empty-batch block MUST NOT access variables created only inside command branches.
- **FR-003**: The update reference, next-offset calculation, polling sleep, backoff policy, and command router MUST remain unchanged.
- **FR-004**: The change MUST NOT affect monitoring state, reboot policy, Hashcore execution, config, or persisted state.
- **FR-005**: A regression test MUST fail against the defective source and pass after the surgical correction.

## Success Criteria

### Measurable Outcomes

- **SC-001**: The regression test finds zero command-local references in the `POLL_EMPTY` block.
- **SC-002**: The full automated suite and Python compilation complete successfully.
- **SC-003**: The production monitor service remains running and is not restarted during implementation.
- **SC-004**: The application diff changes exactly the defective idle-log statements and no polling condition.

## Assumptions

- `POLL_EMPTY` already provides sufficient QA evidence for an empty response.
- Command-duration logs belong only to actual command branches.
- A final controlled service restart will happen after the day's feature work, not during this spec.
