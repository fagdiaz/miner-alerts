# Tasks — Spec 072: Unificación de Serialización de Estado & Desacoplamiento de Shims Redundantes (P2)

**ID**: 072  
**Rama**: `codex/022-adaptive-acquisition`  
**Estado**: Completado  

---

### Fase A: Unificación de Serialización de Estado (P2)

- [x] **T001**: Exponer método estático o función pública `serialize_miner_state(state)` en `app/core/state_manager.py`.
- [x] **T002**: Refactorizar `_build_state_payload()` en `app/miner_monitor.py` para delegar en `serialize_miner_state()`, eliminando el bloque duplicado de ~45 campos.
- [x] **T003**: Verificar paridad determinista de campos en `tests/test_state_serialization_parity.py`.

### Fase B: Extracción de Helper de Búsqueda de Assessment y Keys Seguras (P2)

- [x] **T004**: Crear helpers compartidos `find_assessment_by_target` y `format_miner_key` en `app/telegram/command_center.py`.
- [x] **T005**: Migrar comandos (`diagnostics.py`, `fans.py`, `reboot.py`, `maintenance.py`) para reutilizar `find_assessment_by_target` y `format_miner_key`.

### Fase C: Centralización de Utilidades y Shims (P2)

- [x] **T006**: Centralizar `_dicts()` en `app/core/mining_quality.py` y remover duplicaciones.
- [x] **T007**: Limpiar shims obsoletos en `app/miner_monitor.py` preservando contratos de tests.

### Fase D: Pruebas y Cierre

- [x] **T008**: Validar sintaxis con `py_compile`.
- [x] **T009**: Ejecutar suite de regresión completa: $\ge 1110$ tests PASS (0 fallos, 0 regresiones).
- [x] **T010**: Registrar evidencia y actualizar documentación (`evidence.md`, `DEVELOPMENT_LOG.md`, `ROADMAP.md`).
