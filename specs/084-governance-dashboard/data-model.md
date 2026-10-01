# Data Model & Storage Contracts: Spec 084 — Governance Dashboard (`/directivas`)

**Created**: 2026-10-01
**PROP**: PROP-020

---

## 1. Esquema Relacional SQLite (`governance_snapshots`)

Se añade de forma aditiva en `app/core/event_store.py`:

```sql
CREATE TABLE IF NOT EXISTS governance_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_ts REAL NOT NULL,
    miner_name TEXT NOT NULL,
    fan_action TEXT,
    fan_duty INTEGER,
    target_power_w INTEGER,
    current_power_w REAL,
    chip_temp_c REAL,
    fga_cohort TEXT,
    fga_r_th REAL,
    elevator_group TEXT,
    elevator_gate_status TEXT,
    solar_envelope_active INTEGER NOT NULL DEFAULT 0,
    contingency_mode TEXT,
    restart_required INTEGER NOT NULL DEFAULT 0,
    is_deadlocked INTEGER NOT NULL DEFAULT 0,
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS ix_gov_snapshots_created
    ON governance_snapshots(created_ts DESC);

CREATE INDEX IF NOT EXISTS ix_gov_snapshots_miner
    ON governance_snapshots(miner_name, created_ts DESC);
```

---

## 2. Modelos de Datos en Python (`app/governance/directives_dashboard.py`)

```python
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass(frozen=True)
class GovernanceSnapshot:
    """Instantánea persistente de gobernanza consolidada por minero."""
    created_ts: float
    miner_name: str
    fan_action: str
    fan_duty: int
    target_power_w: Optional[int]
    current_power_w: Optional[float]
    chip_temp_c: Optional[float]
    fga_cohort: str
    fga_r_th: Optional[float]
    elevator_group: str
    elevator_gate_status: str
    solar_envelope_active: bool
    contingency_mode: str
    restart_required: bool
    is_deadlocked: bool
    details: Dict[str, Any] = field(default_factory=dict)
```

---

## 3. Contratos de la Capa de Almacenamiento (`EventStore`)

### `record_governance_snapshot`
```python
def record_governance_snapshot(
    self,
    *,
    created_ts: float,
    miner_name: str,
    fan_action: str,
    fan_duty: int,
    target_power_w: Optional[int],
    current_power_w: Optional[float],
    chip_temp_c: Optional[float],
    fga_cohort: str,
    fga_r_th: Optional[float],
    elevator_group: str,
    elevator_gate_status: str,
    solar_envelope_active: bool,
    contingency_mode: str,
    restart_required: bool,
    is_deadlocked: bool,
    details: Optional[Dict[str, Any]] = None,
) -> int:
    """Inserta una instantánea de gobernanza. Retorna el ID generado."""
```

### `get_recent_governance_snapshots`
```python
def get_recent_governance_snapshots(
    self,
    miner_name: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Obtiene las instantáneas más recientes (filtradas opcionalmente por minero)."""
```
