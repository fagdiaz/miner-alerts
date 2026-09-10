# Tareas: Spec 049 - Active Thermal Purge Ramp & Acoustic Contrast on Safe Shutdown

## Estado General
- **Total Tareas**: 6
- **Completadas**: 6
- **Pendientes**: 0

---

## Tareas de Fase 1 (Dominio Puro y Despachador Concurrente de Coolers)

- [x] **T1: Implementar `execute_parallel_fan_duty` en `app/governance/fleet_shutdown.py`**:
  - Función desacoplada para envío simultáneo de `safe_set_fan_duty` a una lista de mineros.
  - Gestión con `ThreadPoolExecutor(max_workers=min(4, len(miners)))`.
  - Retorno de diccionario de `OperationResult(miner_id, success, error)`.
  - Timeout de 2.5 segundos por petición.

- [x] **T2: Actualizar Renderizadores Móviles en `app/governance/fleet_shutdown.py`**:
  - Actualizar `render_shutdown_in_progress` para indicar la rampa activa al 100% de PWM.
  - Actualizar `render_safe_area_card` para reflejar el piso de reposo acústico (40% PWM / silencio) y chips fríos (<35°C).
  - Garantizar ancho móvil estricto <= 32 columnas visibles.

- [x] **T3: Suite Unitaria de Dominio en `tests/test_fleet_shutdown.py`**:
  - Pruebas unitarias para `execute_parallel_fan_duty` con mocks de éxito y fallo.
  - Validación del ancho de columnas de las nuevas tarjetas con `visible_line_width()`.

---

## Tareas de Fase 2 (Integración en Monitor y Secuencia de Purga)

- [x] **T4: Integrar Rampa 100% y Caída a Reposo 40% en `app/miner_monitor.py`**:
  - En `sd_cfm`: tras `execute_parallel_shutdown`, invocar de inmediato `execute_parallel_fan_duty(selected_miners, 100, vnish_pw)`.
  - En el hilo daemon `ShutdownPurgeNotify`: al expirar los 45 segundos, invocar `execute_parallel_fan_duty(target_miners, 40, vnish_pw)` antes o durante el envío de la tarjeta de área segura.
  - En `resume`: invocar `execute_parallel_fan_duty(target_miners, 100, vnish_pw)` para salir del modo reposo al reactivar el minado.
  - Registrar eventos de rampa de purga y caída a reposo en `event_store`.

---

## Tareas de Fase 3 (Pruebas de Integración, Documentación y Cierre)

- [x] **T5: Pruebas de Integración en `tests/test_safe_fleet_shutdown_integration.py`**:
  - Validar la secuencia completa mockeada de parada: `stop_mining` -> `duty 100%` -> `sleep 45s` -> `duty 40%` -> `send_telegram(SHUTDOWN_SAFE)`.
  - Validar la secuencia de `resume`: `resume_mining` -> desescalado de reposo -> auto-unsnooze.

- [x] **T6: Validación Global, Documentación y Auditoría**:
  - Compilación de sintaxis con `py_compile`.
  - Ejecutar suite completa de pruebas (727/727 tests PASS).
  - Actualizar `specs/049-thermal-purge-ramp/evidence.md`, `docs/audit/DEVELOPMENT_LOG.md`, `docs/speckit/ROADMAP.md` y `prompt.txt`.
