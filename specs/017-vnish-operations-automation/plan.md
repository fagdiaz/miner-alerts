# Implementation Plan: Vnish Operations Automation

**Branch**: `codex/017-vnish-operations-automation` | **Date**: 2026-07-20

## Design

1. Correct the pure parser to inspect the newest bounded lines and retain the
   newest bounded recognized events.
2. Add schema-v5 source-time metadata and `collector_runs` health records.
3. Extend the one-shot collector to persist one generated run summary.
4. Add PowerShell wrapper/installer scripts for a non-overlapping current-user
   scheduled task; do not register it until final rollout.
5. Add a bounded `/diagnose` renderer over existing SQLite evidence only.

## Technology

- Python 3.12+ and SQLite for deterministic local storage.
- Existing `websocket-client` only in the separate collector.
- Native Windows ScheduledTasks cmdlets; no scheduler dependency.
- `unittest`, fake transport, temporary SQLite and static source assertions.

## Safety

- Collector remains GET-upgrade/read-only and sequential.
- Scheduler invokes only the collector wrapper and ignores overlapping runs.
- Parsed source epoch is advisory and carries provenance.
- `/diagnose` is not imported by auto-reboot policy and performs no live IO.
- Real config/state remain untouched until explicit final rollout.
