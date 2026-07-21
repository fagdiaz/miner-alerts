# Feature Specification: Persistent Outage Alerts

**Feature Branch**: `019-persistent-outage-alerts`

**Created**: 2026-07-21

**Status**: Implemented; service activation pending

**Input**: Add persistent reminders when a miner remains OFFLINE, LOW, or HASHBOARD; briefly coalesce state changes across the fleet; avoid recovery-message cascades; and eliminate visible PowerShell windows without changing state or reboot policy.

## User Scenarios & Testing

### User Story 1 - Persistent outage reminders (Priority: P1)

An operator receives an initial consolidated state-change alert and bounded follow-up reminders while any miner remains unable to hash normally, so a long outage cannot be forgotten after one Telegram message.

**Why this priority**: A miner remained OFFLINE for more than one hour after its breaker opened. The first alert was correct, but the absence of reminders delayed intervention.

**Independent Test**: Simulate one confirmed OFFLINE miner, advance time through the configured reminder thresholds, and verify grouped reminders continue until the miner is OK.

**Acceptance Scenarios**:

1. **Given** miner 24 is confirmed OFFLINE, **When** it remains OFFLINE for 15 minutes, **Then** Telegram sends a persistent-outage reminder with duration and current evidence.
2. **Given** the outage remains active, **When** another 30 minutes elapse, **Then** Telegram sends another reminder.
3. **Given** several miners are due for a reminder in the same tick, **When** the reminder is rendered, **Then** one message lists all affected miners.
4. **Given** a miner returns to OK, **When** the next ticks confirm recovery, **Then** reminders for that miner stop.

---

### User Story 2 - Briefly grouped state changes (Priority: P1)

An operator receives one concise fleet message when related OFFLINE, LOW, HASHBOARD, or recovery transitions occur close together instead of one Telegram message per polling tick.

**Why this priority**: Sequential miner recovery currently creates OFFLINE, LOW, and OK message cascades that obscure the actual incident.

**Independent Test**: Queue transitions from multiple miners across adjacent ticks and verify one message is emitted after a short bounded wait while state persistence remains immediate.

**Acceptance Scenarios**:

1. **Given** miner 23 changes state and miner 24 changes state on the next tick, **When** both occur inside the coalescing window, **Then** Telegram sends one STATE CHANGE message containing both events.
2. **Given** only one miner changes state, **When** the coalescing window expires, **Then** its alert is sent without waiting indefinitely.
3. **Given** a detected restart is inside the existing recovery quiet window, **When** state transitions accumulate, **Then** they remain suppressed and the existing recovery summary remains authoritative.
4. **Given** state transitions are buffered for Telegram, **When** the monitor tick completes, **Then** state machine updates, persistence, event history, and auto-reboot evaluation are unchanged and immediate.

---

### User Story 3 - No visible process windows (Priority: P1)

The Vnish collector and Hashcore subprocesses run without stealing desktop focus or flashing PowerShell/cmd windows.

**Why this priority**: Visible console windows interrupt foreground work and make unattended operation unreliable.

**Independent Test**: Inspect the scheduled-task action and subprocess flags, run the collector task, and confirm it uses `pythonw.exe` with no PowerShell action while all subprocess calls request no console window on Windows.

**Acceptance Scenarios**:

1. **Given** the scheduled collector is installed, **When** it runs, **Then** its action executes `pythonw.exe` directly and never launches PowerShell.
2. **Given** Hashcore discovery, selftest, reboot, or restart invokes a console program, **When** it is launched on Windows, **Then** the process uses the no-window creation flag.
3. **Given** the collector runs, **When** it completes, **Then** non-overlap, execution limit, configuration path, and read-only behavior remain unchanged.

### Edge Cases

- A bad state already loaded at process startup must still become eligible for a reminder even if no new transition occurs.
- Reminder timing must use confirmed machine state, not a single raw failed sample.
- Invalid or non-finite rate data must not be rendered as a healthy signal.
- A restart recovery quiet window must not be followed immediately by stale buffered state changes.
- Telegram delivery failure must not alter monitoring or reboot decisions.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST track confirmed `OFFLINE`, `LOW`, and `HASHBOARD` states as active operational outages independently of Telegram transition delivery.
- **FR-002**: The system MUST send the first persistent reminder after 900 seconds by default and repeat it every 1800 seconds by default until recovery.
- **FR-003**: Persistent reminders due in the same monitor tick MUST be grouped into one Telegram message.
- **FR-004**: The system MUST clear an active outage reminder when that miner reaches confirmed `OK`.
- **FR-005**: State-change Telegram events MUST wait for a bounded 30-second coalescing window by default and merge events accumulated across ticks.
- **FR-006**: Coalescing MUST affect Telegram delivery only; state transitions, SQLite events, state persistence, startup guard, and auto-reboot policy MUST remain unchanged.
- **FR-007**: Existing restart-recovery suppression MUST take precedence over generic state-change delivery, and stale buffered transitions MUST not be emitted after the recovery summary.
- **FR-008**: Persistent reminders MUST be deferred during restart recovery and resume only after a fresh bounded interval if the miner remains degraded.
- **FR-009**: New timing and enablement options MUST have safe production defaults in `app/config.example.json` without requiring changes to the real secret-bearing config.
- **FR-010**: The scheduled Vnish collector MUST execute `pythonw.exe` directly rather than PowerShell and preserve its current arguments, working directory, non-overlap, and execution limit.
- **FR-011**: Every monitor-owned `subprocess.run` invocation MUST request `CREATE_NO_WINDOW` on Windows and remain portable with a zero flag elsewhere.
- **FR-012**: The implementation MUST NOT modify manual reboot confirmation, auto-reboot eligibility, cooldowns, reboot windows, QA guardrails, polling offset, or state-machine thresholds.

### Key Entities

- **Pending State Batch**: Ordered transition lines and reboot names waiting for the short Telegram coalescing deadline.
- **Active Outage**: In-memory current degraded state, miner identity, first confirmed timestamp, latest rate, and last reminder timestamp.
- **Scheduled Collector Action**: Windows task action that starts the bounded read-only Vnish collector without an interactive console.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A confirmed outage that lasts 70 minutes produces an initial state alert plus at least two reminders with default settings.
- **SC-002**: State changes from multiple miners within 30 seconds produce exactly one STATE CHANGE Telegram message.
- **SC-003**: No reminder is emitted after the affected miner returns to confirmed OK.
- **SC-004**: The scheduler contract contains no PowerShell executable and points to the virtualenv `pythonw.exe`.
- **SC-005**: All monitor subprocess call sites use a Windows no-console creation flag without changing command arguments or return handling.
- **SC-006**: Existing full test suite, targeted notification tests, Python compilation, JSON parsing, and PowerShell script parsing pass.

## Assumptions

- The existing confirmed states and hysteresis remain the source of truth; this feature does not reinterpret raw miner samples.
- Default polling remains 30 seconds, so a 30-second notification coalescing window adds at most one normal polling interval after state confirmation.
- In-memory reminder timing is sufficient; after a monitor restart, a still-degraded miner becomes eligible again from fresh confirmed observation.
- The virtual environment includes `pythonw.exe`, as verified on the production host.
