# Tasks: Backup Retention And Restore

**Input**: Design artifacts from `specs/028-backup-retention-restore/`

**Risk**: HIGH

**Tests**: Test-first contracts and runtime evidence are required where behavior changes. `py_compile` alone is insufficient.

## Phase 1: Backup Contract And Red Tests

- [ ] T001 Record source schema/WAL mode, retention need and approved destination constraints.
- [ ] T002 [P] Add failing concurrent backup, partial-file and checksum tests.
- [ ] T003 [P] Add failing retention path-guard/non-overlap/free-space tests.
- [ ] T004 [P] Add failing staged restore, integrity and schema tests.
## Phase 2: Backup And Retention

- [ ] T005 [US1] Implement incremental SQLite backup and atomic promotion.
- [ ] T006 [US1] Implement versioned SHA-256 manifest and run report.
- [ ] T007 [US2] Implement 14/8/12 verified-generation retention with dry-run.
## Phase 3: Restore And Scheduling

- [ ] T008 [US3] Implement staging-only restore validation.
- [ ] T009 Install a pythonw.exe non-overlap scheduled backup task.
- [ ] T010 Document the separate manual disaster-replacement runbook without automating it.
## Phase 4: Validation And Rollout

- [ ] T011 Run targeted/full tests, compile, PowerShell parse and path/secret audits.
- [ ] T012 Execute one production backup and staging restore drill.
- [ ] T013 Observe next scheduled run, disk/free-space and monitor latency.
- [ ] T014 Synchronize evidence, roadmap, calendar, runbook, strategy docs and development log.

## Dependencies And Execution Order

Stable schema and approved destination precede implementation. Backup promotion tests precede retention. A verified backup precedes restore. The staging restore drill is the production closeout gate.

## Definition Of Done

- [ ] All T001-T014 tasks are complete with evidence.
- [ ] Acceptance scenarios and negative paths pass.
- [ ] No real config, state, database, logs or secrets enter Git.
- [ ] Action-policy and polling-offset invariants pass when applicable.
- [ ] Runtime activation and observation are recorded; blocked checks remain open.
- [ ] Roadmap, delivery calendar, strategy docs and development log agree.
