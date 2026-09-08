# Tasks: Daily Executive Digest (Spec 034)

**Input**: Design artifacts from `specs/034-daily-executive-digest/`  
**Risk**: LOW-MEDIUM  
**Assigned Engine**: **Gemini 3.8 Flash High** (All Phases)  

---

## Phase 1: Baseline And Red Contracts

- [x] T001 Record baseline command registry and database schema in `specs/034-daily-executive-digest/evidence.md`.
- [x] T002 [P] Add failing tests for metrics aggregation formulas (uptime, TH/s, J/TH, shares %) in `tests/test_daily_digest.py`.
- [x] T003 [P] Add failing tests for card rendering and formatting in `tests/test_daily_digest.py`.
- [x] T004 [P] Add failing tests for scheduling trigger logic (`is_digest_due`, rollover, once-per-day) in `tests/test_daily_digest.py`.
- [x] T005 [P] Add failing tests for backup status discovery and fallback when empty in `tests/test_daily_digest.py`.

---

## Phase 2: Pure Domain Module Implementation

- [x] T006 Implement `app/daily_digest.py` with `fetch_daily_digest_metrics()`, `format_daily_digest()`, and `inspect_latest_backup()`.
- [x] T007 Implement `is_digest_due()` in `app/daily_digest.py`.
- [x] T008 Verify unit tests in `tests/test_daily_digest.py` pass for Phase 2 functions.

---

## Phase 3: Monitor Integration & Command Handlers

- [x] T009 Register `digest` (and alias `summary`) in `CMD_WHITELIST`, `_COMMANDS`, and `/help` in `app/miner_monitor.py`.
- [x] T010 Implement `/digest` command handler in `app/miner_monitor.py`.
- [x] T011 Implement scheduled morning dispatch check in the main monitor evaluation loop in `app/miner_monitor.py`.
- [x] T012 Persist `last_daily_digest_date` in `load_state()` and `save_state()` in `app/miner_monitor.py`.
- [x] T013 Update `app/config.example.json` with `daily_digest_enabled` and `daily_digest_time`.

---

## Phase 4: Validation & Release

- [x] T014 Run full test suite regression across all test files with zero failures.
- [x] T015 Verify Python syntax with `py_compile app/miner_monitor.py app/daily_digest.py`.
- [x] T016 Record execution evidence and performance benchmarks in `specs/034-daily-executive-digest/evidence.md`.
- [x] T017 Update `README.md`, `docs/speckit/RUNBOOK.md`, `docs/audit/DEVELOPMENT_LOG.md`, and `docs/speckit/ROADMAP.md`.

---

## Definition Of Done

- [x] Scheduled daily digest dispatches reliably once per day at configured time.
- [x] `/digest` command delivers 24h summary instantly.
- [x] All metrics (uptime, TH/s, J/TH, shares %, incidents, backup) mathematically verified.
- [x] Zero temporary disk files and zero database write locks.
- [x] All unit and regression tests pass (458 tests).
- [x] Production process PID 38816 remains completely undisturbed.
