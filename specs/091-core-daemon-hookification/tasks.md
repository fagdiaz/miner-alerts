# Tasks: Spec 091 — Pipeline Declarativo de Hooks y Cierre V6.0

**Feature**: `091-core-daemon-hookification`  
**Dependencies**: Spec 090 cerrada  
**Target Outcome**: `miner_monitor.py` $\le 450$ LOC, disolución definitiva del monolito, Release V6.0.

---

## Tareas de Implementación

- [x] **T001** [P0] [Riesgo Medio]: Encapsular la inicialización de `main()` en `CoreSupervisoryEngine.initialize()`.
- [x] **T002** [P0] [Riesgo Medio]: Conectar las rutinas de adquisición y detección a `AcquisitionHook` y `DetectionHook`.
- [x] **T003** [P0] [Riesgo Medio]: Conectar la gobernanza de planta a `GovernanceHook` y la ejecución a `ActuatorHook`.
- [x] **T004** [P0] [Riesgo Medio]: Conectar la persistencia garantizada a `PersistenceHook` y la temporización a `PostTickHook`.
- [x] **T005** [P0] [Riesgo Medio]: Reducir `main()` en `app/miner_monitor.py` al runner declarativo (`engine.run_forever()`).
- [x] **T006** [P0] [Riesgo Bajo]: Verificar que `app/miner_monitor.py` mida $\le 450$ líneas de código.
- [x] **T007** [P0] [Riesgo Alto]: Ejecutar suite completa `pytest -q` garantizando $\ge 1522$ tests PASS (0 fallos, 0 errores).
- [x] **T008** [P0] [Riesgo Alto]: Ejecutar `preflight_stabilize.ps1` (8/8 gates PASS) y reiniciar servicio Windows NSSM `MinerAlerts`.
- [x] **T009** [P0] [Riesgo Bajo]: Registrar entrada en `docs/audit/DEVELOPMENT_LOG.md`, actualizar `docs/speckit/ROADMAP.md` y cerrar con `speckit-stabilize` publicando el Release Mayor V6.0.
