# Implementation Plan: Real-time Hashrate Efficiency & Energy Tracking (Spec 036)

**Branch**: `codex/036-efficiency-energy-tracking` | **Date**: 2026-09-07 | **Spec**: [spec.md](spec.md)

---

## Summary

Build real-time Joules per Terahash (J/TH) energy tracking in `app/energy_efficiency.py` and integrate it into `app/miner_monitor.py`. This includes:
1. Mathematical calculation of $\text{J/TH} = \text{Watts} / \text{TH/s}$ from normalized chain power and rate.
2. Classification of efficiency (Optimal, Normal, Elevated, Degraded, Unknown).
3. On-demand Telegram commands `/efficiency` (fleet table) and `/efficiency <miner>` (detailed card).
4. Preventative warning alert (`EFFICIENCY_WARNING`) triggered when J/TH exceeds 35.0 for 3 consecutive ticks, with 1-hour cooldown and `/snooze` suppression.

---

## Technical Context

**Language/Version**: Python 3.14.x  
**Primary Dependencies**: Standard library (`sqlite3`, `time`, `datetime`, `math`, `dataclasses`, `typing`).  
**Storage**: Read-only SQLite (`data/miner_alerts.db?mode=ro`). Streak and warning timestamps tracked in `MinerState` (`efficiency_streak`, `last_efficiency_warning_ts`).  
**Testing**: `unittest` covering calculations, threshold classifications, table/card formatting, alert streak/cooldown, and real DB benchmarks.  
**Performance Goal**: `/efficiency` command executed in < 50ms.  
**Risk Classification**: LOW-MEDIUM — Read-only telemetry analysis and Telegram presentation. Zero impact on reboot guards or ASIC socket loops.  
**Assigned Engine**: **Gemini 3.8 Flash High** (Motor Primario).

---

## Planned Source Scope

```text
app/energy_efficiency.py            # Calculations, classifications, table/card formatting, alert detector
app/miner_monitor.py                # /efficiency command handler, loop evaluation hook, MinerState streak fields
tests/test_energy_efficiency.py     # Unit and integration tests covering math, formatting, alerts, benchmarks
app/config.example.json             # Document efficiency alert thresholds
README.md                           # Document /efficiency command and energy tracking feature
docs/speckit/RUNBOOK.md             # Operational runbook for energy degradation alerts
docs/audit/DEVELOPMENT_LOG.md       # Newest-first audit log entry
docs/speckit/ROADMAP.md             # Update roadmap progress
```
