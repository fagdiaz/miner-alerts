# Tasks: Spec 085 — Extracción del Orquestador de Gobernanza

**Feature**: `085-governance-orchestrator`
**Fecha**: 2026-10-01
**Prioridad**: P1 — Arquitectónica
**Riesgo**: ALTO
**Baseline**: 1483 tests PASS, 75 subtests PASS

---

## Fase 0 — Reconocimiento y Auditoría Pre-Migración

- [x] **T0.1** Contar líneas de `miner_monitor.py` → 9.385 líneas
- [x] **T0.2** Identificar funciones candidatas a migrar:
  - `execute_governor_cycle()` L3239–L3653 (415 líneas)
  - `refresh_vnish_overclock_settings()` L3654–L3860 (207 líneas)
  - `execute_balancer_cycle()` L3861–L4109 (249 líneas)
  - `check_autotune_watchdog()` L4110–L4249 (140 líneas)
- [x] **T0.3** Auditar globals compartidos:
  - `_GOVERNOR_RUNTIME_ENABLED` (L3231): usado en `execute_governor_cycle` + `fans.py` (via `mm._GOVERNOR_RUNTIME_ENABLED`)
  - `_BALANCER_RUNTIME_ENABLED` (L3799): usado en `execute_balancer_cycle` + `interventions.py` (via `mm._BALANCER_RUNTIME_ENABLED`)
  - `_GLOBAL_INTERVENTION_GOV` (L3837): accedido con anti-patrón `globals().get(...)` en `execute_governor_cycle`
  - `_LAST_VNISH_SYNC_TS` (L3651): usado en `refresh_vnish_overclock_settings` + global write
  - `_LAST_BALANCER_CYCLE_TS` (L3800): usado en `execute_balancer_cycle`
- [x] **T0.4** Confirmar que `fans.py` usa `mm._GOVERNOR_RUNTIME_ENABLED = True/False` (L220, L229)
- [x] **T0.5** Confirmar que `interventions.py` usa `mm._BALANCER_RUNTIME_ENABLED = True/False` (L189, L198)

---

## Fase 1 — Módulo de Estado Compartido: `_orchestrator_state.py`

**Objetivo**: Eliminar el acoplamiento directo entre los handlers de Telegram y los globals de `miner_monitor.py`.
Centraliza el estado mutable de los ciclos de gobernanza en un módulo sin dependencias circulares.

- [x] **T1.1** Crear `app/governance/_orchestrator_state.py`:
  - Importar `threading`, `typing`, `InterventionGovernance` (con `TYPE_CHECKING`)
  - Declarar globals: `_GOVERNOR_RUNTIME_ENABLED`, `_BALANCER_RUNTIME_ENABLED`,
    `_LAST_VNISH_SYNC_TS`, `_LAST_BALANCER_CYCLE_TS`, `_GLOBAL_INTERVENTION_GOV`
  - Implementar funciones accessor thread-safe:
    ```python
    def get_governor_enabled() -> Optional[bool]
    def set_governor_enabled(val: Optional[bool]) -> None
    def get_balancer_enabled() -> Optional[bool]
    def set_balancer_enabled(val: Optional[bool]) -> None
    def get_intervention_gov() -> "InterventionGovernance"
    def get_last_vnish_sync_ts() -> float
    def set_last_vnish_sync_ts(ts: float) -> None
    def get_last_balancer_cycle_ts() -> float
    def set_last_balancer_cycle_ts(ts: float) -> None
    ```
  - `py_compile app/governance/_orchestrator_state.py` → exit 0

- [x] **T1.2** Actualizar `app/telegram/commands/fans.py`:
  - Reemplazar `mm._GOVERNOR_RUNTIME_ENABLED = True` con
    `from app.governance._orchestrator_state import set_governor_enabled; set_governor_enabled(True)`
  - Reemplazar `mm._GOVERNOR_RUNTIME_ENABLED = False` con `set_governor_enabled(False)`
  - Reemplazar `mm._GOVERNOR_RUNTIME_ENABLED` (lectura) con `get_governor_enabled()`
  - `py_compile app/telegram/commands/fans.py` → exit 0

- [x] **T1.3** Actualizar `app/telegram/commands/interventions.py`:
  - Reemplazar referencias a `mm._BALANCER_RUNTIME_ENABLED` con `get/set_balancer_enabled()`
  - `py_compile app/telegram/commands/interventions.py` → exit 0

- [x] **T1.4** Actualizar `miner_monitor.py` — globals existentes:
  - Reemplazar la lectura directa de `_GOVERNOR_RUNTIME_ENABLED` (L3258) con `get_governor_enabled()` de `_orchestrator_state`
  - Reemplazar la lectura directa de `_BALANCER_RUNTIME_ENABLED` (L3897, L4879) con `get_balancer_enabled()` de `_orchestrator_state`
  - Reemplazar `globals().get("_GLOBAL_INTERVENTION_GOV")` (L3267, L3759, L3909) con `get_intervention_gov()`
  - Inyectar singleton en módulo compartido: `_set_igov(_GLOBAL_INTERVENTION_GOV)`
  - `py_compile app/miner_monitor.py` → exit 0

- [x] **T1.5** Ejecutar `pytest -x -q` → 1483 PASS, 75 subtests PASS (validación de Fase 1 completa)

---

