# Evidence: Vnish Preset & Autotuning Dynamic Tracking (Spec 037)

**Feature**: Vnish Preset & Autotuning Dynamic Tracking  
**Branch**: `codex/037-vnish-presets-autotuning`  
**Date**: 2026-09-07  
**Status**: CERTIFIED & COMPLETED  
**Assigned Engine**: **Gemini 3.8 Flash High**  

---

## 1. Baseline Evidence

### Command Registry Baseline:
```text
CMD_WHITELIST contains 26 commands before expansion. Added presets, preset, profile (total 29 commands).
```

### Telemetry Frequency and Voltage Columns in SQLite:
```sql
frequency_mhz_avg REAL
chain_voltage_mv_avg REAL
chain_power_w_total REAL
rate_ths REAL
chains_transitioning_count INTEGER
```

### Baseline Test Suite:
```text
484 tests passing in 4.843s.
Production monitor PID 38816 active with > 4,601 CPU seconds.
```

---

## 2. Unit Test Results

### `tests/test_vnish_presets.py`:
```text
...........
----------------------------------------------------------------------
Ran 11 tests in 0.218s

OK
```

### Full Regression Suite:
```text
----------------------------------------------------------------------
Ran 495 tests in 5.048s

OK
```

---

## 3. Real Production Telemetry Query Benchmark

Execution against live 23.2 MB SQLite database `data/miner_alerts.db`:
```text
Fetch time: 1.77ms

⚙️ Miner Alerts — Perfiles Operativos y Autotuning
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
S19JPRO-23: 🟢 ESTABLE | 516.0 MHz (12.8V) | 2,698 W | 101.1 TH/s (~2700W (516 MHz))
S19JPRO-24: 🟢 ESTABLE | 518.3 MHz (13.0V) | 2,698 W | 100.3 TH/s (~2700W (518 MHz))
S19JPRO-25: 🟢 ESTABLE | 487.3 MHz (12.6V) | 2,498 W | 94.4 TH/s (~2500W (487 MHz))
S19JPRO-26: 🟢 ESTABLE | 484.9 MHz (12.9V) | 2,499 W | 93.7 TH/s (~2500W (485 MHz))
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Flota operando con frecuencias y perfiles estables.
Para detalle individual: /presets <minero>

⚙️ Diagnóstico de Perfil y Tuning — S19JPRO-23
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Estado: 🟢 ESTABLE
• Perfil Inferido: ~2700W (516 MHz)
• Frecuencia Promedio: 516.0 MHz
• Tensión de Cadena: 12.82 V
• Potencia de Cadena: 2,698 W
• Hashrate Actual: 101.1 TH/s
• Eventos Recientes: [Corte de cadena detectado, Firmware inicializando, Firmware en enfriamiento controlado]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Recomendación: Frecuencia y tensión en sincronía con el perfil nominal.
```

---

## 4. Production Soak Verification

```powershell
Get-Process -Id 38816 | Format-List Id, ProcessName, StartTime, CPU, WorkingSet64

Id           : 38816
ProcessName  : python
StartTime    : 27/08/2026 16:11:40
CPU          : 4604,140625
WorkingSet64 : 33173504
```
Continuous uptime > 267.3 hours without interruption.
