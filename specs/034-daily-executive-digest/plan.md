# Implementation Plan: Daily Executive Digest (Spec 034)

**Branch**: `codex/034-daily-executive-digest` | **Date**: 2026-09-07 | **Spec**: [spec.md](spec.md)

---

## Summary

Build an executive telemetry aggregation engine (`app/daily_digest.py`) that queries SQLite `telemetry_samples`, `operational_events`, `reboot_decisions`, and backup metadata across the trailing 24 hours. Connect it to an on-demand Telegram command (`/digest`) and a lightweight morning scheduler (08:00 AM local time) within the main monitor evaluation loop.

---

## Technical Context

**Language/Version**: Python 3.14.x  
**Primary Dependencies**: Standard library (`sqlite3`, `time`, `datetime`, `json`, `math`, `pathlib`).  
**Storage**: Read-only SQLite (`data/miner_alerts.db?mode=ro`). State tracking (`last_daily_digest_date`) in `app/state.json`.  
**Scheduler Strategy**: Evaluated per monitor loop tick against Argentina local time (`argentina_now()`). Once-per-day guard protected by calendar date string (`YYYY-MM-DD`).  
**Testing**: `unittest` with mock and in-memory SQLite instances verifying math formulas (uptime, TH/s, J/TH, shares %), fallback messages, scheduling triggers, and Telegram dispatch.  
**Performance Goal**: 24h query and render under 100ms.  
**Risk Classification**: LOW-MEDIUM — Read-only analytical queries and scheduled notification delivery; zero impact on reboot or monitor state machine.  
**Assigned Engine**: **Gemini 3.8 Flash High** (Motor Primario).

---

## Constitution Check

- **Production Safety First**: PASS. Pure read-only queries with `?mode=ro`. Zero write locks.
- **Single Source Of Truth**: PASS. Telemetry drawn directly from SQLite EventStore; no hardcoded credentials.
- **Telegram Operational Controls**: PASS. Safe command extension, help index updated, robust error catching.
- **Windows Compatibility**: PASS. Pure Python standard library virtualenv.
- **Evidence-Based Completion**: PASS. Full regression suite, compilation check, and command smoke required.

---

## Planned Source Scope

```text
app/daily_digest.py               # Aggregation queries, math formulas, backup inspection, card formatting
app/miner_monitor.py              # Scheduler hook in evaluation loop, /digest command handler, state persistence
tests/test_daily_digest.py        # Unit and integration tests covering queries, formulas, schedule, and command
app/config.example.json           # Document daily_digest_enabled and daily_digest_time
README.md                         # Document /digest command and morning schedule
docs/speckit/RUNBOOK.md           # Add operational runbook for daily digest
docs/audit/DEVELOPMENT_LOG.md     # Newest-first audit log entry
docs/speckit/ROADMAP.md           # Update roadmap progress
```

---

## Rollback And Failure Boundary

- If database queries fail or return empty results, the system outputs a clear textual notification with available metrics without crashing.
- If the scheduler encounters an error during format, it logs `DIGEST_SCHED_ERR` and continues the main loop without dropping ASIC polling.
