# Implementation Plan: Operator Interface Decision

**Branch**: `027-operator-interface-decision` | **Date**: 2026-08-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/027-operator-interface-decision/spec.md`

## Summary

Run the fixed three-run workflow scorecard only after Specs 025/028 pass. Choose
no-build when each P1 workflow has an existing owner. Only exact required fields
failed by Telegram, static HTML and Grafana may authorize a native loopback-only
FastAPI read-only API and minimal server-rendered/HTMX view. No web action path
is permitted.

## Technical Context

**Language/Version**: Python 3.14.x and PowerShell 5.1

**Primary Dependencies**: Conditional FastAPI, Uvicorn and Pydantic; HTMX only if the approved workflow needs interaction

**Storage**: Existing SQLite opened with mode=ro; no new canonical store

**Testing**: `unittest`, deterministic fixtures, contract validation, `py_compile`, and controlled runtime evidence

**Target Platform**: Windows 10, Windows service/Scheduled Tasks, local ASIC network

**Project Type**: Decision artifact plus conditional local read-only web service

**Performance Goals**: Bounded common queries under one second; database/schema failure under two seconds; workflow completion within fixed 30/60/90/120-second targets

**Constraints**: No real secrets or runtime files in Git; no unproved completion; no action authority outside the existing monitor

**Risk Classification**: MEDIUM - a new surface can widen exposure, so the decision gate defaults to no-build and any prototype is loopback read-only

**Scale/Scope**: Current four-miner fleet with bounded behavior for configured growth

## Constitution Check

- **Production Safety First**: PASS by design; loopback-only, read-only SQLite and zero monitor/miner/action imports.
- **Single Source Of Truth**: PASS; local config/state stay outside Git.
- **Telegram Operational Controls**: PASS; dangerous command confirmation remains unchanged.
- **Auto-Reboot Evidence And Gates**: PASS; existing policy remains authoritative and receives regression coverage.
- **Windows Compatibility**: PASS; validation and rollout are PowerShell/service compatible.
- **Evidence-Based Completion**: PASS by plan; runtime evidence and observation remain mandatory.

## Project Structure

### Documentation

```text
specs/027-operator-interface-decision/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/operator-interface.md
|-- checklists/requirements.md
|-- integration-map.md
|-- workflow-scorecard.md
|-- tasks.md
`-- evidence.md
```

### Planned Source Scope

```text
docs/speckit/INTERFACE_STRATEGY.md
diagnostics/interface/workflow-scorecard.md
# Conditional only after gate:
app/operator_api.py
app/operator_views.py
templates/operator/
tests/test_operator_api.py
requirements-interface.txt
```

**Structure Decision**: The decision artifact is mandatory; source files and
dependencies are conditional. A native local service avoids mounting the live
SQLite database into containers. A no-build result must leave every conditional
path absent from Git.

## Phase 0: Research Decisions

See [research.md](research.md), [workflow-scorecard.md](workflow-scorecard.md) and
[integration-map.md](integration-map.md). Grafana is purpose-built for trends;
the existing static dashboard already provides bounded SQLite evidence and
Telegram covers summary/control. FastAPI remains conditional rather than a
technology goal; React adds no demonstrated value at this scale.

## Phase 1: Design

- Use the fixed P1/P2 workflows, required fields and three-run targets before any dependency.
- Choose no-build when existing interfaces pass.
- If approved, use FastAPI/Pydantic for typed read-only resources and Uvicorn bound to 127.0.0.1.
- Use server-rendered HTML/HTMX only for filtering and progressive refresh.
- Enforce exact GET/HEAD routes, 50/200 pagination, 30-day windows, SQLite
  `mode=ro`/`query_only`, redaction and no action imports with tests.

## Rollback And Failure Boundary

- A no-build decision has no runtime change.
- Incomplete dependencies keep the decision blocked and create no runtime files.
- The conditional service is independent and can be stopped/removed without monitor impact.
- Database/API errors fail within the interface and never propagate to monitoring.

## Post-Design Constitution Check

PASS. No unresolved constitution violation exists. Completion remains conditional on `tasks.md` evidence and the scheduled observation window.
