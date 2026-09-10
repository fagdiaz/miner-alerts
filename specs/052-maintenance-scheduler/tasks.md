# Tareas: Spec 052 - Scheduled Maintenance Windows & Soft Pre-Ramp

## Estado General
- **Total Tareas**: 6
- **Completadas**: 6
- **Pendientes**: 0

---

## Tareas de Fase 1 (Dominio Puro, Parser y Tarjetas Móviles)

- [x] **T1: Implementar `app/governance/maintenance_scheduler.py`**:
  - Definir estructuras: `ScheduledWindow`, `ScheduledStage`.
  - Implementar parser temporal robusto `parse_schedule_expression(...)` con soporte relativo (`in 30m`, `in 2h`) y absoluto (`YYYY-MM-DD HH:MM`) en zona horaria local.
  - Implementar evaluador de etapas `evaluate_window_stage(...)` determinando cuándo activar pre-rampa T-10m, T-5m o parada T-0.
  - Implementar tarjetas Mobile-First strictly <= 32 columnas: `render_schedule_confirmation_card`, `render_scheduled_status_card`, `render_pre_ramp_card` y `render_schedule_cancelled_card`.
  - Exportar en `app/governance/__init__.py`.

- [x] **T2: Suite de Pruebas Unitarias en `tests/test_maintenance_scheduler.py`**:
  - Tests para parsing de expresiones válidas e inválidas (rechazo de fechas pasadas o formatos erróneos).
  - Tests para avance de etapas temporales ($T - 10\text{m}$, $T - 5\text{m}$, $T - 0$).
  - Validación de ancho de líneas de las tarjetas con `visible_line_width() <= 32`.

---

## Tareas de Fase 2 (Integración en Monitor, Persistencia y Comandos Telegram)

- [x] **T3: Persistencia Atómica en Estado**:
  - Actualizar `save_state` y `load_state` para serializar y deserializar `scheduled_maintenance` en `state.json`.
  - Reconstitución de ventana activa tras reinicios del servicio.

- [x] **T4: Integrar Hook Periódico en Bucle de `app/miner_monitor.py`**:
  - En cada ciclo del monitor, evaluar la ventana activa:
    * A T-10m: modular presets hacia abajo a 2300W (pre-rampa Tier 1).
    * A T-5m: modular presets hacia abajo a 2100W (pre-rampa Tier 2).
    * A T-0: invocar `execute_parallel_shutdown`, rampa 100% de purga por 45s (Spec 049) y auto-snooze programado hasta fin de ventana.
  - Registrar eventos en `event_store` con acción `scheduled_shutdown_t0` / `scheduled_preramp`.

- [x] **T5: Conectar Comandos Telegram y Cancelación**:
  - Handler para `/schedule_maintenance <tiempo> [duración]`.
  - Handler para `/scheduled` mostrando la ventana activa y botón `[ ❌ Cancelar Ventana ]`.
  - Callback `sch:cancel` para anulación en caliente con tarjeta de confirmación móvil.

---

## Tareas de Fase 3 (Pruebas de Integración, Validación y Cierre)

- [x] **T6: Pruebas de Integración y Certificación Global**:
  - Desarrollar `tests/test_maintenance_scheduler_integration.py` simulando la línea de tiempo completa (programación -> T-10m pre-rampa -> T-0 parada -> cancelación).
  - Compilación de sintaxis con `py_compile`.
  - Ejecutar suite global completa de pruebas (781 tests PASS).
  - Documentar evidencia en `specs/052-maintenance-scheduler/evidence.md`.
  - Actualizar `docs/audit/DEVELOPMENT_LOG.md` y `docs/speckit/ROADMAP.md`.
