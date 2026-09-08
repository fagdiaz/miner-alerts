# Implementation Plan: Telegram Visual Charts (Spec 032)

**Branch**: `codex/032-telegram-visual-charts` | **Date**: 2026-09-07 | **Spec**: [spec.md](spec.md)

---

## Summary

Build an in-memory visual charting engine (`app/telegram_charts.py`) that queries SQLite `telemetry_samples` and renders dark-themed PNG charts directly into memory (`io.BytesIO`). Deliver charts via Telegram `sendPhoto` in response to `/chart [miner|fleet] [hours]` and the inline button `[ 📊 Ver Gráfico ]`.

---

## Technical Context

**Language/Version**: Python 3.14.x  
**Primary Dependencies**: Standard library (`sqlite3`, `io`, `time`), `requests`, and `matplotlib` (installed in `.venv`).  
**Storage**: Read-only SQLite (`data/miner_alerts.db?mode=ro`). Zero temporary files created on disk.  
**Testing**: `unittest` verifying PNG magic headers (`\x89PNG\r\n\x1a\n`), query bucketing, empty dataset handling, and mock `sendPhoto` delivery.  
**Performance Goal**: Chart query and render under 1.0s; Telegram multipart delivery under 1.5s.  
**Risk Classification**: LOW-MEDIUM — Read-only analytical queries and photo delivery; zero impact on reboot or monitor state machine.  
**Assigned Engine**: **Gemini 3.8 Flash High** (Motor Primario).

---

## Constitution Check

- **Production Safety First**: PASS. Analytical read-only queries with `?mode=ro`. No mutations or state changes.
- **Single Source Of Truth**: PASS. No credentials or tokens hardcoded; uses config.
- **Telegram Operational Controls**: PASS. Safe command extension, command help updated, strict chat_id authentication.
- **Windows Compatibility**: PASS. Pure Python virtualenv.
- **Evidence-Based Completion**: PASS. Unit test suite, compilation check, and command smoke required.

---

## Planned Source Scope

```text
app/telegram_charts.py          # Data aggregation and in-memory PNG rendering
app/miner_monitor.py            # send_telegram_photo helper, /chart command handler, chart: callback wiring
tests/test_telegram_charts.py   # Unit tests covering queries, image byte validity, and fallback
README.md                       # Document /chart command
docs/speckit/RUNBOOK.md         # Document chart operational usage
```

---

## Rollback And Failure Boundary

- If `sendPhoto` fails or times out, the system falls back to a textual diagnostic summary without dropping the command.
- If charting dependencies are missing, the monitor gracefully returns an informative text message.
