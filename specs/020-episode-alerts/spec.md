# Feature Specification: Irregular Miner Episodes

**Feature Branch**: `020-episode-alerts`

**Created**: 2026-07-21

**Status**: In Progress

**Input**: Convert LOW, OFFLINE, board-loss and restart transitions into concise, persistent and queryable miner episodes without hiding failures or changing reboot policy.

## User Scenarios & Testing

### User Story 1 - Persistent irregular-state escalation (Priority: P1)

An operator keeps receiving bounded reminders while any miner remains unable to hash normally, so a single alert cannot be forgotten and Telegram is not flooded every polling tick.

**Why this priority**: Miner 24 remained OFFLINE for more than one hour after an electrical breaker opened, but only the first alert was delivered.

**Independent Test**: Keep one or more miners in a confirmed irregular state and verify grouped reminders at the configured episode ages until each miner returns to OK.

**Acceptance Scenarios**:

1. **Given** a miner has entered a confirmed irregular episode, **When** it remains irregular for 5, 10 and 15 minutes, **Then** one grouped reminder is emitted at each age.
2. **Given** the episode persists beyond the first three reminders, **When** it reaches 30, 60 and 120 minutes, **Then** reminders continue at those ages and hourly thereafter.
3. **Given** several miners are due in the same polling cycle, **When** a reminder is emitted, **Then** one Telegram message lists every due miner.
4. **Given** a miner returns to confirmed OK, **When** the episode closes, **Then** no later persistent reminder is emitted for that episode.

---

### User Story 2 - Concise episode history and recovery (Priority: P1)

An operator sees a minimal sequence from the last known OK through LOW, OFFLINE, board-loss or restart states and back to OK, instead of receiving a separate noisy message for every intermediate transition.

**Why this priority**: Normal miner startup can produce OFFLINE, board-loss and LOW states before hashing recovers; independent alerts obscure that they belong to one recovery sequence.

**Independent Test**: Simulate `OK -> LOW -> OK` and `OK -> OFFLINE -> RESTART -> board-loss -> LOW -> OK`, then verify one bounded episode history and one recovery result per miner.

**Acceptance Scenarios**:

1. **Given** a miner changes `OK -> LOW -> OK` within the short notification window, **When** the batch is delivered, **Then** one message shows the complete sequence and final OK state.
2. **Given** a restart causes several intermediate states, **When** the miner recovers, **Then** the recovery report shows the deduplicated state sequence and total duration.
3. **Given** multiple miners participate in the same short fleet incident, **When** a report is delivered, **Then** they are grouped in one message with separate compact sequences.
4. **Given** an episode is recorded, **When** the operator requests its detail, **Then** the response is reconstructed from accumulated operational history and includes related miners in the same bounded time window.

---

### User Story 3 - Truthful current status (Priority: P1)

An operator requesting `/status` sees the current signal without contradictions between a live positive hashrate and a stale confirmed state label.

**Why this priority**: A real status response displayed `97.87 TH/s [OFFLINE]` while recovery hysteresis was waiting for another successful sample.

**Independent Test**: Render current-status combinations for no response, low rate, missing boards, a first healthy recovery sample and confirmed OK.

**Acceptance Scenarios**:

1. **Given** the miner does not answer API 4028, **When** status is rendered, **Then** it shows `N/A [OFFLINE]` and never a stale positive rate.
2. **Given** the miner answers above threshold while its confirmed state is still irregular, **When** status is rendered, **Then** it shows the live rate as recovering and does not label it OFFLINE.
3. **Given** fewer boards than expected are active, **When** status or an alert is rendered, **Then** the user-facing text explains active boards instead of relying on the unexplained internal word HASHBOARD.
4. **Given** an active episode contains a detected restart, **When** status is requested, **Then** it provides a compact click-safe detail reference.

---

### User Story 4 - Prompt restart evidence (Priority: P1)

An operator learns about a detected uptime reset after only the short fleet-grouping window, can request full detail, and does not wait three minutes for the first restart notice.

**Why this priority**: The current default restart coalescing window is 180 seconds, creating a misleading delay after the monitor has already persisted the restart.

**Independent Test**: Detect one and several uptime resets, advance 30 seconds, and verify one grouped restart-aware episode message with detail references.

**Acceptance Scenarios**:

1. **Given** a restart is detected, **When** the 30-second grouping window expires, **Then** the operator receives a restart-aware message without waiting 180 seconds.
2. **Given** other miners restart during the same short window, **When** the message is emitted, **Then** all affected miners appear together.
3. **Given** no monitor or Hashcore action can be attributed, **When** the restart is reported, **Then** wording states that no action was attributed and does not claim a cause.
4. **Given** the miner later recovers, **When** OK is confirmed, **Then** the episode closes with a concise sequence instead of delayed intermediate messages.

