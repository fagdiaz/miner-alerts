# Tasks: Incident Evidence Fusion

**Input**: Design artifacts from `specs/023-incident-evidence-fusion/`

**Risk**: MEDIUM

**Tests**: Test-first contracts and runtime evidence are required where behavior changes. `py_compile` alone is insufficient.

## Phase 1: Evidence Inventory And Red Contracts

- [ ] T001 Map existing tables, analyzers and source codes.
- [ ] T002 [P] Add failing normalization and confidence-ceiling tests.
- [ ] T003 [P] Add isolated, fleet and clock-uncertain replay fixtures.
- [ ] T004 [P] Add schema migration and round-trip tests.
## Phase 2: Fusion Domain

- [ ] T005 [US1] Implement facts, assessments and bounded rules in app/evidence_fusion.py.
- [ ] T006 [US2] Implement baseline eligibility and contradiction rules.
- [ ] T007 [US3] Implement fleet correlation without electrical causality.
## Phase 3: Persistence And Interfaces

- [ ] T008 Add assessment persistence and queries in app/event_store.py.
- [ ] T009 Integrate the shared renderer into Telegram detail and dashboard.
- [ ] T010 Add safe freshness/window defaults to example config.
## Phase 4: Validation And Rollout

- [ ] T011 Run replay, tests, migration, compile and action-invariant checks.
- [ ] T012 Review false correlations against known incidents.
- [ ] T013 Activate read-only paths and observe D+1/D+3.
- [ ] T014 Synchronize evidence, roadmap, calendar, diagnostics docs and development log.

## Dependencies And Execution Order

Spec 022 quality contract blocks fact normalization. Replay and migration tests precede implementation; persistence precedes interfaces; production exposure follows conservative-causality review.

## Definition Of Done

- [ ] All T001-T014 tasks are complete with evidence.
- [ ] Acceptance scenarios and negative paths pass.
- [ ] No real config, state, database, logs or secrets enter Git.
- [ ] Action-policy and polling-offset invariants pass when applicable.
- [ ] Runtime activation and observation are recorded; blocked checks remain open.
- [ ] Roadmap, delivery calendar, strategy docs and development log agree.
