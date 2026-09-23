# Implementation Plan: Spec 079 — Agente Autónomo de Gobernanza de Planta (FGA) y Optimizador Asimétrico de Potencia

## Proposed Changes

### 1. Dominio de Gobernanza (`app/governance/`)
- Crear `app/governance/facility_agent.py`:
  - `FacilityAgent`: Motor determinístico de cálculo de resistencia térmica ($R_{th}$), predicción térmica ($T_{pred}$), clasificación de silicio y optimización asimétrica de presets.
  - Métodos puros y desacoplados:
    - `calculate_thermal_resistance(chip_temp_c, inlet_temp_c, power_w)`
    - `predict_chip_temperature(inlet_temp_c, target_power_w, r_th)`
    - `evaluate_asymmetric_allocation(miners_telemetry, group_limits, strategy)`
    - `format_agent_explanation(miner_name, current_state, knowledge)`

### 2. Capa de Datos y Persistencia (`app/core/`)
- Extender `app/core/event_store.py` (o inicialización SQLite):
  - Añadir tabla `facility_agent_knowledge` si no existe.
  - Métodos `upsert_agent_knowledge(miner_id, r_th, best_preset, ...)` y `get_agent_knowledge(miner_id)`.

### 3. Interfaz de Control en Telegram (`app/telegram/`)
- Crear comando `/agent` en `app/telegram/commands/` para renderizar el panel interactivo del Agente FGA.
- Crear comando `/why` para diagnósticos empíricos de asignación de potencia.
- Crear comando `/strategy` para cambiar la estrategia macro (`balanced`, `max_power`, `efficiency`, `cool_quiet`).

### 4. Integración en `app/miner_monitor.py`
- Instanciar `FacilityAgent` en el supervisor.
- En cada tick, actualizar el modelo de silicio $R_{th}$ de cada máquina con telemetría fresca.
- Orquestar la promoción o desescalada asimétrica respetando el interlock de 180s y los límites de elevador.

### 5. Suite de Pruebas (`tests/`)
- `tests/test_facility_agent.py`:
  - Pruebas unitarias de cálculo de $R_{th}$ y predicción térmica.
  - Pruebas de asignación asimétrica óptima según estrategia.
  - Pruebas de bloqueo térmico predictivo.
  - Pruebas de comandos `/agent`, `/why`, `/strategy`.

---

## Verification Plan

### Automated Tests
- `pytest tests/test_facility_agent.py -v`
- `pytest -q` (Suite completa de 1327+ tests verde)

### Manual Verification
- Invocar `/agent` en Telegram con `DBG_TELEGRAM=1`.
- Observar logs en vivo para verificar que el FGA calcula $R_{th}$ sin overhead.
