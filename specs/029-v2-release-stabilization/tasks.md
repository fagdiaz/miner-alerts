# Tasks: V2 Release Stabilization

**Input**: Design artifacts from `specs/029-v2-release-stabilization/`

**Risk**: HIGH

**Tests**: Test-first contracts and runtime evidence are required where behavior changes. `py_compile` alone is insufficient.

## Phase 1: Freeze And Evidence Inventory

- [ ] T001 Freeze candidate identity, dependency versions, schema and config-example hash.
- [ ] T002 Audit Specs 021-028 statuses, tasks, evidence and observation gates.
- [ ] T003 Build the cross-feature regression matrix and mark missing evidence blocked.
- [ ] T004 Record prior known-good rollback/service identities.
## Phase 2: Automated And QA Regression

- [ ] T005 Run full tests, compile, JSON, PowerShell, Docker/OpenAPI checks where applicable.
- [ ] T006 Run state, action, startup, cooldown, mutex and polling-offset invariants.
- [ ] T007 Run Telegram commands/delivery/no-silence and QA blocked-action matrix.
- [ ] T008 Run liveness, acquisition, evidence, metrics and auxiliary outage isolation checks.
## Phase 3: Recovery And Production Activation

- [ ] T009 Create a release-candidate backup and complete staging restore.
- [ ] T010 Perform one controlled service activation and prove process/runtime identity.
- [ ] T011 Execute read-only smoke and controlled incident/episode checks.
- [ ] T012 Open and contain any P0/P1 blocker before continuing.
## Phase 4: Soak And Documentation

- [ ] T013 Complete 72-hour soak with daily review.
- [ ] T014 Complete final seven-day reliability review.
- [ ] T015 Run three documentation sweeps and synchronize all canonical docs/spec statuses.
- [ ] T016 Run Git secret/runtime artifact and ignored-file hygiene audit.
- [ ] T017 Record explicit release approve/block decision and update development log.

## Dependencies And Execution Order

All accepted or evidence-closed Specs 021, 022, 023, 024, 025, 026, 027 and 028 precede freeze. Any code fix resets affected checks and observation. Restore precedes production approval; 72-hour and seven-day gates precede release closure.

## Definition Of Done

- [ ] All T001-T017 tasks are complete with evidence.
- [ ] Acceptance scenarios and negative paths pass.
- [ ] No real config, state, database, logs or secrets enter Git.
- [ ] Action-policy and polling-offset invariants pass when applicable.
- [ ] Runtime activation and observation are recorded; blocked checks remain open.
- [ ] Roadmap, delivery calendar, strategy docs and development log agree.
