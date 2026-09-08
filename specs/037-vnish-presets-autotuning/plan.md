# Implementation Plan: Vnish Preset & Autotuning Dynamic Tracking (Spec 037)

**Branch**: `codex/037-vnish-presets-autotuning` | **Date**: 2026-09-07 | **Spec**: [spec.md](spec.md)

---

## Summary

Build real-time tracking of operating frequencies, voltages, power profiles, and autotuning status in `app/vnish_presets.py` and integrate it into `app/miner_monitor.py`. This includes:
1. Extraction of frequency (MHz), voltage (V), power (W), and autotuning flags from SQLite `telemetry_samples` and `firmware_events`.
2. Inferring operating profile and classifying tuning status (Stable, Autotuning, Downclocked, Unknown).
3. On-demand Telegram commands `/presets` (fleet table) and `/presets <miner>` (detailed card with recent tuning log events).
4. Proactive informational alert (`PROFILE_CHANGE_ALERT`) when a miner's operating frequency drops by $\ge 25\text{ MHz}$ or autotune encounters issues.

---

## Technical Context

**Language/Version**: Python 3.14.x  
**Primary Dependencies**: Standard library (`sqlite3`, `time`, `datetime`, `math`, `dataclasses`, `typing`).  
**Storage**: Read-only SQLite (`data/miner_alerts.db?mode=ro`). Baseline frequency and warning timestamps tracked in `MinerState` (`baseline_frequency_mhz`, `last_preset_warning_ts`).  
**Testing**: `unittest` covering profile inference, tuning classifications, table/card formatting, alert triggers, and real DB benchmarks.  
**Performance Goal**: `/presets` command executed in < 50ms.  
**Risk Classification**: LOW-MEDIUM — Read-only telemetry analysis and Telegram presentation. Zero impact on reboot guards.  
**Assigned Engine**: **Gemini 3.8 Flash High** (Motor Primario).

---

## Planned Source Scope

```text
app/vnish_presets.py                # Calculations, classifications, table/card formatting, alert detector
app/miner_monitor.py                # /presets command handler, loop evaluation hook, MinerState fields
tests/test_vnish_presets.py         # Unit and integration tests covering profiles, formatting, alerts, benchmarks
app/config.example.json             # Document preset alert options
README.md                           # Document /presets command and profile tracking feature
docs/speckit/RUNBOOK.md             # Operational runbook for profile and autotune alerts
docs/audit/DEVELOPMENT_LOG.md       # Newest-first audit log entry
docs/speckit/ROADMAP.md             # Update roadmap progress
```