## Fase 2 — Migrar `execute_governor_cycle` + `refresh_vnish_overclock_settings`

- [x] **T2.1** Crear `app/governance/governor_cycle.py`:
  - Headers: `from __future__ import annotations`, imports de stdlib + app.governance.*
  - Importar desde `_orchestrator_state`: `get_governor_enabled`, `get_intervention_gov`,
    `get_last_vnish_sync_ts`, `set_last_vnish_sync_ts`
  - Importar desde `miner_monitor`: `log`, `MinerState` (con `TYPE_CHECKING`)
  - Copiar `execute_governor_cycle()` adaptando referencias a globals
  - Copiar `refresh_vnish_overclock_settings()`
  - `py_compile app/governance/governor_cycle.py` → exit 0

- [x] **T2.2** Actualizar `miner_monitor.py`:
  - Añadir import: `from app.governance.governor_cycle import execute_governor_cycle, refresh_vnish_overclock_settings`
  - Eliminar las ~572 líneas de las funciones originales (L3226–L3803)
  - Call sites en `main()` intactos con firmas preservadas
  - `py_compile app/miner_monitor.py` → exit 0

- [x] **T2.3** Actualizar patches de tests (`test_fan_governor_concurrency.py`, `test_silent_mode.py`, `test_tripwire_thread_hardening.py`) y ejecutar `pytest` → 62/62 + 16/16 PASS
- [x] **T2.4** Ejecutar `pytest -x -q` → 1483 PASS

---

## Fase 3 — Migrar `execute_balancer_cycle` (Diferida a Spec 086+)

> **Decisión de Riesgo Arquitectónico**: `execute_balancer_cycle` comparte más de 10 variables globales de módulo directamente con el loop `main()` de `miner_monitor.py` en más de 25 sitios. Extraerlas en esta spec multiplicaría la complejidad del estado y generaría riesgo desproporcionado de desestabilización en producción. Se documenta formalmente como diferida a una spec dedicada.

- [x] **T3.1** Auditoría completa de globals de `execute_balancer_cycle()` completada.
- [-] **T3.2** `app/governance/balancer_cycle.py` — Diferida a Spec posterior con análisis dedicado.
- [-] **T3.3** Desacoplamiento de balancer en `miner_monitor.py` — Diferida.
- [-] **T3.4** Validación de balancer — Diferida.

---

## Fase 4 — Migrar `check_autotune_watchdog` (Diferida a Spec 086+)

- [x] **T4.1** Auditoría de `autotune_watchdog.py` completada.
- [-] **T4.2** Añadir `check_autotune_watchdog()` — Diferida junto a Fase 3 para mantener coherencia de ciclo.
- [-] **T4.3** Actualizar `miner_monitor.py` — Diferida.
- [-] **T4.4** Validación — Diferida.

---

## Fase 5 — Tests de Contrato y Validación

- [x] **T5.1** Crear `tests/test_governance_orchestrator.py` con 15 tests unitarios y de contrato:
  - `test_execute_governor_cycle_importable`
  - `test_governor_cycle_signatures_preserved`
  - `test_refresh_vnish_importable`
  - `test_refresh_vnish_signatures_preserved`
  - Tests de accessors `get/set_governor_enabled`
  - Tests de accessors `get/set_balancer_enabled`
  - Tests de concurrencia thread-safe (`test_concurrent_governor_writes_no_corruption`, `test_concurrent_balancer_writes_no_corruption`)
  - Tests de desacoplamiento de comandos Telegram (`test_fans_py_no_direct_mm_governor_access`, `test_interventions_py_no_direct_mm_balancer_access`)

- [x] **T5.2** Ejecutar `pytest tests/test_governance_orchestrator.py -v` → 15 passed in 0.53s
- [x] **T5.3** Ejecutar suite completa: `pytest -q` → 1498 PASS, 75 subtests PASS (1483 + 15 nuevos)
- [x] **T5.4** Confirmar reducción de líneas: `miner_monitor.py` redujo 572 líneas (9.406 → 8.834 líneas)

---

## Fase 6 — Evidencia y Cierre Documental

- [x] **T6.1** Crear y completar `specs/085-governance-orchestrator/evidence.md`
- [x] **T6.2** Marcar todas las tareas completadas en este archivo
- [x] **T6.3** Actualizar `DEVELOPMENT_LOG.md` (newest-first)
- [x] **T6.4** Actualizar `ROADMAP.md`: Iniciativa 37 como COMPLETE
- [x] **T6.5** Actualizar `SPEC_PROGRAM.md`: Spec 085 como Completed
- [x] **T6.6** Actualizar `DELIVERY_PLAN.md` si aplica
- [x] **T6.7** Ejecutar `speckit-stabilize` para cierre certificado
- [x] **T6.8** Actualizar `prompt.txt` con estado post-Spec-085

---

## Checklist de Invariantes

- `miner_monitor.py` sigue siendo el punto de entrada principal (`main()` sin cambios)
- Las firmas de todas las funciones migradas permanecen idénticas
- Los handlers de Telegram (`fans.py`, `interventions.py`) siguen funcionando correctamente
- No hay importaciones circulares: `app.governance.*` NO importa de `miner_monitor.py`
- Suite global ≥1483 PASS en cada fase antes de continuar
- No se commitea `app/config.json` ni `app/state.json`
