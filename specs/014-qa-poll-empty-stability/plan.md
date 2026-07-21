# Implementation Plan: QA Poll-Empty Stability

**Branch**: `codex/014-qa-poll-empty-stability` | **Date**: 2026-07-20 | **Spec**: `spec.md`

## Summary

Remove a misplaced QA command-duration log from the empty Telegram poll path and lock the scope invariant with a focused source regression test. Do not move or alter dispatch, offset, sleep, exception backoff, or action code.

## Technical Context

**Language/Version**: Existing Python runtime in `.venv`

**Primary Dependencies**: Python standard library, existing `requests` polling implementation

**Storage**: No storage change

**Testing**: `unittest`, `py_compile`, static source comparison

**Target Platform**: Windows service and PowerShell

**Project Type**: Long-running monitor with Telegram polling worker

**Performance Goals**: Empty polling adds no work beyond the existing debug log

**Constraints**: No service restart, no secrets, no action/policy/routing/offset change

**Scale/Scope**: One defective block and one regression test

## Constitution Check

- Production safety: PASS; no action logic is changed.
- Configuration source of truth: PASS; config files are untouched.
- Telegram control reliability: PASS; idle polling no longer fails on command-local names.
- Windows compatibility: PASS; validation uses the repository virtualenv.
- Evidence-based completion: PASS; focused/full tests and source comparison are required.

## Project Structure

```text
app/miner_monitor.py
tests/test_telegram_polling_stability.py
specs/014-qa-poll-empty-stability/
docs/audit/DEVELOPMENT_LOG.md
docs/speckit/ROADMAP.md
```

**Structure Decision**: Keep the fix in the existing worker and add only a source-level regression test because executing the infinite polling worker would require network/thread orchestration unrelated to the defect.

## Design

- Preserve the existing `if DBG_TELEGRAM` and `POLL_EMPTY` structure.
- Remove only the nested QA duration statement that references `action` and `cmd_start` outside their valid command branch.
- Compare polling and core anchors with the parent commit to prove no surrounding algorithm changed.
