# Evidence: Adaptive Acquisition Resilience

**Status**: Planning hardened; implementation blocked by the Spec 021 D+1 gate

## Planning Baseline

- Spec package generated on 2026-08-13.
- Dependency gates: Spec 021 D+1 before implementation and D+3 before
  production activation.
- Risk class: HIGH.
- No production code, local config, state, service or miner was changed by specification generation.

## Pre-Implementation Readiness - 2026-08-13

- Source mapping confirmed the current fleet loop is sequential: each miner may
  issue one `summary` request and, when responsive, one `stats` request before
  the loop sleeps for `poll_seconds`.
- The original exact 30-second assumption was corrected: current cadence is
  full-tick duration plus the configured sleep, so missed epochs must be
  skipped rather than replayed.
- Request budgets are now explicit for authoritative and diagnostic traffic.
- Adaptive scheduling is disabled by default and rollback is the existing
  sequential path through `adaptive_acquisition_enabled=false`.
- Planned tests now cover slow peers, late results, host resume, transport
  failure, partial responses, request budgets, manual-command isolation and
  disabled-path parity.
- No application source, runtime config, state, service or miner was changed by
  this planning hardening.

## Required Evidence Before Completion

- Before/after request, latency and tick report.
- Envelope fixtures for invalid, late and diagnostic handling.
- Numeric request-budget and missed-epoch proof.
- Disabled-path parity and rollback rehearsal.
- State, action and Telegram-offset invariants.
- QA and D+1/D+3 runtime logs.

## Runtime Rollout

- Not started.
- Do not mark this spec complete from checked tasks or compilation alone.
