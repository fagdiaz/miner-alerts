# Tasks: Incident Evidence Fusion

**Input**: Design artifacts from `specs/023-incident-evidence-fusion/`

**Risk**: MEDIUM

**Tests**: Test-first contracts and runtime evidence are required. Compilation
alone is insufficient.

## Phase 1: Inventory And Red Contracts

- [x] T001 Map every current EventStore source/query and analyzer to
  `integration-map.md`; confirm Spec 022 quality persistence is available.
- [x] T002 [P] Add failing configuration/disabled-fallback tests for FR-013 in
  `tests/test_evidence_fusion.py`.
- [x] T003 [P] Add failing normalization, freshness, clock-skew, unknown-code,
  canonical ordering and digest tests for FR-001, FR-002, FR-010, FR-012 and
  FR-015.
- [ ] T004 [P] Add failing confidence-ceiling, timing-only, contradiction,
  collector-partial and electrical-non-causality tests for FR-003-FR-006.
- [ ] T005 [P] Add isolated, fleet, attributed-action, firmware-direct,
  stale-source and clock-uncertain replay fixtures for FR-006 and FR-007.
- [ ] T006 [P] Add failing additive migration, indexed bounded-query,
  round-trip and idempotent-save tests for FR-009, FR-014 and SC-007 in
  `tests/test_event_store.py`.
- [ ] T007 [P] Add action-invariant regression tests proving assessments cannot
  change state, streaks, decisions, notifications or Hashcore calls for FR-008
  and SC-006.

## Phase 2: Pure Fusion Domain

- [ ] T008 [US1] Implement immutable fact, hypothesis and assessment values in
  `app/evidence_fusion.py` without IO or implicit wall-clock access.
- [ ] T009 [US1] Implement recognized-source normalization, freshness,
  canonical serialization and `evidence_digest` for FR-001, FR-002, FR-010,
  FR-012 and FR-015.
- [ ] T010 [US2] Implement stable ordered hypothesis rules, ceilings,
  contradictions and missing evidence from `contracts/evidence-rules.md` for
  FR-003-FR-005.
- [ ] T011 [US3] Reuse existing baseline/quality/restart analyzers and implement
  bounded fleet correlation without electrical causality for FR-006-FR-008.

## Phase 3: Persistence And Shared Interfaces

- [ ] T012 Add EventStore schema migration, source queries, assessment
  save/load and fact references with required indexes and idempotency for
  FR-009 and FR-014.
- [ ] T013 Implement one semantic renderer and bounded Telegram/dashboard
  projections for FR-005 and FR-011.
- [ ] T014 Integrate the feature-flagged assessment adapter behind `/diagnose`,
  preserving `build_miner_diagnosis_text` as disabled/unavailable/over-budget
  fallback for FR-008, FR-011 and FR-013.
- [ ] T015 Integrate the same persisted/shared renderer into
  `tools/operations_dashboard.py` without a second scoring path for FR-011.
- [ ] T016 Add and validate the exact disabled-by-default keys from
  `contracts/config.md` in `app/config.example.json` and runtime parsing for
  FR-013.

## Phase 4: Deterministic And Runtime Validation

- [ ] T017 Prove fixture determinism, timing-only non-confirmation, contradiction
  visibility, fleet non-causality and replay equality for SC-001-SC-004.
- [ ] T018 Measure bounded query count, 24-hour latency under two seconds and
  database growth; run targeted/full tests, migration checks, `py_compile` and
  core/action invariant comparisons for SC-005-SC-007.
- [ ] T019 Activate only the read-only paths in a controlled window after Spec
  022 exit, capture D+0/D+1/D+3 wording/failure/performance evidence and disable
  on any unsupported confirmed claim.
- [ ] T020 Synchronize `evidence.md`, roadmap, delivery calendar, diagnostics
  docs and newest-first development log; leave blocked checks open.

## Requirement Coverage

| Requirement | Tasks |
| --- | --- |
| FR-001 | T003, T009 |
| FR-002 | T003, T009 |
| FR-003 | T004, T010, T017 |
| FR-004 | T004, T010, T017 |
| FR-005 | T004, T010, T013, T017 |
| FR-006 | T004, T005, T011, T017 |
| FR-007 | T005, T011 |
| FR-008 | T007, T011, T014, T018 |
| FR-009 | T006, T012 |
| FR-010 | T003, T009 |
| FR-011 | T013-T015 |
| FR-012 | T003, T008, T009, T017 |
| FR-013 | T002, T014, T016, T019 |
| FR-014 | T006, T012, T018 |
| FR-015 | T003, T009, T010 |
| SC-001 | T003, T005, T017 |
| SC-002 | T004, T017 |
| SC-003 | T003-T005, T013, T017 |
| SC-004 | T005, T007, T011, T017 |
| SC-005 | T006, T012, T018 |
| SC-006 | T007, T014, T018 |
| SC-007 | T006, T012, T018 |

## Dependencies And Execution Order

Spec 021 D+1 blocks implementation start and D+3 blocks Spec 022 production
activation. Spec 022 quality contract and persisted evidence block T008 onward.
Red contracts T002-T007 precede implementation. Pure rules precede persistence;
persistence and shared renderer precede interfaces; production exposure follows
the conservative-causality and action-invariant gates.

## Definition Of Done

- [ ] All T001-T020 tasks are complete with evidence.
- [ ] Every FR/SC mapping above passes or remains explicitly blocked.
- [ ] Acceptance scenarios and negative paths pass deterministically.
- [ ] No real config, state, database, logs, addresses or secrets enter Git.
- [ ] State/action, polling-offset and Telegram-delivery invariants pass.
- [ ] D+0/D+1/D+3 evidence has no unsupported confirmed cause or open P0/P1.
- [ ] Roadmap, delivery calendar, strategy docs and development log agree.
