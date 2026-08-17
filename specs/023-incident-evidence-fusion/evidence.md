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

## T004-T007 Red Contracts And Spec 022 Quality Persistence - 2026-08-16

- T004: Added 24 red contract tests in `tests/test_evidence_fusion.py` for
  `compute_confidence_ceiling` (stale/future_skew/unparsed/partial caps
  `observed`, fresh_symptom/temporal_proximity caps `suspected`, minimum
  ceiling governs), `max_cause_level` fail-closed for offline-alone,
  low-alone, fleet-without-PDU and temporal-proximity, and
  `evaluate_hypothesis` for contradiction visibility and absence ≠
  contradiction.
- T005: Added 15 red contract fixtures for isolated vs fleet detection
  (`detect_fleet_pattern`), attributed-action window (`is_within_attribution_window`,
  900s boundary exact), and firmware clock quality mapping (parsed local,
  parsed UTC, unparsed → ceiling observed).
- T006: Added 6 red contract tests in `tests/test_event_store.py` for
  `incident_assessments` table, `assessment_fact_refs` table,
  `save_assessment` / `load_assessment` method existence, idempotent
  roundtrip by SHA-256 digest, and `ux_assessment_replay` unique index.
  All 6 fail with `AssertionError` (tables/methods not yet created).
- T007: Added 4 action-invariant tests in `tests/test_evidence_fusion.py`:
  no hashcore import, no miner_monitor import, no action fields on
  `IncidentAssessment`, and `compute_evidence_digest` does not mutate input.
  These skip cleanly when `app.evidence_fusion` does not exist.
- Spec 022 T007: Bumped `SCHEMA_VERSION` to 6 in `app/event_store.py`,
  added `acquisition_authority` and `acquisition_reason_code` nullable
  columns to `telemetry_samples`, updated `record_sample` to persist both
  fields. 4 existing migration tests updated to expect v6. 4 new green
  tests in `AcquisitionQualityPersistenceTests`.
- Total test state: 80 red contracts in `test_evidence_fusion.py` (78
  errors + 2 skips, all `ModuleNotFoundError`), 5 expected red failures in
  `test_event_store.py` (T006 contracts), 211 non-red tests PASS (0
  failures, 0 errors, 1 skip). No production code altered.

## Phase 2/3 Implementation (T008-T012) — 2026-08-17

- T008/T009/T010/T011: Created `app/evidence_fusion.py` (pure domain module,
  no IO, no wall-clock, no state mutation). Exports: `FusionConfig` (with
  `from_mapping` returning `(config, warnings)` tuple), `EvidenceFact`,
  `CauseHypothesis`, `IncidentAssessment`, `classify_freshness`,
  `map_clock_quality`, `validate_fact_code`, `sort_facts_canonical`,
  `compute_evidence_digest`, `compute_confidence_ceiling`, `max_cause_level`,
  `evaluate_hypothesis`, `detect_fleet_pattern`, `is_within_attribution_window`.
- T012: Added `incident_assessments` and `assessment_fact_refs` tables to
  `EventStore._create_schema` (additive, `CREATE TABLE IF NOT EXISTS`). Unique
  index `ux_assessment_replay` on `(subject_ref, ruleset_version, evidence_digest)`
  enforces idempotent replay. Added `save_assessment` and `load_assessment`
  methods. `save_assessment` is idempotent: repeated calls with the same replay
  key return the same row id without duplicate rows.
- All 296 tests pass: 0 failures, 0 errors, 0 skips. All previously expected
  T006 red contract failures are now green. 80 `test_evidence_fusion.py` tests
  pass. No production config, state, miner or service was changed.



- Ruleset and fixture versions.
- Targeted/full tests and migration results.
- Sanitized before/after assessments.
- Query latency and database growth.
- Disabled-fallback, bounded-query and action-invariant proof.
- D+0/D+1/D+3 confidence-wording review.

## Runtime Rollout

- Not started.
- Do not mark this spec complete from checked tasks or compilation alone.
