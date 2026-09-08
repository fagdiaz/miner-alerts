# Tasks: Telegram Interactive Callbacks & Inline Keyboards (Spec 031)

**Input**: Design artifacts from `specs/031-telegram-interactive-callbacks/`  
**Risk**: MEDIUM-HIGH  
**Model Delegation Protocol**:  
- **Gemini 3.8 Flash High**: Phases 1, 2, 4, 5 (Test fixtures, pure logic in `app/telegram_callbacks.py`, regression validation, documentation).  
- **Claude Sonnet 4.6 (Thinking)**: Phase 3 (Live multi-threaded polling loop and callback query dispatcher in `app/miner_monitor.py`).

---

## Phase 1: Baseline And Red Contracts (Gemini 3.8 Flash High)

- [x] T001 Capture baseline polling and command update contract in `specs/031-telegram-interactive-callbacks/evidence.md`.
- [x] T002 [P] Add failing tests for callback grammar parsing and length constraints (< 64 bytes) in `tests/test_telegram_callbacks.py`.
- [x] T003 [P] Add failing tests for 60s confirmation token creation, validation, consumption, and expiration in `tests/test_telegram_callbacks.py`.
- [x] T004 [P] Add failing tests for inline keyboard JSON structure validation in `tests/test_telegram_callbacks.py`.

---

## Phase 2: Pure Callback Helper Module (Gemini 3.8 Flash High)

- [x] T005 Implement `CallbackTokenRegistry` with bounded size and 60-second TTL in `app/telegram_callbacks.py`.
- [x] T006 Implement deterministic callback action parser and serializer in `app/telegram_callbacks.py`.
- [x] T007 Implement keyboard layout builders (`build_alert_keyboard`, `build_confirmation_keyboard`, `build_settled_keyboard`) in `app/telegram_callbacks.py`.
- [x] T008 Verify Phase 1 tests pass against `app/telegram_callbacks.py`.

---

## Phase 3: Poller & Dispatcher Integration (Claude Sonnet 4.6 Thinking)

- [x] T009 [US3] Implement `answer_callback_query` and `edit_message_reply_markup` safe HTTP helpers in `app/miner_monitor.py`.
- [x] T010 [US1] Extend `send_telegram` and message queue tuple in `app/miner_monitor.py` to optionally pass `reply_markup`.
- [x] T011 [US3] Update `_poll_telegram_updates()` in `app/miner_monitor.py` to parse `callback_query` objects in addition to `message` updates.
- [x] T012 [US1,US2] Implement `_handle_callback_query()` in `app/miner_monitor.py` implementing strict authentication (`chat_id`), instant diagnostic invocation, and 2-step reboot confirmation (`rb_req` -> `rb_cfm`).
- [x] T013 [US1] Wire episode alert notifications in `app/alert_episodes.py` to attach `build_alert_keyboard()`.

---

## Phase 4: Safety Invariants & Regression Control (Gemini 3.8 Flash High)

- [x] T014 [US3] Verify unauthorized callback attempts produce 0 monitor actions and are rejected in `tests/test_telegram_callbacks.py`.
- [x] T015 [US2] Verify expired tokens (> 60s) reject reboots cleanly with user alert toast in `tests/test_telegram_callbacks.py`.
- [x] T016 Run full test suite regression (all 416 existing tests + new tests) with zero failures.
- [x] T017 Verify Python syntax with `py_compile app/miner_monitor.py app/telegram_callbacks.py`.

---

## Phase 5: Verification & Documentation (Gemini 3.8 Flash High)

- [x] T018 Record mock command & callback test run evidence in `specs/031-telegram-interactive-callbacks/evidence.md`.
- [x] T019 Update `README.md` and `docs/speckit/RUNBOOK.md` with the interactive Telegram buttons guide.
- [x] T020 Add entry to `docs/audit/DEVELOPMENT_LOG.md` and update `docs/speckit/ROADMAP.md`.

---

## Definition Of Done

- [x] Interactive buttons render on Telegram episode alerts.
- [x] `callback_query` is acknowledged within 1.0s.
- [x] Reboot requires two explicit taps and expires after 60s.
- [x] All 430 tests PASS with zero regressions.
- [x] Production process PID 38816 safety interlocks remain intact.
