# Runtime Evidence — Spec 070: Modularización del Core Fase B — Desacoplamiento Seguro de inspect.getsource(main) (ST-05)

**Date**: 2026-09-16  
**Branch**: `codex/022-adaptive-acquisition`  
**Test Suite Status**: 1156 PASS (0 failures, 0 errors, 0 regressions in 32.3s)  
**Windows Service**: `MinerAlerts` (`Running`)  

---

## 1. Fases A y B: Arnés de Comportamiento & Certificación de Paridad Dual

### Objetivos Completados
1. **Creación del Arnés de Comportamiento (`SupervisoryBehavioralHarness`)**:
   - `tests/test_supervisory_core_behavioral.py`: Módulo de evaluación de caja negra determinista para simulación de ciclo supervisorio.
   - 37 tests funcionales que evalúan las reglas de negocio sin inspeccionar texto fuente de `main()`:
     - 8 tests de compuertas de señal y reseteo de temporizadores (`TestAutoRebootSignalGateBehavioral`).
     - 8 tests de detección de `STATE_HASHBOARD` y secuencia de 6 interlocks (`TestHashboardAutoRebootBehavioral`).
     - 13 tests de orden jerárquico de seguridad, interlocks térmicos, de flota y cooldowns (`TestRebootSafetyInterlocksBehavioral`).
     - 8 tests de parsing de telemetría de placas y precedencia de placas faltantes sobre hashrate (`TestVnishHashboardDetectionBehavioral`).

2. **Certificación de Paridad Dual (RI-01, RI-02)**:
   - Coexistencia simultánea y exitosa de los 37 tests legados de `inspect.getsource(main)` y los 37 nuevos tests de comportamiento funcional.
   - El código de producción en `app/miner_monitor.py` permaneció 100% inalterado durante las Fases A y B.
   - La suite global avanzó de 1119 a **1156 tests PASS** (superando la meta de $\ge 1147$).

---

## 2. Ejecución y Comprobación de Comandos

### 2.1 Suite de Comportamiento Supervisor
```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests/test_supervisory_core_behavioral.py
```
**Resultado**:
```
Ran 37 tests in 0.002s

OK
```

### 2.2 Validación de Sintaxis
```powershell
& ".\.venv\Scripts\python.exe" -m py_compile tests/test_supervisory_core_behavioral.py app/miner_monitor.py app/core/engine.py
```
**Resultado**:
- Código de salida 0, compilación limpia.

### 2.3 Suite de Regresión Global con Paridad Dual
```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
```
**Resultado**:
```
Ran 1156 tests in 32.374s

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
- Servicio de producción en estado `Running` continuo.
