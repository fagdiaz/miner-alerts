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

## EventStore Inventory And Red Contracts (T001-T003) - 2026-08-15

- T001: Confirmed five EventStore source tables are indexed and queryable for
  fusion (`telemetry_samples`, `operational_events`, `reboot_decisions`,
  `firmware_events`, `collector_runs`). Schema version is 5. All six reusable
  analyzers (`stability_profile`, `mining_quality`, `restart_intelligence`,
  `alert_episodes`, `vnish_logs`, `vnish_telemetry`) exist in `app/`.
- T001 finding: Spec 022 quality persistence (authority, reason_code columns
  in `telemetry_samples`) is **not yet available** — T007 of Spec 022 remains
  open. Current `quality_flags_json` column exists but does not carry Spec 022
  `Authority`/`Quality`/`reason_code` provenance. Implementation tasks T008+
  remain blocked until T007 completes.
- T002: Created 14 red contract tests in `tests/test_evidence_fusion.py` for
  `FusionConfig.from_mapping` covering disabled-by-default, boolean validation,
  `context_hours` range (1-168), `fleet_window_seconds` range (30-300), NaN
  and Infinity rejection, and exact default fallback behavior per
  `contracts/config.md`.
- T003: Created 32 red contract tests for `EvidenceFact` immutability and
  `fact_id` format, `classify_freshness` (fresh/stale/future_skew/unknown),
  `map_clock_quality` (system/system_local/fixed_utc_offset/unparsed/unknown),
  `validate_fact_code` fail-closed for unknown families,
  `sort_facts_canonical` stable ordering by `(effective_ts, source,
  source_row_id, code)`, and `compute_evidence_digest` determinism, SHA-256
  format, ruleset sensitivity and non-finite value safety.
- All 46 new tests fail with `ModuleNotFoundError: No module named
  'app.evidence_fusion'` — the correct red reason.
- All 206 existing tests pass without regressions (0 failures, 0 errors).
- No production code, config, state, database, service or miner was changed.

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
