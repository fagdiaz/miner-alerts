# Runtime Evidence — Spec 070: Modularización del Core Fase B — Desacoplamiento Seguro de inspect.getsource(main) (ST-05)

**Date**: 2026-09-16  
**Branch**: `codex/022-adaptive-acquisition`  
**Test Suite Status**: 1160 PASS (0 failures, 0 errors, 0 regressions in 34.7s)  
**Windows Service**: `MinerAlerts` (`Running`)  

---

## 1. Fases Completadas: De Paridad Dual a Desacoplamiento Funcional Total

### 1.1 Fases A y B: Arnés de Comportamiento & Paridad Dual
- Construido `tests/test_supervisory_core_behavioral.py` con `SupervisoryBehavioralHarness`.
- 37 tests funcionales cubrieron rigurosamente:
  - 8 tests de compuertas de señal y reseteo de timer.
  - 8 tests de detección de `STATE_HASHBOARD` y secuencia de 6 interlocks.
  - 13 tests de jerarquía de seguridad, guardas térmicas, de flota y cooldowns.
  - 8 tests de parsing de telemetría y precedencia de placas sobre hashrate.
- Paridad dual demostrada con 1156 tests globales PASS.

### 1.2 Fases C y D: Extracción de Hooks y Desacoplamiento de inspect.getsource(main)
- Extraído `DetectionHook` (HookStage.DETECTION = 30) en `app/core/engine.py` con método puro `DetectionHook.classify_state()`.
- Extraído `ActuatorHook` (HookStage.ACTUATOR = 50) en `app/core/engine.py` con `ActuatorHook.evaluate_auto_reboot_policy()`.
- Conectados en `main()` de `app/miner_monitor.py`:
  - `_supervisory_engine.register_hook(DetectionHook())` y `_supervisory_engine.register_hook(ActuatorHook())`.
  - Clasificación de estado delegada limpiamente a `DetectionHook.classify_state()`.
- Modernizadas las 4 suites de tests legadas:
  - `tests/test_vnish_hashboard_detection.py`
  - `tests/test_auto_reboot_signal_gate.py`
  - `tests/test_hashboard_auto_reboot.py`
  - `tests/test_reboot_safety.py`
  - Reemplazadas todas las aserciones basadas en `inspect.getsource(main)` por evaluaciones directas sobre `DetectionHook` y `ActuatorHook`.
- Resultado: Erradicación total del acoplamiento textual sin regresión funcional alguna.

---

## 2. Ejecución y Comprobación de Comandos

### 2.1 Suites de Hooks y Comportamiento Supervisor
```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests/test_supervisory_core_behavioral.py tests/test_supervisory_hooks.py
```
**Resultado**:
```
Ran 88 tests in 0.148s

OK
```

### 2.2 Validación de Sintaxis
```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app/miner_monitor.py app/core/engine.py tests/test_supervisory_core_behavioral.py tests/test_supervisory_hooks.py
```
**Resultado**:
- Código de salida 0, compilación limpia.

### 2.3 Suite de Regresión Global
```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
```
**Resultado**:
```
Ran 1160 tests in 34.759s

OK
```

### 2.4 Estado del Servicio Windows
```powershell
Get-Service MinerAlerts
```
**Resultado**:
```
Status   Name               DisplayName
------   ----               -----------
Running  MinerAlerts        Miner Alerts Monitor
```
- Servicio de producción en estado `Running` ininterrumpido.
