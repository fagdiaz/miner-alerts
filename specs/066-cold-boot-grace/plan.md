# Implementation Plan: Spec 066 — Cold-Boot Fleet Grace Period Post-Arranque (PROP-001)

## Overview
Implementación del período de gracia y calentamiento post-arranque (`WARMING_UP`) para la flota de mineros ASIC, evitando falsas alarmas `STARTUP`, `OFFLINE` y `LOW` durante el booteo de NAND y autotuning de los equipos tras cortes de energía o reinicios de servicio.

---

## Technical Approach & Architecture

### 1. Variables de Control en `miner_monitor.py`
- `startup_fleet_grace_period_seconds = int(config.get("startup_fleet_grace_period_seconds", 180))`
- `startup_fleet_grace_threshold_ths = float(config.get("startup_fleet_grace_threshold_ths", 50.0))`
- `startup_grace_active = startup_fleet_grace_period_seconds > 0`
- `startup_notification_sent = False`

### 2. Comportamiento en el Bucle Principal (`main`)
- **Detección de Estabilización**:
  En cada tick, verificar si la flota alcanzó la condición de salud:
  ```python
  fleet_healthy = (
      len(valid_miners) > 0
      and all(
          (m_state := states.get(f"{m.get('name','')}|{m.get('host','')}:{m.get('port',4028)}")) is not None
          and getattr(m_state, "last_responded", False)
          and (getattr(m_state, "last_rate_ths", 0.0) or 0.0) >= startup_fleet_grace_threshold_ths
          for m in valid_miners
      )
  )
  ```
- **Supresión de Fallas durante Gracia**:
  Si `startup_grace_active`:
  - `state.offline_streak = 0`
  - `state.low_streak = 0`
  - `state.low_since_ts = None`
  - `state.hashboard_since_ts = None`
  - Se inhibe el envío de lotes de episodios irregulares (`episode_batch`) a Telegram mientras `startup_grace_active` sea `True`.
- **Despacho de Tarjeta de Arranque / Flota Restablecida**:
  - Si `startup_fleet_grace_period_seconds == 0`: Comportamiento inmediato clásico en `first_tick`.
  - Si `startup_grace_active` y `fleet_healthy`:
    - Generar tarjeta `🟢 FLOTA RESTABLECIDA ({now_str()})`.
    - Enviar a Telegram con `msg_type="STARTUP"`, `coalesce_key="startup"`.
    - Desactivar `startup_grace_active = False`.
    - `startup_notification_sent = True`.
    - Invocar `episode_notifications.acknowledge_active_initials()`.
    - Registrar evento `startup_fleet_grace_completed` en `event_store`.
  - Si `startup_grace_active` y `(now_ts - process_start_ts) >= startup_fleet_grace_period_seconds`:
    - Finalizar período de gracia por timeout (`startup_grace_active = False`).
    - Enviar tarjeta estándar `STARTUP` con los estados actuales.
    - `startup_notification_sent = True`.
    - Invocar `episode_notifications.acknowledge_active_initials()`.
    - Registrar evento `startup_fleet_grace_expired` en `event_store`.

### 3. Preservación de Invariantes y Contratos de Inspección
- Mantener estrictamente intactos los literales inspeccionados por `tests/test_auto_reboot_signal_gate.py`, `tests/test_hashboard_auto_reboot.py`, `tests/test_reboot_safety.py`, y `tests/test_vnish_hashboard_detection.py`.
- Preservar el modelo monotónico de sleep en `miner_monitor.py:7288`:
  `poll_seconds = max(0.0, _poll_interval_seconds - (time.monotonic() - tick_start))`
  `time.sleep(poll_seconds)`

---

## Verification Strategy
1. **Pruebas Unitarias (`tests/test_startup_grace_period.py`)**:
   - Inicialización con defaults y valores custom.
   - Supresión de streaks y episodios durante la ventana de gracia.
   - Disparo temprano de `🟢 FLOTA RESTABLECIDA` al superar los 50 TH/s.
   - Disparo por timeout tras 180s con flota no recuperada.
   - Desactivación con `startup_fleet_grace_period_seconds = 0`.
   - Invariantes de `inspect.getsource(main)`.
2. **Validación de Integración y Regresiones**:
   - `python -m unittest discover tests` garantizando $\ge 1046$ tests PASS.
   - Verificación de sintaxis con `py_compile`.
   - Limpieza de diff con `git diff --check`.
