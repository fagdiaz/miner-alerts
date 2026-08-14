# Tasks: Hashcore Capability Inventory

**Input**: Design artifacts from `specs/026-hashcore-capability-inventory/`

**Risk**: MEDIUM

**Tests**: Test-first contracts and runtime evidence are required where behavior changes. `py_compile` alone is insufficient.

## Phase 1: Safety Baseline

- [ ] T001 Record hashes of the current `app/miner_monitor.py` action seams and sanitized shapes/counts of the reboot/restart templates without storing local values.
- [ ] T002 Reproduce the static installation baseline in metadata-only mode and prove zero subprocess, miner IO and settings reads.
- [ ] T003 Identify vendor-proven help/version invocations; if none exist, preserve the empty allowlist and explicit `blocked` result.
- [ ] T004 [P] Add failing tests for metadata-only, absent/mismatched allowlist, invalid argv, changed fingerprint and zero-process rejection.
- [ ] T005 [P] Add failing classification, timeout, no-window, disabled-stdin, bounded-stream and sanitization tests.
- [ ] T006 [P] Add raw-output ignore patterns and committed-artifact path/address/secret scans.
## Phase 2: Inventory Tool

- [ ] T007 [US1] Implement standalone `tools/hashcore_inventory.py` with metadata-only as the default and no monitor imports.
- [ ] T008 [US1] Implement exact fingerprint-bound allowlist validation before any process creation.
- [ ] T009 [US1] Implement fixed argv execution with `shell=False`, no-window, stdin disabled, 10-second timeout, one attempt and 64 KiB per-stream bounds.
- [ ] T010 [US2] Implement conservative risk classification with unknown prohibited and one classification per command.
- [ ] T011 Generate deterministic versioned sanitized JSON and Markdown artifacts through temporary-file validation and atomic promotion.
## Phase 3: Capability Assessment

- [ ] T012 [US3] Compare evidenced read-only commands with API 4028, Vnish, EventStore and current diagnostics.
- [ ] T013 Rank only unique read-only gaps by operator value, reliability and implementation cost.
- [ ] T014 Record a separate-spec prerequisite for every accepted candidate; accept zero candidates as a valid result.
## Phase 4: Validation And Closeout

- [ ] T015 Run targeted/full tests, compile, deterministic-output, timeout, no-window, bounded-output and secret scans.
- [ ] T016 Execute metadata-only locally; execute reviewed discovery only if the allowlist is non-empty and exact fingerprints match, then review every artifact.
- [ ] T017 Prove existing action scope, templates, QA gate and monitor call sites unchanged.
- [ ] T018 Synchronize evidence, roadmap, calendar, Hashcore strategy and development log without marking blocked invocation as completed discovery.

## Requirement Coverage

| Requirement | Tasks |
| --- | --- |
| FR-001 | T002, T007, T011, T016 |
| FR-002 | T003-T005, T008-T009, T016 |
| FR-003 | T005, T010-T011, T016 |
| FR-004 | T005-T006, T011, T015-T016 |
| FR-005 | T005, T009, T015-T016 |
| FR-006 | T012-T014 |
| FR-007 | T003-T005, T010-T014 |
| FR-008 | T001, T017 |
| FR-009 | T010, T013-T014 |
| FR-010 | T002, T007, T011, T015-T016 |
| FR-011 | T002, T004, T007, T015-T016 |
| FR-012 | T003-T004, T008, T016 |
| FR-013 | T005, T009, T015-T016 |
| FR-014 | T004-T005, T008-T009, T015 |
| FR-015 | T004, T008, T015-T016 |
| FR-016 | T001, T017 |
| SC-001 | T005, T010-T011, T016 |
| SC-002 | T003-T005, T010, T016 |
| SC-003 | T006, T011, T015-T016 |
| SC-004 | T005, T009, T015-T016 |
| SC-005 | T012-T014 |
| SC-006 | T002, T004, T007, T015-T016 |
| SC-007 | T005, T009, T011, T015-T016 |
| SC-008 | T004, T008, T015-T016 |

## Dependencies And Execution Order

Metadata-only and negative zero-process tests precede all process code. Vendor
evidence and exact fingerprint allowlisting precede execution. Sanitization and
artifact validation precede promotion. Candidate ranking follows complete
classification and cannot expand actions. T016 is metadata-only when the
allowlist remains empty; no task requires inventing an invocation.

## Definition Of Done

- [ ] All T001-T018 tasks are complete with evidence.
- [ ] Acceptance scenarios and negative paths pass.
- [ ] No real config, state, database, logs or secrets enter Git.
- [ ] Action-policy and polling-offset invariants pass when applicable.
- [ ] Runtime activation and observation are recorded; blocked checks remain open.
- [ ] Roadmap, delivery calendar, strategy docs and development log agree.
