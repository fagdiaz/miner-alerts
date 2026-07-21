# Feature Specification: Stability Advisor

**Feature Branch**: `012-stability-advisor`
**Created**: 2026-07-20
**Status**: Complete

## Problem

Raw current values explain whether a miner is healthy now, but not whether it is
drifting away from its own stable operating range. A fixed fleet-wide threshold
cannot explain temperature, chain-voltage, power, frequency, or gradual hashrate
changes. The operator needs evidence-based guidance before deciding whether a
restart or reboot is justified.

## User Scenarios & Testing

### User Story 1 - Understand Per-Miner Sweet Spot (Priority: P1)

As the operator, I need a robust baseline built only from healthy historical
samples so each miner can be compared with its own normal behavior.

**Acceptance Scenarios**:

1. Enough healthy samples produce bounded baseline bands and a confidence value.
2. Missing or malformed optional metrics do not invalidate available evidence.
3. Insufficient history is labeled as learning, never guessed as healthy.

### User Story 2 - Diagnose Current Drift (Priority: P1)

As the operator, I need current hard faults and softer deviations separated so I
can distinguish urgent intervention from a condition that only needs observation.

**Acceptance Scenarios**:

1. Offline, stale, below-threshold, missing-board, and high-temperature evidence
   produce explicit critical reasons.
2. Statistically unusual rate, temperature, chain voltage, power, or frequency
   produces watch evidence without triggering any action.
3. Chain voltage is always labeled as board-side evidence, not AC input voltage.

### User Story 3 - Review The Diagnosis Anywhere (Priority: P2)

As the operator, I need the same diagnosis in Telegram and the local dashboard,
using only persisted history and without contacting miners on demand.

**Acceptance Scenarios**:

1. `/health`, `/health all`, and `/health <miner>` return bounded read-only output.
2. Dashboard miner cards show stability status, baseline ranges, and reasons.
3. The feature does not invoke API 4028, Hashcore, reboot, restart, or config writes.

### Edge Cases

- Empty or unavailable history.
- Latest sample is malformed, stale, or older than baseline rows.
- Zero median or zero variation.
- Mixed schema rows with optional columns missing.
- Counter reset after miner restart.
- More history than the configured query bound.

## Requirements

- **FR-001**: Baselines MUST use finite healthy samples with full known board count.
- **FR-002**: The latest sample MUST be excluded from its own baseline.
- **FR-003**: Robust median and median absolute deviation MUST be used instead of mean-only thresholds.
- **FR-004**: Minimum absolute and relative bands MUST prevent zero-variance false positives.
- **FR-005**: Results MUST distinguish `stable`, `watch`, `critical`, and `learning`.
- **FR-006**: Hard current evidence MUST take precedence over statistical deviations.
- **FR-007**: Every non-stable result MUST include bounded machine-readable reason codes and operator text.
- **FR-008**: Telegram health commands MUST use persisted SQLite samples only and command-delivery semantics.
- **FR-009**: The dashboard MUST show the same analyzer output without adding JavaScript or remote assets.
- **FR-010**: Analysis MUST be read-only and MUST NOT influence state transitions or action policy.
- **FR-011**: Queries, baseline samples, reasons, and rendered output MUST be bounded.
- **FR-012**: The running Windows service MUST not be restarted during implementation.

## Key Entities

- **Metric Band**: Sample count, median, MAD, lower bound, and upper bound.
- **Diagnostic Reason**: Stable code, severity, observed value, expected range, and concise text.
- **Stability Assessment**: Current status, evidence age, baseline confidence, metric bands, and reasons.

## Success Criteria

- **SC-001**: Deterministic fixtures classify stable, learning, stale, hard-fault, and drift cases correctly.
- **SC-002**: One fleet assessment completes in under one second for 5,000 samples on the target machine.
- **SC-003**: Telegram and dashboard render the same status and reason codes for identical input.
- **SC-004**: Existing tests remain green and no Hashcore/API 4028 call is reachable from analysis.
- **SC-005**: No generated artifact, database, runtime config, state, or secret is committed.

## Assumptions

- Twelve prior healthy samples are enough to leave learning mode by default.
- A robust advisory is observational; it cannot authorize or trigger an action.
- Persisted chain voltage is board-side telemetry and cannot prove AC mains quality.
