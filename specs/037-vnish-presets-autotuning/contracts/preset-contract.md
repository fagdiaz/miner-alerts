# Architecture & API Contract: Vnish Preset & Autotuning Tracking (Spec 037)

**Specification**: [spec.md](../spec.md)  
**Status**: ACTIVE  

---

## 1. Types & Classification (`app/vnish_presets.py`)

### Status Constants:
- `STATUS_STABLE` (`🟢 ESTABLE`): Normal steady-state operation.
- `STATUS_AUTOTUNING` (`🔄 EN AUTOTUNING`): Cadenas en calibración/tuning.
- `STATUS_DOWNCLOCKED` (`⚠️ DOWNCLOCKED`): Frecuencia reducida significativamente ($\ge 25\text{ MHz}$).
- `STATUS_UNKNOWN` (`⚪ SIN DATOS`): Telemetría no disponible o minero apagado.

### Dataclass: `PresetAssessment`
```python
@dataclass(frozen=True)
class PresetAssessment:
    miner_name: str
    status: str                         # "STABLE" | "AUTOTUNING" | "DOWNCLOCKED" | "UNKNOWN"
    status_label: str                   # "🟢 ESTABLE", "🔄 EN AUTOTUNING", etc.
    frequency_mhz: Optional[float]
    voltage_v: Optional[float]
    power_w: Optional[float]
    rate_ths: Optional[float]
    inferred_profile: str               # e.g. "~2700W (518 MHz)"
    recent_events: tuple[str, ...]
    recommendation: str
```

---

## 2. Formatting Contracts

### `/presets` (Fleet Overview):
```text
⚙️ Miner Alerts — Perfiles Operativos y Autotuning
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
S19JPRO-23: 🟢 ESTABLE | 516.0 MHz (12.8V) | 2,698 W | 104.2 TH/s (~2700W)
S19JPRO-24: 🟢 ESTABLE | 518.3 MHz (13.0V) | 2,698 W | 104.5 TH/s (~2700W)
S19JPRO-25: 🟢 ESTABLE | 487.3 MHz (12.6V) | 2,498 W | 95.1 TH/s (~2500W)
S19JPRO-26: 🟢 ESTABLE | 484.9 MHz (12.9V) | 2,499 W | 94.8 TH/s (~2500W)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Flota operando con frecuencias y perfiles estables.
Para detalle individual: /presets <minero>
```

### `/presets <miner>` (Single Miner Detail):
```text
⚙️ Diagnóstico de Perfil y Tuning — S19JPRO-24
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Estado: 🟢 ESTABLE
• Perfil Inferido: ~2,700 W / 518 MHz
• Frecuencia Promedio: 518.3 MHz
• Tensión de Cadena: 13.02 V
• Potencia de Cadena: 2,698 W
• Hashrate Actual: 104.5 TH/s
• Eventos Recientes: [Firmware inicio minado]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Recomendación: Frecuencia y tensión en sincronía con el perfil nominal.
```

---

## 3. Warning Alert Contract

### `PROFILE_CHANGE_ALERT` Payload:
```text
ℹ️ [PERFIL/AUTOTUNE] S19JPRO-24 — Ajuste automático de perfil detectado:
Frecuencia reducida: 518.3 MHz -> 484.9 MHz (-33.4 MHz).
Consumo: 2,698 W -> 2,499 W. El firmware ajustó el preset por estabilidad.
```

---

## 4. State & Configuration Contract

### State in `MinerState`:
```python
baseline_frequency_mhz: Optional[float] = None
last_preset_warning_ts: Optional[float] = None
```

### Configuration (`app/config.example.json`):
```json
{
  "preset_alert_enabled": true,
  "preset_frequency_drop_mhz": 25.0,
  "preset_cooldown_seconds": 3600
}
```
