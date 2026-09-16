# Runtime Verification Evidence: Spec 063 — Gobernador Térmico con Conciencia Estacional (Ambient-Aware Thermal PID) (GOV-02)

**Branch**: `codex/022-adaptive-acquisition`
**Date**: 2026-09-15
**Certification Status**: CERTIFIED / PASS

---

## 1. Syntax & Compilation Verification

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\vnish\telemetry.py app\miner_monitor.py app\core\state_manager.py app\governance\fan_governor.py app\governance\__init__.py tests\test_fan_governor_seasonal.py
```
**Output**: Returncode `0` (clean, 0 syntax/lint errors).

---

## 2. Dedicated Seasonal Governor Test Suite

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests\test_fan_governor_seasonal.py
```

**Output**:
```
........[2026-09-15 21:12:22] [GOV DRY] miner=S19JPRO-1 action=HOLD_TARGET duty=50% target=50% holds=1 fails=0 season=WINTER
[2026-09-15 21:12:22] [GOV DRY] miner=S19JPRO-2 action=HOLD_TARGET duty=50% target=50% holds=1 fails=0 season=WINTER
[2026-09-15 21:12:22] [GOV DRY] miner=S19JPRO-3 action=HOLD_TARGET duty=70% target=70% holds=1 fails=0 season=SUMMER
..................
----------------------------------------------------------------------
Ran 26 tests in 0.001s

OK
```

### Coverage Highlights:
1. **Winter Mode (< 18°C)**:
   - Target 76.0°C, deadband [75.0, 77.0]°C, min duty 45% PWM, nominal step up 3%.
   - Enforced floor jump when current PWM < 45%.
2. **Standard Mode (18°C - 28°C)**:
   - Target 82.0°C, deadband [81.0, 82.5]°C, min duty 30% PWM.
   - Exact boundary checks at 18.0°C and 28.0°C.
3. **Summer Mode (> 28°C)**:
   - Target 80.0°C, deadband [79.0, 81.0]°C, min duty 65% PWM, accelerated step up 5%.
   - Floor jump from 50% to 65%.
4. **3 Inviolable Safety Invariants**:
   - `target_temp_c <= 82.0°C` mathematically clamped against misconfiguration.
   - `min_fan_duty_percent >= 30%` mathematically clamped against misconfiguration.
   - `emergency_spike_temp_c` (83.0°C / 83.5°C) unconditionally forces 100% PWM regardless of season or dwell.
5. **Boundary & Fault Tolerance**:
   - Telemetry dropout (`ambient_temp_c = None`) falls back to Standard mode.
   - Out-of-bounds sensor readings (< -10°C or > 60°C) discarded cleanly.
   - Silent Mode acoustic ceiling has clean precedence over seasonal floor.
6. **Group Aggregation**:
   - `elevator_1` miners share 12°C ambient average.
   - `elevator_2` miners share 32°C ambient average.

---

## 3. Combined Fan Governor & Telemetry Test Suites

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests\test_fan_governor.py tests\test_fan_governor_concurrency.py tests\test_fan_governor_seasonal.py tests\test_vnish_telemetry.py tests\test_silent_mode.py
```

**Output**:
```
Ran 82 tests in 2.022s

OK
```

---

## 4. Full Project Regression Gate

```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
```

**Output**:
```
Ran 985 tests in 15.214s

OK
```
- **Total Tests**: 985 (up from 959 baseline, +26 new tests).
- **Failures**: 0.
- **Errors**: 0.
- **Regressions**: 0.

---

## 5. Windows Service Operational Status

```powershell
Get-Service MinerAlerts
```

**Output**:
```
Status   Name               DisplayName
------   ----               -----------
Running  MinerAlerts        Miner Alerts Monitor
```

Windows service `MinerAlerts` continues executing without interruption or restart.
