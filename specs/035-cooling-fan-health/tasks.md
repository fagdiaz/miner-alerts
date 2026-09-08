# Tasks: Cooling & Fan Health Intelligence (Spec 035)

**Input**: Design artifacts from `specs/035-cooling-fan-health/`  
**Risk**: LOW-MEDIUM  
**Assigned Engine**: **Gemini 3.8 Flash High** (All Phases)  

---

## Phase 1: Baseline And Red Contracts

- [x] T001 Record baseline command registry and database columns in `specs/035-cooling-fan-health/evidence.md`.
- [x] T002 [P] Add failing tests for cooling classification rules (HEALTHY, ELEVATED, SATURATED, CRITICAL_HEAT, FAN_DEFECT) in `tests/test_fan_health.py`.
- [x] T003 [P] Add failing tests for thermal headroom calculation in `tests/test_fan_health.py`.
- [x] T004 [P] Add failing tests for fleet table and single miner detail rendering in `tests/test_fan_health.py`.
- [x] T005 [P] Add failing tests for preventative warning streak detection and cooldown suppression in `tests/test_fan_health.py`.

---

## Phase 2: Pure Domain Module Implementation

- [x] T006 Implement `app/fan_health.py` with `assess_miner_cooling()`, `calculate_thermal_headroom()`, `build_fans_table_text()`, and `build_miner_fan_detail_text()`.
- [x] T007 Implement `evaluate_cooling_alerts()` in `app/fan_health.py` with streak and cooldown handling.
- [x] T008 Verify all tests in `tests/test_fan_health.py` pass for Phase 2 functions.

---

## Phase 3: Monitor Integration & Command Handlers

- [x] T009 Register `fans` (and alias `fan`) in `CMD_WHITELIST`, `_COMMANDS`, and `/help` in `app/miner_monitor.py`.
- [x] T010 Implement `/fans` and `/fans <miner>` command handler in `app/miner_monitor.py`.
- [x] T011 Hook `cooling_streak` and `last_cooling_warning_ts` in `MinerState`, `load_state()`, and `save_state()`.
- [x] T012 Hook preventative cooling alert evaluation into the main monitor loop in `app/miner_monitor.py`.
- [x] T013 Update `app/config.example.json` with cooling alert configuration keys.

---

## Phase 4: Validation & Release

- [x] T014 Run full test suite regression across all test files with zero failures.
- [x] T015 Verify Python syntax with `py_compile app/miner_monitor.py app/fan_health.py`.
- [x] T016 Record execution evidence, test counts, and benchmark latency in `specs/035-cooling-fan-health/evidence.md`.
- [x] T017 Update `README.md`, `docs/speckit/RUNBOOK.md`, `docs/audit/DEVELOPMENT_LOG.md`, and `docs/speckit/ROADMAP.md`.

---

## Definition Of Done

- [x] `/fans` command responds instantly (< 100ms) with fleet fan/thermal status.
- [x] `/fans <miner>` outputs deep cooling diagnostics and recommendations.
- [x] Thermal headroom and saturation warning prevent 85°C shutdowns.
- [x] Zero database locks; zero temp files.
- [x] All unit and regression tests pass (472 tests).
- [x] Production monitor process PID 38816 remains undisturbed.
