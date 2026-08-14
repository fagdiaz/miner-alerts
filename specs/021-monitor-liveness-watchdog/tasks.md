# Tasks: Monitor Liveness Watchdog

**Input**: Design artifacts from `specs/021-monitor-liveness-watchdog/`

**Risk**: HIGH

**Tests**: Test-first contracts and runtime evidence are required where behavior changes. `py_compile` alone is insufficient.

## Phase 1: Baseline And Red Contracts

- [x] T001 Record current service, mutex, worker and startup behavior in evidence.md.
- [x] T002 [P] Add failing heartbeat atomicity/schema/clock tests in tests/test_monitor_liveness.py.
- [x] T003 [P] Add failing watchdog classification/dedupe/maintenance tests.
- [x] T004 Capture current SCM failure actions without modifying them.
## Phase 2: Heartbeat And Assessment

- [x] T005 [US1] Implement heartbeat and assessment types in app/liveness.py.
- [x] T006 [US1] Integrate one best-effort atomic heartbeat in app/miner_monitor.py.
- [x] T007 [US3] Add sanitized health rendering and safe config defaults.
## Phase 3: Independent Watchdog

- [x] T008 [US1] Implement tools/monitor_watchdog.py without action imports.
- [x] T009 [US2] Implement tools/install_watchdog_task.ps1 with pythonw.exe and non-overlap.
- [x] T010 [US2] Configure and test SCM recovery with rollback export.
## Phase 4: Validation And Rollout

- [x] T011 Run targeted/full tests, compile, PowerShell parse, config parse and invariant scan.
- [x] T012 Execute QA kill, hang and stale-worker scenarios and prove no Hashcore calls.
- [ ] T013 Perform controlled activation and D+1/D+3 observation with the
  read-only observation gate; D+0 is complete and hidden one-shot captures are
  scheduled for the real D+1/D+3 windows.
- [x] T014 Update evidence, roadmap, delivery calendar, runbook and development log.

## Dependencies And Execution Order

Spec 020 T020 blocks all work. Pure model/tests precede monitor integration; watchdog classification precedes installation; production activation follows QA kill/hang proof.

## Requirements Traceability

| Requirement | Tasks |
| --- | --- |
| FR-001 | T002, T005, T006, T011 |
| FR-002 | T002, T005-T007 |
| FR-003 | T003, T005, T008, T012 |
| FR-004 | T003, T008, T012 |
| FR-005 | T003, T005, T008, T012 |
| FR-006 | T004, T009, T010, T013 |
| FR-007 | T001, T010, T012, T013 |
| FR-008 | T003, T005, T008, T012 |
| FR-009 | T002, T003, T005, T012 |
| FR-010 | T002, T006, T007, T011 |
| SC-001 | T003, T008, T012, T013 |
| SC-002 | T010, T012, T013 |
| SC-003 | T003, T008, T012 |
| SC-004 | T003, T007, T008, T012 |
| SC-005 | T002, T003, T008, T012 |

## Definition Of Done

- [ ] All T001-T014 tasks are complete with evidence.
- [ ] Acceptance scenarios and negative paths pass.
- [ ] No real config, state, database, logs or secrets enter Git.
- [ ] Action-policy and polling-offset invariants pass when applicable.
- [ ] Runtime activation and observation are recorded; blocked checks remain open.
- [ ] Roadmap, delivery calendar, strategy docs and development log agree.
