# Feature Specification: Telegram Interactive Callbacks & Inline Keyboards

**Feature Branch**: `codex/031-telegram-interactive-callbacks`  
**Created**: 2026-09-07  
**Status**: Draft / SpecKit Ready  
**Input**: Telegram Max Initiative (V3 Expansion Plan) — Implement 1-Tap interactive buttons (Inline Keyboards) and asynchronous callback query handling without disrupting the monitor's live polling or reboot safety.  
**Risk Class**: MEDIUM-HIGH (touches Telegram network polling loop and confirmation state in `app/miner_monitor.py`)  
**Assigned Engine**: Claude Sonnet 4.6 (Thinking) for live concurrency/dispatcher implementation; Gemini 3.8 Flash High for testing, contracts, schemas and SpecKit tracking.  

---

## User Scenarios & Testing

### User Story 1 - One-Tap Immediate Diagnostic and Inspection (Priority: P1)

An operator receives a Telegram alert for an irregular episode (e.g., LOW hashrate or board drop) and can immediately tap an inline button below the message (`[ 🩺 Diagnosticar ]` or `[ 📊 Ver Gráfico ]`) without typing commands or looking up miner names.

**Why this priority**: Minimizes operator reaction time during active incidents and eliminates typo errors when executing diagnostic queries.

**Independent Test**: Mock a Telegram alert payload with inline markup, simulate tapping `[ 🩺 Diagnosticar ]` via a synthetic `callback_query`, and verify that the diagnostic summary is dispatched to the chat and the callback is answered with HTTP 200 within 1.0s.

**Acceptance Scenarios**:
1. **Given** an episode alert is sent for `S19JPRO-23`, **When** the message is rendered, **Then** it includes an `inline_keyboard` with `[ 🩺 Diagnosticar 23 ]` and `[ 🔄 Reiniciar 23 ]`.
2. **Given** the operator taps `[ 🩺 Diagnosticar 23 ]`, **When** the callback reaches the poller, **Then** `answerCallbackQuery` is invoked immediately, and `/diagnose 23` output is queued for delivery.

---

### User Story 2 - Safe Two-Step Interactive Reboot Confirmation (Priority: P1)

An operator requests a reboot by tapping `[ 🔄 Reiniciar 23 ]`. Instead of immediately executing the reboot or requiring manual typing of `/c<code>`, the message's inline keyboard updates in-place to display `[ ✅ Confirmar Reinicio ]` and `[ ❌ Cancelar ]` with a 60-second timeout.

**Why this priority**: Prevents accidental physical reboots from accidental pocket-taps while preserving click-safe, zero-typing ergonomics.

**Independent Test**: Simulate tapping `reboot:23`, verify the keyboard is updated via `editMessageReplyMarkup` with a temporary confirmation token, verify confirmation within 60s triggers reboot authorization, and verify confirmation after 61s is rejected as expired.

**Acceptance Scenarios**:
1. **Given** an alert with `[ 🔄 Reiniciar 23 ]`, **When** the operator taps the button, **Then** the message keyboard changes to `[ ✅ Confirmar Reinicio 23 ]` and `[ ❌ Cancelar ]`, and a toast notification "Confirmación requerida (expira en 60s)" is displayed.
2. **Given** the confirmation keyboard is active, **When** the operator taps `[ ✅ Confirmar Reinicio 23 ]` within 60 seconds, **Then** the standard reboot authorization flow executes, and the buttons are edited to `[ 🔄 Reinicio Solicitado ]` (disabled).
3. **Given** the confirmation keyboard is active, **When** the operator taps `[ ❌ Cancelar ]` or 60 seconds elapse, **Then** the confirmation token is invalidated and buttons return to their neutral state.

---

### User Story 3 - Robust Callback Polling & Security Shield (Priority: P1)

The monitor's polling loop receives both normal text `message` updates and `callback_query` updates, verifying strict authorization (`chat_id` match) and answering callbacks before network timeouts occur.

**Why this priority**: Telegram clients show an infinite spinning wheel if a callback is not acknowledged via `answerCallbackQuery` within 10 seconds. Unauthorized users in group chats must not be able to interact with buttons.

**Independent Test**: Send callbacks from authorized `chat_id` and unauthorized `chat_id`. Verify unauthorized callbacks receive an alert "Acceso no autorizado" and execute zero monitor actions.

**Acceptance Scenarios**:
1. **Given** an update contains a `callback_query`, **When** processed by the poller, **Then** `answerCallbackQuery` is called with the matching `callback_query_id`.
2. **Given** an update originates from an unauthorized user ID, **When** processed, **Then** no action is taken, and a warning log is recorded.

---

### User Story 4 - Legacy and Plain Text Command Backward Compatibility (Priority: P2)

Operators or automated scripts using existing text commands (`/status`, `/diagnose`, `/rb23`, `/c123456`) experience zero disruption or syntax changes.

**Why this priority**: Guarantees that clients without inline keyboard support or operators accustomed to text commands retain 100% operational control.

**Independent Test**: Run full suite of existing 416 unit tests and verify all text command regexes, aliases, and click-safe helpers execute without regression.

**Acceptance Scenarios**:
1. **Given** an operator types `/rb23` or `/reboot_no_ok`, **When** received, **Then** the existing text-based confirmation code flow works identically.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST process `callback_query` payload items in `_poll_telegram_updates()` without blocking or crashing the poller thread.
- **FR-002**: System MUST call Telegram `answerCallbackQuery` within 2.0 seconds for every received callback query.
- **FR-003**: System MUST reject any callback originating from a user or chat ID different from `config["telegram"]["chat_id"]`.
- **FR-004**: System MUST format inline keyboards using standard Telegram Bot API `inline_keyboard` JSON payload attached to `reply_markup`.
- **FR-005**: Reboot action via callback MUST require an explicit two-tap sequence: `ask_reboot:<miner>` followed by `confirm_reboot:<token>:<miner>`.
- **FR-006**: Confirmation tokens MUST be cryptographically random (or short HMAC) and expire after exactly 60 seconds.
- **FR-007**: When a reboot is confirmed, cancelled, or expired, the message MUST be updated via `editMessageReplyMarkup` to eliminate duplicate taps.
- **FR-008**: All existing text commands and click-safe aliases MUST remain fully functional.

### Non-Functional & Safety Requirements

- **NFR-001**: Concurrency: Callback handling MUST NOT hold any lock across network socket operations.
- **NFR-002**: Production Safety: Production PID 38816 safety interlocks (cooldowns, startup guard, sustained low requirements) MUST be strictly preserved.
- **NFR-003**: Performance: Answering callbacks MUST have a median latency under 500ms.

---

## Success Criteria

- **SC-001**: 100% of recognized callback queries receive an `answerCallbackQuery` response without client spinner timeouts.
- **SC-002**: Accidental single-tap reboots are 100% prevented by the 2-step interactive flow.
- **SC-003**: Zero regressions across the 416 existing unit and integration tests.
