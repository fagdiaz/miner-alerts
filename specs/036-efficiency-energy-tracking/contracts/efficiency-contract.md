# Architecture & API Contract: Hashrate Efficiency & Energy Tracking (Spec 036)

**Specification**: [spec.md](../spec.md)  
**Status**: ACTIVE  

---

## 1. Types & Classification (`app/energy_efficiency.py`)

### Status Constants:
- `STATUS_OPTIMAL` (`🟢 ÓPTIMA`): $\text{J/TH} \le 28.5$.
- `STATUS_NORMAL` (`🟢 NORMAL`): $28.5 < \text{J/TH} \le 31.5$.
- `STATUS_ELEVATED` (`🟡 ELEVADA`): $31.5 < \text{J/TH} \le 35.0$.
- `STATUS_DEGRADED` (`🟠 DEGRADADA`): $\text{J/TH} > 35.0$.
- `STATUS_UNKNOWN` (`⚪ SIN DATOS`): Telemetry missing or hashrate is 0.

### Dataclass: `EfficiencyAssessment`
```python
@dataclass(frozen=True)
class EfficiencyAssessment:
    miner_name: str
    status: str                         # "OPTIMAL" | "NORMAL" | "ELEVATED" | "DEGRADED" | "UNKNOWN"
    status_label: str                   # "🟢 ÓPTIMA", "🟠 DEGRADADA", etc.
    rate_ths: Optional[float]
    power_w: Optional[float]
    efficiency_j_th: Optional[float]
    recommendation: str
```

---

## 2. Formatting Contracts

### `/efficiency` (Fleet Overview):
```text
⚡ Miner Alerts — Eficiencia Energética (J/TH)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
S19JPRO-23: 🟢 27.8 J/TH | 2,750 W | 98.9 TH/s (Óptima)
S19JPRO-24: 🟢 29.2 J/TH | 2,900 W | 99.3 TH/s (Normal)
S19JPRO-25: 🟡 33.1 J/TH | 3,100 W | 93.6 TH/s (Elevada)
S19JPRO-26: 🟠 41.5 J/TH | 3,070 W | 74.0 TH/s (Degradada)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ Promedio Flota: 32.9 J/TH | Total: 11,820 W (11.8 kW)
⚠️ Atención: S19JPRO-26 presenta degradación energética.
Para detalle individual: /efficiency <minero>
```

### `/efficiency <miner>` (Single Miner Detail):
```text
⚡ Diagnóstico de Eficiencia — S19JPRO-26
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Estado: 🟠 DEGRADADA
• Eficiencia: 41.5 J/TH
• Hashrate Actual: 74.0 TH/s
• Potencia de Cadenas: 3,070 W (3.07 kW)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Recomendación: Eficiencia severamente degradada (> 35.0 J/TH). El equipo consume potencia normal pero genera hashrate subóptimo. Inspeccionar chips con errores o caídas de tensión por cadena.
```

---

## 3. Warning Alert Contract

### `EFFICIENCY_WARNING` Alert Payload:
```text
⚠️ [EFICIENCIA] S19JPRO-26 — Degradación energética detectada (41.5 J/TH).
Potencia: 3,070 W para 74.0 TH/s.
Consumo excesivo por TH generado. Se recomienda inspección de cadenas.
```

---

## 4. State & Configuration Contract

### State in `MinerState`:
```python
efficiency_streak: int = 0
last_efficiency_warning_ts: Optional[float] = None
```

### Configuration (`app/config.example.json`):
```json
{
  "efficiency_alert_enabled": true,
  "efficiency_degraded_threshold_j_th": 35.0,
  "efficiency_degraded_streak": 3,
  "efficiency_cooldown_seconds": 3600
}
```
