# Implementation Plan: Electrical Source Discovery

**Branch**: `024-electrical-source-discovery` | **Date**: 2026-08-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/024-electrical-source-discovery/spec.md`

## Summary

Run a discovery-first hardware and protocol gate. If a trustworthy source exists, add one bounded read-only adapter and normalized electrical samples; otherwise record a blocked dependency. Incident correlation remains advisory.

## Technical Context

**Language/Version**: Python 3.14.x and PowerShell 5.1

**Primary Dependencies**: Conditional source-specific library or standard protocol client selected only after discovery; no dependency approved in advance

**Storage**: Sanitized capability report and optional additive SQLite electrical_samples table

**Testing**: `unittest`, deterministic fixtures, contract validation, `py_compile`, and controlled runtime evidence

**Target Platform**: Windows 10, Windows service/Scheduled Tasks, local ASIC network

**Project Type**: Read-only discovery CLI and conditional bounded collector adapter

**Performance Goals**: At most one documented-rate sample per source interval with no device request burst

**Constraints**: No real secrets or runtime files in Git; no unproved completion; no action authority outside the existing monitor

**Risk Classification**: MEDIUM - electrical evidence may be incomplete or misleading, so discovery is read-only and conclusions remain explicit

**Scale/Scope**: Current four-miner fleet with bounded behavior for configured growth

## Constitution Check

- **Production Safety First**: PASS by design; all protocol writes and all action coupling are prohibited.
- **Single Source Of Truth**: PASS; local config/state stay outside Git.
- **Telegram Operational Controls**: PASS; dangerous command confirmation remains unchanged.
- **Auto-Reboot Evidence And Gates**: PASS; existing policy remains authoritative and receives regression coverage.
- **Windows Compatibility**: PASS; validation and rollout are PowerShell/service compatible.
- **Evidence-Based Completion**: PASS by plan; runtime evidence and observation remain mandatory.

## Project Structure

### Documentation

```text
specs/024-electrical-source-discovery/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- integration-map.md
|-- contracts/capability-report.md
|-- contracts/electrical-source.md
|-- checklists/requirements.md
|-- tasks.md
`-- evidence.md
```

### Planned Source Scope

```text
tools/electrical_discovery.py
app/electrical_telemetry.py        # only after source gate
app/event_store.py                 # additive samples if approved
tests/test_electrical_telemetry.py
diagnostics/electrical/README.md   # sanitized generated artifacts
app/config.example.json
```

**Structure Decision**: Keep hardware discovery and any adapter outside the monitor action path; use EventStore only after source and schema gates pass.

## Phase 0: Research Decisions

See [research.md](research.md) and [integration-map.md](integration-map.md).
Protocol choice follows the actual device. SNMPv3 offers authenticated
management data, Modbus defines interoperable registers but requires a model
map, MQTT is useful only when a device publishes, and miner chain voltage is
not AC evidence.

## Phase 1: Design

- Produce a capability matrix before selecting a dependency.
- Require the exact supported/unsupported/blocked report from
  `contracts/capability-report.md` before adapter work.
- Prefer authenticated read-only SNMPv3 when available; otherwise use documented read-only Modbus/vendor HTTPS/MQTT.
- Normalize measurements into SI units and preserve source clock quality.
- Persist collection health separately from values.
- Feed power facts into Spec 023 only as observed/advisory evidence.
- Enforce one in-flight request, source-specific operation allowlists, no generic
  scanning and no same-interval retries.

## Current Repository Finding

Current Vnish/API 4028 fields are internal chain voltage/power, ASIC frequency,
temperature and firmware-reported PSU/power conditions. No tracked external
PDU/UPS/meter source or AC adapter exists. Planning is ready, but adapter work is
blocked until real hardware identity, documentation and access are supplied.

## Rollback And Failure Boundary

- If discovery is blocked, no runtime component or schema is added.
- The collector is independently disabled without affecting miner monitoring.
- Adapter failure records unavailable evidence and never changes actions.
- A blocked discovery closes without dependency, table, collector or service
  installation.

## Post-Design Constitution Check

PASS. No unresolved constitution violation exists. Completion remains conditional on `tasks.md` evidence and the scheduled observation window.