### Edge Cases

- The service starts while a miner is already irregular.
- A miner alternates among LOW, OFFLINE and board-loss without returning to OK.
- A restart is detected while the confirmed state remains OK.
- A positive current rate arrives while recovery hysteresis still retains OFFLINE or LOW.
- Several miners start or close episodes in adjacent polling ticks.
- SQLite is unavailable; live alerts must continue with an explicit loss of historical detail.
- The process restarts during an active episode; existing persisted transitions remain queryable and the live reminder schedule restarts safely rather than becoming silent.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST define an irregular episode as a confirmed LOW, OFFLINE or board-loss condition that begins after OK and closes only after confirmed OK.
- **FR-002**: The first state/restart notification MUST wait only the existing short fleet-grouping window, bounded to 30 seconds by the production default.
- **FR-003**: Active irregular episodes MUST produce reminders at 5, 10, 15, 30, 60 and 120 minutes of episode age, then once per hour while still active.
- **FR-004**: Reminders due in the same cycle MUST be grouped into one Telegram message.
- **FR-005**: Each episode MUST retain a bounded, consecutive-deduplicated sequence containing state, timestamp and concise evidence.
- **FR-006**: A recovered episode MUST report the sequence from OK through irregular states or restart evidence back to OK and its total duration.
- **FR-007**: Intermediate transitions belonging to a known restart episode MUST update the episode history without producing independent Telegram noise.
- **FR-008**: A restart detection MUST be visible after the short grouping window and MUST retain existing action-attribution wording and incident identity.
- **FR-009**: Restart and episode messages MUST expose a click-safe detail command while preserving the existing `/event <id>` command.
- **FR-010**: Event detail MUST use persisted operational history to show the selected incident timeline and bounded related fleet events.
- **FR-011**: `/status` MUST use current response/rate/board evidence and MUST never combine a positive live hashrate with an OFFLINE label.
- **FR-012**: When current evidence is healthy but confirmed recovery is pending, `/status` MUST identify the miner as recovering rather than OFFLINE or LOW.
- **FR-013**: User-facing board-loss text MUST explain active versus expected boards; internal state constants MUST remain unchanged.
- **FR-014**: Existing state transitions, hysteresis, persistence, startup guard, QA guardrails, auto-reboot, cooldown and Hashcore action logic MUST remain unchanged.
- **FR-015**: The implementation MUST reuse the existing SQLite operational history and MUST continue live alerting if historical storage is unavailable.
- **FR-016**: Configuration defaults MUST be production-safe and documented without changing the real local config or secrets.

### Key Entities

- **Irregular episode**: A bounded live record for one miner containing start time, current state/evidence, deduplicated timeline, restart incident IDs, reminder stage and closure state.
- **Episode notification batch**: One Telegram delivery containing all episodes whose initial notice, reminder or recovery became due together.
- **Operational timeline**: Persisted state-transition and restart events selected around one incident to provide on-demand detail.
- **Current signal view**: The current response, hashrate and board evidence used by `/status`, distinct from confirmed state-machine hysteresis.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A continuously irregular miner produces alerts at 5, 10, 15, 30, 60 and 120 minutes and hourly thereafter, with no polling-tick spam.
- **SC-002**: A detected restart is first reported within 60 seconds under the normal 30-second polling cadence, instead of the current 180-second intentional delay.
- **SC-003**: Every tested episode that returns to OK yields one concise recovery sequence with no separate OFFLINE, board-loss and LOW recovery cascade.
- **SC-004**: No `/status` test case can render a finite above-threshold hashrate with `[OFFLINE]`.
- **SC-005**: All state/restart changes remain available through existing operational history even when Telegram summaries are coalesced.
- **SC-006**: The full automated suite, Python compilation, QA no-action checks and a controlled production restart complete without changing action-policy outcomes.

## Assumptions

- The requested cadence means episode-age notifications at 5, 10, 15, 30, 60 and 120 minutes, followed by hourly reminders.
- `HASHBOARD` remains an internal compatibility state; user-facing messages describe missing or inactive boards.
- Thirty seconds is the prudent fleet-grouping default because it covers one normal polling interval without recreating the observed three-minute restart delay.
- Existing SQLite transition/restart records are the canonical historical source; a new database is unnecessary.
- Telegram remains the primary remote interface and dangerous command confirmation is out of scope for this notification-only change.
