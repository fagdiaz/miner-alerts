# Spec 085 — Extracción del Orquestador de Gobernanza: `GovernanceOrchestrator` (PROP-021)

**Feature ID**: `085-governance-orchestrator`
**Propuesta**: PROP-021
**Fecha**: 2026-10-01
**Autor**: Claude Sonnet 4.6 (Thinking)
**Prioridad**: P1 — Arquitectónica / Deuda Técnica
**Riesgo**: ALTO
**Dependencias**: Spec 082 ✅, Spec 083 ✅, Spec 084 ✅
**Baseline**: 1483 tests PASS, 75 subtests PASS, 0 fallos

---

## 1. Problema

`miner_monitor.py` tiene **9.385 líneas** y concentra lógica de dominio muy dispar:
- Adquisición de telemetría (ASIC API 4028, VNish REST)
- Gobernanza de ciclo (Fan Governor, Balancer, Autotune Watchdog)
- Mantenimiento de estado (load/save, MinerState)
- Telegram (polling, comandos, callbacks, formateo)
- Coordinación cross-subsistema (target_pwr, interlocks térmicos)

Consecuencia directa: **cada spec de gobernanza toca el archivo más crítico del sistema**, aumentando el riesgo de regresión por colisión de cambios. Las Specs 082–084 ya lo demostraron.

### Funciones candidatas a extraer (≈998 líneas):

| Función | Líneas actuales | Módulo destino |
|---|---|---|
| `execute_governor_cycle()` | L3239–L3653 (415 L) | `app/governance/governor_cycle.py` |
| `refresh_vnish_overclock_settings()` | L3654–L3860 (207 L) | `app/governance/governor_cycle.py` |
| `execute_balancer_cycle()` | L3861–L4109 (249 L) | `app/governance/balancer_cycle.py` |
| `check_autotune_watchdog()` | L4110–L4249 (140 L) | `app/governance/autotune_watchdog.py` (ya existe) |

---

## 2. Diseño de Solución

### Patrón: Module Migration + Thin Shim (sin refactorización de API)

**Principio de seguridad #1**: No cambiar las firmas de funciones. Las funciones se mueven a nuevos módulos con firmas idénticas. `miner_monitor.py` importa y llama igual que antes.

**Principio de seguridad #2**: No mover globals. Los globals de módulo (`_GOVERNOR_RUNTIME_ENABLED`, `_BALANCER_RUNTIME_ENABLED`, etc.) se mueven junto con sus funciones al nuevo módulo.

**Principio de seguridad #3**: Un módulo a la vez. Cada función se migra en una tarea independiente con `py_compile` + `pytest` entre cada una.

### Nuevo módulo: `app/governance/governor_cycle.py`

Contiene:
- Global `_GOVERNOR_RUNTIME_ENABLED`
- Global `_LAST_VNISH_SYNC_TS`
- `execute_governor_cycle(miners, states, state_lock, config, now_ts, qa_mode)`
- `refresh_vnish_overclock_settings(miners, states, state_lock, vnish_pw, timeout, force, now_ts)`

### Nuevo módulo: `app/governance/balancer_cycle.py`

Contiene:
- Global `_BALANCER_RUNTIME_ENABLED`
- Global `_LAST_BALANCER_CYCLE_TS`
- Todos los globals relacionados con balancer (`_POST_BLACKOUT_TRACKER`, `_LAST_PHASE_DROP_ALERT_TS`, etc.)
- `execute_balancer_cycle(miners, states, state_lock, config, now_ts, qa_mode, db_path, ...)`

### Módulo existente ampliado: `app/governance/autotune_watchdog.py`

- `check_autotune_watchdog()` se mueve desde `miner_monitor.py` al módulo que ya existe.

### `miner_monitor.py` post-migración

- Importa las funciones desde sus nuevos módulos.
- Llama con exactamente los mismos argumentos.
- Las ≈998 líneas migradas se reemplazan por ≈3 líneas de import.
- Resultado estimado: **~8.390 líneas** (reducción de ~995 líneas = -10.6%).

> **Nota sobre el objetivo ≤6.000 líneas del ROADMAP**: Alcanzar ≤6.000 líneas requeriría además migrar el polling de Telegram (~880 líneas), los handlers de callbacks (~1.200 líneas) y las funciones de formateo de texto (~600 líneas). Eso es alcance de Spec 086+. Esta spec se limita al bloque de gobernanza para mantener el riesgo controlado.

---

## 3. Impacto y Riesgo

### Riesgos identificados

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| Globals compartidos entre módulos | MEDIA | Mover globals junto con sus funciones al módulo destino; exponer via `__all__` |
| Imports circulares | MEDIA | `miner_monitor.py` importa de `app.governance.*`; `app.governance.*` NO importa de `miner_monitor.py` — dirección unidireccional ya establecida |
| Tests que parchean paths internos | BAJA | Auditar tests de Fan Governor, Balancer, Watchdog antes de migrar |
| Regresión en concurrencia | BAJA | Las funciones no cambian de comportamiento, solo de ubicación |

### Tests de regresión requeridos

```
pytest tests/test_fan_governor*.py -v
pytest tests/test_governance_context_contracts.py -v
pytest tests/test_fga_actuator.py tests/test_facility_agent.py -v
pytest -x -q  # Suite global: debe mantenerse ≥1483 PASS
```

---

## 4. Criterio de Éxito (DoD)

1. `app/governance/governor_cycle.py` creado con `execute_governor_cycle` y `refresh_vnish_overclock_settings`.
2. `app/governance/balancer_cycle.py` creado con `execute_balancer_cycle` y sus globals asociados.
3. `check_autotune_watchdog()` integrada en `app/governance/autotune_watchdog.py`.
4. `miner_monitor.py` importa las funciones desde sus nuevos módulos. **No hay cambios de comportamiento.**
5. `py_compile` en los 4 archivos modificados: exit 0.
6. Suite global: **≥1483 tests PASS**, 0 fallos, 0 errores.
7. NSSM MinerAlerts RUNNING post-deploy.
8. `miner_monitor.py` reducido de 9.385 a ≤8.400 líneas.

---

## 5. Fuera del Alcance

- Cambios en lógica de gobernanza (Fan Governor, Balancer) → Spec 086+
- Migración de Telegram polling/handlers → Spec 086+
- Cambio de firmas de funciones
- Creación de clase `GovernanceOrchestrator` (se evalúa en Spec 086 si la extracción plana resulta insuficiente)
