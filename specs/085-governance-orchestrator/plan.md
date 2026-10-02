# Plan: Spec 085 — Extracción del Orquestador de Gobernanza (PROP-021)

**Feature**: `085-governance-orchestrator`
**Fecha**: 2026-10-01
**Riesgo**: ALTO
**Baseline**: 1483 tests PASS, 75 subtests PASS

---

## Análisis de Obstáculos Pre-Migración

### Obstáculo 1: `globals().get("_GLOBAL_INTERVENTION_GOV")` (L3267)

`execute_governor_cycle()` accede dinámicamente al namespace global de `miner_monitor.py` para obtener
`_GLOBAL_INTERVENTION_GOV`. Si la función se mueve a otro módulo, `globals()` ya no verá esa variable.

**Solución**: Antes de mover la función, refactorizar el anti-patrón a un import directo del módulo:
```python
# Antes (L3267):
gov_obj = globals().get("_GLOBAL_INTERVENTION_GOV")

# Después:
from app.governance._orchestrator_state import get_intervention_gov
gov_obj = get_intervention_gov()
```

### Obstáculo 2: Variables globales de módulo compartidas entre funciones

`_GOVERNOR_RUNTIME_ENABLED`, `_BALANCER_RUNTIME_ENABLED`, `_GLOBAL_INTERVENTION_GOV`, 
`_LAST_VNISH_SYNC_TS`, etc. viven en `miner_monitor.py` y son accedidas por:
- Las funciones que vamos a mover
- Los handlers de Telegram (`/gov on`, `/gov off`, `/bal on`, `/bal off`)

Si simplemente movemos las funciones, los handlers de Telegram dejarán de ver los globals.

**Solución**: Crear `app/governance/_orchestrator_state.py` — módulo de estado compartido que centraliza
estos globals. Tanto `miner_monitor.py` (para los handlers de Telegram) como los nuevos módulos de ciclo
importarán de ahí.

---

## Estrategia de Migración — 4 Fases

### Fase 0: Crear módulo de estado compartido

Crear `app/governance/_orchestrator_state.py`:
```python
# Globals compartidos entre miner_monitor.py y los módulos de ciclo
_GOVERNOR_RUNTIME_ENABLED: Optional[bool] = None
_BALANCER_RUNTIME_ENABLED: Optional[bool] = None
_LAST_VNISH_SYNC_TS: float = 0.0
_LAST_BALANCER_CYCLE_TS: float = 0.0
_GLOBAL_INTERVENTION_GOV: InterventionGovernance = InterventionGovernance()

# Accessors thread-safe para los handlers de Telegram y los ciclos
def get_governor_enabled() -> Optional[bool]: ...
def set_governor_enabled(val: Optional[bool]) -> None: ...
def get_balancer_enabled() -> Optional[bool]: ...
def set_balancer_enabled(val: Optional[bool]) -> None: ...
def get_intervention_gov() -> InterventionGovernance: ...
def get_last_vnish_sync_ts() -> float: ...
def set_last_vnish_sync_ts(ts: float) -> None: ...
```

### Fase 1: Migrar `execute_governor_cycle` + `refresh_vnish_overclock_settings`

**Origen**: `miner_monitor.py` L3231–L3653  
**Destino**: `app/governance/governor_cycle.py`

Pasos:
1. Crear `app/governance/governor_cycle.py` con los imports necesarios.
2. Copiar `execute_governor_cycle()` y `refresh_vnish_overclock_settings()`.
3. Reemplazar `globals().get("_GLOBAL_INTERVENTION_GOV")` con `get_intervention_gov()`.
4. Reemplazar `global _GOVERNOR_RUNTIME_ENABLED` / `global _LAST_VNISH_SYNC_TS` con
   las funciones de `_orchestrator_state`.
5. En `miner_monitor.py`: reemplazar las ~415 + 207 líneas con:
   ```python
   from app.governance.governor_cycle import execute_governor_cycle, refresh_vnish_overclock_settings
   ```
6. Actualizar los handlers `/gov on`, `/gov off` para usar `set_governor_enabled()` de `_orchestrator_state`.
7. `py_compile` ambos archivos + `pytest -x -q`.

### Fase 2: Migrar `execute_balancer_cycle`

**Origen**: `miner_monitor.py` L3799–L4109  
**Destino**: `app/governance/balancer_cycle.py`

Incluye los globals de balancer: `_BALANCER_RUNTIME_ENABLED`, `_LAST_BALANCER_CYCLE_TS`,
`_POST_BLACKOUT_TRACKER`, `_ACTIVE_PHASE_DROPS`, `_LAST_PHASE_DROP_ALERT_TS`, etc.

### Fase 3: Migrar `check_autotune_watchdog`

**Origen**: `miner_monitor.py` L4110–L4249  
**Destino**: `app/governance/autotune_watchdog.py` (módulo existente, añadir función)

### Fase 4: Tests de contrato + Validación global

- Crear `tests/test_governance_orchestrator.py` con tests de contrato para:
  - `execute_governor_cycle` importada desde `governor_cycle.py`
  - `execute_balancer_cycle` importada desde `balancer_cycle.py`
  - Estado compartido via `_orchestrator_state.py`
- Suite global: `pytest -x -q` → ≥1483 PASS

---

## Impacto estimado en líneas

| Acción | Líneas en miner_monitor.py |
|---|---|
| Baseline actual | 9.385 |
| -Fase 1 (governor + vnish) | -620 |
| -Fase 2 (balancer) | -310 |
| -Fase 3 (watchdog) | -140 |
| +imports añadidos | +6 |
| **Total estimado** | **~8.321** |

Reducción: ~1.064 líneas (-11.3%).

---

## Nota sobre el objetivo ≤6.000 líneas

Para alcanzar ≤6.000 líneas se necesitaría además extraer:
- Telegram polling worker (~400 L) → `app/telegram/poller.py`
- Handlers de callbacks (~1.200 L) → `app/telegram/handlers/`
- Funciones de formateo (~300 L) → `app/telegram/formatters/`
- Funciones de MinerState → `app/core/miner_state.py`

Eso es alcance de Spec 086+. Esta spec acota el riesgo al bloque de gobernanza.

---

## Orden de implementación seguro

```
Fase 0 (_orchestrator_state.py)
  ↓ py_compile + pytest -x -q
Fase 1 (governor_cycle.py)
  ↓ py_compile + pytest -x -q
Fase 2 (balancer_cycle.py)
  ↓ py_compile + pytest -x -q
Fase 3 (autotune_watchdog.py)
  ↓ py_compile + pytest -x -q
Fase 4 (tests + cierre documental)
```
