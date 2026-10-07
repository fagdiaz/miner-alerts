# Tasks: Spec 089 — Telemetría de Cadenas & Sockets ASIC

**Feature**: `089-hardware-telemetry-decoupling`  
**Dependencies**: Spec 088 cerrada  
**Target Outcome**: -1.000 LOC en `miner_monitor.py`, cero regresiones de red.

---

## Tareas de Implementación

- [x] **T001** [P1] [Riesgo Medio]: Crear `app/hardware/chain_collector.py` y extraer `_async_collect_chain_telemetry` y `_async_evaluate_predictive_chain_break` (L2944–L3361).
- [x] **T002** [P1] [Riesgo Bajo]: Reemplazar funciones duplicadas de socket 4028 (`read_summary`, etc.) en `miner_monitor.py` por re-exports desde `app/network/cgminer_client.py`.
- [x] **T003** [P1] [Riesgo Bajo]: Mover formateadores de texto (`build_stability_health_text`, `build_mining_quality_text`, etc.) a `app/telegram/fleet_cards.py`.
- [x] **T004** [P1] [Riesgo Bajo]: Re-exportar todas las funciones migradas en `miner_monitor.py` para compatibilidad de tests legacy.
- [x] **T005** [P1] [Riesgo Bajo]: Ejecutar `py_compile` en los módulos modificados.
- [x] **T006** [P0] [Riesgo Bajo]: Ejecutar tests de hardware (`test_chain_health.py`, `test_mining_quality.py`) y suite global ($\ge 1522$ tests PASS).
- [x] **T007** [P0] [Riesgo Bajo]: Ejecutar `preflight_stabilize.ps1` (8/8 gates PASS) y reiniciar servicio Windows NSSM `MinerAlerts`.
- [x] **T008** [P1] [Riesgo Bajo]: Registrar entrada en `docs/audit/DEVELOPMENT_LOG.md` y cerrar con `speckit-stabilize`.
