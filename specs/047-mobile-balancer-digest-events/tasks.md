# Tareas: Spec 047 - Mobile-First Card Layout for Balancer, Digest & Operational Events

## Estado General
- **Total Tareas**: 8
- **Completadas**: 8
- **Pendientes**: 0

---

## Tareas de Fase 1 (Módulos Puros, Renderers y Tests Unitarios)

- [x] **T1: Inicialización de Artefactos Speckit Spec 047**: Crear `contracts/mobile-diagnostics-api.md`, `checklists/requirements.md`, `evidence.md` y actualizar `.specify/feature.json`.
- [x] **T2: Extensión de Teclados y Callbacks (`app/telegram/fleet_cards.py`)**:
  - Ampliar `parse_diagnostic_callback()` para admitir `balancer`, `elev`, `digest`, `events`.
  - Ampliar `build_diagnostic_keyboard()` con soporte para estos nuevos reportes.
- [x] **T3: Refactor Mobile-First de Balancer y Elevadores (`app/governance/preset_balancer.py`)**:
  - Actualizar `build_balancer_table_text()`, `build_miner_balancer_detail_text()` y `build_elevator_sensitivity_text()` a tarjetas verticales $\le 32$ columnas con viñetas `•` y wrapping de recomendaciones.
- [x] **T4: Refactor Mobile-First de Daily Digest (`app/telegram/daily_digest.py`)**:
  - Actualizar `format_daily_digest()` a bloques verticales alineados $\le 32$ columnas.
- [x] **T5: Refactor Mobile-First de Snooze (`app/telegram/snooze.py`)**:
  - Actualizar `build_snooze_status_text()` a fichas verticales por minero $\le 32$ columnas.
- [x] **T6: Refactor Mobile-First de Eventos e Incidentes (`app/core/event_store.py`)**:
  - Actualizar `render_event_list()`, `render_event_detail()` y `render_reboot_decision()` a tarjetas verticales $\le 32$ columnas.
- [x] **T7: Suite Unitaria Exhaustiva (`tests/test_mobile_diagnostics.py`)**:
  - Validar límite estricto $\le 32$ columnas visibles en todas las líneas de salida.
  - Validar resiliencia ante datos nulos o mineros desconectados.
  - Adaptar pruebas existentes si alguna aserción textual cambió.

---

## Tareas de Fase 2 (Integración en Monitor, Callbacks y Certificación)

- [x] **T8: Conexión en Dispatcher, Callbacks de Refresco y Certificación (`app/miner_monitor.py`)**:
  - Cablear callbacks `diag:ref:balancer`, `diag:ref:elev`, `diag:ref:digest`, `diag:ref:events` en `_handle_diagnostic_callback` con ACK temprano (< 50ms) y edición in-place.
  - Adjuntar teclados inline en el dispatcher para `/balancer`, `/elevadores`, `/digest`, `/events`.
  - Agregar pruebas de integración en `tests/test_telegram_callbacks.py`.
  - Validar suite global completa ($\ge 687$ tests PASS), release audit y comprobación sintáctica.
  - Actualizar documentación y handoff en `prompt.txt`.
