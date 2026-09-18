# Tasks: Spec 074 - Paired Elevator Contingency & Inrush Dampener

- [x] T001: Extend `GroupContingencyState` and `ContingencyDecision` with backwards-compatible paired inrush fields in `app/governance/adaptive_contingency.py`.
- [x] T002: Implement `evaluate_paired_contingency` / inrush dampening calculation in `app/governance/adaptive_contingency.py`.
- [x] T003: Update `set_miner_preset` in `app/vnish/client.py` to support `clamp_top_preset=True`.
- [x] T004: Update `compute_governor_step` in `app/governance/fan_governor.py` with `is_warming_up` and `< 500W` guard for `RECOVERY_MAX_COOLING`.
- [x] T005: Harden `app/miner_monitor.py` line 6157 and line 7558 with `normalize_miner_name` matching and state preset synchronization.
- [x] T006: Create comprehensive test suite `tests/test_paired_elevator_contingency.py` covering all 4 hardening pillars.
- [x] T007: Run full regression suite and verify 100% PASS across all unit tests.
