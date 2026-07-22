# Implementation Plan: Irregular Miner Episodes

**Branch**: `020-episode-alerts` | **Date**: 2026-07-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/020-episode-alerts/spec.md`

## Summary

Replace the three overlapping Telegram-only notification coordinators with one focused episode coordinator while preserving the existing state machine and action gates. The coordinator will accumulate a bounded per-miner timeline, coalesce initial/restart/recovery notices for 30 seconds, escalate unresolved episodes at 5/10/15/30/60/120 minutes and hourly thereafter, and render truthful current status from live signal evidence. Existing SQLite operational events remain the historical source; event detail gains a bounded related timeline and click-safe `/e<ID>` access.

## Technical Context

**Language/Version**: Python 3.14.2 in the existing virtualenv

**Primary Dependencies**: Python standard library, `requests`, Telegram Bot API polling, ASIC API 4028; no new dependency

**Storage**: Existing SQLite `operational_events` and `telemetry_samples`; local `state.json` remains unchanged

**Testing**: `unittest`, `py_compile`, PowerShell/Speckit preflight, controlled QA state sequences

**Target Platform**: Windows 10, NSSM service, PowerShell operations, local S19j Pro network

**Project Type**: Single-process monitor with Telegram sender/polling threads

**Performance Goals**: No miner IO added; O(number of miners plus bounded episode history) per tick; Telegram delivery remains queued

**Constraints**: State machine, hysteresis, auto-reboot, startup guard, cooldown/window, QA and Hashcore action contracts are immutable for this feature; real config/secrets remain untouched

**Scale/Scope**: Current four-miner fleet; bounded histories and maximum 50 related timeline events

## Constitution Check

- **Production safety**: PASS. Notification presentation and read-only history only; no action condition or state transition changes.
- **Runtime config source**: PASS. New defaults are added to `config.example.json`; local `config.json` is not edited.
- **Telegram controls**: PASS. `/e<ID>` is read-only and maps to existing event detail; command replies use command delivery semantics.
- **Auto-reboot evidence/gates**: PASS. Existing action block is outside the implementation scope and receives regression coverage.
- **Windows compatibility**: PASS. No dependency or process model changes.
- **Evidence completion**: PASS by plan. Targeted/full tests, syntax, QA sequence, runtime restart and logs are required tasks.

## Project Structure

### Documentation

```text
specs/020-episode-alerts/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   `-- telegram-episodes.md
|-- checklists/
|   `-- requirements.md
|-- tasks.md
`-- evidence.md
```

### Source Code

```text
app/
|-- alert_episodes.py      # pure episode state, cadence and renderers
|-- event_store.py         # bounded related-event query/render
|-- miner_monitor.py       # existing loop/Telegram integration only
`-- config.example.json

tests/
|-- test_alert_episodes.py
|-- test_event_store.py
|-- test_monitor_incidents.py
|-- test_notification_stability.py
`-- test_reboot_safety.py
```

**Structure Decision**: A small pure module prevents another large coordinator from expanding `miner_monitor.py`. Integration stays local to the existing loop, parser and `/status` branch. SQLite schema remains version 5 because the existing append-only event model already stores every required transition and restart.

## Phase 0: Research Decisions

See [research.md](research.md). The decisive findings are: current-status truth must be separated from confirmed state hysteresis; restart delay is a configured 180-second notification batch; existing SQLite history is sufficient; and a single episode timeline is safer than layering more suppression flags.

## Phase 1: Design

- Introduce a bounded process-local `IrregularEpisodeCoordinator` with deterministic timestamps and no miner IO.
- Use absolute episode-age milestones `[300, 600, 900, 1800, 3600, 7200]`, then repeat every 3600 seconds.
- Capture the return value of existing transition persistence as the detail reference.
- Replace fixed restart recovery quieting with episode-aware coalescing: initial/restart information after 30 seconds, persistent reminders while open, concise summary on confirmed OK.
- Render status from `responded`, current finite rate and current board count. Use `RECUPERANDO` when evidence is healthy but hysteresis has not yet confirmed OK.
- Extend event detail through bounded SQL queries around the selected miner episode; no live miner requests.

## Post-Design Constitution Check

PASS. No new action path, persisted action trigger, dependency, secret, miner request or web endpoint is introduced. The only new command is read-only and click-safe. Active episodes are process-local while canonical transitions remain durable in SQLite.
