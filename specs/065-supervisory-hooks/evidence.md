# Evidence: Spec 065 — Pipeline Declarativo de Hooks en CoreSupervisoryEngine (ST-04)

**Date**: 2026-09-15 | **Status**: COMPLETED | **Branch**: `codex/022-adaptive-acquisition`

---

## Syntax Validation

```
& ".venv\Scripts\python.exe" -m py_compile app\core\engine.py app\core\context.py app\miner_monitor.py
# Output: SYNTAX OK (exit code 0)
```

---

## New Test Suite: tests/test_supervisory_hooks.py

```
& ".venv\Scripts\python.exe" -m pytest tests\test_supervisory_hooks.py -q --tb=short
# Output: 47 passed in 0.72s
```

**Clases de tests cubiertas:**
- `TestHookStageOrdering` — 5 tests: orden determinista de etapas, min/max, 7 etapas existentes.
- `TestSupervisoryHookBase` — 2 tests: contrato de clase base.
- `TestHookResult` — 2 tests: dataclass, valores por defecto, error result.
- `TestRegisterHook` — 3 tests: ordenamiento al registrar, múltiples hooks por etapa, copia.
- `TestExecuteTick` — 5 tests: orden de ejecución, tick_data flow, TickResult, hook_results.
- `TestErrorContainment` — 5 tests: error registrado, pipeline continúa, result.ok=False, múltiples fallos.
- `TestPersistenceGuarantee` — 3 tests: PERSISTENCE siempre se ejecuta, incluso si todo falla.
- `TestMonotonicTimingModel` — 4 tests: sleep > 0 en hooks rápidos, clamp a 0 en hooks lentos, duración medida, fórmula max(0, poll - elapsed).
- `TestTimingGuardHook` — 4 tests: stage PRE_TICK, name, tick_data._timing_guard_start, ejecución sin error.
- `TestGovernanceInterlockHook` — 3 tests: stage GOVERNANCE, retorno sin governance, retorno dict.
- `TestPersistenceHook` — 3 tests: stage PERSISTENCE, llama state_manager.save(), sin crash si sm=None.
- `TestEnginePipelineE2E` — 5 tests: pipeline canónico sin errores, orden correcto, tick_sequence, sin hooks, count.
- `TestMinerMonitorEngineIntegration` — 3 tests: importaciones disponibles, fórmula sleep correcta, PERSISTENCE < POST_TICK.

---

## T006 Integration: miner_monitor.py

**Archivo modificado**: `app/miner_monitor.py`

**Cambio 1** — Instanciación del engine antes del `while True:` (líneas ~5313-5328):
```python
# Spec 065: Pipeline declarativo de hooks — instanciación aditiva
from app.core.engine import (
    CoreSupervisoryEngine,
    GovernanceInterlockHook,
    PersistenceHook,
    TimingGuardHook,
)
_supervisory_engine = CoreSupervisoryEngine(monitor_ctx)
_supervisory_engine.register_hook(TimingGuardHook(warn_threshold_seconds=25.0))
_supervisory_engine.register_hook(GovernanceInterlockHook())
_supervisory_engine.register_hook(PersistenceHook())
log(
    f"SUPERVISORY_HOOKS pipeline_ready=true "
    f"hooks={len(_supervisory_engine.registered_hooks)} "
    f"stages=[PRE_TICK,GOVERNANCE,PERSISTENCE]"
)
```

**Cambio 2** — Reemplazo de `time.sleep(poll_seconds)` por modelo monotónico (líneas ~7258-7276):
```python
# Spec 065: Pipeline de hooks + modelo monotónico de tiempo
try:
    _supervisory_engine.execute_tick(
        states=states,
        last_update_id_ref=last_update_id_ref,
        now_ts=now_ts,
    )
except Exception as _hook_exc:
    log(f"[WARN] SUPERVISORY_HOOKS execute_tick failed: {type(_hook_exc).__name__}: {_hook_exc}")
# Modelo monotónico: poll_seconds es intervalo mínimo entre tick_starts.
_elapsed = time.monotonic() - tick_start
_sleep_seconds = max(0.0, poll_seconds - _elapsed)
time.sleep(_sleep_seconds)
```

**Contratos de inspect.getsource(main) — no violados:**
- `test_auto_reboot_signal_gate`: busca `"state.low_since_ts = None"`, `"auto_reboot_signal"` → intacto.
- `test_hashboard_auto_reboot`: busca `"elif (\n                    new_state == STATE_HASHBOARD"` → intacto.
- `test_reboot_safety`: busca patrones de seguridad en main() y telegram_polling_worker → intacto.
- `test_vnish_hashboard_detection`: busca `inspect.getsource(main)` → intacto.

---

## Global Test Suite

```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
# Output: Ran 1043 tests in 34.225s — OK (0 failures, 0 errors)
```

**Confirmación**: 1043/1043 tests PASS (996 baseline + 47 nuevos de Spec 065). Cero regresiones.
Servicio Windows `MinerAlerts` verificado en estado `Running`.

---

## Invariantes Verificadas

| Invariante | Estado |
|---|---|
| `len(tests_pass) >= 996` | ✅ Verificado |
| Contratos `inspect.getsource(main)` intactos | ✅ Verificado |
| Sintaxis Python válida (py_compile) | ✅ Verificado |
| PERSISTENCE siempre se ejecuta | ✅ 3 tests dedicados |
| Modelo monotónico: `sleep = max(0, poll - elapsed)` | ✅ 4 tests + aplicado en main() |
| Zero peticiones HTTP extras | ✅ Sin nuevas llamadas de red |
