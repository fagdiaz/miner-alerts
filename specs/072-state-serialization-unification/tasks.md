# Tasks — Spec 072: Unificación de Serialización de Estado & Desacoplamiento de Shims Redundantes (P2)

**ID**: 072  
**Rama**: `codex/022-adaptive-acquisition`  
**Estado**: Pendiente  

---

### Fase A: Unificación de Serialización de Estado (P2)

- [ ] **T001**: Exponer método estático o función pública `serialize_miner_state(state)` en `app/core/state_manager.py`.
- [ ] **T002**: Refactorizar `_build_state_payload()` en `app/miner_monitor.py` para delegar en `serialize_miner_state()`, eliminando el bloque duplicado de ~45 campos.
- [ ] **T003**: Verificar paridad determinista de campos en `tests/test_state_serialization_parity.py`.

### Fase B: Extracción de Helper de Búsqueda de Assessment (P2)

- [ ] **T004**: Crear helper compartido `find_assessment_by_target(assessments, target_id)` en `app/telegram/command_helpers.py` o módulo común.
- [ ] **T005**: Migrar comandos `/cooling`, `/efficiency`, `/profile`, `/governance`, `/preset` para reutilizar el helper.

### Fase C: Centralización de Utilidades y Shims (P2)

- [ ] **T006**: Centralizar `_dicts()` en `app/core/mining_quality.py` y remover duplicaciones.
- [ ] **T007**: Limpiar shims obsoletos en `app/miner_monitor.py` preservando contratos de tests.

### Fase D: Pruebas y Cierre

- [ ] **T008**: Validar sintaxis con `py_compile`.
- [ ] **T009**: Ejecutar suite de regresión completa: $\ge 1079$ tests PASS.
- [ ] **T010**: Registrar evidencia y actualizar documentación (`evidence.md`, `DEVELOPMENT_LOG.md`, `ROADMAP.md`).
