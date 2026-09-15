# Requirements Checklist: Spec 060 — Monitor Core Daemon & State Manager Architecture (ST-01 / ST-02 - Milestone V5.0)

## Baseline & Gates

- [x] Base branch is `codex/022-adaptive-acquisition`.
- [x] Initial regression suite passes (928 tests PASS in 12.77s).
- [x] No changes committed to `app/config.json` or `app/state.json`.

## Requirements Validation

- [x] **R1 (StateManager)**: `app/core/state_manager.py` implements pure snapshot building in memory under `state_lock` (L1) and disk flushing under `_flush_lock` (L2), eliminating NTFS fsync retention on `state_lock`.
- [x] **R2 (MonitorContext)**: `app/core/context.py` encapsulates all runtime dependencies via `MonitorContext` and `build_monitor_context`.
- [x] **R3 (CoreSupervisoryEngine)**: `app/core/engine.py` provides hook orchestration and `TickResult` lifecycle for the 30s supervisor.
- [x] **R4 (main() Compatibility)**: `main()` in `app/miner_monitor.py` instantiates `state_manager` and `monitor_ctx` without modifying block order or breaking static `inspect.getsource(main)` contracts.
- [x] **R5 (Unit Test Coverage)**: `tests/test_core_daemon.py` tests all components (7 tests PASS).
- [x] **R6 (Regression Invariant)**: 100% of global test suite passes (935/935 tests PASS in 13.531s).
