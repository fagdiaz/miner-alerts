# Evidence - Spec 055: Auto-Reboot ante Falla de Placa y Recuperación Automática de Hashboard

## 1. Syntax Compilation Verification

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py tests\test_hashboard_auto_reboot.py
# Exit Code: 0 (Clean)
```

## 2. Unit and Pipeline Test Execution

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_hashboard_auto_reboot
```

Output:
```
..............
----------------------------------------------------------------------
Ran 14 tests in 0.022s

OK
```

Test Cases Covered:
1. `test_state_low_preserves_original_behavior`: 100% backward compatibility for `STATE_LOW`.
2. `test_state_ok_never_allows_evaluation`: `STATE_OK` always rejected.
3. `test_hashboard_total_failure_with_timer_allows_evaluation`: 0/3 boards with `hashboard_since_ts` allows evaluation.
4. `test_hashboard_total_failure_without_timer_blocks_evaluation`: Missing timer blocks evaluation.
5. `test_hashboard_total_failure_with_invalid_signal_blocks_evaluation`: Unresponsive miner blocks evaluation.
6. `test_hashboard_partial_failure_policy`: Enforces `allow_partial_hashboard` configuration gate.
7. `test_hashboard_disabled_by_config_blocks_evaluation`: Feature flag disabling stops evaluation.
8. `test_reset_sustained_hashboard_if_ineligible`: Reset behavior on restored boards, invalid signals, or partial failures.
9. `test_miner_state_hashboard_since_ts_serialization`: Model field serialization and deserialization.
10. `test_hashboard_timer_advances_deterministically`: Monotonic progress of `hashboard_since_ts` across ticks.
11. `test_hashboard_timer_resets_on_recovery_to_ok`: State recovery clears timer.
12. `test_hashboard_timer_resets_on_reboot_detected`: Telemetry elapsed reset clears timer.
13. `test_runtime_wiring_hashboard_reboot_pipeline_preserves_interlocks`: Source AST verification confirming:
    - `startup_guard < sustained < interlocks < cooldown < window < hashcore`
    - Firmware transition guard resets `hashboard_since_ts` to `now_ts`
    - Hashcore action resets both timers
    - Telegram alert format verified
14. `test_record_auto_reboot_decision_populates_hashboard_elapsed`: EventStore records `low_elapsed_seconds=600.0` from `hashboard_since_ts`.

## 3. Targeted Invariant Regression Checks

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_auto_reboot_signal_gate tests.test_reboot_safety tests.test_vnish_hashboard_detection tests.test_hashboard_auto_reboot
```

Output:
```
...................................
----------------------------------------------------------------------
Ran 35 tests in 0.068s

OK
```

## 4. Full Suite Global Regression

```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests
```

Output:
```
Ran 854 tests in 14.525s

OK
```
Zero regressions across all existing suites (Adaptive Acquisition, Quality Telemetry, Evidence Fusion, Thermal Governors, Balancer, Telegram Bot, EventStore).
