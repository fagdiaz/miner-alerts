# Evidence - Spec 057: Intervention Governance & Adaptive Elevator Contingency

## Summary of Execution
- **Spec**: `057-intervention-governance-contingency`
- **Engine**: Gemini 3.8 Flash High
- **Total Tests**: 902 tests (100% PASS, 0 errors, 0 failures, 0 regressions)
- **Execution Time**: ~13.9s

---

## 1. Syntax & Static Compilation Verification

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py
& ".\.venv\Scripts\python.exe" -m py_compile app\governance\intervention_policy.py
& ".\.venv\Scripts\python.exe" -m py_compile app\governance\adaptive_contingency.py
& ".\.venv\Scripts\python.exe" -m py_compile app\telegram\command_center.py
```
**Outcome**: All files compiled cleanly with exit code 0.

---

## 2. Unit Test Suites (Spec 057 Targeted)

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_intervention_governance tests.test_adaptive_contingency
```
**Output**:
```
.....................
----------------------------------------------------------------------
Ran 21 tests in 0.043s

OK
```

### Breakdown:
1. `tests/test_intervention_governance.py` (13 tests):
   - Default state all allowed (`reboots_l1`, `reboots_l2`, `fan_governor`, `preset_balancer`, `contingency`).
   - Master disable ("Vnish Libre") blocks all mutating actions with descriptive reason.
   - Granular toggles (`reboots_enabled`, `governor_enabled`, `contingency_enabled`, `presets_enabled`).
   - Expiration timer automatically restores permissions.
   - Serialization and deserialization roundtrip.
   - Command center UI rendering (5th row button `[ 🛡️ Intervenciones: 🟢 ON / 🔴 LIBRE ]`, submenus, tactile toggles).
   - Integration tests with `evaluate_auto_restart_candidate` confirming soft auto-restart blocking and timer expiration recovery.
2. `tests/test_adaptive_contingency.py` (8 tests):
   - Canary identification for `elevator_1` (Miner 24) and `elevator_2` (Miner 25).
   - Relative preset ladder transitions (e.g. 2700W -> 2500W, 2500W -> 2300W, floor 2100W, ceiling 2700W).
   - User Story 3: Initial canary restart reduces ONLY canary by 1 tier relative to current state; partner miner stays untouched.
   - User Story 4: Limits exploration — canary second restart steps down further (2500W -> 2300W).
   - Floor protection: `HOLD_CONTINGENCY` when reaching minimum wattage (2100W).
   - Robust partner restart: drops partner 1 tier relative to its current state.
   - Step-Up Soak: 2 continuous hours without restart triggers progressive ramp-up and return to nominal.
   - Serialization roundtrip for `GroupContingencyState`.

---

## 3. Global Regression Verification

```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests
```
**Output**:
```
Ran 902 tests in 13.861s

OK
```
- **Prior baseline (Spec 056)**: 881 tests PASS.
- **Current baseline (Spec 057)**: 902 tests PASS (+21 new deterministic tests, 0 regressions).

---

## 4. Key Functional Deliverables
1. `app/governance/intervention_policy.py`: Pure immutable dataclass `InterventionGovernance` and interlocking helpers.
2. `app/governance/adaptive_contingency.py`: Asymmetric elevator contingency module with canary throttle, relative reductions, limit exploration, and 2h step-up soak recovery.
3. `app/telegram/command_center.py`: Telegram Interactive Command Center button `[ 🛡️ Intervenciones ]` with submenus, granular toggles, and countdown timers (30m, 1h, 2h, 4h, indef).
4. `app/miner_monitor.py`:
   - Interlocked actuators: Soft Auto-Restart (L1), Hard Auto-Reboot (L2), Fan Governor, and Preset Balancer.
   - Persistent state in `state.json` (`intervention_governance` and `elevator_contingency`).
   - Incident wiring for unexpected restarts on elevator miners.
   - Periodic step-up soak tick in main polling loop.
   - Text commands: `/interventions <status|on|off|30m|1h|2h|4h>` and `/contingency <status|reset>`.
