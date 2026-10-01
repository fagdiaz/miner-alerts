# Plan de Implementación: Spec 082 — MinerGovernanceContext

**Spec**: `specs/082-governance-context/spec.md`
**Feature**: `082-governance-context`
**PROP**: PROP-018
**Fecha de planificación**: 2026-10-01
**Prioridad**: P0 — Arquitectónica / Deuda Técnica
**Riesgo**: ALTO (afecta los subsistemas de gobernanza centrales)
**Modelo de implementación**: Claude Sonnet 4.6 (Thinking)

---

## Objetivo

Crear `MinerGovernanceContext`: un dataclass inmutable que actúa como contrato
de estado centralizado entre todos los subsistemas de gobernanza. En esta spec,
la integración se limita al Fan Governor (subsistema más crítico). El patrón
establecido aquí se extenderá en Specs 083 y 085.

**Invariante de seguridad**: Todos los subsistemas existentes siguen funcionando
sin cambios cuando NO reciben el nuevo contexto (retrocompatibilidad total).

---

## Arquitectura de la Solución

### Módulo Nuevo: `app/governance/governance_context.py`

```
MinerGovernanceContext (frozen dataclass)
├── Dominio Potencia
│   ├── current_power_w: Optional[float]       # Potencia real ejecutada por cgminer
│   ├── target_power_w: Optional[float]        # Potencia objetivo del ciclo de gobernanza
│   ├── configured_preset: Optional[str]       # Preset en /config/cgminer.conf (VNish)
│   └── executed_preset: Optional[str]         # Preset activo en cgminer process
│
├── Dominio Térmico
│   ├── chip_temp_c: Optional[float]           # Temperatura máxima de chips (°C)
│   ├── inlet_temp_c: Optional[float]          # Temperatura de inlet (°C)
│   ├── fga_thermal_resistance: Optional[float] # R_th = (T_chip - T_inlet) / P
│   └── fga_cohort: Optional[str]             # "COOL" | "STANDARD" | "HOT" | None
│
├── Dominio Estado Firmware
│   ├── restart_required: bool                 # VNish: cgminer necesita restart
│   ├── restart_detected_ts: Optional[float]  # Timestamp primera detección
│   └── thermal_pause_active: bool            # Pausa térmica activa (thermal_guard)
│
└── Dominio Operativo
    ├── uptime_seconds: Optional[float]        # Uptime del minero en segundos
    ├── electrical_group: Optional[str]        # "elevator_1" | "elevator_2"
    ├── miner_name: str                        # Nombre display del minero
    └── is_warming_up: bool                   # Fase cold-boot grace activa

Métodos de clase:
    from_state(state, now_ts, config) -> MinerGovernanceContext
    # Función pura, sin I/O, sin efectos secundarios
```

### Integración en Fan Governor (`app/governance/fan_governor.py`)

Cambio mínimo — se agrega `ctx` como parámetro opcional al final:

```python
def compute_governor_step(
    cfg: GovernorConfig,
    current_temp_c: float,
    ...
    ctx: Optional["MinerGovernanceContext"] = None,  # NUEVO — opcional
) -> GovernorDecision:
    # Armonización contextual al inicio (paso 0 implícito):
    _effective_target_pwr = target_power_w
    if ctx is not None and ctx.restart_required:
        if ctx.current_power_w is not None and ctx.current_power_w >= 500.0:
            _effective_target_pwr = ctx.current_power_w  # F-02 → contrato formal
    # El resto del algoritmo usa _effective_target_pwr en vez de target_power_w
    # en el check de RECOVERY_MAX_COOLING solamente.
```

### Construcción del Contexto en `miner_monitor.py`

En el bucle por minero, antes de llamar al Fan Governor:

```python
gov_ctx = MinerGovernanceContext.from_state(state, now_ts, config_per_miner)
decision = compute_governor_step(..., ctx=gov_ctx)
```

---

## Diseño Detallado por Archivo

### Archivo 1: `app/governance/governance_context.py` (NUEVO)

- Importaciones: `dataclasses`, `typing`, `__future__` annotations
- Sin dependencias circulares: no importa de `miner_monitor.py`
- `MinerGovernanceContext` con `frozen=True`, `slots=True` (Python 3.10+, fallback sin slots)
- `from_state()` es un `@classmethod` que lee de `MinerState` y dict de config
- Valores por defecto seguros para todos los campos opcionales (`None` o `False`)

### Archivo 2: `app/governance/fan_governor.py` (MODIFICADO)

- Añadir import con `TYPE_CHECKING` guard para evitar circulares en runtime
- Añadir parámetro `ctx: Optional["MinerGovernanceContext"] = None` al final de `compute_governor_step()`
- Insertar bloque de armonización al inicio del cuerpo (antes del paso 1 actual)
- Sin cambios en `GovernorConfig`, `GovernorDecision`, ni demás firmas

