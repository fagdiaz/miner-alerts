# Evidencia de Ejecución: Spec 093 — Watchdog de Elevadores Eléctricos, Corrección de Rachas y Auto-Recuperación de Firmware

**Fecha**: 2026-10-27  
**Feature**: `specs/093-elevator-watchdog-and-firmware-autorecovery`  
**Estado**: CERTIFICADO (Preflight QA PASS, Tests 1536 PASS)

---

## 1. Incidente Físico y Hallazgos Forenses

### Evento Real:
- Relé físico del elevador 2 (`elevator_2`) se trabó por sobretensión, cortando suministro eléctrico a `S19JPRO-25` (192.168.100.25) y `S19JPRO-26` (192.168.100.26).
- Durante el corte (~95 minutos), Telegram **no envió** la alerta de minero offline ni la alerta de corte de circuito.
- Al restaurar energía, `S19JPRO-26` arrancó en firmware stock de Bitmain (`BMMiner 1.0.0`) en lugar de VNish 1.2.6.

### Causas Raíz Identificadas:
1. **Reseteo Prematuro de Rachas (`app/core/engine.py`)**:
   - En `DetectionHook.execute`, la condición `if new_state == STATE_OK:` borraba incondicionalmente `state.offline_streak = 0`.
   - Cuando fallaba un minero, el tick 1 incrementaba la racha a 1. Debido a la histeresis de alerta (`fails_before_alert = 3`), `classify_state` devolvía el estado previo (`STATE_OK`).
   - El hook evaluaba `new_state == STATE_OK` y reseteaba la racha a 0 en el mismo tick. Por ende, la racha jamás alcanzaba 3 y el minero nunca transitaba a `OFFLINE`.
2. **Discriminador de Corte de Fase Desconectado (`app/core/pipeline.py`)**:
   - `process_phase_drop_cycle` (implementado en Spec 051) estaba importado pero no se invocaba en ningún hook del pipeline V6.0 (`GovernanceHook`).
3. **Ausencia de Escalera de Auto-Recuperación de Firmware Stock**:
   - Las placas de control BeagleBone Black de Bitmain caen a la partición NAND de fábrica ante cortes bruscos. No existía lógica para emitir un reboot digest HTTP `/cgi-bin/reboot.cgi` o reflash con restauración de perfil de manera desatendida.

---

## 2. Acciones Inmediatas y Mitigación en Vivo

1. **Reinicio Digest a Minero 26**:
   - Se emitió POST `/cgi-bin/reboot.cgi` con autenticación Digest `root:root` a `192.168.100.26`.
   - El equipo reinició cargando VNish 1.2.6 con su perfil dorado intacto (`top_preset: 2500`, `preset: 2300`, Binance Pool `fagdiaz.19216810026`).
   - Hashrate recuperado: 3/3 cadenas activas operando a >87 TH/s nominal.

2. **Implementación de Arquitectura de Auto-Recuperación**:
   - `app/core/engine.py`: Corrección de lógica de reseteo de rachas en `DetectionHook`.
   - `app/governance/firmware_recovery.py`: Módulo autónomo con reinicio Bitmain stock, reflash VNish y restauración de matrices.
   - `app/core/pipeline.py`: Conexión de `process_phase_drop_cycle` y `handle_stock_firmware_recovery` en `GovernanceHook`.
   - `app/core/restart_intelligence.py`: Manejador de stock firmware fallback en reinicios.

---

## 3. Comandos de Verificación Ejecutados

### A. Pruebas Unitarias e Integración Spec 093
```powershell
& ".\.venv\Scripts\python.exe" -m pytest -v tests/test_spec093_elevator_and_firmware_recovery.py
```
**Resultado**: 6 passed in 0.76s.

### B. Compilación de Sintaxis Python
```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\core\engine.py app\core\pipeline.py app\governance\firmware_recovery.py app\core\restart_intelligence.py tests\test_spec093_elevator_and_firmware_recovery.py
```
**Resultado**: Código de salida 0 (sin errores).

### C. Suite Completa de Regresión
```powershell
& ".\.venv\Scripts\python.exe" -m pytest -q tests/
```
**Resultado**: 1536 passed, 75 subtests passed in 40.65s (0 fallos).

### D. Preflight QA (`speckit-qa`)
```powershell
& powershell -ExecutionPolicy Bypass -File .agents\skills\speckit-qa\scripts\preflight.ps1 -RunBuilds
```
**Resultado**:
```json
{"Status":"PASS","FeatureDir":"F:\\02-ASIC - mineros\\miner-alerts\\specs\\093-elevator-watchdog-and-firmware-autorecovery","MissingRequiredFiles":[],"Checklist":{"Total":0,"Open":0},"Scope":{"Python":true,"Telegram":false,"Reboot":true,"Config":false,"Docs":true},"DirtyPathCount":7,"Gates":[{"Name":"git-diff-check","Status":"PASS","ExitCode":0,"Summary":""},{"Name":"python-py-compile","Status":"PASS","ExitCode":0,"Summary":""}]}
```
