# Evidence: Spec 066 — Cold-Boot Fleet Grace Period Post-Arranque (PROP-001)

## Status: COMPLETED & CERTIFIED
- **Baseline Tests**: 1046 PASS
- **Final Tests**: 1062 PASS (16 nuevos tests certificados, 0 fallos, 0 regresiones)
- **Duration**: 34.4s
- **Date**: 2026-09-15

---

## Validation Commands & Results

### 1. Syntax Compilation
```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py app\core\engine.py tests\test_startup_grace_period.py
```
**Result**: `0 errors (SYNTAX OK)`

### 2. Focused Test Suite (Spec 066 & Hooks)
```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_startup_grace_period tests.test_supervisory_hooks -v
```
**Result**:
```text
Ran 66 tests in 0.166s
OK
```

### 3. Constitutional Invariant Tests
```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_auto_reboot_signal_gate tests.test_hashboard_auto_reboot tests.test_reboot_safety tests.test_vnish_hashboard_detection -v
```
**Result**:
```text
Ran 37 tests in 0.071s
OK (All inspect.getsource(main) invariants preserved 100%)
```

### 4. Full Regression Discovery Suite
```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover tests
```
**Result**:
```text
Ran 1062 tests in 34.434s
OK
```

### 5. Git Diff & QA Preflight Script
```powershell
git diff --check
& powershell.exe -ExecutionPolicy Bypass -File .agents\skills\speckit-qa\scripts\preflight.ps1 -RunBuilds
```
**Result**:
```json
{"Status":"PASS","FeatureDir":"F:\\02-ASIC - mineros\\miner-alerts\\specs\\066-cold-boot-grace","MissingRequiredFiles":[],"Checklist":{"Total":0,"Open":0},"Scope":{"Python":true,"Telegram":false,"Reboot":true,"Config":true,"Docs":true},"DirtyPathCount":7,"Gates":[{"Name":"git-diff-check","Status":"PASS","ExitCode":0,"Summary":""},{"Name":"python-py-compile","Status":"PASS","ExitCode":0,"Summary":""}]}
```

---

## Implemented Deliverables

1. **Configuración y Defaults (`app/config.example.json`)**:
   - `"startup_fleet_grace_period_seconds": 180`
   - `"startup_fleet_grace_threshold_ths": 50.0`

2. **Supresión de Fallas y Falsas Alarmas en WARMING_UP (`app/miner_monitor.py`)**:
   - Supresión de acumulación de `offline_streak` y `low_streak` mientras `startup_grace_active` sea `True`.
   - Mantenimiento estricto a `None` de `low_since_ts` y `hashboard_since_ts`.
   - Transición segura a `STATE_OK` ante respuesta de hash $\ge$ `threshold_ths`.
   - Inhibición de despacho de `EPISODE_ALERT` a Telegram durante la ventana de gracia.

3. **Consolidación Temprana y por Timeout (`app/miner_monitor.py`)**:
   - Predicado puro `is_fleet_warmup_complete(miners, states, threshold_ths, expected_boards)`.
   - Formateador `format_fleet_restored_line(name, rate, temp)`.
   - Emisión de tarjeta limpia `🟢 FLOTA RESTABLECIDA` cuando toda la flota alcanza $\ge 50$ TH/s.
   - Emisión de tarjeta `STARTUP [FIN PERÍODO DE GRACIA]` si el temporizador de 180s expira.
   - Reconocimiento automático de incidentes iniciales con `acknowledge_active_initials()`.
   - Retrocompatibilidad absoluta: si `startup_fleet_grace_period_seconds == 0`, se comporta de forma inmediata clásica en `first_tick`.

4. **Sincronización de Governance en Hooks (`app/core/engine.py` & `app/miner_monitor.py`)**:
   - Eliminación de la desincronización de `monitor_ctx.governance` actualizándolo en cada tick desde `_GLOBAL_INTERVENTION_GOV`.
   - `GovernanceInterlockHook` lee preferentemente de `tick_data.get("governance") or context.governance`.
