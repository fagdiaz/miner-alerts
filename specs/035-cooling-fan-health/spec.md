# Feature Specification: Cooling & Fan Health Intelligence (Spec 035)

**Feature Branch**: `codex/035-cooling-fan-health`  
**Created**: 2026-09-07  
**Status**: Ready / SpecKit Active  
**Input**: Monitor Engine V3 (V3 Expansion Plan) — Early detection of thermal dissipation saturation, dirty intake filters, failing fans, and mechanical RPM imbalance before emergency firmware thermal shutdown occurs. Accessible via command `/fans` (and `/fan [miner]`) and proactive Telegram cooling warning episodes.  
**Risk Class**: LOW-MEDIUM (Read-only telemetry analysis, health status calculation, Telegram command & warning notification)  
**Assigned Engine**: **Gemini 3.8 Flash High** (Pure domain logic, data models, anomaly classification algorithms, and comprehensive test suite).  

---

## User Scenarios & Testing

### User Story 1 - Instant Cooling & Fan Inspection via `/fans` (Priority: P1)

An operator sends `/fans` (or `/fans 23`) in Telegram and immediately receives the cooling status of the fleet (RPM, PWM %, max chip temperature, and thermal headroom to the 85°C safety ceiling).

**Why this priority**: Operators currently have to guess fan health or wait for an overheat alarm to trigger after damage or throttling has already started.

**Independent Test**: Query latest telemetry for all miners, calculate cooling headroom ($85^\circ\text{C} - T_{\text{max}}$), assess fan saturation state, and verify formatted response with health indicators (`OK`, `SATURATED`, `STALL/IMBALANCE`).

**Acceptance Scenarios**:
1. **Given** active telemetry samples, **When** `/fans` is queried, **Then** the bot replies with each miner's RPM, PWM %, Max Temp, Headroom, and health classification.
2. **Given** a specific miner (e.g. `/fans 23`), **When** queried, **Then** the bot outputs detailed fan status and specific recommendations.

---

### User Story 2 - Preventative Thermal Saturation & Filter Cleaning Warning (Priority: P1)

When a miner's cooling system is saturated (e.g. Fan PWM ≥ 95% or Fan RPM ≥ 5800 sustained over $K$ consecutive ticks while $T_{\text{max}} \ge 78^\circ\text{C}$), the system emits a preventative Telegram warning advising the operator to inspect airflow and clean dust filters before thermal throttling occurs at 85°C.

**Why this priority**: A dirty filter causes fans to spin at 100% consuming excess power while temperatures slowly creep into danger zones. Proactive alerts allow scheduled maintenance without unscheduled downtime.

**Acceptance Scenarios**:
1. **Given** a miner with fans at ≥ 95% PWM and temp ≥ 78°C for 3 consecutive ticks, **When** evaluated, **Then** a `COOLING_WARNING` event is emitted: `"⚠️ [ENFRIAMIENTO] S19JPRO-24 — Saturación térmica detectada (6,300 RPM, 79°C). Margen crítico (6°C). Se recomienda limpieza de filtros."`.
2. **Given** temperatures normalize or fan PWM drops below threshold, **When** evaluated, **Then** the warning clears gracefully.

---

### User Story 3 - Mechanical Fan Failure & RPM Imbalance Detection (Priority: P1)

If telemetry indicates a missing fan signal, a fan running below minimum operational RPM (< 2000 RPM) under load, or severe RPM imbalance across fans, the system flags a mechanical fan defect.

**Acceptance Scenarios**:
1. **Given** a miner reporting `fan_signal_missing` or tachometer drop (< 2000 RPM) while hashing, **When** evaluated, **Then** the bot flags a fan hardware alarm.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST support command `/fans` (and alias `/fan`):
  - `/fans`: displays fleet cooling table with RPM, PWM %, max temperature, and safety margin.
  - `/fans <miner>`: displays detailed cooling diagnostics for a single miner.
  - Registered in `CMD_WHITELIST`, `_COMMANDS`, and `/help`.
- **FR-002**: System MUST calculate:
  - Thermal Headroom: $\text{Headroom} = \max(0.0, 85.0 - T_{\text{max}})$.
  - Cooling State Classification:
    * `HEALTHY`: $T_{\text{max}} < 75^\circ\text{C}$ and PWM < 90%.
    * `ELEVATED`: $75^\circ\text{C} \le T_{\text{max}} < 78^\circ\text{C}$ or PWM ≥ 90%.
    * `SATURATED`: $T_{\text{max}} \ge 78^\circ\text{C}$ and (PWM ≥ 95% or RPM ≥ 5800).
    * `CRITICAL_HEAT`: $T_{\text{max}} \ge 82^\circ\text{C}$.
    * `FAN_DEFECT`: Fan RPM < 2000 RPM under load or `fan_signal_missing`.
- **FR-003**: System MUST support configurable preventative cooling alerts:
  - `"cooling_alert_enabled"`: boolean (default `true`).
  - `"cooling_saturate_temp_c"`: float (default `78.0`).
  - `"cooling_saturate_pwm_pct"`: float (default `95.0`).
  - `"cooling_saturate_streak"`: int (default `3`).
- **FR-004**: System MUST correlate fan data directly from `telemetry_samples` and `VnishTelemetry` in SQLite.

### Non-Functional & Safety Requirements

- **NFR-001**: Zero disruption to running production monitor PID 38816.
- **NFR-002**: Read-only SQLite isolation (`?mode=ro`).
- **NFR-003**: Deduplication: cooling warning alerts MUST use cooldowns (e.g. 1 hour) to avoid spamming the operator.

---

## Success Criteria

- **SC-001**: `/fans` command responds with complete fleet cooling metrics in < 500ms.
- **SC-002**: Thermal saturation correctly detects and warns before reaching 85°C firmware shutdown.
- **SC-003**: 100% unit and integration test coverage across all cooling states with zero regressions.
