# API & Component Contracts: Spec 047 - Mobile Diagnostics & Operational Events

## 1. Extensiones en `app/telegram/fleet_cards.py`

### Constantes de Callback
```python
DIAG_REF_BALANCER = "diag:ref:balancer"
DIAG_REF_ELEV = "diag:ref:elev"
DIAG_REF_DIGEST = "diag:ref:digest"
DIAG_REF_EVENTS = "diag:ref:events"
```

### Supported report types en `build_diagnostic_keyboard`:
- `"status"`: `[ 🔄 Actualizar ] [ 📊 Métricas ] [ 📱 Menú ]`
- `"fans"`, `"eff"`, `"presets"`, `"balancer"`, `"elev"`, `"digest"`, `"events"`: `[ 🔄 Actualizar ] [ 📱 Menú ]`

---

## 2. Contratos de Funciones en Gobernanza y Ecosistema

### `app/governance/preset_balancer.py`
```python
def build_balancer_table_text(
    decisions: List[Tuple[StabilityMetrics, BalancerDecision]],
    is_enabled: bool = False,
    is_dry_run: bool = True,
) -> str:
    """Format fleet preset balance table grouped by elevator (line width <= 32 cols)."""

def build_miner_balancer_detail_text(
    metrics: StabilityMetrics,
    decision: BalancerDecision,
) -> str:
    """Format individual miner balancer diagnostic card (line width <= 32 cols)."""

def build_elevator_sensitivity_text(
    summaries: Dict[str, ElevatorSensitivitySummary],
) -> str:
    """Format elevator voltage sensitivity diagnostic cards (line width <= 32 cols)."""
```

### `app/telegram/daily_digest.py`
```python
def format_daily_digest(
    metrics: Dict[str, Any],
    date_str: Optional[str] = None,
) -> str:
    """Format executive brief for Telegram mobile (line width <= 32 cols)."""
```

### `app/telegram/snooze.py`
```python
def build_snooze_status_text(
    miners: List[Dict[str, Any]],
    states: Dict[str, Any],
    now_ts: Optional[float] = None,
) -> str:
    """Build response text for /snoozed command (line width <= 32 cols)."""
```

### `app/core/event_store.py`
```python
def render_event_list(events: list[Dict[str, Any]]) -> str:
    """Render recent events list formatted for Telegram mobile (line width <= 32 cols)."""

def render_event_detail(
    event: Optional[Dict[str, Any]],
    *,
    related_events: Optional[list[Dict[str, Any]]] = None,
) -> str:
    """Render single incident card with evidence (line width <= 32 cols)."""

def render_reboot_decision(decision: Optional[Dict[str, Any]]) -> str:
    """Render auto-reboot explanation card (line width <= 32 cols)."""
```
