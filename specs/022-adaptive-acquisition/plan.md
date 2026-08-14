# Implementation Plan: Adaptive Acquisition Resilience

**Branch**: `022-adaptive-acquisition` | **Date**: 2026-08-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/022-adaptive-acquisition/spec.md`

## Summary

Extract a deterministic acquisition scheduler behind a disabled-by-default
feature flag. It yields one authoritative envelope per miner per nominal
30-second epoch, skips missed epochs and uses a small bounded executor to
isolate slow endpoints. Optional episode diagnostics are typed
non-authoritative and barred from state/action mutation.

## Technical Context

**Language/Version**: Python 3.14.x and PowerShell 5.1

**Primary Dependencies**: Python standard library concurrent.futures and existing socket/JSON adapters; no new package

**Storage**: Existing SQLite telemetry plus bounded in-memory poll health

**Testing**: `unittest`, deterministic fixtures, contract validation, `py_compile`, and controlled runtime evidence

**Target Platform**: Windows 10, Windows service/Scheduled Tasks, local ASIC network

**Project Type**: Pure acquisition module integrated into the existing monitor loop

**Performance Goals**: Healthy fleet epoch under ten seconds at current scale,
five-second endpoint deadline, bounded workers, no per-miner overlap and no
catch-up burst after scheduler delay

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
|-- integration-map.md
|-- baseline.md
|-- test-design.md
|-- fixtures/acquisition-contract.json
|-- quickstart.md
|-- contracts/acquisition.md
|-- contracts/config.md
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

See [research.md](research.md), [integration-map.md](integration-map.md) and
[contracts/config.md](contracts/config.md).
API 4028 has no trusted push contract. Limited concurrent epochs reduce
head-of-line blocking, while typed provenance prevents faster probes from
changing count-based safety semantics. The integration map fixes the transport,
ordering, state-clock and manual-command boundaries against current source.

## Phase 1: Design

- Assign a monotonic epoch ID and deadline.
- Use two workers by default with a small start stagger.
- Return timeout/error envelopes instead of dropping miners.
- Measure the existing sleep-after-tick cadence before fixing epoch boundaries;
  do not infer an exact 30-second wall-clock baseline from `poll_seconds`.
- Schedule at most one current epoch after host resume and never replay missed
  epochs.
- Limit authoritative IO to one summary plus one conditional stats request per
  miner per epoch, without retries. Limit diagnostics to one summary request
  per eligible miner per interval.
- Keep authoritative cadence nominally at 30 seconds and diagnostic episode
  probes at a disabled-by-default 10 seconds.
- Keep manual Telegram command IO outside the scheduler and preserve its
  current cooldowns.
- Measure latency, request volume and stale rates before production enablement.

## Rollback And Failure Boundary

- `adaptive_acquisition_enabled=false` is the default. The flag restores the
  exact sequential acquisition boundary through the same envelope interface;
  deterministic parity and a live rollback rehearsal are required.
- Diagnostic probes default off and can be disabled independently.
- Errors fail closed and never reuse stale values as current.

## Post-Design Constitution Check

PASS. No unresolved constitution violation exists. Completion remains conditional on `tasks.md` evidence and the scheduled observation window.
