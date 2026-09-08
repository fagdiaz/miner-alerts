# Implementation Plan: Miner Maintenance Snooze (Spec 033)

**Branch**: `codex/033-miner-maintenance-snooze` | **Date**: 2026-09-07 | **Spec**: [spec.md](spec.md)

---

## Summary

Implement the Miner Maintenance Snooze feature to allow temporary silencing of alerts, reminders, degraded status messages, and auto-reboots per miner (or fleet-wide) during physical maintenance or servicing windows. Accessible via Telegram commands (`/snooze`, `/unsnooze`, `/snoozed`) and 1-tap interactive inline keyboard button `[ 🔕 Silenciar 1h ]`.

---

## Technical Context

**Language/Version**: Python 3.14.x  
**Primary Dependencies**: Standard library (`time`, `json`, `math`, `typing`, `dataclasses`).  
**Storage**: `app/state.json` (`snooze_until_ts` per miner).  
**Concurrency & Threading**: Protected by `state_lock` within `app/miner_monitor.py`.  
**Testing**: `unittest` verifying argument parsing, time clamping, state serialization, auto-reboot suppression, alert batch filtering, and callback dispatch.  
**Risk Classification**: LOW-MEDIUM — Alert and reboot suppression logic; fails safe (un-snoozed if invalid or expired).  
**Assigned Engine**: **Gemini 3.8 Flash High** (Motor Primario).

---

## Constitution Check

- **Production Safety First**: PASS. Auto-reboot is strictly blocked when a miner is snoozed, preventing hazardous automated reboots during physical maintenance.
- **Single Source Of Truth**: PASS. State serialized to `app/state.json`. Zero hardcoded credentials.
- **Telegram Operational Controls**: PASS. Safe command extension, input validation, strict chat_id authentication on callbacks.
- **Windows Compatibility**: PASS. Pure Python virtualenv.
- **Evidence-Based Completion**: PASS. Full test suite verification and evidence documentation required.

---

## Planned Source Scope

```text
app/telegram_snooze.py           # Pure domain models, duration parsing, time formatting, and filter helpers
app/miner_monitor.py             # MinerState schema update, load/save state, suppression checks, command handlers, snz callback handling
tests/test_telegram_snooze.py    # Unit and integration test suite covering all snooze scenarios
README.md                        # Document /snooze commands and inline button behavior
docs/speckit/RUNBOOK.md          # Add operational runbook for maintenance windows
docs/audit/DEVELOPMENT_LOG.md    # Newest-first audit log entry
docs/speckit/ROADMAP.md          # Update roadmap progress
```

---

## Rollback And Failure Boundary

- If snooze parameters are invalid or parsing fails, the system defaults to 60 minutes or reports usage without crashing.
- If `snooze_until_ts` is expired or corrupted, it evaluates to un-snoozed, failing open to standard monitoring.
