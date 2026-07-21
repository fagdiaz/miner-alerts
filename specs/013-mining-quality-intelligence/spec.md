# Feature Specification: Mining Quality Intelligence

**Feature Branch**: `codex/013-mining-quality-intelligence`
**Created**: 2026-07-20
**Status**: Complete

## Problem

Current monitoring captures hashrate, boards, temperatures, chain voltage, power,
frequency, and cumulative hardware errors. The deployed Vnish firmware also
exposes accepted, rejected, and stale share counters plus per-chain state and
fault evidence. Those signals are not yet normalized into historical quality
evidence, so the operator cannot distinguish a healthy miner, a pool/network
quality issue, a board-side fault, and a recent counter reset before deciding
whether intervention is justified.

## User Scenarios & Testing

### User Story 1 - Preserve Mining Quality Evidence (Priority: P1)

As the operator, I need bounded quality counters and chain health persisted with
normal telemetry so later diagnosis uses evidence rather than a single alert.

**Acceptance Scenarios**:

1. Valid cumulative accepted, rejected, stale, chain state, and chain fault data
   is normalized without storing raw firmware payloads.
2. Missing, malformed, negative, or non-finite values remain unknown and do not
   create a fault.
3. Existing databases migrate additively without losing prior samples or events.

### User Story 2 - Separate Degradation From Counter Reset (Priority: P1)

As the operator, I need changes between comparable samples classified so a miner
restart or counter reset is not misreported as poor share quality.

**Acceptance Scenarios**:

1. Comparable samples produce accepted, rejected, stale, and hardware-error deltas.
2. Decreasing counters or elapsed time produce a reset/learning result, never a
   negative rate or critical alert.
3. Current chain faults or non-mining chains take precedence over statistical
   share-quality warnings.

### User Story 3 - Review Quality Without Touching Miners (Priority: P2)

As the operator, I need the same bounded quality diagnosis in Telegram and the
local dashboard without issuing extra miner requests or actions.

**Acceptance Scenarios**:

1. `/quality`, `/quality all`, and `/quality <miner>` use persisted samples only.
2. Dashboard cards show quality status, share deltas, and concise reasons.
3. No quality result triggers reboot, restart, Hashcore, or a state transition.

### Edge Cases

- First sample after installation or schema migration.
- Miner uptime or counters reset between samples.
- No accepted shares during a short interval.
- Counters represented as numeric strings or malformed values.
- Missing chain state/fault fields on non-Vnish firmware.
- More miners or history than the configured output/query bounds.

## Requirements

- **FR-001**: Quality normalization MUST accept only finite, non-negative counters.
- **FR-002**: Chain state/fault evidence MUST be bounded and sanitized.
- **FR-003**: Raw API responses, pool URLs, workers, credentials, and secrets MUST NOT be persisted.
- **FR-004**: Schema migration MUST be additive and preserve existing schema-v2 data.
- **FR-005**: Deltas MUST be calculated only between chronologically comparable samples from the same uptime epoch.
- **FR-006**: Counter or uptime regression MUST produce `counter_reset`, not negative rates.
- **FR-007**: Assessments MUST distinguish `learning`, `stable`, `watch`, and `critical`.
- **FR-008**: Current chain fault/non-mining evidence MUST take precedence over share-rate drift.
- **FR-009**: Rejected and stale percentages MUST be derived from interval deltas, not cumulative lifetime percentages.
- **FR-010**: Telegram and dashboard MUST use the same pure assessment logic.
- **FR-011**: Query sizes, reasons, strings, and command output MUST be bounded.
- **FR-012**: The feature MUST NOT modify state-machine or auto-reboot eligibility.
- **FR-013**: No additional API 4028, HTTP, SSH, or Hashcore call may be added to the monitor loop or command handler.
- **FR-014**: The running Windows service MUST not be restarted during implementation.

## Key Entities

- **Mining Quality Telemetry**: Sanitized counters and current chain-health evidence from an already-fetched sample.
- **Quality Delta**: Non-negative interval changes between comparable samples.
- **Quality Assessment**: Status, confidence, interval, derived percentages, and bounded reasons.

## Success Criteria

- **SC-001**: Deterministic tests cover healthy, rejected, stale, chain-fault,
  non-mining, missing-data, and counter-reset cases.
- **SC-002**: Existing schema-v2 fixtures migrate to the new schema without data loss.
- **SC-003**: One assessment over 2,000 bounded samples completes in under one second on the target machine.
- **SC-004**: Telegram and dashboard produce the same status/reason codes for identical history.
- **SC-005**: Existing tests remain green and static inspection finds no action or live-IO call in the quality command path.

## Assumptions

- Firmware counters are cumulative within one miner uptime epoch.
- One prior comparable sample is enough to calculate an interval, while confidence
  improves with more comparable intervals.
- Share-quality warnings are advisory and cannot authorize an action.
- Chain voltage remains board-side telemetry and does not prove AC input quality.
