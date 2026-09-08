# Feature Specification: Miner Maintenance Snooze (Spec 033)

**Feature Branch**: `codex/033-miner-maintenance-snooze`  
**Created**: 2026-09-07  
**Status**: Ready / SpecKit Active  
**Input**: Telegram Max Initiative (V3 Expansion Plan) — Temporary alert & auto-reboot suppression per miner for physical maintenance, fan cleaning, PSU servicing, or planned downtime via `/snooze`, `/unsnooze`, `/snoozed` and alert inline button `[ 🔕 Silenciar 1h ]`.  
**Risk Class**: LOW-MEDIUM (State persistence, Alert & reboot suppression, Telegram command & callback query dispatch)  
**Assigned Engine**: **Gemini 3.8 Flash High** (Pure domain logic, state serialization, command parsing, filter predicates, and comprehensive test suite).  

---

## User Scenarios & Testing

### User Story 1 - 1-Tap Snooze Directly from Episode Alerts (Priority: P1)

An operator receives a critical alert (e.g. LOW hashrate due to heat or OFFLINE due to maintenance). Rather than dealing with repetitive notification spam or race conditions with auto-reboots while physically fixing the miner, the operator taps `[ 🔕 Silenciar 1h ]`.

**Why this priority**: When a miner is down for hardware servicing, receiving reminders every 5-10 minutes and having the system attempt auto-reboots while wires are disconnected creates confusion and operational hazard.

**Independent Test**: Simulate an episode alert with inline buttons, trigger callback `snz:23:60`, verify callback acknowledgment `answerCallbackQuery(text="🔕 S19JPRO-23 silenciado por 60 min")`, assert keyboard transitions to settled state (`[ 🔕 Silenciado (60m) ]`), and verify `snooze_until_ts` is set in state.

**Acceptance Scenarios**:
1. **Given** an episode alert with `[ 🔕 Silenciar 1h ]`, **When** the operator taps the button, **Then** the bot confirms with a toast notification, updates the message keyboard to `[ 🔕 Silenciado (60m) ]`, and sets a 60-minute suppression window.
2. **Given** a miner under active snooze, **When** subsequent evaluation ticks occur while the miner remains in `STATE_LOW` or `STATE_OFFLINE`, **Then** no new irregular episode alerts or persistent outage reminders are sent to Telegram.

---

### User Story 2 - Telegram Operational Commands for Maintenance Windows (Priority: P1)

An operator plans to service one or more miners and executes `/snooze 23 120` (or `/snooze all 30`) before touching the equipment.

**Why this priority**: Operators require full proactive control over suppression windows of variable duration (e.g. 15 min, 1h, 2h, up to 24h) before an alert even fires.

**Independent Test**: Issue `/snooze 23 45`, `/snooze all 15`, `/snoozed`, and `/unsnooze 23` via mock dispatcher and verify state transitions and output messages.

**Acceptance Scenarios**:
1. **Given** a valid miner ID, **When** `/snooze 23 [minutes]` is sent, **Then** the bot silences the miner for the specified duration (default: 60m, min: 1m, max: 1440m/24h) and replies with the exact local expiry time.
2. **Given** the argument `all` or `fleet`, **When** `/snooze all 60` is executed, **Then** all configured miners are snoozed.
3. **Given** one or more snoozed miners, **When** `/snoozed` is called, **Then** the bot displays each snoozed miner, remaining time (e.g. `42m`), and expiry timestamp. If none are snoozed, it reports all miners are under active supervision.
4. **Given** a snoozed miner, **When** `/unsnooze 23` is sent, **Then** snooze is immediately revoked, resuming normal alert and auto-reboot monitoring.

---

### User Story 3 - Absolute Auto-Reboot Safety Suppression (Priority: P1)

While a miner is snoozed, the auto-reboot policy must be strictly suppressed for that miner.

**Why this priority**: CRITICAL SAFETY. If an operator has disconnected power or fans from an ASIC to replace parts, an automated reboot trigger could damage hardware or attempt socket connections into broken states.

**Independent Test**: Configure a miner with `low_streak` exceeding threshold and `reboot_pending_until` active; set `snooze_until_ts = now + 3600`; execute monitoring tick and assert `reboot_names_tick` does NOT include the snoozed miner.

**Acceptance Scenarios**:
1. **Given** a snoozed miner whose metrics qualify for auto-reboot, **When** the monitoring evaluation loop runs, **Then** auto-reboot is skipped and logged as `AUTO_REBOOT_SNOOZED`.

---

### User Story 4 - State Persistence & Zero-Touch Natural Expiry (Priority: P2)

Active snoozes are persisted in `app/state.json` so process restarts or watchdog recoveries do not prematurely cancel maintenance windows. When the timer expires, normal supervision resumes automatically.

**Acceptance Scenarios**:
1. **Given** an active snooze, **When** `miner_monitor.py` reboots and calls `load_state()`, **Then** the active `snooze_until_ts` is restored.
2. **Given** a snooze whose timestamp has passed (`now_ts >= snooze_until_ts`), **When** monitored, **Then** `is_miner_snoozed()` returns `False` and normal alerts resume seamlessly.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST support Telegram commands:
  - `/snooze <miner_id|all> [minutes]` (default 60 minutes, clamped between 1 and 1440).
  - `/unsnooze <miner_id|all>`: immediately clears snooze.
  - `/snoozed`: lists all snoozed miners with remaining time in minutes/hours.
- **FR-002**: System MUST handle `snz:<miner_id>:<minutes>` callback query from inline alert buttons:
  - Acknowledge callback immediately (< 1.0s) via `answerCallbackQuery`.
  - Update message markup to settled state `[ 🔕 Silenciado ({minutes}m) ]`.
  - Set `snooze_until_ts` on the miner state.
- **FR-003**: While a miner is snoozed:
  - Irregular episode alerts for this miner MUST be suppressed.
  - Persistent outage reminders for this miner MUST be suppressed.
  - Degraded hourly status notifications for this miner MUST be suppressed.
  - Automatic reboots (`auto_reboot`) for this miner MUST be strictly blocked.
- **FR-004**: System MUST persist `snooze_until_ts` in `app/state.json` across restarts.
- **FR-005**: `/status` output MUST visually badge snoozed miners with `[🔕 Silenciado: Xm rest.]`.
- **FR-006**: Command help (`/help`) and command whitelist MUST include `snooze`, `unsnooze`, and `snoozed`.

### Non-Functional & Safety Requirements

- **NFR-001**: Thread safety: state mutations (`snooze_until_ts`) must be protected by `state_lock`.
- **NFR-002**: Pure modular design: core parsing, formatting, and predicate logic isolated in `app/telegram_snooze.py`.
- **NFR-003**: Zero disruption to running production monitor PID 38816.

---

## Success Criteria

- **SC-001**: Clicking `[ 🔕 Silenciar 1h ]` on an alert confirms in < 500ms and edits the button to a settled state.
- **SC-002**: 100% of auto-reboots and alert notifications are suppressed for snoozed miners during the snooze window.
- **SC-003**: 100% unit and integration test coverage across all snooze workflows with 0 regressions.
