# Tasks: Adaptive Acquisition Resilience

**Input**: Design artifacts from `specs/022-adaptive-acquisition/`

**Risk**: HIGH

**Tests**: Test-first contracts and runtime evidence are required where behavior changes. `py_compile` alone is insufficient.

## Phase 1: Baseline And Red Contracts

- [ ] T001 Record request order, timeouts, tick duration and counts.
- [ ] T002 [P] Add failing epoch completeness and late-result tests.
- [ ] T003 [P] Add failing quality and provenance tests.
- [ ] T004 [P] Prove diagnostic evidence cannot alter state/action counters.
## Phase 2: Authoritative Acquisition

- [ ] T005 [US1] Implement epochs, envelopes and bounded executor in app/acquisition.py.
- [ ] T006 [US1] Integrate authoritative envelopes at the current evaluation boundary.
- [ ] T007 [US2] Persist and render explicit quality and age.
## Phase 3: Diagnostic Probes

- [ ] T008 [US3] Add disabled-by-default bounded episode diagnostics.
- [ ] T009 [US3] Expose diagnostic data only to read-only context.
- [ ] T010 Add safe config defaults, request budgets and overlap guards.
## Phase 4: Validation And Rollout

- [ ] T011 Run targeted/full tests, compile, JSON and core invariant checks.
- [ ] T012 Compare 24-hour shadow metrics with baseline.
- [ ] T013 Activate in a controlled window and observe D+1/D+3.
- [ ] T014 Synchronize evidence, roadmap, calendar, diagnostics docs and development log.

## Dependencies And Execution Order

Spec 021 D+1 blocks rollout. Baseline metrics and provenance tests precede executor integration; diagnostics follow authoritative stability; production follows shadow comparison.

## Definition Of Done

- [ ] All T001-T014 tasks are complete with evidence.
- [ ] Acceptance scenarios and negative paths pass.
- [ ] No real config, state, database, logs or secrets enter Git.
- [ ] Action-policy and polling-offset invariants pass when applicable.
- [ ] Runtime activation and observation are recorded; blocked checks remain open.
- [ ] Roadmap, delivery calendar, strategy docs and development log agree.
