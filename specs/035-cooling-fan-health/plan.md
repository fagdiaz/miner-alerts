# Implementation Plan: Cooling & Fan Health Intelligence (Spec 035)

**Branch**: `codex/035-cooling-fan-health` | **Date**: 2026-09-07 | **Spec**: [spec.md](spec.md)

---

## Summary

Implement cooling and fan health intelligence in `app/fan_health.py` and integrate it into `app/miner_monitor.py`. This includes:
1. Pure domain classification of miner cooling state (Healthy, Elevated, Saturated, Critical Heat, Fan Defect) based on $T_{\text{max}}$, Fan RPM, and Fan PWM %.
2. Thermal headroom calculation ($85.0^\circ\text{C} - T_{\text{max}}$).
3. Fast on-demand Telegram commands `/fans` (fleet table) and `/fans <miner>` (detailed single miner diagnostic card) pulling from SQLite or active memory state without blocking miner polling.
4. Preventative cooling saturation warnings emitted when a miner sustains PWM ≥ 95% or RPM ≥ 5800 at $T_{\text{max}} \ge 78^\circ\text{C}$ for $K=3$ consecutive ticks, with a 1-hour notification cooldown.

---

## Technical Context

**Language/Version**: Python 3.14.x  
**Primary Dependencies**: Standard library (`sqlite3`, `time`, `datetime`, `math`, `dataclasses`, `typing`).  
**Storage**: Read-only SQLite (`data/miner_alerts.db?mode=ro`). Streak and warning timestamp tracking in `MinerState` (`cooling_streak`, `last_cooling_warning_ts`).  
**Safety Thresholds**:
- Nominal Trip Ceiling: $85.0^\circ\text{C}$ (Antminer firmware emergency thermal trip).
- Saturation Temp: $78.0^\circ\text{C}$ (Configurable via `"cooling_saturate_temp_c"`).
- Saturation PWM: $95.0\%$ (Configurable via `"cooling_saturate_pwm_pct"`).
- Saturation Streak: $3$ ticks (Configurable via `"cooling_saturate_streak"`).
- Warning Cooldown: $3600$s (1 hour, configurable via `"cooling_cooldown_seconds"`).  
**Testing**: `unittest` covering all cooling classification logic, thermal headroom math, table formatting, detailed card generation, warning streak triggers, cooldown suppression, and command dispatch.  
**Performance Goal**: `/fans` command executed and rendered in < 50ms.  
**Risk Classification**: LOW-MEDIUM — Read-only analytics, Telegram presentation, and advisory notifications. Does NOT alter miner operating modes or reboot interlocks.  
**Assigned Engine**: **Gemini 3.8 Flash High** (Motor Primario).

---

## Constitution Check

- **Production Safety First**: PASS. Pure read-only inspection; zero write locks; PID 38816 untouched.
- **Single Source Of Truth**: PASS. Reuses normalized `telemetry_samples` and `VnishTelemetry` schema.
- **Telegram Operational Controls**: PASS. Command whitelisted, help index updated, throttled warnings with cooldown.
- **Windows Compatibility**: PASS. Standard Python virtualenv without OS-specific bindings.
- **Evidence-Based Completion**: PASS. Full regression suite, compilation check, and command verification required.

---

## Planned Source Scope

```text
app/fan_health.py               # Pure domain logic: classification, headroom, table/card formatting, warning detector
app/miner_monitor.py            # /fans command handler, monitor loop evaluation hook, MinerState streak fields
tests/test_fan_health.py        # Comprehensive test suite covering states, calculations, formatting, cooldowns
app/config.example.json         # Document cooling alert thresholds and toggle
README.md                       # Document /fans and cooling intelligence feature
docs/speckit/RUNBOOK.md         # Add operational runbook for cooling warnings and filter cleaning
docs/audit/DEVELOPMENT_LOG.md   # Newest-first audit log entry
docs/speckit/ROADMAP.md         # Update roadmap progress
```

---

## Rollback And Failure Boundary

- If fan RPM or PWM data is missing from telemetry (e.g. stock Antminer or third-party firmware), the system gracefully displays `N/A` without raising exceptions.
- If SQLite read fails, fallback to in-memory state snapshot ensures `/fans` command never crashes.
- Preventative warning evaluation errors are trapped and logged without disrupting miner polling or reboot guards.
