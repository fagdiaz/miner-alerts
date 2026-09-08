# Architecture & API Contract: Cooling & Fan Health Intelligence (Spec 035)

**Specification**: [spec.md](../spec.md)  
**Status**: ACTIVE  

---

## 1. Domain Types & Classification (`app/fan_health.py`)

### `CoolingStatus` Enum:
- `HEALTHY` (Label: `🟢 OK`): $T_{\text{max}} < 75^\circ\text{C}$ and (PWM is None or PWM < 90%).
- `ELEVATED` (Label: `🟡 ELEVADO`): $75^\circ\text{C} \le T_{\text{max}} < 78^\circ\text{C}$ or (PWM ≥ 90% and PWM < 95%).
- `SATURATED` (Label: `🟠 SATURADO`): $T_{\text{max}} \ge 78^\circ\text{C}$ and (PWM ≥ 95% or RPM ≥ 5800).
- `CRITICAL_HEAT` (Label: `🔴 CRÍTICO`): $T_{\text{max}} \ge 82^\circ\text{C}$.
- `FAN_DEFECT` (Label: `⚠️ DEFECTO FAN`): RPM < 2000 RPM while hashing or `fan_signal_missing` in flags.
- `UNKNOWN` (Label: `⚪ SIN DATOS`): Telemetry unrecorded or miner offline.

### Dataclass: `CoolingAssessment`
```python
@dataclass(frozen=True)
class CoolingAssessment:
    miner_name: str
    status: str                         # "HEALTHY" | "ELEVATED" | "SATURATED" | "CRITICAL_HEAT" | "FAN_DEFECT" | "UNKNOWN"
    status_label: str                   # "🟢 OK", "🟠 SATURADO", etc.
    max_temp_c: Optional[float]
    thermal_headroom_c: Optional[float] # max(0.0, 85.0 - max_temp_c) if max_temp_c else None
    fan_rpm_max: Optional[int]
    fan_pwm_percent: Optional[float]
    diagnostic_flags: tuple[str, ...]
    recommendation: str
```

---

## 2. Formatting Contracts

### `/fans` (Fleet Overview):
```text
❄️ Miner Alerts — Estado de Enfriamiento
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
S19JPRO-23: 🟢 OK | 5,400 RPM (82%) | 71.2°C (Margen: 13.8°C)
S19JPRO-24: 🟠 SATURADO | 6,350 RPM (98%) | 79.4°C (Margen: 5.6°C)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ Atención: S19JPRO-24 opera con disipación saturada. Limpiar filtros de aire.
Para detalle individual: /fans <minero>
```

### `/fans <miner>` (Single Miner Detail):
```text
❄️ Diagnóstico de Enfriamiento — S19JPRO-24
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Estado: 🟠 SATURADO
• Temp. Máxima: 79.4°C (Límite: 85.0°C)
• Margen Térmico: 5.6°C
• Velocidad Fans: 6,350 RPM
• Potencia PWM: 98%
• Flags: []
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Recomendación: Disipación saturada con ventiladores al máximo. Inspeccionar y limpiar filtros antipolvo o verificar temperatura ambiental.
```

---

## 3. Warning Alert Contract

### `COOLING_WARNING` Alert Payload:
```text
⚠️ [ENFRIAMIENTO] S19JPRO-24 — Saturación térmica detectada (6,350 RPM, 98% PWM, 79.4°C).
Margen crítico hacia corte: 5.6°C.
Se recomienda inspección de flujo y limpieza preventiva de filtros antipolvo.
```

### `FAN_DEFECT` Alert Payload:
```text
🚨 [VENTILADOR] S19JPRO-23 — Falla mecánica de ventilador detectada (1,200 RPM).
Riesgo de sobrecalentamiento inminente. Revisar cooler o tacómetro.
```

---

## 4. State & Configuration Contract

### State in `MinerState`:
```python
cooling_streak: int = 0
last_cooling_warning_ts: Optional[float] = None
```

### Config Options (`app/config.example.json`):
```json
{
  "cooling_alert_enabled": true,
  "cooling_saturate_temp_c": 78.0,
  "cooling_saturate_pwm_pct": 95.0,
  "cooling_saturate_rpm": 5800,
  "cooling_saturate_streak": 3,
  "cooling_cooldown_seconds": 3600
}
```
