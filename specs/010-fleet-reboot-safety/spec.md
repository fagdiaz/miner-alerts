# Feature Specification: Fleet-Aware Auto-Reboot Safety

**Feature Branch**: `010-fleet-reboot-safety`  
**Created**: 2026-07-20  
**Status**: Complete

## Problem

The monitor evaluates automatic reboot independently for each miner. A sustained
LOW can therefore reach Hashcore while another miner is also degraded because of
a shared network, pool, power, or environmental incident. A LOW caused by high
temperature can also reach the action path even though rebooting does not remove
the thermal cause. These cases need conservative interlocks before automatic
action, without changing state classification or manual controls.

## User Scenarios & Testing

### User Story 1 - Prevent Cascading Fleet Reboots (Priority: P0)

As the operator, I need automatic reboot blocked when multiple miners are
simultaneously degraded so a shared incident does not trigger a reboot cascade.

**Acceptance Scenarios**:

1. Given one sustained valid LOW miner and all peers healthy, the existing action gates remain available.
2. Given at least two affected miners in the latest complete fleet observation, the candidate is blocked with `fleet_incident` and Hashcore is not called.
3. Given no complete previous fleet observation, the fleet interlock does not invent missing evidence; startup guard remains authoritative.
4. When the shared condition clears, the remaining valid LOW miner can resume the existing gate chain on a later tick.

### User Story 2 - Do Not Reboot A Thermally Constrained Miner (Priority: P0)

As the operator, I need a sustained LOW with current high-temperature evidence
blocked before Hashcore so thermal throttling is not treated as a reboot remedy.

**Acceptance Scenarios**:

1. A finite current maximum temperature at or above the configured safety limit blocks with `high_temperature`.
2. Missing or malformed temperature evidence does not fabricate a thermal block.
3. Manual reboot, restart, and confirmation flows remain unchanged.

### User Story 3 - Explain Every Safety Block (Priority: P1)

As the operator, I need logs and `/why` evidence showing why action was blocked,
which miners were affected, and the observed temperature.

**Acceptance Scenarios**:

1. Every applied interlock records one reboot decision with the current signal and context.
2. `/why` renders the new result and relevant evidence without live miner IO.
3. The incident report includes the new decision result through the existing generic aggregation.

### Edge Cases

- The fleet contains one miner only.
- The minimum affected count is configured below two or above fleet size.
- A peer changes from invalid to healthy between completed observations.
- Temperature is `None`, text, NaN, infinity, or exactly equal to the limit.
- QA mode, startup guard, cooldown, and reboot-window limits are also active.

## Requirements

- **FR-001**: The system MUST evaluate thermal and fleet safety interlocks only for a current valid LOW candidate that has satisfied startup and sustained-LOW prerequisites.
- **FR-002**: The fleet interlock MUST use the latest completed fleet observation plus the current candidate, without additional miner API calls.
- **FR-003**: The default fleet threshold MUST be two affected miners and MUST be configurable.
- **FR-004**: Affected fleet signals MUST include current valid LOW and unavailable/invalid current signal, but not a healthy current signal.
- **FR-005**: The thermal interlock MUST require a finite current maximum temperature at or above a configurable limit whose default is 85 C.
- **FR-006**: Applied interlocks MUST prevent Hashcore execution and record `fleet_incident` or `high_temperature` with evidence.
- **FR-007**: Existing state transitions, hysteresis, startup guard, sustained duration, cooldown, reboot window, QA block, and Hashcore behavior MUST remain unchanged outside the new blocks.
- **FR-008**: Manual Telegram reboot/restart and confirmation flows MUST remain unchanged.
- **FR-009**: The feature MUST add no network request, background worker, dependency, or persisted state field.
- **FR-010**: Production defaults MUST enable both conservative interlocks while allowing explicit local configuration.
- **FR-011**: The real `app/config.json` and runtime state MUST NOT be modified.
- **FR-012**: The Windows service MUST not be restarted during implementation.

## Key Entities

- **Completed Fleet Observation**: The per-miner signal classifications from the last fully processed monitor tick.
- **Safety Interlock Decision**: An allow/block result with a stable reason, affected miners, and thermal evidence.
- **Reboot Decision Audit**: The existing durable record extended through result and details, without schema changes.

## Success Criteria

- **SC-001**: Deterministic tests prove zero automatic actions for shared degradation and high temperature.
- **SC-002**: A single otherwise eligible LOW miner still reaches the pre-existing cooldown/window/QA/action chain.
- **SC-003**: All current tests plus new interlock tests pass on Windows.
- **SC-004**: Diff inspection proves no changes to state transition conditions, manual commands, polling offset, or Hashcore invocation semantics.
- **SC-005**: The service remains running on the pre-change process until the controlled end-of-day restart.

## Assumptions

- A completed observation is at most one normal polling interval old.
- Simultaneous degradation is treated conservatively as a possible shared incident; the feature does not claim a root cause.
- Vnish `max_temp_c` is board/chip telemetry and not ambient or PSU input temperature.
- Unknown telemetry remains unknown and does not by itself trigger a thermal block.
