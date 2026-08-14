# Evidence: Incident Evidence Fusion

**Status**: Planned; no implementation or runtime evidence yet

## Planning Baseline

- Spec package generated on 2026-08-13.
- Dependency gate: Spec 022 rollout and acquisition-quality evidence.
- Risk class: MEDIUM.
- No production code, local config, state, service or miner was changed by specification generation.

## Planning Hardening - 2026-08-13

- Mapped current EventStore tables, timestamps, analyzers, `/diagnose` fallback
  and dashboard boundary in `integration-map.md`.
- Defined exact observed/suspected/confirmed semantics, confidence ceilings,
  stale/clock behavior, fleet non-causality and electrical proof boundary in
  `contracts/evidence-rules.md`.
- Defined disabled-by-default configuration and validation in
  `contracts/config.md`.
- Defined additive idempotent assessment persistence, canonical replay digest,
  bounded indexed reads and one shared renderer.
- Added explicit FR/SC-to-task coverage and negative replay/action-invariant
  gates.
- This hardening changed planning artifacts only. No runtime source, local
  config/state/database, service or miner was changed.

## Required Evidence Before Completion

- Ruleset and fixture versions.
- Targeted/full tests and migration results.
- Sanitized before/after assessments.
- Query latency and database growth.
- Disabled-fallback, bounded-query and action-invariant proof.
- D+0/D+1/D+3 confidence-wording review.

## Runtime Rollout

- Not started.
- Do not mark this spec complete from checked tasks or compilation alone.
