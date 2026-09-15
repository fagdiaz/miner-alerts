# Tasks - Spec 057: Intervention Governance & Adaptive Elevator Contingency

## Protocolo de Ejecución Segura para Gemini 3.8 Flash High
Para garantizar precisión matemática absoluta, carga al ~40-50% de contexto por iteración, y cero riesgo de alucinación o regresiones en producción, la Spec 057 se divide en **4 Iteraciones Bounded y Secuenciales**:

```
[Iteración 1: Modelo Puro Gobernanza & Menús] -> [Iteración 2: Interlocking & Persistencia] -> [Iteración 3: Contingencia Asimétrica Canario] -> [Iteración 4: Telegram, Regresión y Despliegue]
```

---

## Iteración 1: Modelo Puro de Gobernanza de Intervenciones y Menús Táctiles de Telegram
> **Alcance**: Módulo puro de gobernanza y componentes visuales/táctiles para Telegram Command Center. Riesgo en producción: **0%**.
- [x] **T001**: Crear módulo puro `app/governance/intervention_policy.py`:
  - Dataclass `InterventionGovernance(master_enabled=True, reboots_enabled=True, governor_enabled=True, contingency_enabled=True, expires_at_ts=None, disabled_reason="")`.
  - Función pura `should_allow_intervention(action_type: str, gov: InterventionGovernance, now_ts: float) -> Tuple[bool, str]`.
  - Función pura `apply_governance_toggle(gov: InterventionGovernance, target: str, now_ts: float, duration_seconds: Optional[float] = None) -> InterventionGovernance`.
  - Helper `format_governance_status(gov: InterventionGovernance, now_ts: float) -> str`.
- [x] **T002**: Extender `app/telegram/command_center.py`:
  - Constantes: `CC_NAV_INTERVENTIONS = "cc:nav:interventions"`, `CC_ACT_INT_TOGGLE = "cc:act:int_tog"`, `CC_ACT_INT_ALL = "cc:act:int_all"`, `CC_ACT_INT_TIMER = "cc:act:int_tim"`.
  - Función pura `render_interventions_menu(gov: InterventionGovernance, now_ts: float) -> Tuple[str, Dict[str, Any]]`.
  - Actualizar `render_main_dashboard` para incluir el botón `[ 🛡️ Intervenciones: 🟢/🟡/🔴 ]`.
  - Extender `parse_command_center_callback` para reconocer la gramática `cc:nav:interventions` y `cc:act:int_*`.
- [x] **T003**: Crear suite de tests unitarios `tests/test_intervention_governance.py` validando lógica pura, transiciones de estado, temporizadores de expiración y ruteo de layouts.
- [x] **T004**: Ejecutar `unittest tests.test_intervention_governance` y verificar 100% PASS.


---

## Iteración 2: Integración de Interlocking en Actuadores del Monitor
> **Alcance**: Cablear guardián de gobernanza en el bucle principal de monitorización y persistencia de estado.
- [x] **T005**: Incorporar `intervention_gov: InterventionGovernance` en el estado global o `MinerState` con carga y guardado atómico en `save_state` y `load_state` de `app/miner_monitor.py`.
- [x] **T006**: Interlockear actuadores mutantes con `should_allow_intervention`:
  - Guard en Nivel 1 Soft Restart (`evaluate_auto_restart_candidate` / `_async_execute_mining_restart`).
  - Guard en Nivel 2 Hard Reboot (`auto_reboot_signal_allows_evaluation`).
  - Guard en Fan Governor (`fan_governor_step`).
  - Guard en Preset Balancer.
- [x] **T007**: Agregar auto-reactivación al expirar `expires_at_ts` en el tick del monitor con notificación proactiva a Telegram:
  `🛡️ INTERVENCIONES REACTIVADAS AUTOMÁTICAMENTE: Finalizó la suspensión temporal.`
- [x] **T008**: Validar que la telemetría, el guardado en SQLite, el watchdog y las alertas sigan operando normalmente con intervenciones desactivadas (tests deterministas en `tests/test_intervention_governance.py`).

---

## Iteración 3: Módulo de Contingencia Asimétrica Relativa al Estado Actual (Canary Throttle)
> **Alcance**: Lógica pura de contingencia matutina por elevador, sin asumir 2700W fijos y basada en el minero sensible/canario.
- [x] **T009**: Crear módulo `app/governance/adaptive_contingency.py`:
  - Asignación declarativa de mineros canarios por grupo (`elevator_1` $\to$ S19JPRO-24, `elevator_2` $\to$ S19JPRO-25).
  - Función pura `find_previous_preset_tier(current_preset: str) -> Optional[str]` basada en `DEFAULT_PRESET_LADDER` (relativa al estado actual, nunca asume 2700W).
  - Función pura `evaluate_canary_contingency(event_type: str, miner_name: str, elevator_group: str, fleet_presets: Dict[str, str], elevator_restarts_in_window: int) -> Optional[ContingencyAction]`:
    * Al primer reinicio en el elevador: solo desescala el minero canario 1 peldaño de su preset actual. El compañero se mantiene inalterado.
    * Regla de límites: Si el canario vuelve a reiniciar, desescala otro peldaño. Si el compañero robusto reinicia, reduce 1 peldaño.
    * Regla de Step-Up: Si transcurren 2 horas sin reinicios en el grupo, rampa progresiva hacia arriba.
- [x] **T010**: Crear `tests/test_adaptive_contingency.py` con pruebas unitarias deterministas cubriendo casos de reinicio inicial de canario, reinicio de robusto, límites y recuperación suave.
- [x] **T011**: Ejecutar `unittest tests.test_adaptive_contingency` y verificar 100% PASS.

---

## Iteración 4: UX Telegram, Certificación Global (880+ tests) y Cierre
> **Alcance**: Integración final de callbacks, comprobación global de cero regresiones y documentación.
- [x] **T012**: Cablear despacho de callbacks `cc:act:int_*` en `_handle_command_center_callback` en `app/miner_monitor.py`.
- [x] **T013**: Añadir comandos rápidos de texto `/interventions <on|off|status|30m|1h|2h>` y `/contingency <status|reset>`.
- [x] **T014**: Ejecutar suite global completa de pruebas unitarias (`unittest discover -s tests`) certificando 881+ tests PASS (cero regresiones).
- [x] **T015**: Validar sintaxis con `py_compile app/miner_monitor.py`.
- [x] **T016**: Actualizar `docs/audit/DEVELOPMENT_LOG.md`, `docs/speckit/ROADMAP.md` y dejar `prompt.txt` listo para la ejecución de la Iteración 1.
