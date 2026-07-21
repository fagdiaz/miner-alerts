# Feature Specification: Vnish Transition Reboot Interlock

**Feature Branch**: `codex/015-vnish-transition-reboot-interlock`

**Created**: 2026-07-20

**Status**: Complete

**Input**: Prevent unnecessary automatic reboots while current Vnish chain evidence says tuning, autotune, calibration, startup, initialization, or warm-up is in progress.

## User Scenarios & Testing

### User Story 1 - Firmware work is not interrupted (Priority: P1)

As an operator, I need Miner Alerts to observe an explicit Vnish chain transition instead of rebooting the miner during that transition, because interrupting tuning or initialization can extend downtime and hide the original cause.

**Why this priority**: This directly reduces unnecessary automatic actions using evidence already collected from the miner in the same tick.

**Independent Test**: Evaluate an otherwise eligible LOW candidate with current transitioning-chain evidence and prove the policy records a firmware-transition block without invoking Hashcore.

**Acceptance Scenarios**:

1. **Given** automatic reboot is otherwise eligible and at least one current chain is transitioning, **When** policy gates are evaluated, **Then** the action is blocked as `firmware_transition`.
2. **Given** a transition block, **When** the next tick is evaluated after the transition ends, **Then** LOW must sustain for the configured duration again before automatic action.
3. **Given** transition evidence is missing or zero, **When** all existing gates allow action, **Then** this interlock does not change the previous result.
4. **Given** a manual reboot/restart confirmation, **When** it is executed, **Then** the new automatic-only interlock does not participate.

### User Story 2 - Operators can explain the block (Priority: P2)

As an operator, I need logs and `/why` history to show that Vnish transition evidence blocked the action, including the number of transitioning chains.

**Why this priority**: A conservative gate without evidence could look like a broken automation.

**Independent Test**: Persist and render a `firmware_transition` decision with bounded chain evidence.

**Acceptance Scenarios**:

1. **Given** a transition block, **When** the decision is logged, **Then** it includes `blocked_by=firmware_transition` and a bounded transition count.
2. **Given** the persisted decision, **When** an operator requests the explanation, **Then** the response identifies the firmware/chain transition and observation policy.

### Edge Cases

- Missing, malformed, or non-finite transition evidence is unknown and does not invent a transition.
- A transition and high temperature occur together; the existing thermal interlock keeps precedence.
- The guard is disabled explicitly; previous action eligibility is preserved.
- The miner remains LOW after the transition; a fresh sustained interval is required.

## Requirements

### Functional Requirements

- **FR-001**: The automatic reboot interlock MUST consume only current telemetry already fetched in the same monitoring tick.
- **FR-002**: An explicit transitioning-chain count above zero MUST block automatic reboot when the guard is enabled.
- **FR-003**: A transition block MUST restart the existing sustained-LOW action timer without changing the state-machine label or streaks.
- **FR-004**: Missing, malformed, zero, or disabled transition evidence MUST NOT independently block action.
- **FR-005**: Thermal safety MUST retain precedence over firmware transition, and firmware transition MUST be evaluated before fleet/cooldown/window/action execution.
- **FR-006**: The decision MUST be persisted and logged as `firmware_transition` with no raw firmware payload.
- **FR-007**: Manual reboot/restart, Telegram confirmation, startup guard, QA guard, cooldown, window, polling, and state persistence contracts MUST remain intact.
- **FR-008**: Production defaults MUST enable the conservative interlock and document how to disable it explicitly.

## Key Entities

- **Current transition evidence**: A bounded count of current chains in a recognized firmware transition state.
- **Reboot interlock decision**: Allowed/blocked result, reason, transition count, existing thermal/fleet context.
- **Sustained LOW timer**: Existing action timer reset after transition evidence so post-transition degradation is re-observed.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of otherwise eligible candidates with explicit transition evidence are blocked before Hashcore execution.
- **SC-002**: Zero automatic actions can occur immediately after a transition solely because pre-transition LOW time accumulated.
- **SC-003**: Existing no-transition interlock tests and the complete automated suite remain passing.
- **SC-004**: Every transition block produces one persisted decision and an explicit bounded log reason.
- **SC-005**: No additional miner API request is introduced.

## Assumptions

- Current Vnish `chain_stateN` fields are the available transition signal; full firmware logs remain future work.
- Blocking and restarting the action timer is safer than interrupting an explicit transition.
- The guard is automatic-only and intentionally does not change operator-confirmed manual actions.
