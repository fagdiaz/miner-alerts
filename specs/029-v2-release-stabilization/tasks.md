# Tasks: V2 Release Stabilization

**Input**: Design artifacts from `specs/029-v2-release-stabilization/`

**Risk**: HIGH

**Tests**: Test-first contracts and runtime evidence are required where behavior changes. `py_compile` alone is insufficient.

## Phase 1: Freeze And Evidence Inventory

- [ ] T001 Audit Specs 021-028 and reject freeze until each has exactly one evidenced terminal disposition.
- [ ] T002 Freeze Git/clean-tree, deterministic runtime-payload, Python/dependencies, schema, config-example and SCM/task identities.
- [ ] T003 Materialize R001-R025 with expected result, applicability, owner and evidence source; missing mandatory evidence is blocked.
- [ ] T004 Record prior known-good runtime, venv, service, task and SCM recovery identities without copying real config/state/data.
- [ ] T005 [P] Add failing manifest/digest, terminal-disposition, matrix-completeness and clock-reset tests.
## Phase 2: Automated And QA Regression

- [ ] T006 Implement or finalize a read-only release audit that emits the sanitized manifest/matrix and never executes actions.
- [ ] T007 Run R001-R004 full tests, compile, JSON, PowerShell, dependency and conditional Docker/OpenAPI checks.
- [ ] T008 Run R005-R007 and R010-R013 state, startup, action, episode, incident, mutex and polling invariants.
- [ ] T009 Run R008-R009 Telegram commands/delivery/no-silence and QA blocked-action matrix.
- [ ] T010 Run R014-R021 liveness, acquisition, evidence, electrical, metrics, Hashcore, backup and interface checks/dispositions.
## Phase 3: Recovery And Production Activation

- [ ] T011 Create the release-candidate online backup and complete R020 staging restore.
- [ ] T012 Rehearse runtime/service rollback selection without replacing live SQLite/state or weakening safety gates.
- [ ] T013 Perform one controlled service activation and prove R022 process/runtime identity.
- [ ] T014 Execute read-only smoke, controlled episode/incident checks and R023 auxiliary outage isolation.
- [ ] T015 Open, classify and contain any P0/P1 blocker before observation continues.
## Phase 4: Soak And Documentation

- [ ] T016 Capture daily observations 1-3 and close R024 only at or after 72 continuous hours on one runtime payload.
- [ ] T017 Capture daily observations 4-7 and close R025 only at or after 168 continuous hours with no evidence gap/open P0/P1.
- [ ] T018 Run three documentation sweeps and synchronize all canonical docs/spec statuses.
- [ ] T019 Run Git secret/runtime artifact, ignored-file, link/status and conditional-file hygiene audits.
- [ ] T020 Generate the complete evidence manifest and explicit approve/block decision; update development log without overriding missing evidence.

## Requirement Coverage

| Requirement | Tasks |
| --- | --- |
| FR-001 | T001-T006, T015, T020 |
| FR-002 | T001, T003, T010, T018, T020 |
| FR-003 | T002, T005-T007 |
| FR-004 | T003, T008, T013-T014 |
| FR-005 | T008-T009, T014 |
| FR-006 | T003, T010, T014 |
| FR-007 | T011 |
| FR-008 | T004, T012-T013 |
| FR-009 | T015-T017, T020 |
| FR-010 | T018-T020 |
| FR-011 | T001, T003, T010, T018, T020 |
| FR-012 | T002, T005-T006 |
| FR-013 | T001, T003, T010, T018, T020 |
| FR-014 | T003, T005-T010, T020 |
| FR-015 | T005, T015-T017, T020 |
| FR-016 | T005-T006, T016-T017 |
| FR-017 | T002, T005-T006, T013, T016-T017 |
| FR-018 | T004, T011-T012 |
| FR-019 | T003, T005-T006, T016-T020 |
| SC-001 | T003, T007-T014 |
| SC-002 | T015-T017, T020 |
| SC-003 | T011 |
| SC-004 | T008-T009, T013-T014, T016 |
| SC-005 | T018-T020 |
| SC-006 | T003, T005-T010, T020 |
| SC-007 | T016-T017, T020 |
| SC-008 | T005-T006, T016-T017 |
| SC-009 | T004, T012 |

## Dependencies And Execution Order

All Specs 021-028 require accepted, blocked_external, no_build or deferred
evidence before T002 freeze. T005 red contracts precede T006. Static/QA rows
precede backup/activation; restore and rollback rehearsal precede activation.
The hour-72 checkpoint is inside, not additional to, the continuous 168-hour
review. Any runtime/config/schema/service change resets affected checks and
observation; docs-only changes preserve time only under the same payload digest.

## Definition Of Done

- [ ] All T001-T020 tasks are complete with evidence.
- [ ] Acceptance scenarios and negative paths pass.
- [ ] No real config, state, database, logs or secrets enter Git.
- [ ] Action-policy and polling-offset invariants pass when applicable.
- [ ] Runtime activation and observation are recorded; blocked checks remain open.
- [ ] Roadmap, delivery calendar, strategy docs and development log agree.
