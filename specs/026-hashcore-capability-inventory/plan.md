# Implementation Plan: Hashcore Capability Inventory

**Branch**: `026-hashcore-capability-inventory` | **Date**: 2026-08-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/026-hashcore-capability-inventory/spec.md`

## Summary

Build a sanitized, versioned inventory from the installed Toolkit using only bounded vendor-proven help/version discovery. Classify every operation conservatively and produce integration candidates, without changing current reboot/restart execution.

## Technical Context

**Language/Version**: Python 3.14.x and PowerShell 5.1

**Primary Dependencies**: Python standard library subprocess and the installed Toolkit; no new package

**Storage**: Versioned sanitized JSON/Markdown under diagnostics/hashcore, with raw local output ignored

**Testing**: `unittest`, deterministic fixtures, contract validation, `py_compile`, and controlled runtime evidence

**Target Platform**: Windows 10, Windows service/Scheduled Tasks, local ASIC network

**Project Type**: Offline/read-only inventory CLI and documentation artifacts

**Performance Goals**: Every invocation has a short documented timeout and the full inventory completes under two minutes

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
|-- checklists/requirements.md
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

**Structure Decision**: Keep inventory outside the monitor and commit only sanitized normalized artifacts. Raw local outputs remain ignored.

## Phase 0: Research Decisions

See [research.md](research.md). The repository currently knows only existing reboot/restart templates. The installed binary is the authoritative capability source, but unknown commands are unsafe; discovery must be evidence-first and no-window.

## Phase 1: Design

- Fingerprint installation and version before command discovery.
- Use a fixed allowlist of vendor-proven help/version invocations.
- Normalize output shape while preserving exit code and timeout evidence.
- Classify unknown as prohibited until vendor evidence proves otherwise.
- Rank read-only candidates by unique operational value and source overlap.

## Rollback And Failure Boundary

- Inventory tooling is standalone and removable without runtime impact.
- Timeout or ambiguous output closes the item as unknown.
- No monitor code or production templates change in this spec.

## Post-Design Constitution Check

PASS. No unresolved constitution violation exists. Completion remains conditional on `tasks.md` evidence and the scheduled observation window.
