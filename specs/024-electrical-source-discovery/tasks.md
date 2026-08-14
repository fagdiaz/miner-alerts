# Tasks: Electrical Source Discovery

**Input**: Design artifacts from `specs/024-electrical-source-discovery/`

**Risk**: MEDIUM

**Tests**: Test-first contracts and runtime evidence are required where behavior changes. `py_compile` alone is insufficient.

## Phase 1: Discovery Gate

- [ ] T001 Inventory actual PSU, PDU, UPS, meter and breaker capabilities.
- [ ] T002 Document model, firmware, protocol, units, update rate and authentication.
- [ ] T003 Capture sanitized read-only evidence or record the missing hardware dependency.
- [ ] T004 Decide supported, unsupported or blocked before adding a dependency.
## Phase 2: Conditional Red Contracts

- [ ] T005 [P] Add sample normalization, units, stale and timeout tests if a source is approved.
- [ ] T006 [P] Add a static no-write operation contract.
- [ ] T007 [P] Add additive EventStore migration tests if persistence is approved.
## Phase 3: Conditional Adapter

- [ ] T008 [US2] Implement one source-specific bounded read-only adapter.
- [ ] T009 [US2] Persist normalized measurements and collection health.
- [ ] T010 [US3] Map measurements to advisory evidence-fusion facts.
## Phase 4: Validation And Closeout

- [ ] T011 Run tests, compile, config parse, no-write and action-invariant checks.
- [ ] T012 Run 72-hour shadow collection or document blocked status.
- [ ] T013 Review clock, units, data gaps and false correlation.
- [ ] T014 Synchronize evidence, roadmap, calendar, strategies, runbook and development log.

## Requirement Coverage

| Requirement | Tasks |
| --- | --- |
| FR-001 | T001-T004 |
| FR-002 | T002, T005, T011, T013 |
| FR-003 | T003, T004, T012 |
| FR-004 | T006, T008, T011 |
| FR-005 | T001, T002, T004 |
| FR-006 | T005, T008, T009 |
| FR-007 | T005, T009, T013 |
| FR-008 | T006, T010, T011 |
| FR-009 | T002, T003, T011 |
| FR-010 | T002, T005, T008, T012 |
| SC-001 | T001-T004, T012 |
| SC-002 | T002, T005, T011 |
| SC-003 | T005, T009, T011-T013 |
| SC-004 | T006, T008, T010, T011 |
| SC-005 | T005, T009, T012, T013 |

## Dependencies And Execution Order

Physical discovery is the hard gate. Adapter, dependency and schema tasks do not start if no trustworthy source is proven. Correlation follows valid shadow samples only.

## Definition Of Done

- [ ] All T001-T014 tasks are complete with evidence.
- [ ] Acceptance scenarios and negative paths pass.
- [ ] No real config, state, database, logs or secrets enter Git.
- [ ] Action-policy and polling-offset invariants pass when applicable.
- [ ] Runtime activation and observation are recorded; blocked checks remain open.
- [ ] Roadmap, delivery calendar, strategy docs and development log agree.
