# Tasks: Spec 090 — Modernización de Tests Invariantes

**Feature**: `090-test-invariants-modernization`  
**Dependencies**: Spec 089 cerrada  
**Target Outcome**: Desbloqueo arquitectónico de `main()` con 100% de cobertura funcional.

---

## Tareas de Implementación

- [ ] **T001** [P1] [Riesgo Bajo]: Reescribir `TestStartupGraceInvariantContracts` en `tests/test_startup_grace_period.py` utilizando `SupervisoryBehavioralHarness`.
- [ ] **T002** [P1] [Riesgo Bajo]: Validar que las 5 precedencias de auto-reboot se prueben black-box.
- [ ] **T003** [P1] [Riesgo Bajo]: Ejecutar `pytest tests/test_startup_grace_period.py` y verificar 0 fallos.
- [ ] **T004** [P0] [Riesgo Bajo]: Ejecutar suite completa `pytest -q` ($\ge 1522$ tests PASS).
- [ ] **T005** [P0] [Riesgo Bajo]: Ejecutar `preflight_stabilize.ps1` (8/8 gates PASS).
- [ ] **T006** [P1] [Riesgo Bajo]: Registrar entrada en `docs/audit/DEVELOPMENT_LOG.md` y cerrar con `speckit-stabilize`.
