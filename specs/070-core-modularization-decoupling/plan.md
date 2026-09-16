# Plan de Implementación — Spec 070: Modularización del Core Fase B — Desacoplamiento Seguro de inspect.getsource(main) (ST-05)

**ID**: 070  
**Rama**: `codex/022-adaptive-acquisition`  
**Estado**: Planificado  

---

## 1. Matriz de Equivalencia Funcional (37 Invariantes)

| Suite Legada | Tests | Invariante Evaluado Textualmente | Equivalente en Behavioral Harness |
| :--- | :---: | :--- | :--- |
| `test_auto_reboot_signal_gate.py` | 8 | `state.low_since_ts = None` en `reboot_reason`; compuertas de señal `auto_reboot_signal_allows_evaluation` | Simular tick con `reboot_reason != None` $\rightarrow$ comprobar que `state.low_since_ts` se anula y no evalúa auto-reboot. |
| `test_hashboard_auto_reboot.py` | 8 | `elif (\n new_state == STATE_HASHBOARD`; secuencia de 6 interlocks | Simular minero con `active_boards < 3` $\rightarrow$ verificar transición directa a `STATE_HASHBOARD` y comprobación secuencial de los 6 interlocks. |
| `test_reboot_safety.py` | 13 | Orden textual: `startup < sustained < interlocks < cooldown < window < hashcore` | Inyectar secuencialmente fallos en cada compuerta $\rightarrow$ comprobar que la compuerta previa bloquea la evaluación de las posteriores. |
| `test_vnish_hashboard_detection.py` | 8 | `active_boards < expected_boards` antes de `rate_ths < threshold_ths` | Minero con 2 placas y hashrate bajo $\rightarrow$ verificar que se diagnostica `HASHBOARD` (no `LOW`). |

---

## 2. Arquitectura del Arnés de Comportamiento (`tests/test_supervisory_core_behavioral.py`)

```python
class SupervisoryBehavioralHarness:
    """Arnés de prueba de caja negra que orquesta ticks deterministas."""
    def __init__(self) -> None:
        self.context = build_mock_monitor_context()
        self.engine = CoreSupervisoryEngine(self.context)
        # Registrar hooks reales...

    def run_tick(
        self,
        miners_payload: List[Dict[str, Any]],
        now_ts: float,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> TickResult:
        return self.engine.execute_tick(now_ts=now_ts, extra_tick_data=extra_data)
```

---

## 3. Fases de Ejecución

1. **Fase 1 (Arnés Puro)**: Construir `tests/test_supervisory_core_behavioral.py` conteniendo los 37 tests funcionales. Ejecutar la suite: verificar que los 37 tests pasan.
2. **Fase 2 (Validación Dual)**: Ejecutar `unittest discover`: verificar $\ge 1109$ tests globales PASS. El código de producción permanece inalterado.
3. **Fase 3 (Refactorización de Hooks)**: Modularizar `miner_monitor.py` extrayendo la lógica a `DetectionHook` y `ActuatorHook`. Actualizar los 4 archivos de test legados para que invoquen funciones de evaluación puras en lugar de `inspect.getsource(main)`.
