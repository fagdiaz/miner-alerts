# Tasks: Adaptive Acquisition Resilience

**Input**: Design artifacts from `specs/022-adaptive-acquisition/`

**Risk**: HIGH

**Tests**: Test-first contracts and runtime evidence are required where behavior changes. `py_compile` alone is insufficient.

## Phase 1: Baseline And Red Contracts

- [ ] T001 Record sequential summary/stats order, five-second timeouts,
  sleep-after-tick cadence, per-miner request counts and tick latency percentiles.
- [ ] T002 [P] Add failing epoch completeness, late-result, missed-epoch and
  host-resume no-burst tests, including proof that authoritative outage checks
  do not back off beyond the current epoch.
- [ ] T003 [P] Add failing quality/provenance tests, including fleet transport
  failure versus individual timeout and partial summary/stats responses.
- [ ] T004 [P] Prove diagnostic evidence cannot alter state/action counters and
  both authoritative/diagnostic paths respect their numeric request budgets.
## Phase 2: Authoritative Acquisition

- [ ] T005 [US1] Implement epochs, envelopes and bounded executor in app/acquisition.py.
- [ ] T006 [US1] Integrate authoritative envelopes behind
  `adaptive_acquisition_enabled=false`; preserve and test the sequential fallback.
- [ ] T007 [US2] Persist and render explicit quality and age, and expose bounded
  PollHealth data for later metrics export.
## Phase 3: Diagnostic Probes

- [ ] T008 [US3] Add disabled-by-default bounded episode diagnostics.
- [ ] T009 [US3] Expose diagnostic data only to read-only context.
- [ ] T010 Add safe disabled defaults, two-worker cap, numeric request budgets,
  deadlines, no-retry policy and per-miner overlap guards.
## Phase 4: Validation And Rollout

- [ ] T011 Run targeted/full tests, compile, JSON and exact state/action,
  Telegram-offset, manual-command and startup/reboot invariant checks.
- [ ] T012 Compare 24-hour shadow latency/request/quality metrics with baseline
  and rehearse flag rollback with deterministic parity.
- [ ] T013 Activate in a controlled window and observe D+1/D+3.
- [ ] T014 Synchronize evidence, roadmap, calendar, diagnostics docs and development log.

## Dependencies And Execution Order

Spec 021 D+1 blocks implementation and D+3 blocks production activation.
Baseline metrics and provenance tests precede executor integration; the
disabled sequential fallback precedes any shadow run; diagnostics follow
authoritative stability; production follows shadow comparison and rollback
rehearsal.

## Definition Of Done

- [ ] All T001-T014 tasks are complete with evidence.
- [ ] Acceptance scenarios and negative paths pass.
- [ ] No real config, state, database, logs or secrets enter Git.
- [ ] Action-policy and polling-offset invariants pass when applicable.
- [ ] Runtime activation and observation are recorded; blocked checks remain open.
- [ ] Roadmap, delivery calendar, strategy docs and development log agree.
