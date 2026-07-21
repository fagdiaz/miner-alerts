# Implementation Plan: Vnish Telemetry And Reboot Decision Audit

**Branch**: `007-vnish-decision-audit` | **Date**: 2026-07-20 | **Spec**: [spec.md](spec.md)

## Summary

Extend the existing observational SQLite layer with normalized Vnish telemetry
and a reboot-decision audit trail. Reuse the monitor's existing `stats` request,
record each meaningful result from the current auto-reboot branches before their
existing exits, expose `/why` from local history, and add a standalone report.
No condition in the state machine or action policy changes.

## Technical Context

**Language/Version**: Existing Python 3 virtualenv on Windows
**Primary Dependencies**: Python standard library, existing `requests`; no new dependency
**Storage**: Existing SQLite database, migrated from schema v1 to v2 in place
**Testing**: `unittest`, `py_compile`, JSON parse, Speckit QA preflight
**Target Platform**: Existing Windows service and PowerShell operations
**Performance Goal**: No extra `stats` network request; local `/why` and report under two seconds
**Constraints**: Observation-only; no raw payload storage; no service restart until end-of-day release
**Scale**: Four miners today, tens of miners within current retention design

## Constitution Check

### Pre-Design Gate

- **Production Safety First**: PASS. Audit follows existing decisions and cannot authorize an action.
- **Single Source Of Truth**: PASS. Only the example config receives shared defaults.
- **Telegram Operational Controls**: PASS. `/why` is read-only and deterministic.
- **Auto-Reboot Evidence And Gates**: PASS. Conditions/order remain unchanged and get evidence hooks only.
- **Windows Compatibility**: PASS. Standard-library modules and current service layout are retained.
- **Evidence-Based Completion**: PASS. Migration, parser, action-parity, command, and report tests are required.

### Post-Design Gate

- The parser is pure and independent from production policy.
- Schema migration is additive and transactional.
- Existing state evaluation still consumes the same active-board result as before.
- Decision records are written before existing `continue` statements but do not replace them.
- No new daemon, container, HTTP server, or runtime framework is introduced.

## Architecture

### Data Flow

1. The existing monitor tick reads `summary` and one `stats` response per responding miner.
2. Existing active-board behavior is preserved; the same response is additionally passed to a pure Vnish normalizer.
3. On the configured sample interval, normalized fields are stored in the existing sample row.
4. Existing auto-reboot branches call a small audit helper with their actual result and current evidence.
5. `/why` reads the newest decision row from SQLite.
6. `tools/incident_report.py` correlates database rows offline without runtime config or network access.

### Technology Decision

- **Keep SQLite**: transactional migrations, indexed correlations, zero deployment dependency, sufficient write volume.
- **Keep stdlib dataclasses/typing**: a pure parser is testable and portable to the existing service.
- **Defer FastAPI/dashboard**: a UI is useful only after telemetry and decision contracts are stable; adding an HTTP process now would not reduce reboot risk.
- **Defer Prometheus/Grafana**: valuable for fleet-scale time series later, but current four-miner incident analysis benefits more from normalized local evidence and explicit decisions.
- **Do not Dockerize the Windows service path**: Hashcore Toolkit and service ACL integration remain host-bound; containers may later host a read-only UI only.

## Project Structure

```text
app/
|-- miner_monitor.py          # reuse stats response, audit hooks, /why
|-- event_store.py            # schema v2, samples and decision queries
|-- vnish_telemetry.py        # pure normalization and evidence formatting
`-- config.example.json       # retention default only

tools/
`-- incident_report.py        # local Markdown/JSON correlation

tests/
|-- test_vnish_telemetry.py
|-- test_event_store.py
|-- test_reboot_decision_audit.py
`-- test_incident_report.py
```

## Delivery Phases

### Phase 1 - Pure Telemetry Contract

- Define normalized telemetry and conservative units.
- Parse all STATS entries and malformed data safely.
- Test real-shaped payloads captured by the existing sanitized diagnostics tool.

### Phase 2 - Schema V2

- Add telemetry columns and `reboot_decisions` transactionally.
- Add indexed query APIs, retention, and schema-version reporting.
- Test fresh creation and v1-to-v2 migration.

### Phase 3 - Runtime Evidence Hooks

- Reuse one stats response per tick.
- Persist normalized samples at the existing bounded interval.
- Audit each existing auto-reboot result before existing exits.
- Add `/why` as local-history-only UX.

### Phase 4 - Offline Correlation And Release Evidence

- Generate Markdown/JSON reports from SQLite.
- Run syntax, unit, config, QA, and diff validation.
- Update evidence, development log, and roadmap.
- Commit and push; do not restart the running service in this iteration.

## Complexity Tracking

No constitution exception. The additive module and table reduce logic inside the
production loop while preserving its exact policy ordering.
