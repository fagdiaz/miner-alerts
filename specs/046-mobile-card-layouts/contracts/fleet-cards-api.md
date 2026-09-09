# API & Component Contracts: Spec 046 - Mobile Fleet Cards

## 1. Módulo `app/telegram/fleet_cards.py`

### Constantes de Callback
```python
DIAG_PREFIX = "diag:"
DIAG_REF_STATUS = "diag:ref:status"
DIAG_REF_FANS = "diag:ref:fans"
DIAG_REF_EFF = "diag:ref:eff"
DIAG_REF_PRESETS = "diag:ref:presets"
```

### Funciones Principales

#### `render_fleet_status_card`
```python
def render_fleet_status_card(
    states: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
    miners: Optional[List[Dict[str, Any]]] = None,
    now_ts_str: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Render the mobile-first fleet status card (/status).
    
    Returns:
        Tuple of (message_text, reply_markup_dict).
        Every data line is guaranteed to have visible_line_width <= 32.
        Message length is strictly < 2,000 characters.
    """
```

#### `build_diagnostic_keyboard`
```python
def build_diagnostic_keyboard(report_type: str) -> Dict[str, Any]:
    """Generate inline keyboard for diagnostic reports.
    
    Supported report_type:
      - 'status': [ 🔄 Actualizar ] [ 📊 Gráfico ] [ 📱 Menú ]
      - 'fans': [ 🔄 Actualizar ] [ 📱 Menú ]
      - 'eff': [ 🔄 Actualizar ] [ 📱 Menú ]
      - 'presets': [ 🔄 Actualizar ] [ 📱 Menú ]
    """
```

#### `parse_diagnostic_callback`
```python
@dataclass(frozen=True)
class DiagnosticCallbackAction:
    action: str  # 'ref'
    report_type: str  # 'status', 'fans', 'eff', 'presets'

def parse_diagnostic_callback(callback_data: str) -> Optional[DiagnosticCallbackAction]:
    """Parse diagnostic callback strictly validating payload <= 64 bytes."""
```

---

## 2. Refactors en Módulos de Gobernanza

### `app/governance/fan_health.py`
```python
def build_fans_table_text(assessments: List[CoolingAssessment]) -> str:
    """Format mobile-first cooling health cards (visible line width <= 32 cols)."""
```

### `app/governance/energy_efficiency.py`
```python
def build_efficiency_table_text(assessments: List[EfficiencyAssessment]) -> str:
    """Format mobile-first energy efficiency cards (visible line width <= 32 cols)."""
```

### `app/vnish/presets.py`
```python
def build_presets_table_text(assessments: List[PresetAssessment]) -> str:
    """Format mobile-first operating presets cards (visible line width <= 32 cols)."""
```
