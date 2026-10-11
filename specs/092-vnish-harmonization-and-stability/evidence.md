# Operational & Certification Evidence: Spec 092

## 1. Quality Gates Summary
- **Python Syntax Compilation**: `py_compile app/miner_monitor.py app/core/pipeline.py app/core/engine.py app/governance/power_progression.py` -> **PASS**
- **Regression Suite**: `pytest -q tests/` -> **1530 passed, 75 subtests passed in 38.24s** -> **PASS**
- **Git Diff & Whitespace Cleanliness**: `git diff --check` -> **PASS** (zero trailing whitespace, normalized LF)
- **Preflight Stabilization Certification**: `preflight_stabilize.ps1` -> **8/8 gates PASS**
- **Windows NSSM Service**: `MinerAlerts` -> **SERVICE_RUNNING** (~390 TH/s nominal, clean continuous ticks in `logs/out.log`, active `DetectionHook` & `ActuatorHook`, zero runtime exceptions)

## 2. VNish Harmonization & Stability Verification
- **Thermal Margin**: Fan Governor calibrado con `target_temp_c: 79.5`, `deadband_low_c: 78.0`, `deadband_high_c: 81.0`, `emergency_temp_c: 82.5`, garantizando $\ge 3^\circ\text{C}$ de margen antes del corte térmico de 84.0°C de VNish.
- **Asymmetric Silicon Clamping**:
  - `S19JPRO-24`: Clampeado a 2500W en supervisor y en firmware VNish (`top_preset: "2500"`, `preset: "2500"`, `restart_required: false`).
  - `S19JPRO-26`: Clampeado a 2500W en supervisor y en firmware VNish (`top_preset: "2500"`, `preset: "2500"`, `restart_required: false`).
  - `S19JPRO-23` y `S19JPRO-25`: Operando sostenidamente a 2700W (M23 con 60+ horas ininterrumpidas de uptime continuo).
- **SQLite Periodic Telemetry & Maintenance**:
  - Ingesta periódica en `chain_telemetry_samples` reactivada en `PostTickHook` (`[CHAIN_TELEMETRY] miner=S19JPRO-* collected=3 inserted=3`).
  - Mantenimiento periódico SQLite WAL reactivado (`mode=PASSIVE busy=0 log=40 checkpointed=40`).
