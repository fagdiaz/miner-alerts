# Data Model: Spec 083 — FGA Actuator Loop (PROP-019)

**Feature**: `083-fga-actuator-loop` | **Date**: 2026-10-01

---

## 1. Estructura de Datos en Memoria

### `FgaActuatorDecision` (`app/governance/fga_actuator.py`)

Dataclass inmutable que encapsula la evaluación completa de una oportunidad de actuación del FGA:

```python
@dataclass(frozen=True)
class FgaActuatorDecision:
    candidate_miner: str
    target_preset: str
    current_preset: str
    strategy: str
    can_proceed: bool
    gate_action: str            # ALLOW_TRANSITION, HOLD_FACILITY_SETTLE, etc.
    gate_reason: str
    action_status: str          # PROPOSED, BLOCKED, EXECUTED, FAILED, SIMULATED, NOOP
    remaining_settle_s: float = 0.0
    projected_group_power_w: float = 0.0
    power_w: Optional[float] = None
    chip_temp_c: Optional[float] = None
    thermal_resistance: Optional[float] = None
    electrical_group: Optional[str] = None
    created_ts: float = field(default_factory=time.time)
```

---

## 2. Esquema Relacional Persistente (SQLite WAL)

### Tabla `facility_agent_actions` (`app/core/event_store.py`)

Registra cada acción evaluada, autorizada o bloqueada por las compuertas de gobernanza:

```sql
CREATE TABLE IF NOT EXISTS facility_agent_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_ts REAL NOT NULL,
    miner_name TEXT NOT NULL,
    electrical_group TEXT,
    strategy TEXT NOT NULL,
    from_preset TEXT NOT NULL,
    to_preset TEXT NOT NULL,
    action_status TEXT NOT NULL,     -- 'BLOCKED' | 'EXECUTED' | 'FAILED' | 'SIMULATED' | 'NOOP'
    gate_name TEXT,                  -- 'ALLOW_TRANSITION', 'HOLD_FACILITY_SETTLE', etc.
    reason TEXT NOT NULL,
    power_w REAL,
    chip_temp_c REAL,
    thermal_resistance REAL
);

CREATE INDEX IF NOT EXISTS idx_fga_actions_created 
    ON facility_agent_actions(created_ts DESC);

CREATE INDEX IF NOT EXISTS idx_fga_actions_miner 
    ON facility_agent_actions(miner_name, created_ts DESC);
```

---

## 3. Contratos de Ingesta

El motor del actuador ingesta una secuencia de instancias [`MinerGovernanceContext`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/governance_context.py):

| Campo en `MinerGovernanceContext` | Uso en FGA Actuator | Justificación |
| :--- | :--- | :--- |
| `current_power_w` | Cálculo de $R_{th}$ si `restart_required=True` | Resuelve Fricción F-04: evita usar targets desactualizados |
| `chip_temp_c` | Modelado térmico y Thermal Headroom Gate | Identifica necesidad de step-down o viabilidad de 2700W |
| `inlet_temp_c` | Cálculo de $\Delta T = T_{chip} - T_{inlet}$ | Temperatura ambiente en boca de admisión |
| `restart_required` | Señal de bypass / ancla de potencia | Impide distorsión de $R_{th}$ y bloquea comandos redundantes |
| `is_warming_up` | Guardia de exclusión | Máquinas en arranque o autotune no son moduladas |
| `electrical_group` | Agrupamiento por elevador | Verificación de límite de 5400W/5000W |
