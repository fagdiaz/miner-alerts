# Tasks: Miner Maintenance Snooze (Spec 033)

**Input**: Design artifacts from `specs/033-miner-maintenance-snooze/`  
**Risk**: LOW-MEDIUM  
**Assigned Engine**: **Gemini 3.8 Flash High** (All Phases)  

---

## Phase 1: Baseline And Red Contracts

- [x] T001 Record baseline command registry and state schema in `specs/033-miner-maintenance-snooze/evidence.md`.
- [x] T002 [P] Add failing tests for duration parsing, clamping, and remaining time formatting in `tests/test_telegram_snooze.py`.
- [x] T003 [P] Add failing tests for auto-reboot suppression invariant when miner is snoozed in `tests/test_telegram_snooze.py`.
- [x] T004 [P] Add failing tests for alert episode suppression when miner is snoozed in `tests/test_telegram_snooze.py`.
- [x] T005 [P] Add failing tests for `snz:<miner_id>:<minutes>` callback handling and markup edit in `tests/test_telegram_snooze.py`.

---

## Phase 2: Pure Domain Module Implementation

- [x] T006 Implement `app/telegram_snooze.py` with `parse_snooze_duration()`, `is_miner_snoozed()`, `format_snooze_remaining()`, and `build_snooze_status_text()`.
- [x] T007 Add `filter_snoozed_episodes()` helper to detect and suppress snoozed miners from episode notifications.
- [x] T008 Verify unit tests in `tests/test_telegram_snooze.py` pass for Phase 2 functions.

---

## Phase 3: Monitor State & Command Integration

- [x] T009 Add `snooze_until_ts` to `MinerState`, update `load_state()` and `save_state()` in `app/miner_monitor.py`.
- [x] T010 Register `snooze`, `unsnooze`, `snoozed` in `CMD_WHITELIST` and command dispatcher in `app/miner_monitor.py`.
- [x] T011 Wire `snz` callback action in `_handle_callback_query()` in `app/miner_monitor.py`.
- [x] T012 Apply auto-reboot suppression check (`is_miner_snoozed`) in the monitor evaluation loop in `app/miner_monitor.py`.
- [x] T013 Apply alert episode suppression check for snoozed miners before dispatching notifications in `app/miner_monitor.py`.
- [x] T014 Badge snoozed status in `/status` output lines.

---

## Phase 4: Validation & Release

- [x] T015 Run full test suite regression across all test files with zero failures.
- [x] T016 Verify Python syntax with `py_compile app/miner_monitor.py app/telegram_snooze.py`.
- [x] T017 Record execution evidence in `specs/033-miner-maintenance-snooze/evidence.md`.
- [x] T018 Update `README.md`, `docs/speckit/RUNBOOK.md`, `docs/audit/DEVELOPMENT_LOG.md`, and `docs/speckit/ROADMAP.md`.

---

## Definition Of Done

- [x] `/snooze`, `/unsnooze`, `/snoozed` commands fully functional.
- [x] Inline button `[ 🔕 Silenciar 1h ]` snoozes miner and edits keyboard to settled state.
- [x] Auto-reboots and alert notifications are 100% suppressed during active snooze.
- [x] Active snooze survives process restart via `app/state.json`.
- [x] All unit and regression tests pass (448 tests).
- [x] Production process PID 38816 remains completely undisturbed.
