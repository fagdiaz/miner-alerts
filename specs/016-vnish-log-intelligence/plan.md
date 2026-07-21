# Implementation Plan: Vnish Log Intelligence

**Branch**: `codex/016-vnish-log-intelligence` | **Date**: 2026-07-20 | **Spec**: `spec.md`

## Summary

Add a pure Vnish log taxonomy, an idempotent schema-v4 firmware event store, a bounded sequential WebSocket collector CLI, and read-only Telegram/dashboard views. Keep acquisition outside the monitor loop and prohibit all action-policy consumption in this version.

## Technical Context

**Language/Version**: Python 3.14 local; compatible with project Python 3.12 container baseline

**Primary Dependencies**: `websocket-client` for collector only; existing standard library and SQLite

**Storage**: Additive SQLite schema v4 `firmware_events`

**Testing**: `unittest`, fake WebSocket transport, migration fixtures, CLI/live smoke, `py_compile`

**Target Platform**: Native Windows PowerShell against local Vnish S19j Pro network

**Project Type**: Monitor plus separate read-only operations CLI and static dashboard

**Performance Goals**: Bounded memory/bytes/events; no monitor-loop latency

**Constraints**: No raw logs in DB/git, no POST/actions, no background worker in monitor, no auto-reboot coupling

**Scale/Scope**: Four miners, four confirmed log tabs, replayed historical buffers

## Constitution Check

- Production safety: PASS; collector is separate and read-only, events are advisory only.
- Configuration/secrets: PASS; real config is read locally and remains ignored.
- Auto-reboot: PASS; parser/store/views are not imported by policy modules.
- Windows: PASS; native CLI is primary.
- Evidence: PASS; live bounded read-only smoke and unverified limitations are recorded.

## Project Structure

```text
app/vnish_logs.py
app/event_store.py
app/miner_monitor.py
tools/vnish_log_collector.py
tools/operations_dashboard.py
tests/test_vnish_logs.py
tests/test_event_store.py
tests/test_operations_dashboard.py
requirements.txt
specs/016-vnish-log-intelligence/
```

**Structure Decision**: Keep protocol acquisition in `tools/`, pure parsing in `app/`, and shared persistence/views in existing modules. The production monitor never opens a Vnish log WebSocket.

## Collection Flow

```text
config miners -> sequential ws read -> bounded text chunks -> pure parser
-> generated event + SHA-256 fingerprint -> INSERT OR IGNORE schema v4
-> /firmware and static dashboard read SQLite
```

## Safety Gates

- Allowed endpoint prefix exactly `/api/v1/logs-ws/`.
- Allowed tabs fixed to `status`, `miner`, `autotune`, `system`.
- Connect/idle timeout and max bytes/events clamped.
- No reconnect/retry loop in one invocation.
- No raw content persisted or printed by default.
- Duplicate insert is a successful no-op.
