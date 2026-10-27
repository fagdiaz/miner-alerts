# Implementation Plan: Spec 093 — Watchdog de Elevadores Eléctricos, Corrección de Rachas y Auto-Recuperación de Firmware

**Feature**: `093-elevator-watchdog-and-firmware-autorecovery`  
**Dependencies**: Arquitectura V6.0 Hookified (`app/core/engine.py`, `app/core/pipeline.py`)  
**Risk Level**: Medio (Gobernanza y Detección de Estados)  
**Safety Gates**: `py_compile`, `pytest` $\ge 1530$ tests PASS, `speckit-qa`, `speckit-stabilize` 8/8 gates.

---

## 1. Technical Architecture & File Impact

### Módulos Modificados
1. `app/core/engine.py`:
   - Corregir el reseteo de `offline_streak` y `low_streak` en `DetectionHook.execute`.
   - Garantizar que la racha solo se limpie al transicionar de un estado anómalo a `STATE_OK` o cuando `responded` sea `True`.
2. `app/core/pipeline.py`:
   - Cablear la llamada a `process_phase_drop_cycle` en `GovernanceHook.execute` o `DetectionHook.execute`.
   - Pasar `tick_failed_miners` y `tick_responded_miners` procesados en `AcquisitionHook`.
   - Conectar el manejador de auto-recuperación de firmware cuando se detecte `stock_firmware_fallback_detected`.
3. `app/governance/firmware_recovery.py` (Nuevo):
   - Funciones `reboot_stock_bitmain(host, timeout_s=5.0) -> bool`.
   - `attempt_stock_firmware_recovery(host, miner_name, config, ...) -> Tuple[bool, str]`.
   - Control de estados transitorios (`_FIRMWARE_RECOVERY_ATTEMPTS`, cooldowns, candados para evitar dobles disparos).
4. `tests/test_spec093_elevator_and_firmware_recovery.py` (Nuevo):
   - Pruebas deterministas para:
     a) Racha offline incrementando hasta 3 y transicionando a `OFFLINE`.
     b) Disparo de alerta de elevador cuando todos los mineros de un grupo caen.
     c) Reintento de reboot Bitmain y fallback a `FirmwareFlasher`.

---

## 2. Step-by-Step Execution Sequence

1. **Paso 1: Corrección de Rachas en `app/core/engine.py`**:
   - Modificar las líneas 1087-1092 de `DetectionHook.execute`:
     ```python
     if new_state == STATE_OK:
         if prev_state != STATE_OK:
             state.low_streak = 0
             state.offline_streak = 0
         state.hashboard_since_ts = None
         state.auto_restart_count = 0
     ```
2. **Paso 2: Creación del Módulo de Auto-Recuperación `app/governance/firmware_recovery.py`**:
   - Implementar `reboot_stock_bitmain` con autenticación Digest.
   - Implementar `process_stock_firmware_fallback` que maneje el escalonamiento (intento 1: reboot, intento 2: flash + restore profile) con notificaciones a Telegram.
3. **Paso 3: Cableado en `app/core/pipeline.py`**:
   - Cablear `process_phase_drop_cycle` dentro de `GovernanceHook` usando los mineros fallidos y respondidos de la etapa de adquisición.
   - Integrar la invocación de `process_stock_firmware_fallback` cuando se reporte `stock_firmware_fallback_detected`.
4. **Paso 4: Pruebas y Validación**:
   - Crear suite de pruebas exhaustiva en `tests/test_spec093_elevator_and_firmware_recovery.py`.
   - Compilación con `py_compile`.
   - Ejecutar suite de regresión completa (`pytest`).
5. **Paso 5: Preflight QA y Estabilización**:
   - Ejecutar `speckit-qa` (`.agents/skills/speckit-qa/scripts/preflight.ps1`).
   - Reiniciar el servicio `MinerAlerts` en Windows y verificar telemetría en vivo.
   - Ejecutar `speckit-stabilize` (`preflight_stabilize.ps1`).
   - Actualizar documentación (`DEVELOPMENT_LOG.md`, `ROADMAP.md`, `prompt.txt`).
