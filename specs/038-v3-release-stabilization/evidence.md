# Evidence: V3 Core Concurrency & Release Stabilization (Spec 038)

**Feature**: V3 Core Concurrency & Release Stabilization  
**Branch**: `codex/038-v3-release-stabilization`  
**Date**: 2026-09-07  
**Status**: CERTIFIED & COMPLETED  
**Assigned Engine**: **Claude Sonnet 4.6 (Thinking) + Gemini 3.8 Flash High (Multi-Model Collaboration)**  

---

## 1. Baseline Evidence

### Test Suite Baseline:
```text
495 tests PASS in 5.048s across all test suites prior to concurrency hardening.
0 failures, 0 errors.
```

### Production Process Soak:
```text
PID 38816 running continuously > 267.3 hours with > 4,611 CPU seconds.
Memory: ~35.0 MB WorkingSet.
```

### Remote Dashboard & Metrics Server:
```text
tools/serve_monitor_ui.py running on port 8080 (background task-867).
Grafana running on port 3000.
```

---

## 2. Concurrency Audit Findings & Hardening

1. **`CallbackTokenRegistry` Thread Safety**:
   - Initial run of `test_rapid_cycle_no_exceptions` caught:
     `RuntimeError: dictionary changed size during iteration` when 5 threads concurrently issued `rb_req`, `rb_cfm`, and `rb_ccl`.
   - **Fix Applied**: Equipped `CallbackTokenRegistry` with `self._lock = threading.Lock()` and snapshot iteration `list(self._tokens.items())`.
   - **Result**: Zero contention exceptions, single-use token semantics verified.

2. **SQLite Connection Hygiene**:
   - `fetch_latest_cooling_assessments` (`app/fan_health.py`) and `fetch_latest_efficiency_assessments` (`app/energy_efficiency.py`) updated to enforce strict `finally: if conn: conn.close()` alongside `?mode=ro` and `timeout=2.0s`.
   - Verified read-under-write safety without database lock contention against production `PID 38816`.

3. **`save_state()` Dictionary Iteration**:
   - Updated `save_state()` in `app/miner_monitor.py` to iterate over `list(states.items())`, preventing concurrent modification exceptions during live state saving.

---

## 3. Concurrency Test Suite Results

### `tests/test_v3_concurrency.py`:
```text
...................
----------------------------------------------------------------------
Ran 19 tests in 1.233s

OK
```

### Full Repository Regression Suite:
```text
----------------------------------------------------------------------
Ran 514 tests in 14.610s

OK
```

---

## 4. Release Candidate V3 Certification Gate

- **Total Specs Completed**: 38 of 38 (100% of V1, V2, and V3 Roadmap).
- **Zero Regressions**: 514/514 passing automated tests.
- **Live Production Soak**: PID 38816 running undisturbed > 267.3 hours.
- **Outcome**: **RELEASE CANDIDATE V3.0.0 APPROVED**.
