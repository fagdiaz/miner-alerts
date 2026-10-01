# Plan de Implementación: Spec 083 — FGA Actuator Loop (PROP-019)

**Branch**: `codex/022-adaptive-acquisition` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/083-fga-actuator-loop/spec.md`

---

## Resumen Ejecutivo

Conectar el motor de optimización asimétrica de planta ([`facility_agent.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/facility_agent.py)) con el orquestador de presupuestos de potencia ([`elevator_budget.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/elevator_budget.py)), cerrando el ciclo de decisión-ejecución con el firmware VNish. El actuador consume el contrato [`MinerGovernanceContext`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/governance_context.py), asegurando que el cálculo de resistencia térmica $R_{th}$ use la potencia real medida $P_{real}$ (resolviendo la fricción residual F-04). Toda acción se valida a través de los Gates 0 a 6 del `ElevatorBudget`, se persiste en SQLite (`facility_agent_actions`), y se expone al operador en Telegram mediante `/agent run` y `/agent history`.

---

## Technical Context

**Language/Version**: Python 3.10+ (entorno de ejecución virtualenv activo en Windows, compatible con Python 3.14).

**Primary Dependencies**:
- `app.governance.governance_context.MinerGovernanceContext` (Spec 082)
- `app.governance.facility_agent` (Spec 079)
- `app.governance.elevator_budget` (Specs 077/078)
- `app.vnish.client.safe_set_miner_preset`
- `app.core.event_store.EventStore`
- `app.telegram.commands.agent`

**Storage**: SQLite WAL mode (`event_store.db`), tabla aditiva `facility_agent_actions`.

**Testing**: `pytest` con tests unitarios y de contrato deterministas en `tests/test_fga_actuator.py`.

**Target Platform**: Windows 11 / Windows Server, servicio NSSM `MinerAlerts`, comunicación REST API 4028 y VNish API port 80.

**Performance Goals**:
- Latencia de evaluación de ciclo completo FGA $\le 5\text{ ms}$.
- Persistencia de acción en SQLite $\le 50\text{ ms}$.
- Respuesta a `/agent run` en Telegram $\le 3\text{ s}$.

**Constraints**:
- **Cero disrupción inconsulta**: Respeto estricto a `presets_enabled` y ventanas de reposo (`Facility Settle` 180s, `Incident Quiet` 300s).
- **Invariantes P0**: No afectar protecciones de silicio ni bypass de compuertas de seguridad.
- **Formato Telegram**: Mensajes y tarjetas formateadas estrictamente a $\le 32$ columnas.
- **Protección de secretos**: `config.json` y `state.json` nunca expuestos.

---

## Constitution Check

| Principio | Estado | Justificación / Salvaguarda |
| :--- | :---: | :--- |
| **P0 – Seguridad de Hardware** | ✅ PASS | Todo cambio de preset pasa por los Gates 0-6 de `ElevatorBudget` y Thermal Guard antes de actuar en hardware. |
| **P1 – Control de Intervención** | ✅ PASS | Si `presets_enabled=False` o `is_warming_up=True`, el actuador FGA no ejecuta `safe_set_miner_preset`. |
| **P2 – Telemetría No Bloqueante** | ✅ PASS | Las evaluaciones y persistencias operan sin llamadas bloqueantes en los hilos de adquisición de socket. |
| **P3 – Mobile-First Telegram** | ✅ PASS | Respuestas de `/agent run` y `/agent history` formateadas con ancho $\le 32$ columnas. |
| **P4 – Persistencia Atómica** | ✅ PASS | Inserción en `facility_agent_actions` usando transacciones acotadas y locks de SQLite en modo WAL. |

---

## Arquitectura de la Solución

```
                          ┌────────────────────────────────┐
                          │  miner_monitor.py / /agent run │
                          └───────────────┬────────────────┘
                                          │
                                          ▼
                         ┌─────────────────────────────────┐
                         │   MinerGovernanceContext[]      │
                         │  (Potencia real, T_chip, inlet) │
                         └────────────────┬────────────────┘
                                          │
                                          ▼
     ┌────────────────────────────────────────────────────────────────────────┐
     │ app/governance/fga_actuator.py                                         │
     │                                                                        │
     │ 1. evaluate_asymmetric_allocation(contexts, strategy)                 │
     │    └── Usa current_power_w si restart_required=True (Fix F-04)         │
     │ 2. candidate_step -> (miner_name, target_preset, reason)              │
     │ 3. evaluate_facility_transition_permission(...)                       │
     │    └── Gates 0-6: Quiet, Settle, Hardware, Solar, Headroom, Budget    │
     │ 4. Si can_proceed=True & presets_allowed:                             │
     │    └── safe_set_miner_preset() + record_transition()                  │
     │ 5. EventStore.record_facility_agent_action(...)                        │
     └────────────────────────────────────┬───────────────────────────────────┘
                                          │
                   ┌──────────────────────┴──────────────────────┐
                   ▼                                             ▼
     ┌───────────────────────────┐                 ┌───────────────────────────┐
     │ SQLite EventStore         │                 │ Telegram Bot              │
     │ (facility_agent_actions)  │                 │ (/agent run /history)     │
     └───────────────────────────┘                 └───────────────────────────┘
```

### Componentes y Módulos

1. **`app/governance/fga_actuator.py` (NUEVO)**:
   - Contiene la lógica desacoplada `FgaActuatorEngine` / `evaluate_fga_actuator_step()`.
   - Recibe la lista de `MinerGovernanceContext`, el estado `FacilityBudgetState`, la estrategia FGA y las opciones de configuración.
   - Ejecuta `evaluate_asymmetric_allocation()` asegurando potencia real.
   - Si surge un `candidate_step`, evalúa compuertas en `elevator_budget.py`.
   - Retorna un `FgaActuatorDecision` estructurado con el estado de autorización y la acción requerida.

2. **`app/governance/facility_agent.py` (MODIFICADO - Aditivo)**:
   - Soporte para que `build_thermal_profile()` reciba `MinerGovernanceContext` opcionalmente, extrayendo `power_w` de `ctx.effective_target_power_w` o `ctx.current_power_w` cuando `restart_required=True` (solución de fricción F-04).

3. **`app/core/event_store.py` (MODIFICADO - Aditivo)**:
   - Definición de tabla `facility_agent_actions` e índices.
   - Métodos:
     - `record_facility_agent_action(miner_name, electrical_group, strategy, from_preset, to_preset, action_status, gate_name, reason, power_w, chip_temp_c, thermal_resistance, created_ts=None)`
     - `get_facility_agent_actions(miner_name=None, limit=20)`

4. **`app/telegram/commands/agent.py` (MODIFICADO)**:
   - Subcomando `/agent run`: dispara una evaluación inmediata, ejecuta la acción si está permitida (o simula en QA), persiste el resultado y envía tarjeta ejecutiva $\le 32$ cols.
   - Subcomando `/agent history [minero]`: muestra las últimas acciones registradas en SQLite.

5. **`app/miner_monitor.py` (MODIFICADO - Integración mínima)**:
   - Invocación periódica en el bucle de gobernanza bajo control de temporizador y `presets_enabled`.

6. **`tests/test_fga_actuator.py` (NUEVO)**:
   - Suite completa de pruebas de contrato y comportamiento cubriendo todos los escenarios de aceptación de la Spec 083.
