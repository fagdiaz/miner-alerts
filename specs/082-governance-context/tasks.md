# Tasks: Spec 082 — MinerGovernanceContext

**Feature**: `082-governance-context`
**Fecha**: 2026-10-01
**Prioridad**: P0 — Arquitectónica
**Riesgo**: ALTO

---

## Fase 0 — Reconocimiento (Pre-implementación)

- [x] **T0.1** Leer `MinerState` en `miner_monitor.py` para mapear campos reales existentes
  (`vnish_restart_required`, `vnish_restart_detected_ts`, `thermal_pause_until_ts`,
  `balancer_preset`, `is_warming_up`, etc.)
- [x] **T0.2** Leer la sección de llamada a `compute_governor_step()` en `miner_monitor.py`
  para identificar el punto exacto de inyección del contexto
- [x] **T0.3** Verificar versión de Python del venv: `& ".venv\Scripts\python.exe" --version`
  (determina si `slots=True` está disponible en dataclass)
- [x] **T0.4** Verificar que `fga_cohort` exista en `MinerState` o en `state` como atributo

## Fase 1 — Módulo Puro (sin dependencias)

- [x] **T1.1** Crear `app/governance/governance_context.py` con `MinerGovernanceContext`
  (frozen dataclass, 4 dominios, 12 campos tipados)
- [x] **T1.2** Implementar `MinerGovernanceContext.from_state(state, now_ts, config)` como
  classmethod puro (sin I/O, sin efectos secundarios)
- [x] **T1.3** `py_compile app/governance/governance_context.py` → debe pasar sin errores

## Fase 2 — Tests del Módulo Puro

- [x] **T2.1** Crear `tests/test_governance_context_contracts.py`
- [x] **T2.2** Implementar T001: `test_context_is_immutable` (frozen=True lanza FrozenInstanceError)
- [x] **T2.3** Implementar T002: `test_from_state_basic` (construcción mínima sin excepciones)
- [x] **T2.4** Implementar T003: `test_from_state_optional_none` (campos None cuando no hay datos)
- [x] **T2.5** Ejecutar `pytest tests/test_governance_context_contracts.py -v` → 26 tests PASS (superó el mínimo de 3)

## Fase 3 — Integración Fan Governor

- [x] **T3.1** Modificar `app/governance/fan_governor.py`:
  - Añadir `from typing import TYPE_CHECKING` (si no existe)
  - Añadir guard `if TYPE_CHECKING: from app.governance.governance_context import MinerGovernanceContext`
  - Añadir `ctx: Optional["MinerGovernanceContext"] = None` al final de la firma de `compute_governor_step()`
  - Insertar bloque de armonización al inicio del cuerpo (antes del paso 1)
- [x] **T3.2** `py_compile app/governance/fan_governor.py` → debe pasar sin errores
- [x] **T3.3** Implementar T004: `test_governor_no_recovery_when_restart_required`
  (restart_required=True + curr=2498W → NO RECOVERY_MAX_COOLING)
- [x] **T3.4** Implementar T005: `test_governor_recovery_without_ctx`
  (sin ctx, idéntico al baseline — paridad)
- [x] **T3.5** Implementar T006: `test_governor_recovery_with_ctx_false`
  (ctx.restart_required=False + curr<target-120 → SÍ RECOVERY_MAX_COOLING)
- [x] **T3.6** Implementar T007: `test_ctx_thermal_pause_active`
- [x] **T3.7** Implementar T008: `test_ctx_fga_cohort_propagation`
- [x] **T3.8** Implementar T009: `test_governor_ctx_overrides_effective_target`
- [x] **T3.9** Implementar T010: `test_governor_backwards_compat_no_ctx`
- [x] **T3.10** Implementar T011: `test_ctx_construction_performance` (< 1ms)
- [x] **T3.11** Ejecutar `pytest tests/test_governance_context_contracts.py -v` → 26 tests PASS

## Fase 4 — Integración en Ciclo Principal

- [x] **T4.1** Modificar `app/miner_monitor.py`:
  - Añadir import de `MinerGovernanceContext` desde `app.governance.governance_context`
  - En el bucle de ciclo por minero, antes del Fan Governor:
    `gov_ctx = MinerGovernanceContext.from_state(state, now_ts, miner_config)`
  - Pasar `ctx=gov_ctx` a `compute_governor_step()`
- [x] **T4.2** `py_compile app/miner_monitor.py` → debe pasar sin errores

## Fase 5 — Validación Global

- [x] **T5.1** Ejecutar suite completa: `pytest -x -q` → 1466 tests PASS, 75 subtests, 0 fallos, 0 errores
- [x] **T5.2** Confirmar que los tests de Fan Governor existentes (no los nuevos) siguen pasando
  sin cambios en sus fixtures

## Fase 6 — Evidencia y Cierre Documental

- [x] **T6.1** Crear `specs/082-governance-context/evidence.md` con:
  - Output de `py_compile` en los 3 archivos
  - Output de `pytest tests/test_governance_context_contracts.py -v` (26 tests)
  - Output de `pytest -x -q` (suite global)
  - Timestamp de ejecución
- [x] **T6.2** Marcar todas las tareas completadas en este archivo
- [x] **T6.3** Actualizar `DEVELOPMENT_LOG.md` con entrada newest-first para Spec 082
- [x] **T6.4** Actualizar `ROADMAP.md`: Iniciativa 34 marcada como COMPLETE
- [x] **T6.5** Actualizar `SPEC_PROGRAM.md`: Spec 082 como Completed en Program State
- [x] **T6.6** Actualizar `DELIVERY_PLAN.md`: Spec 082 como Closed

---

## Checklist de Invariantes (no tocar)

- Retrocompatibilidad: las llamadas a `compute_governor_step()` sin `ctx` producen resultados idénticos
- `MinerState` no se modifica por esta spec
- No se agregan campos a `config.example.json` (el contexto se construye desde state existente)
- No hay cambios en la lógica de alertas Telegram, auto-restart, ni cooldowns
- El ciclo de gobernanza no introduce latencia medible
