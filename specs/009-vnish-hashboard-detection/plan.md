# Implementation Plan: Vnish Hashboard Detection

**Branch**: `009-vnish-hashboard-detection` | **Date**: 2026-07-20 | **Spec**: [spec.md](spec.md)

## Approach

1. Add the `chain_acnN` case already proven in `tools/miner_diagnostics.py` to the production counter.
2. Iterate all `STATS` dictionaries in `read_stats_snapshot`, stopping at the first explicit board signal.
3. Keep the same single API call and return the full response for Spec 007 telemetry.
4. Add table-driven parser tests and a source assertion that HASHBOARD precedence remains before LOW.
5. Run all high-risk gates and defer service activation.

## Constitution Check

- Production safety: PASS; explicit board failure maps to the existing non-auto-reboot HASHBOARD state.
- Configuration/source of truth: PASS; no config change.
- Auto-reboot gates: PASS pending tests; action code is untouched.
- Windows compatibility: PASS.
- Evidence-based completion: PASS pending full validation.

## Scope Boundary

No new hysteresis, threshold, action, Telegram command, storage schema, network
call, or framework is introduced. This patch only restores the intended board
signal from Vnish's actual response shape.
