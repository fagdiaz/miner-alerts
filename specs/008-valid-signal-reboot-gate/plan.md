# Implementation Plan: Valid Signal Auto-Reboot Gate

**Branch**: `008-valid-signal-reboot-gate` | **Date**: 2026-07-20 | **Spec**: [spec.md](spec.md)

## Summary

Add one pure current-signal classifier and use it as the outer gate of the
existing LOW auto-reboot block. Invalid and recovered observations are audited,
logged, and clear only the sustained LOW timestamp. Eligible observations enter
the unchanged startup/sustained/cooldown/window/QA/action chain.

## Constitution Check

- **Production Safety First**: PASS. The change removes unsafe action eligibility.
- **Single Source Of Truth**: PASS. No config changes.
- **Telegram Operational Controls**: PASS. Manual commands are untouched.
- **Auto-Reboot Evidence And Gates**: HIGH-RISK PASS pending QA and policy tests.
- **Windows Compatibility**: PASS. Standard library only.
- **Evidence-Based Completion**: PASS. Pure and integration-level policy tests are required.

## Design

1. `classify_auto_reboot_signal()` returns one of three constants.
2. Existing state transition calculations remain byte-for-byte unchanged.
3. Existing preliminary `not_low` evidence for LOW signal before state hysteresis remains.
4. When `new_state == LOW`:
   - `invalid_signal`: audit/log once, clear `low_since_ts`, stop action evaluation for this miner tick without skipping later state notifications.
   - `not_low`: audit/log once, clear `low_since_ts`, stop action evaluation for this miner tick without skipping later state notifications.
   - `eligible`: enter the unchanged startup guard and all downstream gates.
5. No `continue` is added at the outer gate; normal post-policy state/event processing continues.

## Validation

- Unit table for all signal classes including non-finite floats.
- Source-level policy harness around the extracted gate behavior.
- Full existing suite and py_compile.
- Speckit HIGH-risk QA.
- No service restart until the end-of-day controlled activation.
