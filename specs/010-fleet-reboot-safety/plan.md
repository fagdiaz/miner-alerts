# Implementation Plan: Fleet-Aware Auto-Reboot Safety

**Branch**: `010-fleet-reboot-safety` | **Date**: 2026-07-20 | **Spec**: [spec.md](spec.md)

## Summary

Add a pure, dependency-free safety evaluator and wire it into the existing
auto-reboot chain after startup and sustained-LOW checks but before cooldown,
window, QA, and Hashcore. It blocks high-temperature candidates and shared fleet
degradation using the prior completed tick plus the current candidate. Existing
SQLite decision details provide durable evidence without a schema migration.

## Technical Context

**Language/Version**: Python in the existing Windows virtualenv  
**Primary Dependencies**: Python standard library and existing Vnish telemetry model  
**Storage**: Existing SQLite `reboot_decisions.details_json`; no schema change  
**Testing**: `unittest`, source-level policy wiring checks, `py_compile`  
**Target Platform**: Windows service, PowerShell, ASIC API 4028, Hashcore Toolkit CLI  
**Project Type**: Single Python monitor with local operational tools  
**Performance Goals**: Constant-time fleet evaluation over the configured miner count; no added IO  
**Constraints**: No manual-action changes, no service restart, no secret/config runtime edits  
**Scale/Scope**: Current small local fleet; deterministic behavior for arbitrary configured counts

## Constitution Check

- **Production Safety First**: PASS. Both paths only remove automatic action eligibility.
- **Single Source Of Truth**: PASS. Defaults live in `app/config.example.json`; real config is untouched.
- **Telegram Operational Controls**: PASS. Manual command code is outside scope.
- **Auto-Reboot Evidence And Gates**: HIGH-RISK PASS pending QA and policy tests.
- **Windows Compatibility**: PASS. No new dependency or process.
- **Evidence-Based Completion**: PASS. Pure tests, full suite, source-order checks, and service-state evidence are required.

## Design

1. Add `app/reboot_safety.py` with an immutable decision value and a pure evaluator.
2. Thermal evaluation accepts only finite numbers and blocks at the configured inclusive limit.
3. Fleet evaluation overlays the current candidate on the latest completed signal map and counts only `eligible` and `invalid_signal` classifications.
4. The monitor builds a current signal map while polling and publishes it as the completed map only after the full miner loop.
5. The interlock is consulted after startup guard and sustained LOW, before cooldown/window/QA/action.
6. `record_auto_reboot_decision` stores the stable reason plus details in the existing schema.
7. `/why` renders thermal/fleet details from the stored decision only.

## Project Structure

```text
app/reboot_safety.py
app/miner_monitor.py
app/event_store.py
app/config.example.json
tests/test_reboot_safety.py
specs/010-fleet-reboot-safety/
docs/speckit/
docs/audit/DEVELOPMENT_LOG.md
```

## Validation

- Pure boundary tables for temperature and fleet counts.
- Policy wiring assertions for gate order and completed-tick publication.
- Existing event-store render tests for new evidence.
- Full unit suite, Python compilation, diff check, and Speckit HIGH-risk preflight.
- Service remains running but is not restarted.

## Complexity Tracking

No constitution violations. A separate pure module is justified because it
isolates a dangerous policy decision and permits deterministic tests without
starting the monitor or invoking Hashcore.
