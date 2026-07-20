# Implementation Plan: Incident History And Restart Intelligence

**Branch**: `006-incident-history` | **Date**: 2026-07-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/006-incident-history/spec.md`

## Summary

Add a local, durable operational history and a restart-intelligence layer around
the monitor's existing uptime-reset signal. Persist bounded telemetry and events,
classify restart detections against existing successful action timestamps, send
a dedicated alert for unexpected restarts, and expose read-only history through
Telegram. The database is strictly observational and cannot influence action
policy.

## Technical Context

**Language/Version**: Python 3.x from the existing Windows virtualenv

**Primary Dependencies**: Python standard library (`sqlite3`, `threading`, `json`), existing `requests`, Telegram Bot API polling, ASIC API 4028, Hashcore Toolkit CLI

**Storage**: Repository-local SQLite database in WAL mode; existing `app/state.json` remains runtime state

**Testing**: Standard-library `unittest`, existing Speckit QA preflight, Python `py_compile`, QA-mode Telegram smoke checks

**Target Platform**: Windows service, PowerShell, local ASIC network

**Project Type**: Single-process monitoring service with worker threads and Telegram control surface

**Performance Goals**: Database writes remain sub-tick and history commands return in under two seconds for the expected four-miner deployment

**Constraints**: No new runtime dependency; no action from historical data; no secrets in the database or repository; no state-machine, auto-reboot, cooldown, polling-offset, or confirmation-policy change

**Scale/Scope**: Four current miners, five-minute samples, 90-day sample retention, 365-day event retention, future growth to tens of miners

## Constitution Check

### Pre-Design Gate

- **Production Safety First**: PASS. Storage and classification are observation-only; action gates are explicitly out of scope.
- **Single Source Of Truth**: PASS. New shared defaults go only to `app/config.example.json`; real config/state remain untouched.
- **Telegram Operational Controls**: PASS. New commands are read-only, deterministic, and use command-delivery semantics.
- **Auto-Reboot Evidence And Gates**: PASS. Existing uptime-reset signal is observed but no auto-reboot condition is changed.
- **Windows Compatibility**: PASS. SQLite is built into Python and paths are resolved for Windows service execution.
- **Evidence-Based Completion**: PASS. Unit, syntax, QA preflight, and controlled runtime checks are planned.

### Post-Design Gate

- SQLite failure containment prevents observability from stopping monitoring.
- New command handlers perform local database reads only.
- Restart classification consumes existing action timestamps but cannot mutate policy.
- Data retention is bounded and local runtime data is ignored by Git.
- No constitution violations require complexity exceptions.

## Architecture

### Runtime Flow

1. `main()` initializes an optional `EventStore` after configuration and logging.
2. The existing monitor loop continues to calculate miner state and auto-reboot decisions unchanged.
3. A bounded sample is recorded after each miner observation when its sample interval is due.
4. Existing state transitions and uptime-reset detections are copied into normalized events.
5. Restart classification correlates only against existing successful manual/automatic action timestamps.
6. Unexpected restarts are sent as a dedicated incident notification independent of state-change timing.
7. Telegram `/events` and `/event <id>` read from the local store without miner or Hashcore I/O.

### Failure Containment

- Database initialization failure disables history for the process and logs the absolute path and error.
- Individual read/write failures are caught inside the store, logged, and return safe empty/error results.
- SQLite access is serialized with a reentrant lock because the monitor and Telegram worker share one store.
- WAL and bounded busy timeout support concurrent reads without introducing retries or worker threads.
- Cleanup runs at startup and at most once per day.

## Project Structure

### Documentation (this feature)

```text
specs/006-incident-history/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   `-- telegram-history.md
|-- checklists/
|   `-- requirements.md
|-- tasks.md
`-- evidence.md
```

### Source Code

```text
app/
|-- miner_monitor.py          # existing loop, event hooks, Telegram routing
|-- event_store.py            # SQLite schema, persistence, queries, retention
|-- restart_intelligence.py   # pure restart attribution/classification
`-- config.example.json       # production-safe shared defaults

tests/
|-- test_event_store.py
`-- test_restart_intelligence.py
```

**Structure Decision**: Keep the production entrypoint intact and place storage
and pure classification in focused modules. This limits changes in the already
large monitor while preserving direct-script and package import compatibility.

## Delivery Phases

### Phase 1 - Durable Foundation

- Implement schema v1, WAL initialization, indexes, bounded writes, read APIs,
  retention, and failure containment.
- Add deterministic tests for persistence, filtering, retention, and concurrency.

### Phase 2 - Restart Intelligence

- Classify the existing `reboot_reason` signal using existing action timestamps.
- Record restart and state-transition events.
- Send a dedicated unexpected-restart message with incident ID and evidence.
- Preserve every current action gate and notification control.

### Phase 3 - Telegram History

- Add `/events`, `/events <miner>`, and `/event <id>` as read-only commands.
- Use local storage only and deterministic no-data/unavailable/invalid replies.
- Add help metadata and command-delivery wiring.

### Phase 4 - Operations And Release

- Add production-safe config defaults and Git ignores for database artifacts.
- Run unit tests, syntax checks, diff checks, Speckit QA, and service-level smoke checks.
- Record evidence, development log, and roadmap completion.

## Complexity Tracking

No constitution violation or new external service is introduced. SQLite is the
smallest durable relational layer that supports correlation and indexed history
without adding deployment dependencies.
