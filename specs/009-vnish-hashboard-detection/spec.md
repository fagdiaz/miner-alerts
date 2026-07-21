# Feature Specification: Vnish Hashboard Detection

**Feature Branch**: `009-vnish-hashboard-detection`
**Created**: 2026-07-20
**Status**: Complete

## Problem

The production monitor checks only the first `STATS` entry and does not recognize
Vnish `chain_acn1..N`. The current four-miner sanitized snapshot places chain
evidence in `STATS[1]`; the standalone diagnostics collector correctly reports
three boards while production would return unknown. The existing `HASHBOARD`
state is therefore not receiving its intended signal.

## User Story - Distinguish Missing Board From Generic LOW (Priority: P0)

As the operator, I need the monitor to count Vnish boards from the actual payload
so that a missing hashboard is labeled explicitly and is not treated as a generic
LOW auto-reboot candidate.

### Acceptance Scenarios

1. Metadata in `STATS[0]` and three positive `chain_acn1..3` values in `STATS[1]` returns three active boards.
2. A zero or invalid `chain_acnN` value is not counted.
3. A list-form `chain_acn` and existing `chainN_asicnum/alive/status` formats remain supported.
4. No recognizable board field returns unknown, not zero.
5. Current real-shaped payloads with three boards remain `OK` when all other state inputs are healthy.
6. A proven count below `expected_boards` follows the existing `HASHBOARD` state/notification path and does not enter LOW auto-reboot.

## Requirements

- **FR-001**: `_count_active_boards` MUST support `chain_acn0..9` in addition to existing formats.
- **FR-002**: `read_stats_snapshot` MUST inspect each dictionary in `STATS` and use the first one that yields a board count.
- **FR-003**: Unknown evidence MUST remain `None`; malformed values MUST not crash the tick.
- **FR-004**: The monitor parser MUST match the board-count semantics already used by `tools/miner_diagnostics.py`.
- **FR-005**: No additional API request may be introduced.
- **FR-006**: Existing HASHBOARD precedence over LOW, notification text, recovery, auto-reboot gates, QA, and polling MUST remain unchanged.
- **FR-007**: Tests MUST include the current Vnish `STATS[1].chain_acn1..3` shape and degraded/malformed variants.
- **FR-008**: The running service MUST not be restarted during implementation.

## Success Criteria

- All four current sanitized payload shapes count three active boards.
- A two-active-board fixture returns two and the state precedence remains HASHBOARD before LOW.
- Full existing tests, py_compile, diff check, and Speckit HIGH-risk QA pass.
