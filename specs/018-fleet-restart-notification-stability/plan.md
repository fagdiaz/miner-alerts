# Implementation Plan: Fleet Restart Notification Stability

**Branch**: `codex/018-fleet-restart-notification-stability` | **Date**: 2026-07-21 | **Spec**: `spec.md`

## Summary

Add a bounded in-memory restart notification batch and Telegram-only recovery
quiet window, correct unattributed restart wording, and make the separate
Windows collector task hidden with a lower default cadence. No state-machine or
action-policy condition changes.

## Technical Context

**Language/Version**: Python 3.14, PowerShell 5.1

**Primary Dependencies**: Existing requests/Telegram queue, Windows ScheduledTasks

**Storage**: Existing SQLite event store; batching remains in memory

**Testing**: unittest, static scheduler contract tests, py_compile, PowerShell parser

**Target Platform**: Windows service plus current-user scheduled task

**Project Type**: Production monitor and Telegram bot

**Performance Goals**: Bounded per-tick work; no miner IO added

**Constraints**: No Hashcore/action changes, no polling changes, no secrets, no new dependencies

**Scale/Scope**: Four miners today; bounded fleet list for configured miners

## Constitution Check

- Production safety: PASS; changes only reduce notification noise and task visibility/frequency.
- Runtime config source: PASS; only `config.example.json` receives defaults.
- Telegram controls: PASS; no command or confirmation flow changes.
- Auto-reboot evidence/gates: PASS; no action-policy branch changes.
- Windows compatibility: PASS; PowerShell 5.1 task action is explicitly tested.
- Evidence completion: REQUIRED before rollout.

## Project Structure

```text
app/miner_monitor.py
app/config.example.json
tools/install_vnish_collector_task.ps1
tests/test_monitor_incidents.py
tests/test_vnish_scheduler.py
specs/018-fleet-restart-notification-stability/
docs/audit/DEVELOPMENT_LOG.md
docs/speckit/ROADMAP.md
```

**Structure Decision**: Reuse the existing monitor loop, notification queue and
scheduler installer; add only pure render/readiness helpers plus in-memory
batch state.
