# Feature Specification: Vnish Preset & Autotuning Dynamic Tracking (Spec 037)

**Feature Branch**: `codex/037-vnish-presets-autotuning`  
**Created**: 2026-09-07  
**Status**: Ready / SpecKit Active  
**Input**: Monitor Engine V3 (V3 Expansion Plan) — Real-time tracking of ASIC frequency (MHz), chain voltages (V), power profiles, and dynamic autotuning events from Vnish firmware. Accessible via `/presets` (aliases `/preset`, `/profile`) and proactive profile adjustment warnings.  
**Risk Class**: LOW-MEDIUM (Read-only telemetry and firmware event correlation, Telegram presentation, non-disruptive notifications)  
**Assigned Engine**: **Gemini 3.8 Flash High** (Pure domain models, SQLite correlation, string formatting, and test suite).  

---

## User Scenarios & Testing

### User Story 1 - Instant Fleet Operating Profile Inspection via `/presets` (Priority: P1)

An operator sends `/presets` in Telegram to inspect the operational profile of all miners (average frequency, voltage, power draw, and tuning state), ensuring that all miners are hashing at their expected settings.

**Acceptance Scenarios**:
1. **Given** active telemetry samples with frequency and voltage, **When** `/presets` is invoked, **Then** the bot replies with each miner's average frequency (MHz), voltage (V), power (W), hashrate (TH/s), inferred profile, and tuning status (`🟢 ESTABLE`, `🔄 EN AUTOTUNING`, `⚠️ DOWNCLOCKED`).
2. **Given** a specific miner (e.g. `/presets 24`), **When** queried, **Then** the bot outputs deep profile breakdown and correlation with recent autotune logs from SQLite `firmware_events`.

---

### User Story 2 - Proactive Downclock & Autotuning Alert (Priority: P1)

When Vnish firmware dynamically drops operating frequency (downclock $\ge 25\text{ MHz}$ sustained for 3 ticks) due to thermal saturation or voltage drops, or encounters a failed autotune cycle (`firmware_autotune_failed`), the system emits a proactive informational alert.

**Acceptance Scenarios**:
1. **Given** a miner whose operating frequency drops by $\ge 25\text{ MHz}$ while hashing, **When** evaluated, **Then** the bot emits:
   `"ℹ️ [PERFIL/AUTOTUNE] S19JPRO-24 — Ajuste automático de perfil detectado: 518.3 MHz -> 484.9 MHz. El firmware redujo frecuencia."`
2. **Given** an autotune failure in firmware logs, **When** evaluated, **Then** a warning is emitted.

---

## Requirements

### Functional Requirements

- **FR-001**: Support commands `/presets`, `/preset`, `/profile`:
  - `/presets [all]`: Fleet table with MHz, Volts, Watts, TH/s, profile label, tuning state.
  - `/presets <miner>`: Detailed profile card with recent firmware autotune events.
- **FR-002**: Frequency & profile inference:
  - Extract `frequency_mhz_avg`, `chain_voltage_mv_avg`, `chain_power_w_total`, `rate_ths` from `telemetry_samples`.
  - Inferred profile buckets (approx):
    * Low (~2500W / ~485 MHz)
    * Medium (~2700W / ~518 MHz)
    * High (~3000W / ~550 MHz)
- **FR-003**: Tuning state classification:
  - `AUTOTUNING`: If `chains_transitioning_count > 0` or recent autotune event within 10 min.
  - `DOWNCLOCKED`: If frequency dropped $\ge 25\text{ MHz}$ from baseline.
  - `STABLE`: Frequency consistent within $\pm 10\text{ MHz}$ and normal operation.
  - `UNKNOWN`: Telemetry missing or miner offline.
- **FR-004**: Proactive alerting:
  - `"preset_alert_enabled"`: boolean (default `true`).
  - `"preset_frequency_drop_mhz"`: float (default `25.0`).
  - `"preset_cooldown_seconds"`: float (default `3600`).
- **FR-005**: Integration with `/snooze`:
  - When a miner is snoozed, profile alerts for that miner MUST be suppressed.

### Non-Functional & Safety Requirements

- **NFR-001**: Zero disruption to running production monitor PID 38816 (>267h soak).
- **NFR-002**: SQLite read-only mode (`?mode=ro`).
- **NFR-003**: Fast response time (< 50ms).
- **NFR-004**: 100% test pass rate across all existing and new test suites.

---

## Success Criteria

- **SC-001**: `/presets` command responds in < 50ms with complete fleet frequency & profile metrics.
- **SC-002**: Accurately correlates telemetry with recent firmware tuning logs.
- **SC-003**: 0 regressions across entire test suite.
