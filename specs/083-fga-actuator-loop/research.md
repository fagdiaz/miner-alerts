# Phase 0 Research: FGA Actuator Loop & Gate Bridge

**Feature**: `083-fga-actuator-loop` | **PROP**: PROP-019 | **Date**: 2026-10-01

---

## 1. Problema de Integración y Análisis de Estado del Arte

### 1.1 Brecha Actual: FGA Desconectado del Actuador
- `app/governance/facility_agent.py` define `evaluate_asymmetric_allocation()`, una función pura que calcula la asignación óptima de potencia por minero (2700W en silicio frío, 2500W en cálido, control de presupuestos por elevador a $\le 5400\text{W}$).
- Sin embargo, en `miner_monitor.py`, únicamente se invoca `upsert_facility_agent_knowledge()` para guardar métricas pasivas de $R_{th}$ en SQLite. Las decisiones del FGA nunca alcanzaban a `elevator_budget.py` ni al actuador `safe_set_miner_preset()`.
- La orquestación de cambio de presets en `miner_monitor.py` (líneas 8780–9056) operaba de manera fragmentada e inconsistente con las recomendaciones del FGA.

### 1.2 Resolución de la Fricción F-04 (Telemetría Distorsionada por `restart_required`)
- En el caso S19JPRO-24 auditado el 2026-10-01, el minero estaba configurado en 2700W pero ejecutando físicamente 2500W porque requería reinicio (`restart_required=True`).
- Si se calculaba $R_{th} = (T_{chip} - T_{inlet}) / P$ con $P = 2700\text{W}$, el denominador artificialmente alto subestimaba la resistencia térmica, clasificando erróneamente el silicio como `COOL`.
- **Solución contractual**: La Spec 082 estableció `MinerGovernanceContext.effective_target_power_w` y `current_power_w`. El FGA debe usar `current_power_w` (o `effective_target_power_w`) garantizando que cuando $P_{real} \ge 500\text{W}$, el cálculo de $R_{th}$ use estrictamente la potencia física medida en las cadenas.

### 1.3 Compuertas de Seguridad (`ElevatorBudget` Gates 0 a 6)
- Todo `candidate_step` emitido por el FGA debe ser sometido a:
  - **Gate 0**: `Incident Quiet Window` (300s post-incidente por elevador).
  - **Gate 1**: `Facility Settle Window` (180s post-transición en la acometida compartida).
  - **Gate 2**: `Individual Hardware Ceiling` (`max_hardware_preset` por minero).
  - **Gate 3**: `Solar Thermal Envelope` (11:00-17:00 hs clamped a 2500W si $T \ge 82^\circ\text{C}$).
  - **Gate 3.1**: `Thermal Headroom Gate` ($T_{chip} < 80^\circ\text{C}$ antes de permitir subida a 2700W).
  - **Gate 4**: `Soft Contingency Schedule` (pico: 2500W; valle: 2700W).
  - **Gate 5**: `Group Power Budget` ($\le 5000\text{W}$ pico / $\le 5400\text{W}$ valle).
  - **Gate 6**: `Symmetric Balance` (partner $\ge 2500\text{W}$ antes de subir a 2700W).

---

## 2. Decisiones de Diseño

1. **Módulo Desacoplado `app/governance/fga_actuator.py`**:
   - Para no sobrecargar `facility_agent.py` (que es estrictamente matemático y libre de dependencias de red) ni `miner_monitor.py` (monolito que se busca reducir en Spec 085), se crea un módulo puente: `fga_actuator.py`.
   - Expone la clase `FgaActuatorEngine` y la función pura `evaluate_fga_actuator_step()`.

2. **Esquema de Base de Datos Aditivo**:
   - Se crea la tabla `facility_agent_actions` en SQLite mediante `EventStore`.
   - Se mantiene `SCHEMA_VERSION = 7` sin forzar migraciones destructivas mediante `CREATE TABLE IF NOT EXISTS`.

3. **Subcomando `/agent run` en Telegram**:
   - Ejecuta la evaluación bajo demanda.
   - Si detecta un candidato autorizado, ejecuta la modulación (o simula si `qa_mode=True`), registra el evento y devuelve una tarjeta ejecutiva $\le 32$ cols con el resultado de la compuerta.
