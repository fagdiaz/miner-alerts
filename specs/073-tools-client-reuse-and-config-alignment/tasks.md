# Tasks — Spec 073: Reutilización de Clientes en Tools & Alineación de Configuración (P3)

**ID**: 073  
**Rama**: `codex/022-adaptive-acquisition`  
**Estado**: Pendiente  

---

### Fase A: Reutilización de Clientes de Red en Tools (P3)

- [ ] **T001**: Refactorizar `tools/miner_diagnostics.py` para usar `app.network.cgminer_client.query_cgminer`.
- [ ] **T002**: Refactorizar `tools/debug_4028.py` para reutilizar `app.network.cgminer_client`.
- [ ] **T003**: Crear pruebas unitarias en `tests/test_miner_diagnostics_client.py` verificando el comportamiento sin regresión.

### Fase B: Auditor de Configuración (P3)

- [ ] **T004**: Desarrollar `tools/audit_config.py` con validación cruzada de claves, tipos y valores por defecto contra `app/config.example.json`.
- [ ] **T005**: Crear pruebas unitarias en `tests/test_audit_config.py` validando los casos de éxito, claves faltantes y discrepancias de tipo.

### Fase C: Consolidación de Fixtures de Test (P3)

- [ ] **T006**: Crear `tests/fixtures_compact_ux.py` consolidando fixtures redundantes entre `test_compact_format.py` y `test_compact_ux.py`.
- [ ] **T007**: Actualizar los dos archivos de pruebas para importar desde el módulo consolidado.

### Fase D: Pruebas y Cierre

- [ ] **T008**: Compilación de sintaxis con `py_compile`.
- [ ] **T009**: Suite de regresión completa: $\ge 1110$ tests PASS (0 fallos, 0 regresiones).
- [ ] **T010**: Documentación de evidencia (`evidence.md`), actualización de `DEVELOPMENT_LOG.md` y `ROADMAP.md`.
