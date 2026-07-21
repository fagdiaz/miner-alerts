# Implementation Plan: Persistent Outage Alerts

**Branch**: `019-persistent-outage-alerts` | **Date**: 2026-07-21 | **Spec**: `specs/019-persistent-outage-alerts/spec.md`

## Summary

Add a Telegram-only state batcher and in-memory persistent-outage reminder coordinator around the existing confirmed state output. Replace the Vnish scheduled task's PowerShell action with direct `pythonw.exe` execution and add a portable no-console creation flag to existing subprocess calls. No state or reboot policy is changed.

## Technical Context

**Language/Version**: Python 3.14, PowerShell 5.1

**Primary Dependencies**: Standard library, existing requests/Telegram queue, Windows ScheduledTasks

**Storage**: Existing `state.json` and SQLite remain unchanged; notification coordination is process-local

**Testing**: `unittest`, static scheduler/subprocess contract tests, `py_compile`, JSON parse, PowerShell parser

**Target Platform**: Windows service plus local ASIC network

**Project Type**: Single-process monitoring service with one scheduled diagnostics collector

**Performance Goals**: No miner IO added; notification coordination remains O(number of configured miners)

**Constraints**: No business-policy changes, no new dependency, no secret-bearing config edits, no duplicate monitor instance

**Scale/Scope**: Current four-miner fleet with bounded behavior for larger configured fleets

## Constitution Check

- Production Safety First: PASS; only confirmed states drive reminders and no action gate changes.
- Single Source Of Truth: PASS; defaults are code/example config and real config is not edited.
- Telegram Operational Controls: PASS; delivery path is reused and commands are untouched.
- Auto-Reboot Evidence And Gates: PASS; evaluation order and conditions are outside the edit scope.
- Windows Compatibility: PASS; direct `pythonw.exe` task action and portable creation flags are tested.
- Evidence-Based Completion: PASS; runtime activation and UAC-dependent steps are recorded explicitly.

## Project Structure

```text
app/miner_monitor.py
app/config.example.json
tools/install_vnish_collector_task.ps1
tests/test_notification_stability.py
tests/test_vnish_scheduler.py
specs/019-persistent-outage-alerts/
docs/audit/DEVELOPMENT_LOG.md
docs/speckit/ROADMAP.md
docs/speckit/RUNBOOK.md
```

**Structure Decision**: Keep notification coordinators beside the existing restart coordinator in the monitor and retain the current one-file runtime architecture.

## Complexity Tracking

No constitution violations.
