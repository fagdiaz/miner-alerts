# Implementation Plan: Hashcore Capability Inventory

**Branch**: `026-hashcore-capability-inventory` | **Date**: 2026-08-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/026-hashcore-capability-inventory/spec.md`

## Summary

Build a sanitized, versioned inventory from the installed Toolkit in two
strictly separated phases: default metadata-only fingerprinting with zero
processes, then optional bounded invocation only from an exact
fingerprint-bound vendor-proven allowlist. Classify every evidenced operation
conservatively and produce integration candidates without changing current
reboot/restart execution.

## Technical Context

**Language/Version**: Python 3.14.x and PowerShell 5.1

**Primary Dependencies**: Python standard library subprocess and the installed Toolkit; no new package

**Storage**: Versioned sanitized JSON/Markdown under diagnostics/hashcore, with raw local output ignored

**Testing**: `unittest`, deterministic fixtures, contract validation, `py_compile`, and controlled runtime evidence

**Target Platform**: Windows 10, Windows service/Scheduled Tasks, local ASIC network

**Project Type**: Offline/read-only inventory CLI and documentation artifacts

**Performance Goals**: Metadata-only completes within 5 seconds; every approved invocation is capped at 10 seconds and 64 KiB per stream; the full inventory completes under two minutes

**Constraints**: No real secrets or runtime files in Git; no unproved completion; no action authority outside the existing monitor

**Risk Classification**: MEDIUM - unsupported Toolkit discovery can be dangerous, so unknown operations are prohibited and inventory is read-only

**Scale/Scope**: Current four-miner fleet with bounded behavior for configured growth

## Constitution Check

- **Production Safety First**: PASS by design; unknown equals prohibited and no new mutating operation is invoked.
- **Single Source Of Truth**: PASS; local config/state stay outside Git.
- **Telegram Operational Controls**: PASS; dangerous command confirmation remains unchanged.
- **Auto-Reboot Evidence And Gates**: PASS; existing policy remains authoritative and receives regression coverage.
- **Windows Compatibility**: PASS; validation and rollout are PowerShell/service compatible.
- **Evidence-Based Completion**: PASS by plan; runtime evidence and observation remain mandatory.

## Project Structure

### Documentation

```text
specs/026-hashcore-capability-inventory/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/capability-inventory.md
|-- contracts/discovery-allowlist.md
|-- checklists/requirements.md
|-- integration-map.md
|-- tasks.md
`-- evidence.md
```

### Planned Source Scope

```text
tools/hashcore_inventory.py
tests/test_hashcore_inventory.py
diagnostics/hashcore/README.md
docs/speckit/HASHCORE_TOOLKIT_STRATEGY.md
app/miner_monitor.py          # invariant inspection only; no planned behavior change
```

**Structure Decision**: Keep inventory outside the monitor and commit only
sanitized normalized artifacts. Raw local outputs remain ignored. The installed
wrapper is a pass-through, not a policy boundary, so metadata collection and
process invocation are separate code paths.

## Phase 0: Research Decisions

See [research.md](research.md) and [integration-map.md](integration-map.md).
Static inspection proves a local Toolkit `1.6.0+167` installation and a batch
wrapper that forwards arbitrary arguments. It does not prove any argument safe.
The invocation allowlist therefore remains empty and process discovery blocked.

## Phase 1: Design

- Fingerprint installation and version without process creation before command discovery.
- Make metadata-only the default and valid blocked outcome.
- Use a fixed, fingerprint-bound allowlist of vendor-proven help/version invocations only when evidence exists.
- Normalize output shape while preserving exit code and timeout evidence.
- Classify unknown as prohibited until vendor evidence proves otherwise.
- Rank read-only candidates by unique operational value and source overlap.

## Rollback And Failure Boundary

- Inventory tooling is standalone and removable without runtime impact.
- Missing/mismatched allowlist starts zero processes and closes as blocked.
- Timeout or ambiguous output closes the item as unknown.
- No monitor code or production templates change in this spec.

## Post-Design Constitution Check

PASS. No unresolved constitution violation exists. Completion remains conditional on `tasks.md` evidence and the scheduled observation window.
