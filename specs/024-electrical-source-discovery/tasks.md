# Tasks: Electrical Source Discovery

**Input**: Design artifacts from `specs/024-electrical-source-discovery/`

# Tasks: Electrical Source Discovery

**Input**: Design artifacts from `specs/024-electrical-source-discovery/`

**Risk**: MEDIUM

**Tests**: Test-first contracts and runtime evidence are required where behavior changes. `py_compile` alone is insufficient.

## Phase 1: Discovery Gate

- [x] T001 Inventory actual PSU, PDU, UPS, meter and breaker capabilities; record
  current miner-domain fields as non-AC evidence.
- [x] T002 Produce the sanitized capability report with model, firmware,
  protocol, exact read allowlist, units, scaling, update rate and authentication.
- [x] T003 Capture sanitized read-only evidence or record the missing hardware dependency.
- [x] T004 Decide supported, unsupported or blocked before adding a dependency (CLOSED: `blocked_external`).

## Phase 2: Conditional Red Contracts (N/A - Blocked External)

- [x] T005 [P] Normalization tests (N/A - missing external hardware dependency).
- [x] T006 [P] Operation-allowlist and cadence contract tests (N/A - blocked external).
- [x] T007 [P] Additive EventStore migration tests (N/A - schema migration withheld).

## Phase 3: Conditional Adapter (N/A - Blocked External)

- [x] T008 [US2] Source-specific allowlisted adapter (N/A - no physical meter installed).
- [x] T009 [US2] Normalized measurements persistence (N/A - blocked external).
- [x] T010 [US3] Advisory evidence-fusion facts mapping (N/A - blocked external).

## Phase 4: Validation And Closeout

- [x] T011 Run tests, compile, config parse, no-write and action-invariant checks.
- [x] T012 Document blocked status in discovery capability report and evidence.
- [x] T013 Review miner board signals vs external AC line boundary.
- [x] T014 Synchronize evidence, roadmap, calendar, strategies, runbook and development log.

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
| FR-011 | T002, T004, T006, T008, T011 |
| FR-012 | T005, T009, T011-T013 |
| SC-001 | T001-T004, T012 |
| SC-002 | T002, T005, T011 |
| SC-003 | T005, T009, T011-T013 |
| SC-004 | T006, T008, T010, T011 |
| SC-005 | T005, T009, T012, T013 |
| SC-006 | T006, T008, T011, T012 |

## Dependencies And Execution Order

Physical discovery was the hard gate. In accordance with T004, the missing hardware
dependency was formally recorded and adapter/persistence development was withheld.

## Definition Of Done

- [x] Discovery gate T001-T004 complete with formal evidence in `evidence.md`.
- [x] Sanitized capability report generated in `artifacts/spec024-electrical-capability-report.json`.
- [x] Explicit terminal disposition `blocked_external` recorded; zero fake AC inference.
- [x] No real config, state, database, logs or secrets enter Git.
- [x] Action-policy and polling-offset invariants pass (no new actions or writes).
- [x] Roadmap, delivery calendar, strategy docs and development log agree.
