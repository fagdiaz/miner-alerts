# Tasks: Spec 088 — Desacoplamiento de Ciclos de Gobernanza

**Feature**: `088-governance-cycles-decoupling`
**Dependencies**: Spec 087 cerrada
**Target Outcome**: -388 LOC en `miner_monitor.py`, cero regresiones en balanceo.

---

## Tareas de Implementación

- [x] **T001** [P1] [Riesgo Medio]: Crear `app/governance/balancer_cycle.py` y extraer `execute_balancer_cycle` (L3362–L3614).
- [x] **T002** [P1] [Riesgo Medio]: Extraer `check_autotune_watchdog` (L3615–L3754) como `execute_autotune_watchdog_cycle` en `app/governance/autotune_watchdog.py`.
- [x] **T003** [P1] [Riesgo Bajo]: Re-exportar ambas funciones en `miner_monitor.py` para compatibilidad de importaciones externas.
- [x] **T004** [P1] [Riesgo Bajo]: Conectar las llamadas en el bucle principal de `main()` hacia los nuevos módulos de gobernanza.
- [x] **T005** [P1] [Riesgo Bajo]: Ejecutar `py_compile` en los módulos modificados.
- [x] **T006** [P0] [Riesgo Medio]: Ejecutar `pytest tests/test_autotune_watchdog.py tests/test_hw_error_tripwire.py tests/test_preset_balancer_integration.py` y suite completa (>= 1522 tests PASS).
- [x] **T007** [P0] [Riesgo Bajo]: Ejecutar `preflight_stabilize.ps1` (8/8 gates PASS) y reiniciar servicio Windows NSSM `MinerAlerts`.
- [x] **T008** [P1] [Riesgo Bajo]: Registrar entrada en `docs/audit/DEVELOPMENT_LOG.md` y cerrar con `speckit-stabilize`.
