# Feature Specification: Valid Signal Auto-Reboot Gate

**Feature Branch**: `008-valid-signal-reboot-gate`  
**Created**: 2026-07-20  
**Status**: Draft

## Problem

The existing auto-reboot action branch is entered when the hysteretic state is
still `LOW`, even if the current observation has no valid hashrate or has already
recovered above threshold. The code logs `invalid_signal` but does not stop the
subsequent LOW action evaluation. A sustained timer can therefore survive a bad
or recovered sample and allow an unnecessary reboot.

## User Scenarios & Testing

### User Story 1 - Never Reboot Without A Current Valid LOW Signal (Priority: P0)

As the operator, I need auto-reboot to require the current observation to be a
finite hashrate below threshold so that stale LOW state cannot trigger action.

**Acceptance Scenarios**:

1. `responded=false` while state remains LOW blocks with `invalid_signal`, resets the sustained timer, and never calls Hashcore.
2. `rate_ths=None`, NaN, or infinity while state remains LOW behaves the same.
3. A finite rate at or above threshold while recovery hysteresis keeps state LOW blocks with `not_low`, resets the sustained timer, and never calls Hashcore.
4. A later valid LOW sample starts a new sustained interval from that sample.
5. A valid finite LOW signal follows startup guard, sustained duration, cooldown, window, QA, and Hashcore behavior exactly as before.

## Requirements

- **FR-001**: A pure helper MUST classify current signal as `eligible`, `invalid_signal`, or `not_low`.
- **FR-002**: `eligible` MUST require `responded=true`, a finite numeric rate, and `rate_ths < threshold_ths`.
- **FR-003**: The auto-reboot action branch MUST be unreachable for `invalid_signal` and `not_low`.
- **FR-004**: Invalid or recovered signals while hysteretic state remains LOW MUST clear `low_since_ts` after recording/logging the block.
- **FR-005**: A subsequent valid LOW observation MUST start a new `low_since_ts` interval.
- **FR-006**: The existing state-machine state and hysteresis counters MUST NOT be forcibly changed by this gate.
- **FR-007**: Existing startup guard, sustained duration, cooldown, window, QA, Hashcore invocation, notifications, and polling MUST retain their order and values for eligible signals.
- **FR-008**: Decision audit MUST record exactly one applicable invalid/recovered block per tick.
- **FR-009**: No runtime dependency or configuration option MUST be added.
- **FR-010**: The service MUST not be restarted during implementation.

## Success Criteria

- **SC-001**: Deterministic tests cover false/no response, missing rate, NaN, infinity, threshold equality, recovered rate, and valid LOW.
- **SC-002**: A policy harness proves Hashcore call count is zero for every ineligible signal and one only for an otherwise eligible scenario.
- **SC-003**: All pre-existing tests and Speckit HIGH-risk QA pass.
- **SC-004**: Diff inspection confirms no change to state transition conditions or downstream gate ordering.
