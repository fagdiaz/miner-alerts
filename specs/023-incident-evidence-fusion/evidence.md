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

## Renderer And Config Defaults (T013, T016) — 2026-08-17

- T013: Implemented `render_assessment_text` and `render_assessment_telegram`
  in `app/evidence_fusion.py` enforcing the 6-section order defined in
  `contracts/incident-assessment.md` (header, observed facts, hypotheses,
  contradictions, missing evidence, read-only footer `[LECTURA / SIN ACCION AUTOMATICA]`).
  Added 2 unit tests in `TestSharedSemanticRenderer` verifying section order,
  formatting, and character-bounded splitting for Telegram messages.
- T016: Added disabled-by-default keys (`incident_fusion_enabled: false`,
  `incident_fusion_context_hours: 24`, `incident_fusion_fleet_window_seconds: 60`)
  to `app/config.example.json`.
- All 298 tests pass: 0 failures, 0 errors, 0 skips.


## Diagnose Adapter (T014) — 2026-08-26

- T014: Implemented the feature-flagged assessment adapter behind `/diagnose`
  in `app/miner_monitor.py` (lines ~2182-2360 post-import shift).
- Module-level imports added to both `try` and `except ImportError` branches:
  `FusionConfig`, `IncidentAssessment`, `RULESET_VERSION as _FUSION_RULESET_VERSION`,
  `compute_evidence_digest as _compute_evidence_digest`,
  `render_assessment_telegram as _render_assessment_telegram`.
- Adapter logic:
  * Reads `incident_fusion_enabled` via `FusionConfig.from_mapping(config)` (default `False`).
  * When enabled + EventStore available: builds a structurally-valid `IncidentAssessment`
    with empty fact/hypothesis sets (full evidence wiring deferred to T015+), persists it
    via `save_assessment` (idempotent, errors swallowed), measures elapsed time.
  * If elapsed ≥ 2.0 s → budget exceeded → strict fallback.
  * On any exception in the fusion block → strict fallback.
  * Fallback unconditionally calls `build_miner_diagnosis_text` and sends legacy text.
  * When fusion succeeds, calls `render_assessment_telegram` and sends each part.
- State-machine invariant (FR-008 / SC-006): The adapter block is a pure read path.
  It does not write to any state variable, does not change cooldowns, streaks, reboot
  eligibility, or polling timers.  Verified by code inspection: no assignment to
  `miner_states`, `reboot_*`, `streak`, `poll_*` or `timer_*` within the adapter.
- Unit tests: 8 new tests in `tests/test_t014_diagnose_adapter.py`:
  * `TestDiagnoseAdapterDisabled` (2): disabled flag → legacy, save_assessment not called.
  * `TestDiagnoseAdapterEnabled` (3): enabled → fusion header present, read-only footer,
    save_assessment called once.
  * `TestDiagnoseAdapterFallbackOnException` (2): hard fusion exception → legacy;
    save_assessment exception swallowed, fusion text still sent.
  * `TestAssessmentActionInvariant` (1): `IncidentAssessment` has none of the 5 forbidden
    action fields (SC-006).
- Validation commands:
  * `py_compile app\miner_monitor.py` → exit 0 (SYNTAX OK)
  * Full suite: 313/313 tests PASS (failures=0, errors=0, skips=0).
    Previous baseline was 305; 8 new T014 tests added.

## Dashboard Integration (T015) — 2026-08-26

- T015: Integrated incident assessments into `tools/operations_dashboard.py`.
- Changes:
  * `"incident_assessments"` added to `_KNOWN_TABLES` allowlist (line 27+).
  * New `_latest_assessments(connection, *, since_ts, limit)` function: bounded read-only
    query on `incident_assessments` filtered by `assessment_now_ts >= since_ts`, ordered
    newest-first, limited to `min(safe_limit, 50)` rows. No scoring or inference.
  * `build_dashboard_data` now calls `_latest_assessments` and adds both
    `summary["assessments"]` (count) and `"incident_assessments"` (row list) to its
    return dict.
  * New `_render_assessment_rows(assessments)` function: pure display of stored fields
    (`assessment_now_ts`, `subject_ref`, `subject_type`, `status`, `ruleset_version`,
    `evidence_digest[:16]`). No hypothesis re-computation (FR-011).
  * `render_dashboard_html` now renders a new section "Evaluaciones de incidente" with
    the eyebrow "Lectura / sin accion automatica" using `_render_assessment_rows`.
- FR-011 invariant: `operations_dashboard.py` does NOT import or call any scoring
  functions from `evidence_fusion` (`evaluate_hypothesis`, `compute_confidence_ceiling`,
  `max_cause_level`, `detect_fleet_pattern`, `IncidentAssessment(…)`). Verified by
  source-text test `test_fr011_no_scoring_imports_in_render_path`.
