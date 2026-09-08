# Tasks: Hashrate Efficiency & Energy Tracking (Spec 036)

**Input**: Design artifacts from `specs/036-efficiency-energy-tracking/`  
**Risk**: LOW-MEDIUM  
**Assigned Engine**: **Gemini 3.8 Flash High** (All Phases)  

---

## Phase 1: Baseline And Red Contracts

- [x] T001 Record baseline command whitelist and power telemetry columns in `specs/036-efficiency-energy-tracking/evidence.md`.
- [x] T002 [P] Add failing tests for J/TH calculation and threshold classifications in `tests/test_energy_efficiency.py`.
- [x] T003 [P] Add failing tests for fleet overview table and detailed miner card formatting in `tests/test_energy_efficiency.py`.
- [x] T004 [P] Add failing tests for efficiency warning streak and cooldown handling in `tests/test_energy_efficiency.py`.
- [x] T005 [P] Add failing tests for SQLite telemetry extraction and fallback logic in `tests/test_energy_efficiency.py`.

---

## Phase 2: Pure Domain Module Implementation

- [x] T006 Implement `app/energy_efficiency.py` with `calculate_efficiency_j_th()`, `assess_miner_efficiency()`, `build_efficiency_table_text()`, and `build_miner_efficiency_detail_text()`.
- [x] T007 Implement `evaluate_efficiency_alerts()` and `fetch_latest_efficiency_assessments()` in `app/energy_efficiency.py`.
- [x] T008 Verify all tests in `tests/test_energy_efficiency.py` pass for Phase 2 functions.

---

## Phase 3: Monitor Integration & Command Handlers

- [x] T009 Register `efficiency` (and alias `eff`) in `CMD_WHITELIST`, `_COMMANDS`, and `/help` in `app/miner_monitor.py`.
- [x] T010 Implement `/efficiency` and `/efficiency <miner>` command handler in `app/miner_monitor.py`.
- [x] T011 Hook `efficiency_streak` and `last_efficiency_warning_ts` in `MinerState`, `load_state()`, and `save_state()`.
- [x] T012 Hook preventative efficiency evaluation into the main monitor loop in `app/miner_monitor.py`.
- [x] T013 Update `app/config.example.json` with efficiency alert configuration keys.

---

## Phase 4: Validation & Release

- [x] T014 Run full test suite regression across all test files with zero failures.
- [x] T015 Verify Python syntax with `py_compile app/miner_monitor.py app/energy_efficiency.py`.
- [x] T016 Record execution evidence, test counts, and benchmark latency in `specs/036-efficiency-energy-tracking/evidence.md`.
- [x] T017 Update `README.md`, `docs/speckit/RUNBOOK.md`, `docs/audit/DEVELOPMENT_LOG.md`, and `docs/speckit/ROADMAP.md`.

---

## Definition Of Done

- [x] `/efficiency` responds in < 50ms with fleet J/TH metrics.
- [x] `/efficiency <miner>` outputs deep single-miner energy diagnostics.
- [x] Degradation alert fires on sustained low efficiency (> 35 J/TH) and respects `/snooze`.
- [x] All unit and regression tests pass (484 tests).
- [x] Production monitor process PID 38816 remains undisturbed.
