# Implementation Plan: Adaptive Acquisition Resilience

**Branch**: `022-adaptive-acquisition` | **Date**: 2026-08-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/022-adaptive-acquisition/spec.md`

## Summary

Extract a deterministic acquisition scheduler that yields one authoritative envelope per miner per 30-second epoch. A small bounded executor isolates slow endpoints; optional episode diagnostics are typed non-authoritative and barred from state/action mutation.

## Technical Context

**Language/Version**: Python 3.14.x and PowerShell 5.1

**Primary Dependencies**: Python standard library concurrent.futures and existing socket/JSON adapters; no new package

**Storage**: Existing SQLite telemetry plus bounded in-memory poll health

**Testing**: `unittest`, deterministic fixtures, contract validation, `py_compile`, and controlled runtime evidence

**Target Platform**: Windows 10, Windows service/Scheduled Tasks, local ASIC network

**Project Type**: Pure acquisition module integrated into the existing monitor loop

**Performance Goals**: Fleet epoch under ten seconds at current scale, bounded workers and no per-miner overlap

**Constraints**: No real secrets or runtime files in Git; no unproved completion; no action authority outside the existing monitor

**Risk Classification**: HIGH - acquisition timing can affect state evidence, so one authoritative epoch and action invariants are mandatory

**Scale/Scope**: Current four-miner fleet with bounded behavior for configured growth

## Constitution Check

- **Production Safety First**: PASS by design; only authoritative envelopes cross the state and action boundary.
- **Single Source Of Truth**: PASS; local config/state stay outside Git.
- **Telegram Operational Controls**: PASS; dangerous command confirmation remains unchanged.
- **Auto-Reboot Evidence And Gates**: PASS; existing policy remains authoritative and receives regression coverage.
- **Windows Compatibility**: PASS; validation and rollout are PowerShell/service compatible.
- **Evidence-Based Completion**: PASS by plan; runtime evidence and observation remain mandatory.

## Project Structure

### Documentation

```text
specs/022-adaptive-acquisition/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/acquisition.md
|-- checklists/requirements.md
|-- tasks.md
`-- evidence.md
```

### Planned Source Scope

```text
app/acquisition.py
app/miner_monitor.py          # consume authoritative envelopes
app/event_store.py            # quality persistence if required
app/config.example.json
tests/test_acquisition.py
tests/test_reboot_safety.py
tests/test_telegram_polling_stability.py
```

**Structure Decision**: Move scheduling and normalization into a pure module while retaining one monitor loop and existing protocol adapters.

## Phase 0: Research Decisions

See [research.md](research.md). API 4028 has no trusted push contract. Limited concurrent epochs reduce head-of-line blocking, while typed provenance prevents faster probes from changing count-based safety semantics.

## Phase 1: Design

- Assign a monotonic epoch ID and deadline.
- Use two workers by default with a small start stagger.
- Return timeout/error envelopes instead of dropping miners.
- Keep authoritative cadence at 30 seconds and diagnostic episode probes at a disabled-by-default 10 seconds.
- Measure latency, request volume and stale rates before production enablement.

## Rollback And Failure Boundary

- A feature flag restores sequential acquisition through the same envelope interface.
- Diagnostic probes default off and can be disabled independently.
- Errors fail closed and never reuse stale values as current.

## Post-Design Constitution Check

PASS. No unresolved constitution violation exists. Completion remains conditional on `tasks.md` evidence and the scheduled observation window.
