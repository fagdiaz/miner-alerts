# Tasks: V3 Core Concurrency & Release Stabilization (Spec 038)

**Input**: Design artifacts from `specs/038-v3-release-stabilization/`  
**Risk**: HIGH  
**Assigned Engine**: **Claude Sonnet 4.6 (Thinking)** (Multi-threading, mutex coordination, queue concurrency & FSM race conditions)  

---

## Phase 1: Concurrency & Lock Audits in `miner_monitor.py`

- [x] T001 Audit `state_lock` synchronization for `MinerState` access across all Telegram commands in `app/miner_monitor.py`.
- [x] T002 Audit `state_lock` synchronization in main loop evaluation of `/snooze`, `/fans`, `/efficiency`, and `/presets`.
- [x] T003 Ensure atomic snapshotting in `save_state()` to prevent `RuntimeError: dictionary changed size during iteration`.

---

## Phase 2: Callback Query Dispatcher & Token Concurrency

- [x] T004 Audit `pending_reboot_tokens` thread-safety and token consumption atomicity in `app/telegram_callbacks.py` and `app/miner_monitor.py`.
- [x] T005 Audit timeout handling in `answer_callback_query()` and `edit_message_reply_markup()` ensuring non-blocking behavior.

---

## Phase 3: SQLite Connection Concurrency & Cleanup

- [x] T006 Audit `conn.close()` hygiene in `finally:` blocks across `telegram_charts.py`, `daily_digest.py`, `fan_health.py`, `energy_efficiency.py`, `vnish_presets.py`.
- [x] T007 Verify all read URIs strictly use `?mode=ro` and explicit timeouts <= 2.0s.

---

## Phase 4: Deterministic Concurrency Test Suite

- [x] T008 Create `tests/test_v3_concurrency.py` with multi-threaded stress tests simulating concurrent commands, callbacks, and polling loops.
- [x] T009 Verify all concurrency tests pass without deadlocks or race conditions.

---

## Phase 5: Release Candidate V3 Certification

- [x] T010 Run full test suite regression across all test files (all 495+ tests must pass).
- [x] T011 Verify Python syntax with `py_compile`.
- [x] T012 Verify production process `PID 38816` remains active and healthy.
- [x] T013 Update `specs/038-v3-release-stabilization/evidence.md` with audit logs and test metrics.
- [x] T014 Update `docs/audit/DEVELOPMENT_LOG.md` and `docs/speckit/ROADMAP.md`.
