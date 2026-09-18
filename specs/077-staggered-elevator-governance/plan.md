# Implementation Plan: Spec 077 — Gobernanza Escalonada de Elevadores, Bajada Compartida y Soft-Contingencia Horaria

## 1. Arquitectura de Módulos

1. **`app/governance/elevator_budget.py` (Nuevo Módulo Determinista Puro)**:
   - `FacilityBudgetState`:
     - `last_facility_transition_ts`: Timestamp del último cambio de preset en toda la instalación.
     - `active_transition_miner`: Minero actualmente en ventana de estabilización.
     - `settle_window_seconds`: 180.0s.
   - `can_facility_transition_miner(miner_name, target_preset, now_ts)`:
     - Verifica si la instalación completa superó la ventana de 180s.
     - Verifica si la potencia del grupo supera 5000W en horario de Soft-Contingencia o 5400W en valle.
   - `evaluate_soft_contingency_schedule(now_dt)`:
     - Evalúa si el momento actual (hora local UTC-3) cae en Lunes-Viernes 08:30-10:30 o 19:30-22:30.
     - Retorna si la Soft-Contingencia está activa y el preset techo (2500W).
   - `choose_optimal_pair_presets(current_p1, current_p2, target_group_power)`:
     - Aplica la preferencia simétrica: prefiere (2500, 2500) antes que (2700, 2300).

2. **`app/governance/preset_balancer.py` (Extensión)**:
   - Integración de `can_facility_transition_miner`: Si la bajada compartida está en ventana de settle o el presupuesto se excede, pospone la orden con `ACTION_HOLD_FACILITY_SETTLE` o `ACTION_HOLD_BUDGET_LIMIT`.

3. **`app/miner_monitor.py` (Integración Operativa)**:
   - Instanciación de `FacilityBudgetState` compartido.
   - En cada tick supervisor, evaluación de Soft-Contingencia horaria: si se entra en franja crítica, encola desescaladas escalonadas hacia 2500W.
   - Envío de notificaciones informativas a Telegram (`[SOFT-CONTINGENCIA] Activada franja pico...`).

---

## 2. Fases de Implementación y Certificación

- **Fase 1 (T001)**: Módulo puro `app/governance/elevator_budget.py`.
- **Fase 2 (T002)**: Suite de pruebas unitarias exhaustivas en `tests/test_elevator_budget.py`.
- **Fase 3 (T003)**: Integración con `preset_balancer.py` (prioridad simétrica y cerrojo de bajada compartida).
- **Fase 4 (T004)**: Integración en loop de producción de `miner_monitor.py`.
- **Fase 5 (T005)**: Validación de suite global ($\ge 1285$ tests PASS) y compilación limpia (`py_compile`).
- **Fase 6 (T006 - T007)**: Documentación de evidencia, log de desarrollo, commit Git y reinicio de servicio Windows.