### Archivo 3: `app/miner_monitor.py` (MODIFICADO)

- Añadir import de `MinerGovernanceContext` desde `app.governance.governance_context`
- En el bucle de ciclo por minero: construir `gov_ctx = MinerGovernanceContext.from_state(...)`
- Pasar `ctx=gov_ctx` en la llamada a `compute_governor_step()`
- Sin cambios en la lógica de resolución de `target_pwr`, cooldowns ni estados

### Archivo 4 (NUEVO): `tests/test_governance_context_contracts.py`

| Test ID | Test | Descripción |
|---------|------|-------------|
| T001 | `test_context_is_immutable` | `ctx.chip_temp_c = 99` lanza `FrozenInstanceError` |
| T002 | `test_from_state_basic` | Construcción desde MinerState mínimo funciona sin excepciones |
| T003 | `test_from_state_optional_none` | Campos opcionales son `None` si no hay datos en state |
| T004 | `test_governor_no_recovery_when_restart_required` | restart_required=True + curr=2498W → NO RECOVERY_MAX_COOLING |
| T005 | `test_governor_recovery_without_ctx` | Sin ctx, comportamiento idéntico al baseline (paridad) |
| T006 | `test_governor_recovery_with_ctx_false` | ctx.restart_required=False + curr<target-120 → SÍ RECOVERY_MAX_COOLING |
| T007 | `test_ctx_thermal_pause_active` | thermal_pause_active=True se propaga desde MinerState |
| T008 | `test_ctx_fga_cohort_propagation` | fga_cohort se lee desde state.fga_cohort si existe |
| T009 | `test_governor_ctx_overrides_effective_target` | ctx.current_power_w prevalece en check de RECOVERY_MAX_COOLING |
| T010 | `test_governor_backwards_compat_no_ctx` | Llamada sin ctx produce resultado idéntico al baseline |
| T011 | `test_ctx_construction_performance` | from_state() < 1ms (100 iteraciones) |

---

## Contratos de Seguridad

| Invariante | Verificación |
|------------|-------------|
| Retrocompatibilidad total | Tests T005, T010 de paridad sin `ctx` |
| Inmutabilidad del contexto | Test T001 |
| Sin efectos secundarios en `from_state()` | Función pura, inspección de código |
| No RECOVERY_MAX_COOLING con restart_required | Test T004 determinista |
| Ciclo de gobernanza sin latencia adicional | Test T011 (< 1ms construcción) |
| 1440 tests PASS sin regresiones | Gate de cierre en evidence.md |

---

## Riesgos y Mitigaciones

| Riesgo | Probabilidad | Mitigación |
|--------|-------------|-----------|
| Importación circular (`fan_governor` ↔ `governance_context`) | MEDIA | Usar `TYPE_CHECKING` guard en fan_governor.py |
| Regresión en tests del Fan Governor existentes | BAJA | Parámetro `ctx` es `= None` por defecto |
| Campo `fga_cohort` no existe en `MinerState` actual | MEDIA | `getattr(state, 'fga_cohort', None)` seguro |
| `thermal_pause_until_ts` requiere comparación con `now_ts` | MEDIA | Pasar `now_ts` como parámetro a `from_state()` |
| `slots=True` no disponible en Python < 3.10 | BAJA | Verificar versión Python; fallback sin `slots` |

---

## Secuencia de Implementación

```
T1: Verificar campos reales de MinerState (leer miner_monitor.py sección MinerState)
T2: Crear governance_context.py (módulo puro sin dependencias)
T3: Agregar tests T001-T003 → validan módulo puro
T4: Modificar fan_governor.py (import TYPE_CHECKING + parámetro ctx + armonización)
T5: Agregar tests T004-T011 → validan integración Fan Governor
T6: Modificar miner_monitor.py (import + construcción + paso de ctx)
T7: pytest completo → ≥1440 tests PASS
T8: py_compile en 3 archivos modificados
T9: evidence.md + DEVELOPMENT_LOG.md
```

---

## Criterio de Cierre (Definition of Done)

- [ ] `app/governance/governance_context.py` creado y compilado
- [ ] `app/governance/fan_governor.py` modificado con retrocompatibilidad
- [ ] `app/miner_monitor.py` construye y pasa `gov_ctx` en el ciclo de gobernanza
- [ ] `tests/test_governance_context_contracts.py`: 11 tests PASS
- [ ] Suite global: ≥1440 tests PASS, 0 fallos
- [ ] `py_compile` limpio en los 3 archivos modificados
- [ ] `evidence.md` con comandos reales ejecutados y output real
- [ ] `DEVELOPMENT_LOG.md` actualizado al inicio
- [ ] `ROADMAP.md` y `SPEC_PROGRAM.md` actualizados con Spec 082 cerrada
