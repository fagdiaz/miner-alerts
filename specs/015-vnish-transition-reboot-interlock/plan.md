# Implementation Plan: Vnish Transition Reboot Interlock

**Branch**: `codex/015-vnish-transition-reboot-interlock` | **Date**: 2026-07-20 | **Spec**: `spec.md`

## Summary

Extend the existing pure reboot interlock with current Vnish transition evidence already normalized by Mining Quality. When enabled and positive, block automatic reboot, persist/log the reason, and reset only the sustained action timer so a full LOW interval is required after transition. Keep manual actions and all other policy gates unchanged.

## Technical Context

**Language/Version**: Existing Python runtime in `.venv`

**Primary Dependencies**: Standard library and existing local modules only

**Storage**: Existing SQLite `reboot_decisions.details_json`; no schema change

**Testing**: `unittest`, source-order assertions, `py_compile`, QA safety tests

**Target Platform**: Windows service, Vnish S19j Pro, Hashcore Toolkit CLI

**Project Type**: Long-running monitor and Telegram operations bot

**Performance Goals**: Constant-time gate; zero additional miner IO

**Constraints**: No manual-action change, no raw firmware payload, no new state field, no service restart during implementation

**Scale/Scope**: Existing four-miner deployment; generic per-miner policy

## Constitution Check

- Production safety: PASS; this adds a no-action gate and requires QA evidence.
- Config source: PASS; only `config.example.json` and code default are changed.
- Auto-reboot evidence/gates: PASS; existing ordering is retained and tested.
- Telegram controls: PASS; manual command paths are out of scope.
- Windows/evidence: PASS; full local validation and deferred controlled rollout are explicit.

## Project Structure

```text
app/reboot_safety.py
app/miner_monitor.py
app/event_store.py
app/config.example.json
tests/test_reboot_safety.py
tests/test_reboot_decision_audit.py
specs/015-vnish-transition-reboot-interlock/
docs/speckit/RUNBOOK.md
```

**Structure Decision**: Reuse the pure interlock module and existing decision audit. No framework or persistence technology is added because the requirement is a synchronous policy gate over existing data.

## Gate Order

1. Existing current-signal eligibility.
2. Existing startup guard.
3. Existing LOW sustained check.
4. Existing thermal interlock.
5. New Vnish transition interlock.
6. Existing fleet incident interlock.
7. Existing cooldown/window/QA checks.
8. Existing Hashcore action.

## Data Handling

- Input: `MiningQualityTelemetry.chains_transitioning_count` from the same tick.
- Stored evidence: count and enabled state only.
- Action timer: `low_since_ts` set to the current evaluation time after a transition block.
- No raw chain-state strings are persisted by this feature.
