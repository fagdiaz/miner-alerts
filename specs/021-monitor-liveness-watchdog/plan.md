# Implementation Plan: Monitor Liveness Watchdog

**Branch**: `021-monitor-liveness-watchdog` | **Date**: 2026-08-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/021-monitor-liveness-watchdog/spec.md`

## Summary

Add a bounded heartbeat writer to the monitor and a separate standard-library watchdog CLI scheduled by Windows. The watchdog reads only heartbeat and service/process state, sends liveness notifications, and validates SCM recovery without importing monitor action code.

## Technical Context

**Language/Version**: Python 3.14.x and PowerShell 5.1

**Primary Dependencies**: Python standard library, existing requests for Telegram delivery, Windows SCM and Task Scheduler; no new package

**Storage**: Atomic data/monitor_heartbeat.json and bounded ignored watchdog state; existing SQLite/config unchanged

**Testing**: `unittest`, deterministic fixtures, contract validation, `py_compile`, and controlled runtime evidence

**Target Platform**: Windows 10, Windows service/Scheduled Tasks, local ASIC network

**Project Type**: Existing monitor plus one independent read-only watchdog CLI and installer

**Performance Goals**: Heartbeat write under 20 ms per tick; watchdog under 10 seconds once per minute

**Constraints**: No real secrets or runtime files in Git; no unproved completion; no action authority outside the existing monitor

**Risk Classification**: HIGH - supervision and recovery changes can affect process availability but cannot authorize miner actions

**Scale/Scope**: Current four-miner fleet with bounded behavior for configured growth

## Constitution Check

- **Production Safety First**: PASS by design; the watchdog has no miner network or Hashcore access and startup safety remains authoritative.
- **Single Source Of Truth**: PASS; local config/state stay outside Git.
- **Telegram Operational Controls**: PASS; dangerous command confirmation remains unchanged.
- **Auto-Reboot Evidence And Gates**: PASS; existing policy remains authoritative and receives regression coverage.
- **Windows Compatibility**: PASS; validation and rollout are PowerShell/service compatible.
- **Evidence-Based Completion**: PASS by plan; runtime evidence and observation remain mandatory.

## Project Structure

### Documentation

```text
specs/021-monitor-liveness-watchdog/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/liveness.md
|-- checklists/requirements.md
|-- tasks.md
`-- evidence.md
```

### Planned Source Scope

```text
app/miner_monitor.py          # heartbeat integration only
app/liveness.py              # pure heartbeat/assessment
tools/monitor_watchdog.py    # independent watchdog
tools/install_watchdog_task.ps1
tools/observe_liveness.py    # read-only D+0/D+1/D+3 gate
tools/install_liveness_observation_tasks.ps1
tests/test_monitor_liveness.py
tests/test_liveness_observation.py
tests/test_reboot_safety.py
app/config.example.json
```

**Structure Decision**: Keep liveness assessment pure and the independent process under tools; only one best-effort heartbeat call enters the monitor tick.

## Phase 0: Research Decisions

See [research.md](research.md). SCM process status cannot prove tick progress, while heartbeat alone cannot restart a dead process. Both mechanisms are required and complementary.

## Phase 1: Design

- Write heartbeat through a temporary file plus atomic replace after a successful fleet tick.
- Use stable reason codes for service, process, tick, Telegram worker, collector and clock failures.
- Schedule the watchdog through pythonw.exe so it never creates a visible console.
- Use an expiring maintenance lease rather than a global disable flag.
- Validate restart only in QA first, then in one controlled production window.

## Rollback And Failure Boundary

- Removing the watchdog task restores prior supervision without changing monitor actions.
- Heartbeat write failure logs and monitoring continues; watchdog reports evidence unavailable.
- Export SCM recovery settings before change so they can be restored independently.

## Post-Design Constitution Check

PASS. No unresolved constitution violation exists. Completion remains conditional on `tasks.md` evidence and the scheduled observation window.
