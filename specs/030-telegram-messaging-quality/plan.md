# Implementation Plan: Telegram Messaging Quality

**Branch**: `codex/030-telegram-messaging-quality` | **Date**: 2026-08-13 | **Spec**: [spec.md](spec.md)

## Summary

Introduce pure message-contract helpers for deterministic size handling and delivery classification, align the central command registry/help with the real dispatcher, and harden queue admission without changing monitoring or action policy.

## Technical Context

**Language/Version**: Python 3.14.x

**Primary Dependencies**: Python standard library and existing `requests`; no new package or Telegram framework

**Storage**: Existing config/state/SQLite unchanged

**Testing**: `unittest`, parser/render/queue fixtures, full regression, `py_compile`, config parse, secret scan and runtime read-only command smoke

**Target Platform**: Windows service through NSSM, Telegram Bot API long polling

**Performance Goals**: Rendering and splitting under 10 ms; command reply admitted immediately; no extra miner I/O

**Constraints**: Plain text only; 4096-character platform ceiling; no automatic retries; secrets stay local; no core-policy changes

**Risk Classification**: MEDIUM - delivery and presentation change, miner actions do not

## Constitution Check

- **Production Safety First**: PASS; no miner action or policy change.
- **Single Source Of Truth**: PASS; the command registry remains central and local secrets remain ignored.
- **Telegram Operational Controls**: PASS; dangerous actions retain confirmation and official click-safe aliases.
- **Auto-Reboot Evidence And Gates**: PASS; untouched and regression-scanned.
- **Windows Compatibility**: PASS; standard library and current service model only.
- **Evidence-Based Completion**: PASS; runtime command smoke and rollout evidence are mandatory.

## Planned Source Scope

```text
app/telegram_messages.py
app/miner_monitor.py
app/alert_episodes.py
tests/test_telegram_messaging.py
tests/test_notification_stability.py
README.md
docs/speckit/RUNBOOK.md
```

## Design

- Keep `send_telegram` as the single integration point.
- Add pure helpers for category, criticality, text normalization and bounded splitting.
- Preserve the existing queue tuple contract where practical; add only metadata needed for deterministic admission/outcome logs.
- Derive help and official aliases from the central command registry.
- Preserve episode coordinator timing and change presentation only.

## Rollback And Failure Boundary

- Renderer/helper changes can be reverted without data migration.
- A splitting failure falls back to one bounded safe error rather than executing any action.
- Queue hardening affects delivery only; monitoring continues if Telegram is unavailable.
- Rollout uses QA and read-only commands before one controlled service restart.

## Post-Design Constitution Check

PASS. No unresolved safety or governance violation exists.
