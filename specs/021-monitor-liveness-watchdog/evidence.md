# Evidence: Monitor Liveness Watchdog

**Status**: Planned; no implementation or runtime evidence yet

## Planning Baseline

- Spec package generated on 2026-08-13.
- Dependency gate: Spec 020 production activation, smoke and initial soak.
- Risk class: HIGH.
- No production code, local config, state, service or miner was changed by specification generation.

## Required Evidence Before Completion

- Exact tests and compilation.
- Before/after SCM failure-action export.
- Sanitized heartbeat samples.
- Watchdog open/recovery logs and delivery.
- New PID, mutex, startup guard and no-action proof.

## Runtime Rollout

- Not started.
- Do not mark this spec complete from checked tasks or compilation alone.
