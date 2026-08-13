# Tasks: Hashcore Capability Inventory

**Input**: Design artifacts from `specs/026-hashcore-capability-inventory/`

**Risk**: MEDIUM

**Tests**: Test-first contracts and runtime evidence are required where behavior changes. `py_compile` alone is insufficient.

## Phase 1: Safety Baseline

- [ ] T001 Record current reboot/restart templates and action-call invariant.
- [ ] T002 Identify vendor-proven help/version invocations without executing unknown commands.
- [ ] T003 [P] Add failing classification, timeout, no-window and sanitization tests.
- [ ] T004 [P] Add raw-output ignore patterns and committed-artifact secret scan.
## Phase 2: Inventory Tool

- [ ] T005 [US1] Implement bounded standalone tools/hashcore_inventory.py.
- [ ] T006 [US2] Implement conservative risk classification with unknown prohibited.
- [ ] T007 Generate versioned sanitized JSON and Markdown artifacts.
## Phase 3: Capability Assessment

- [ ] T008 [US3] Compare read-only commands with API 4028/Vnish/current diagnostics.
- [ ] T009 Rank only unique read-only gaps by value, reliability and implementation cost.
- [ ] T010 Record separate-spec prerequisites for every accepted candidate.
## Phase 4: Validation And Closeout

- [ ] T011 Run targeted/full tests, compile, timeout and secret scans.
- [ ] T012 Execute approved discovery locally and review every artifact.
- [ ] T013 Prove existing action scope and templates unchanged.
- [ ] T014 Synchronize evidence, roadmap, calendar, Hashcore strategy and development log.

## Dependencies And Execution Order

Safety baseline and vendor-proven invocation allowlist precede execution. Sanitization precedes committed artifacts. Candidate ranking follows complete classification and cannot expand actions.

## Definition Of Done

- [ ] All T001-T014 tasks are complete with evidence.
- [ ] Acceptance scenarios and negative paths pass.
- [ ] No real config, state, database, logs or secrets enter Git.
- [ ] Action-policy and polling-offset invariants pass when applicable.
- [ ] Runtime activation and observation are recorded; blocked checks remain open.
- [ ] Roadmap, delivery calendar, strategy docs and development log agree.
