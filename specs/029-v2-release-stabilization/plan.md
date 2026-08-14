# Implementation Plan: V2 Release Stabilization

**Branch**: `029-v2-release-stabilization` | **Date**: 2026-08-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/029-v2-release-stabilization/spec.md`

## Summary

Freeze features and a deterministic runtime payload, build stable R001-R025
evidence from every terminal dependency, run clean-environment and cross-feature
regressions, execute controlled service activation plus staging restore, complete
one continuous 168-hour review with a 72-hour checkpoint, and reconcile all
documentation before binary approve/block.

## Technical Context

**Language/Version**: Python 3.14.x and PowerShell 5.1

**Primary Dependencies**: Existing project/runtime dependencies and optional accepted observability/interface stacks; no new dependency

**Storage**: Existing SQLite plus release evidence and one verified external backup

**Testing**: `unittest`, deterministic fixtures, contract validation, `py_compile`, and controlled runtime evidence

**Target Platform**: Windows 10, Windows service/Scheduled Tasks, local ASIC network

**Project Type**: Release integration, validation, operational rollout and documentation closeout

**Performance Goals**: No regression beyond per-spec budgets; monitor and auxiliary resource baselines remain within approved limits; seven daily reports cover at least 168 continuous hours

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
|-- integration-map.md
|-- regression-matrix.md
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

**Structure Decision**: Use existing per-spec artifacts as evidence sources.
Stabilization owns the stable matrix, release manifest and documentation
baseline, not duplicated feature implementations. A small release-audit tool may
normalize evidence but cannot execute actions or infer missing runtime health.

## Phase 0: Research Decisions

See [research.md](research.md), [regression-matrix.md](regression-matrix.md) and
[integration-map.md](integration-map.md). The gate distinguishes full Git
identity from the deployed runtime-payload digest, requires terminal dependency
states and formalizes continuous observation rather than relying on checked
tasks or suite totals.

## Phase 1: Design

- Freeze accepted feature scope, terminal dispositions, full candidate identity
  and deterministic runtime-payload digest.
- Map every core invariant and operator workflow to a deterministic check.
- Run static/unit/integration/QA first, then controlled production activation.
- Use one 168-hour active review with daily reports and an hour-72 checkpoint.
- Perform three final documentation sweeps and block on unresolved contradictions.

## Rollback And Failure Boundary

- Keep the previous known-good service command/config and SCM settings documented before activation.
- A failed candidate is stopped and prior build/service definition restored without restoring state triggers.
- Database restoration remains staged/manual and never automatic.
- Any P0/P1 finding returns ownership to the smallest affected spec or isolated hotfix evidence.
- Runtime/config/schema/service changes reset affected checks and observation;
  docs-only changes preserve runtime hours only under the same payload digest.

## Post-Design Constitution Check

PASS. No unresolved constitution violation exists. Completion remains conditional on `tasks.md` evidence and the scheduled observation window.
