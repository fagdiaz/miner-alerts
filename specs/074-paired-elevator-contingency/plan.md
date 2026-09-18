# Implementation Plan: Spec 074 - Paired Elevator Contingency & Inrush Dampener

## Architectural Design

### 1. Data Contracts & State Extension
In [app/governance/adaptive_contingency.py](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/adaptive_contingency.py):
Extend `GroupContingencyState` with optional fields:
- `inrush_dampener_active: bool = False`
- `inrush_dampener_expires_ts: Optional[float] = None`
- `inrush_dampener_partner: str = ""`
- `inrush_dampener_restored_preset: Optional[str] = None`

Extend `ContingencyDecision` with optional fields:
- `partner_miner: str = ""`
- `partner_target_preset: str = ""`
- `partner_requires_write: bool = False`

### 2. Matching Hardening in Monitor
In [app/miner_monitor.py](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py):
Normalize names in `_tgt_miner` lookup:
```python
from app.governance.adaptive_contingency import normalize_miner_name
_tgt_miner = next(
    (m_item for m_item in miners
     if normalize_miner_name(m_item.get("name", "")) == normalize_miner_name(_decision.target_miner)),
    None
)
```
Update target state `balancer_preset`:
```python
_target_state = states.get(f"{_tgt_miner.get('name','')}|{_tgt_miner.get('host','')}:{_tgt_miner.get('port',4028)}")
if _target_state:
    _target_state.balancer_preset = _decision.target_preset
```

### 3. Vnish REST Client Hardening
In [app/vnish/client.py](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/vnish/client.py):
Update `set_miner_preset` to accept `clamp_top_preset: bool = True`:
```python
overclock_dict: Dict[str, Any] = {"preset": clean_preset}
if clamp_top_preset:
    overclock_dict["preset_switcher"] = {"top_preset": clean_preset}
payload = {"miner": {"overclock": overclock_dict}}
```

### 4. Governor Warmup Floor
In [app/governance/fan_governor.py](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/fan_governor.py):
Update `compute_governor_step` to add `is_warming_up: bool = False`:
Do not trigger `ACTION_RECOVERY_MAX_COOLING` if `is_warming_up` is True or `current_power_w < 500.0`.
Emergency spike at $T > 83.5^\circ\text{C}$ remains untouched and prioritized.
