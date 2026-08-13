# Implementation Plan: V2 Release Stabilization

**Branch**: `029-v2-release-stabilization` | **Date**: 2026-08-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/029-v2-release-stabilization/spec.md`

## Summary

Freeze features, build a release matrix from every accepted spec, run clean-environment and cross-feature regressions, execute controlled service activation plus backup restore, complete a 72-hour soak and seven-day review, and reconcile all documentation before release approval.

## Technical Context

**Language/Version**: Python 3.14.x and PowerShell 5.1

**Primary Dependencies**: Existing project/runtime dependencies and optional accepted observability/interface stacks; no new dependency

**Storage**: Existing SQLite plus release evidence and one verified external backup

**Testing**: `unittest`, deterministic fixtures, contract validation, `py_compile`, and controlled runtime evidence

**Target Platform**: Windows 10, Windows service/Scheduled Tasks, local ASIC network

**Project Type**: Release integration, validation, operational rollout and documentation closeout

**Performance Goals**: No regression beyond per-spec budgets; monitor and auxiliary resource baselines remain within approved limits

**Constraints**: No real secrets or runtime files in Git; no unproved completion; no action authority outside the existing monitor

**Risk Classification**: HIGH - this is the integrated production release gate across all prior reliability and observability work

**Scale/Scope**: Current four-miner fleet with bounded behavior for configured growth

## Constitution Check

- **Production Safety First**: PASS by design; feature freeze is mandatory and any P0/P1 finding blocks release.
- **Single Source Of Truth**: PASS; local config/state stay outside Git.
- **Telegram Operational Controls**: PASS; dangerous command confirmation remains unchanged.
- **Auto-Reboot Evidence And Gates**: PASS; existing policy remains authoritative and receives regression coverage.
- **Windows Compatibility**: PASS; validation and rollout are PowerShell/service compatible.
- **Evidence-Based Completion**: PASS by plan; runtime evidence and observation remain mandatory.

## Project Structure

### Documentation

```text
specs/029-v2-release-stabilization/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/release-gate.md
|-- checklists/requirements.md
|-- tasks.md
`-- evidence.md
```

### Planned Source Scope

```text
tests/                         # full regression and focused release contracts
specs/021-*/evidence.md ... specs/029-*/evidence.md
docs/speckit/
docs/audit/DEVELOPMENT_LOG.md
README.md
AGENTS.md
# Production code changes only as isolated bug fixes with separate evidence
```

**Structure Decision**: Use existing per-spec artifacts as evidence sources. Stabilization owns the integration matrix and documentation baseline, not duplicated feature implementations.

## Phase 0: Research Decisions

See [research.md](research.md). The project constitution already requires runtime evidence beyond compilation. This spec formalizes feature freeze, clean validation, controlled activation, restore proof and an observation period as one release gate.

## Phase 1: Design

- Freeze accepted feature scope and record exact candidate identity.
- Map every core invariant and operator workflow to a deterministic check.
- Run static/unit/integration/QA first, then controlled production activation.
- Use 72-hour active soak followed by final seven-day reliability review.
- Perform three final documentation sweeps and block on unresolved contradictions.

## Rollback And Failure Boundary

- Keep the previous known-good service command/config and SCM settings documented before activation.
- A failed candidate is stopped and prior build/service definition restored without restoring state triggers.
- Database restoration remains staged/manual and never automatic.
- Any P0/P1 finding returns ownership to the smallest affected spec or isolated hotfix evidence.

## Post-Design Constitution Check

PASS. No unresolved constitution violation exists. Completion remains conditional on `tasks.md` evidence and the scheduled observation window.
