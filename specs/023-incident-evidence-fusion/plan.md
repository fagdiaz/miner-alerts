# Implementation Plan: Incident Evidence Fusion

**Branch**: `023-incident-evidence-fusion` | **Date**: 2026-08-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/023-incident-evidence-fusion/spec.md`

## Summary

Add a pure evidence-fusion layer over SQLite and existing analyzers. Normalize facts, calculate conservative versioned hypotheses, persist reproducible assessments and render the same read-only result in Telegram and the dashboard.

## Technical Context

**Language/Version**: Python 3.14.x and PowerShell 5.1

**Primary Dependencies**: Python standard library, existing EventStore, stability, quality, restart and Vnish modules; no new package

**Storage**: Additive SQLite assessment tables; existing telemetry and events remain canonical

**Testing**: `unittest`, deterministic fixtures, contract validation, `py_compile`, and controlled runtime evidence

**Target Platform**: Windows 10, Windows service/Scheduled Tasks, local ASIC network

**Project Type**: Read-only domain module, event-store migration and interface integration

**Performance Goals**: Bounded 24-hour assessment under two seconds at current data volume

**Constraints**: No real secrets or runtime files in Git; no unproved completion; no action authority outside the existing monitor

**Risk Classification**: MEDIUM - correlation changes operator interpretation but remains read-only and cannot trigger actions

**Scale/Scope**: Current four-miner fleet with bounded behavior for configured growth

## Constitution Check

- **Production Safety First**: PASS by design; assessments cannot authorize actions and uncertainty remains explicit.
- **Single Source Of Truth**: PASS; local config/state stay outside Git.
- **Telegram Operational Controls**: PASS; dangerous command confirmation remains unchanged.
- **Auto-Reboot Evidence And Gates**: PASS; existing policy remains authoritative and receives regression coverage.
- **Windows Compatibility**: PASS; validation and rollout are PowerShell/service compatible.
- **Evidence-Based Completion**: PASS by plan; runtime evidence and observation remain mandatory.

## Project Structure

### Documentation

```text
specs/023-incident-evidence-fusion/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/incident-assessment.md
|-- checklists/requirements.md
|-- tasks.md
`-- evidence.md
```

### Planned Source Scope

```text
app/evidence_fusion.py
app/event_store.py
app/miner_monitor.py          # read-only detail integration
tools/operations_dashboard.py
tests/test_evidence_fusion.py
tests/test_event_store.py
```

**Structure Decision**: Keep rules pure, bounded reads and persistence in EventStore, and one shared renderer for every interface.

## Phase 0: Research Decisions

See [research.md](research.md). Existing deterministic analyzers already provide the ingredients. Fusion references persisted facts and exposes contradictions instead of duplicating collection or using an opaque model.

## Phase 1: Design

- Define stable fact/cause codes and a versioned ruleset.
- Build baselines only from confirmed stable, fresh, finite samples.
- Use confidence ceilings with confirmed reserved for direct evidence.
- Persist assessments and fact references for later replay.
- Expose results on demand without adding unsolicited Telegram volume.

## Rollback And Failure Boundary

- Additive tables are ignored when the feature is disabled.
- Persistence failure degrades to an unavailable historical assessment without altering monitoring.
- Removing interface wiring leaves raw events untouched.

## Post-Design Constitution Check

PASS. No unresolved constitution violation exists. Completion remains conditional on `tasks.md` evidence and the scheduled observation window.
