# Tasks: Spec 083 — FGA Actuator Loop (PROP-019)

**Feature**: `083-fga-actuator-loop`
**Fecha**: 2026-10-01
**Prioridad**: P1 — Gobernanza Integrada
**Riesgo**: MEDIO (actuación de presets en hardware acotada por compuertas)
**Modelo recomendado**: Gemini 3.8 Flash High (Primary Engine)

---

## Fase 0 — Reconocimiento y Mapeo Previo

- [x] **T0.1** Verificar esquema y métodos en `app/core/event_store.py` (`facility_agent_knowledge`, WAL mode, locks transaccionales).
- [x] **T0.2** Revisar firmas e invariantes de `evaluate_asymmetric_allocation()` en `app/governance/facility_agent.py`.
- [x] **T0.3** Revisar compuertas Gates 0 a 6 en `evaluate_facility_transition_permission()` de `app/governance/elevator_budget.py`.
- [x] **T0.4** Mapear el despachador de Telegram en `app/telegram/commands/agent.py`.

## Fase 1 — Persistencia de Acciones en SQLite (EventStore)

- [x] **T1.1** Agregar definición de tabla `facility_agent_actions` e índices en `app/core/event_store.py`.
- [x] **T1.2** Implementar método `record_facility_agent_action()` con manejo defensivo de excepciones y transacciones atómicas.
- [x] **T1.3** Implementar método `get_facility_agent_actions()` para consultas históricas (filtrado opcional por minero y limitador).
- [x] **T1.4** Validar sintaxis: `py_compile app/core/event_store.py`.

## Fase 2 — Armonización de Telemetría FGA (Resolución Fricción F-04)

- [x] **T2.1** Modificar `build_thermal_profile()` y `evaluate_asymmetric_allocation()` en `app/governance/facility_agent.py` para permitir ingesta de `MinerGovernanceContext` o potencia real cuando `restart_required=True`.
- [x] **T2.2** Garantizar que si `restart_required=True` y `current_power_w >= 500.0`, el cálculo de $R_{th}$ use `current_power_w` como divisor.
- [x] **T2.3** Validar sintaxis: `py_compile app/governance/facility_agent.py`.

## Fase 3 — Módulo del Actuador FGA (`app/governance/fga_actuator.py`)

- [x] **T3.1** Crear dataclass `FgaActuatorDecision` (frozen, inmutable, con detalles de compuerta y estado de acción).
- [x] **T3.2** Implementar función pura `evaluate_fga_actuator_step()`:
  - Consumir lista de `MinerGovernanceContext`.
  - Ejecutar `evaluate_asymmetric_allocation()`.
  - Si hay `candidate_step`, validar contra `evaluate_facility_transition_permission()` (Gates 0-6).
  - Determinar estado (`PROPOSED`, `BLOCKED`, `PERMITTED`).
- [x] **T3.3** Implementar ejecutor seguro `execute_fga_actuator_step()` con soporte para `qa_mode` y llamada segura a `safe_set_miner_preset()`.
- [x] **T3.4** Validar sintaxis: `py_compile app/governance/fga_actuator.py`.

## Fase 4 — Suite de Tests de Contrato y Comportamiento

- [x] **T4.1** Crear `tests/test_fga_actuator.py`.
- [x] **T4.2** Implementar test unitario para la tabla e inserción/recuperación en `EventStore`.
- [x] **T4.3** Implementar test de verificación F-04: $R_{th}$ no se distorsiona con `restart_required=True`.
- [x] **T4.4** Implementar test de candidate step pasando por Gates 0-6 del `ElevatorBudget`.
- [x] **T4.5** Implementar test de bloqueo por `Facility Settle Window` (Gate 1) y `Incident Quiet Window` (Gate 0).
- [x] **T4.6** Implementar test de bloqueo por `Hardware Ceiling` (Gate 2) y `Thermal Headroom` (Gate 3.1).
- [x] **T4.7** Ejecutar `pytest tests/test_fga_actuator.py -v` → 100% PASS (11 tests).

## Fase 5 — Interfaz Móvil Telegram (`/agent run` y `/agent history`)

- [x] **T5.1** Actualizar `AgentCommand` en `app/telegram/commands/agent.py` para soportar subcomando `run`.
- [x] **T5.2** Implementar subcomando `history` en `app/telegram/commands/agent.py` para visualizar las últimas acciones registradas.
- [x] **T5.3** Asegurar que las respuestas cumplan con el formato móvil estricto $\le 32$ columnas.
- [x] **T5.4** Validar sintaxis: `py_compile app/telegram/commands/agent.py`.

## Fase 6 — Integración en el Bucle Principal del Monitor

- [x] **T6.1** Integrar la invocación periódica de `evaluate_fga_actuator_step()` en `app/miner_monitor.py` bajo guardia `presets_enabled`.
- [x] **T6.2** Validar sintaxis: `py_compile app/miner_monitor.py`.

## Fase 7 — Control de Calidad y Preflight (`speckit-qa`)

- [x] **T7.1** Ejecutar `speckit-qa` (verificación de compuertas de seguridad, sintaxis y consistencia).
- [x] **T7.2** Ejecutar la suite global de pruebas: `pytest -x -q` (1477 tests PASS, 0 fallos).

## Fase 8 — Evidencia, Documentación y Cierre

- [x] **T8.1** Generar `specs/083-fga-actuator-loop/evidence.md` con los resultados de pruebas y comandos ejecutados.
- [x] **T8.2** Actualizar `docs/audit/DEVELOPMENT_LOG.md` con la entrada newest-first de la Spec 083.
- [x] **T8.3** Actualizar `docs/speckit/ROADMAP.md` marcando la Iniciativa 35 / Spec 083 como COMPLETED.
- [x] **T8.4** Actualizar `docs/speckit/SPEC_PROGRAM.md`.
- [x] **T8.5** Ejecutar `speckit-stabilize` antes del cierre final.
- [x] **T8.6** Actualizar `prompt.txt` con el contexto fresco para la siguiente sesión.
