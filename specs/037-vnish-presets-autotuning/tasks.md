# Tasks: Vnish Preset & Autotuning Dynamic Tracking (Spec 037)

**Input**: Design artifacts from `specs/037-vnish-presets-autotuning/`  
**Risk**: LOW-MEDIUM  
**Assigned Engine**: **Gemini 3.8 Flash High** (All Phases)  

---

## Phase 1: Baseline And Red Contracts

- [x] T001 Record baseline command whitelist and telemetry frequency columns in `specs/037-vnish-presets-autotuning/evidence.md`.
- [x] T002 [P] Add failing tests for profile inference and tuning status classifications in `tests/test_vnish_presets.py`.
- [x] T003 [P] Add failing tests for fleet overview table and detailed miner card formatting in `tests/test_vnish_presets.py`.
- [x] T004 [P] Add failing tests for downclock alert triggers and cooldown suppression in `tests/test_vnish_presets.py`.
- [x] T005 [P] Add failing tests for SQLite telemetry and firmware events correlation in `tests/test_vnish_presets.py`.

---

## Phase 2: Pure Domain Module Implementation

- [x] T006 Implement `app/vnish_presets.py` with `infer_operating_profile()`, `assess_miner_preset()`, `build_presets_table_text()`, and `build_miner_preset_detail_text()`.
- [x] T007 Implement `evaluate_preset_alerts()` and `fetch_latest_preset_assessments()` in `app/vnish_presets.py`.
- [x] T008 Verify all tests in `tests/test_vnish_presets.py` pass for Phase 2 functions.

---

## Phase 3: Monitor Integration & Command Handlers

- [x] T009 Register `presets`, `preset`, `profile` in `CMD_WHITELIST`, `_COMMANDS`, and `/help` in `app/miner_monitor.py`.
- [x] T010 Implement `/presets` and `/presets <miner>` command handler in `app/miner_monitor.py`.
- [x] T011 Hook `baseline_frequency_mhz` and `last_preset_warning_ts` in `MinerState`, `load_state()`, and `save_state()`.
- [x] T012 Hook preventative profile/downclock evaluation into the main monitor loop in `app/miner_monitor.py`.
- [x] T013 Update `app/config.example.json` with preset alert configuration keys.

---

## Phase 4: Validation & Release

- [x] T014 Run full test suite regression across all test files with zero failures.
- [x] T015 Verify Python syntax with `py_compile app/miner_monitor.py app/vnish_presets.py`.
- [x] T016 Record execution evidence, test counts, and benchmark latency in `specs/037-vnish-presets-autotuning/evidence.md`.
- [x] T017 Update `README.md`, `docs/speckit/RUNBOOK.md`, `docs/audit/DEVELOPMENT_LOG.md`, and `docs/speckit/ROADMAP.md`.

---

## Definition Of Done

- [x] `/presets` responds in < 50ms with fleet MHz, V, W, TH/s and tuning status.
- [x] `/presets <miner>` outputs deep single-miner profile diagnostics and recent tuning events.
- [x] Downclock alert fires on sustained drop ($\ge 25\text{ MHz}$) and respects `/snooze`.
- [x] All unit and regression tests pass.
- [x] Production monitor process PID 38816 remains undisturbed.