- Unit tests: 10 new tests in `tests/test_operations_dashboard.py`
  (`IncidentAssessmentsDashboardTests`):
  * Data layer (5): key present, count in summary, bounded by since_ts, newest-first
    ordering, empty list when no assessments.
  * HTML rendering (3): section header present, stored fields rendered, empty-state
    graceful message.
  * Invariants (2): FR-011 no-scoring check, `_KNOWN_TABLES` allowlist check.
- Validation commands:
  * `py_compile tools\operations_dashboard.py` → exit 0 (SYNTAX OK)
  * Full suite: 323/323 tests PASS (failures=0, errors=0, skips=0).
    Previous baseline was 313; 10 new T015 tests added.



## Deterministic Validation (T017) — 2026-08-26

- T017: Implemented formal deterministic validation for SC-001 through SC-004 in `tests/test_t017_deterministic_validation.py`.
- Criteria proven:
  * SC-001 (Determinism & Replay Equality): Verified `compute_evidence_digest` produces identical SHA-256 digests across 25 random permutations of synthetic fact collections; internal row IDs and ingested timestamps do not alter the semantic digest; canonical sorting stably breaks ties; repeated calls to `render_assessment_text` and `render_assessment_telegram` produce bit-for-bit identical output.
  * SC-002 (Timing-Only Non-Confirmation): Verified `compute_confidence_ceiling(['temporal_proximity_only'])` caps at `suspected`; `max_cause_level` for all candidate causes with temporal proximity returns at most `suspected` (never `confirmed`); raw symptoms (`signal.current_offline`, `signal.current_low`) cannot confirm root causes; stale or clock-skewed evidence drops ceiling to `observed`.
  * SC-003 (Contradiction Visibility & Missing Evidence): Verified that decisive contradictions (`action.no_successful_action_in_window`) drop hypothesis confidence from `confirmed` to `suspected` and appear in `assessment.contradictions`; missing requirements appear in `assessment.missing_evidence`; both sections are explicitly rendered in text output under `[CONTRADICCIONES]` and `[EVIDENCIA FALTANTE O DESACTUALIZADA]`; absence is categorized as missing rather than contradiction; incomplete status always displays safety footer `[LECTURA / SIN ACCION AUTOMATICA]`.
  * SC-004 (Fleet Non-Causality & Action Invariance): Verified `detect_fleet_pattern` flags `fleet.concurrent_degradation` for concurrent miners within 60s window; fleet pattern alone never confirms `power.electrical_fault` without external PDU evidence (`max_cause_level` returns `suspected`); `IncidentAssessment` dataclass has 0 forbidden action fields (`allow_reboot`, `trigger_reboot`, `hashcore_command`, `external_cli_command`, `auto_action`, `reboot_eligible`); pure functions do not mutate input argument collections.
- Validation:
  * `py_compile tests\test_t017_deterministic_validation.py` → exit 0 (SYNTAX OK)
  * Test execution: 17/17 tests in `tests/test_t017_deterministic_validation.py` PASS in 0.002s.
## Performance, Bounded Queries And Growth Validation (T018) — 2026-08-26

- T018: Implemented benchmarks and performance tests in `tests/test_t018_performance_and_growth.py` validating SC-005, SC-006 and SC-007.
- Results:
  * SC-005 (Latency < 2.0s & Bounded Queries): Populated 24-hour fleet dataset (2,880 telemetry rows across 4 miners + 50 operational events + 50 reboot decisions + 50 firmware events + collector run). 24-hour context retrieval and dashboard assessment took 0.08s (far below the 2.0s ceiling). Query count strictly bounded at 6 SQL queries (FR-014 satisfied, zero $O(N)$ per-row queries).
  * SC-007 (Idempotent Save & Growth Bound): 50 repeated saves of identical `(subject_ref, ruleset_version, evidence_digest)` produced exactly 1 persisted row in `incident_assessments` (no duplicate rows, DB size remained bounded within single page tolerance).
  * SC-006 (Action Invariance): Confirmed 0 action fields in `IncidentAssessment` dataclass (`allow_reboot`, `trigger_reboot`, `hashcore_command`, `auto_action`, `reboot_eligible`); confirmed `incident_fusion_enabled` defaults to `False`; verified `app.evidence_fusion` has zero imports of `reboot_safety`, `hashcore` or `miner_monitor`.
- Validation:
  * `py_compile tests\test_t018_performance_and_growth.py` → exit 0 (SYNTAX OK)
  * Test execution: 4/4 tests in `tests/test_t018_performance_and_growth.py` PASS in 0.313s.
  * Full suite: 344/344 tests PASS (failures=0, errors=0, skips=0). Baseline 340 + 4 new T018 tests.

- Ruleset and fixture versions.
- Targeted/full tests and migration results.
- Sanitized before/after assessments.
- Query latency and database growth.
- Disabled-fallback, bounded-query and action-invariant proof.
- D+0/D+1/D+3 confidence-wording review.

## Runtime Rollout

- Not started.
- Do not mark this spec complete from checked tasks or compilation alone.
