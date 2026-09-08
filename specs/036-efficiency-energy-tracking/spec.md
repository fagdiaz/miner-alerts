# Feature Specification: Real-time Hashrate Efficiency & Energy Tracking (Spec 036)

**Feature Branch**: `codex/036-efficiency-energy-tracking`  
**Created**: 2026-09-07  
**Status**: Ready / SpecKit Active  
**Input**: Monitor Engine V3 (V3 Expansion Plan) — Real-time tracking of Joules per Terahash ($J/\text{TH} = \text{Watts} / \text{TH/s}$), detection of electrical and chip degradation before hashrate collapse, accessible via `/efficiency` (alias `/eff`) and proactive Telegram energy warning episodes.  
**Risk Class**: LOW-MEDIUM (Read-only telemetry calculation, Telegram reporting, advisory warnings, zero reboot interlock disturbance)  
**Assigned Engine**: **Gemini 3.8 Flash High** (Pure domain mathematical formulas, data models, Telegram formatters, and complete test suite).  

---

## User Scenarios & Testing

### User Story 1 - Instant Fleet & Miner Efficiency Inspection via `/efficiency` (Priority: P1)

An operator or mine manager runs `/efficiency` in Telegram to evaluate the power efficiency of the fleet, identifying whether machines are operating in optimal energy bands (~28-30 J/TH) or wasting power.

**Acceptance Scenarios**:
1. **Given** active telemetry samples with power and hashrate, **When** `/efficiency` is sent, **Then** the bot replies with each miner's J/TH, power in Watts, hashrate in TH/s, fleet average J/TH, total power in kW, and efficiency classification.
2. **Given** a specific miner (e.g. `/efficiency 24`), **When** queried, **Then** the bot replies with deep diagnostic card showing efficiency, power, chips/hashrate correlation, and maintenance recommendations.

---

### User Story 2 - Proactive Electrical & Thermal Degradation Alert (Priority: P1)

When a miner suffers chip degradation, board drop, or severe thermal throttling, power consumption remains elevated while hashrate drops, causing J/TH to spike (e.g. > 35.0 J/TH). The system detects this sustained anomaly ($K=3$ consecutive ticks) and emits a proactive alert to avoid burning electricity fruitlessly.

**Acceptance Scenarios**:
1. **Given** a miner hashing with J/TH > 35.0 for 3 consecutive ticks, **When** evaluated, **Then** the monitor emits a `EFFICIENCY_WARNING` event:
   `"⚠️ [EFICIENCIA] S19JPRO-24 — Degradación energética detectada: 41.2 J/TH (3,050 W para 74.0 TH/s). Exceso de consumo por TH generado."`
2. **Given** efficiency recovers below 35.0 J/TH, **When** evaluated, **Then** the streak resets cleanly.

---

## Requirements

### Functional Requirements

- **FR-001**: Support command `/efficiency` (and alias `/eff`):
  - `/efficiency [all]`: Fleet table with J/TH, Watts, TH/s, fleet total power in kW, fleet average J/TH.
  - `/efficiency <miner>`: Detailed efficiency card for one miner with recommendations.
- **FR-002**: Mathematical calculation:
  $$\text{Efficiency (J/TH)} = \frac{\text{chain\_power\_w\_total}}{\text{rate\_ths}}$$
- **FR-003**: Efficiency classification:
  - `OPTIMAL` (🟢 ÓPTIMA): $\le 28.5\text{ J/TH}$.
  - `NORMAL` (🟢 NORMAL): $28.5 < \text{J/TH} \le 31.5$.
  - `ELEVATED` (🟡 ELEVADA): $31.5 < \text{J/TH} \le 35.0$.
  - `DEGRADED` (🟠 DEGRADADA): $> 35.0\text{ J/TH}$.
  - `UNKNOWN` (⚪ SIN DATOS): Power or hashrate missing/offline.
- **FR-004**: Proactive alerting:
  - `"efficiency_alert_enabled"`: boolean (default `true`).
  - `"efficiency_degraded_threshold_j_th"`: float (default `35.0`).
  - `"efficiency_degraded_streak"`: int (default `3`).
  - `"efficiency_cooldown_seconds"`: float (default `3600`).
- **FR-005**: Integration with `/snooze`:
  - When a miner is snoozed, efficiency warnings for that miner MUST be suppressed.

### Non-Functional & Safety Requirements

- **NFR-001**: Zero disruption to running production monitor PID 38816 (>267h soak).
- **NFR-002**: SQLite read-only mode (`?mode=ro`).
- **NFR-003**: `/efficiency` command latency under 50ms.
- **NFR-004**: 100% test pass rate across all existing and new test suites.

---

## Success Criteria

- **SC-001**: Instant `/efficiency` feedback in < 50ms with accurate J/TH values.
- **SC-002**: Degradation warning detects abnormal power draw before complete hashrate collapse.
- **SC-003**: Zero regressions across full test suite.
