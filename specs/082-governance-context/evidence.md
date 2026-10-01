# Evidence: Spec 082 — MinerGovernanceContext (PROP-018)

**Fecha**: 2026-10-01
**Ejecutor**: Claude Sonnet 4.6 (Thinking)
**Estado**: CERTIFIED ✅

---

## 1. py_compile — Módulos implementados

### `app/governance/governance_context.py`
```
& ".\.venv\Scripts\python.exe" -m py_compile app\governance\governance_context.py
Exit code: 0 (OK)
```

### `app/governance/fan_governor.py`
```
& ".\.venv\Scripts\python.exe" -m py_compile app\governance\fan_governor.py
Exit code: 0 (OK)
```

### `app/miner_monitor.py`
```
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py
Exit code: 0 (OK)
```

---

## 2. Tests de Contrato — pytest tests/test_governance_context_contracts.py -v

```
26 passed in 0.53s
```

Tests individuales PASS:
- TestT001_Immutability::test_context_is_immutable ✅
- TestT001_Immutability::test_context_immutable_optional_field ✅
- TestT001_Immutability::test_context_immutable_bool_field ✅
- TestT002_FromStateBasic::test_from_state_basic_construction ✅
- TestT002_FromStateBasic::test_from_state_restart_required_true ✅
- TestT002_FromStateBasic::test_from_state_thermal_pause_active ✅
- TestT002_FromStateBasic::test_from_state_thermal_pause_expired ✅
- TestT002_FromStateBasic::test_from_state_is_warming_up_within_grace ✅
- TestT002_FromStateBasic::test_from_state_miner_name_from_display_name ✅
- TestT002_FromStateBasic::test_built_at_ts_monotonic ✅
- TestT003_FromStateNoneFields::test_all_none_state ✅
- TestT003_FromStateNoneFields::test_fga_cohort_none_when_not_set ✅
- TestT003_FromStateNoneFields::test_fga_cohort_propagated ✅
- TestT003_FromStateNoneFields::test_electrical_group_from_group_key ✅
- TestT003_FromStateNoneFields::test_electrical_group_none_when_absent ✅
- TestT004_NoRecoveryWhenRestartRequired::test_governor_no_recovery_when_restart_required ✅
- TestT005_RecoveryWithoutCtx::test_governor_recovery_without_ctx ✅
- TestT006_RecoveryWithCtxFalse::test_governor_recovery_with_ctx_false ✅
- TestT007_ThermalPauseActive::test_ctx_thermal_pause_active ✅
- TestT008_FgaCohortPropagation::test_ctx_fga_cohort_propagation ✅
- TestT009_EffectiveTargetOverride::test_governor_ctx_overrides_effective_target ✅
- TestT009_EffectiveTargetOverride::test_effective_target_unchanged_when_no_restart ✅
- TestT009_EffectiveTargetOverride::test_effective_target_when_restart_and_no_configured_target ✅
- TestT010_BackwardsCompatNoCtx::test_governor_backwards_compat_no_ctx ✅
- TestT010_BackwardsCompatNoCtx::test_governor_backwards_compat_step_up ✅
- TestT011_CtxConstructionPerformance::test_ctx_construction_performance ✅ (< 1ms promedio)

---

## 3. Suite Global — pytest -x -q

```
1466 passed, 75 subtests passed in 46.23s
```

- Baseline previo: 1440 passed, 75 subtests passed
- Incremento: +26 tests nuevos (todos los de Spec 082)
- 0 fallos, 0 errores, 0 warnings críticos

---

## 4. Invariantes verificados

| Invariante | Estado |
|---|---|
| Retrocompatibilidad: llamadas sin `ctx` producen resultados idénticos | ✅ PASS (T010) |
| `MinerState` no modificado por esta spec | ✅ No hay cambios en MinerState |
| No hay campos nuevos en `config.example.json` | ✅ Confirmado |
| No hay cambios en lógica de alertas Telegram, auto-restart, cooldowns | ✅ Confirmado |
| El ciclo de gobernanza no introduce latencia medible | ✅ PASS (T011: < 1ms) |
| `frozen=True` garantiza inmutabilidad post-construcción | ✅ PASS (T001) |

---

## 5. Archivos modificados

| Archivo | Cambio |
|---|---|
| `app/governance/governance_context.py` | NUEVO — `MinerGovernanceContext` frozen dataclass + `effective_target_power_w` property |
| `app/governance/fan_governor.py` | MODIFICADO — `TYPE_CHECKING` import + `ctx` param en `compute_governor_step()` |
| `app/miner_monitor.py` | MODIFICADO — import `MinerGovernanceContext` + `gov_ctx = from_state(...)` + `ctx=gov_ctx` |
| `tests/test_governance_context_contracts.py` | NUEVO — 26 tests de contrato (T001–T011) |
