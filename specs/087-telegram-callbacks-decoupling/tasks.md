# Tasks: Spec 087 — Desacoplamiento de Callbacks de Telegram

**Feature**: `087-telegram-callbacks-decoupling`
**Baseline**: 1522 tests PASS, 75 subtests PASS
**Target Outcome**: -1.508 LOC en `miner_monitor.py`, cero regresiones.

---

## Tareas de Implementación

- [x] **T001** [P1] [Riesgo Bajo]: Migrar `_handle_command_center_callback` (L3755–L4261, ~506 líneas) desde `miner_monitor.py` hacia `app/telegram/command_center.py`.
- [x] **T002** [P1] [Riesgo Bajo]: Migrar `_handle_help_callback` (L4262–L4307, ~45 líneas) desde `miner_monitor.py` hacia `app/telegram/help_center.py`.
- [x] **T003** [P1] [Riesgo Bajo]: Migrar `_handle_diagnostic_callback` (L4308–L4547, ~240 líneas) y `_handle_callback_query` (L4548–L5228, ~680 líneas) hacia `app/telegram/callbacks.py`.
- [x] **T004** [P1] [Riesgo Bajo]: Desacoplar `app/telegram/router.py`: reemplazar las importaciones de callbacks desde `miner_monitor` por importaciones directas desde `app.telegram.*`.
- [x] **T005** [P1] [Riesgo Bajo]: Crear shims de re-export en `app/miner_monitor.py` para preservar 100% de retrocompatibilidad con tests y herramientas externas.
- [x] **T006** [P1] [Riesgo Bajo]: Ejecutar `py_compile` en todos los módulos modificados.
- [x] **T007** [P0] [Riesgo Bajo]: Ejecutar `pytest -q` garantizando >= 1522 tests PASS (0 fallos, 0 errores).
- [x] **T008** [P0] [Riesgo Bajo]: Ejecutar `preflight_stabilize.ps1` (8/8 gates PASS) y reiniciar servicio Windows NSSM `MinerAlerts`.
- [x] **T009** [P1] [Riesgo Bajo]: Registrar entrada en `docs/audit/DEVELOPMENT_LOG.md`, actualizar `docs/speckit/ROADMAP.md` y cerrar con `speckit-stabilize`.
