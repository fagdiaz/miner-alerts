# Tasks: Operator Interface Decision

**Input**: Design artifacts from `specs/027-operator-interface-decision/`

**Risk**: MEDIUM

**Tests**: Test-first contracts and runtime evidence are required where behavior changes. `py_compile` alone is insufficient.

## Phase 1: Mandatory Decision Gate

- [ ] T001 Verify Spec 025/028 exit evidence; record `blocked` and stop if either dependency is incomplete.
- [ ] T002 Run three timed repetitions for every eligible W01-W06 interface pair using `workflow-scorecard.md`.
- [ ] T003 Validate every run against canonical evidence, freshness visibility and required fields; select one simplest passing owner per P1 workflow.
- [ ] T004 Document `no_build` or exact failed P1 fields and scoped `fastapi_mvp` in `evidence.md`.
- [ ] T005 If no-build is selected, prove conditional source/dependency/service paths are absent and stop implementation tasks successfully.
## Phase 2: Conditional Red Contracts

- [ ] T006 [P] Add failing exact-loopback, disabled-proxy/CORS, GET/HEAD-only and route-allowlist tests.
- [ ] T007 [P] Add failing SQLite `mode=ro`/`query_only`, schema, busy/missing and no-`immutable=1` tests.
- [ ] T008 [P] Add failing 50/200 pagination, 30-day window, cursor, stale-data and redaction tests.
- [ ] T009 [P] Add dependency/import audits prohibiting monitor, config, miner IO, Telegram action, Hashcore, requests and subprocess paths.
- [ ] T010 [P] Add workflow-level acceptance tests for only approved failed P1 fields.
## Phase 3: Conditional MVP

- [ ] T011 [US2] Add pinned conditional dependencies only after T004 selects `fastapi_mvp`.
- [ ] T012 [US2] Implement typed FastAPI projections over bounded SQLite `mode=ro`/`query_only` queries.
- [ ] T013 [US2] Add minimal server-rendered or HTMX views only for approved failed fields.
- [ ] T014 [US3] Enforce exact `127.0.0.1` startup, no proxy/CORS, no action/config routes and sanitized errors.
## Phase 4: Validation And Closeout

- [ ] T015 Run targeted/full tests, compile, OpenAPI, listener, route, dependency, query-bound and secret audits if built.
- [ ] T016 Repeat the exact three-run workflow scorecard and prove monitor independence.
- [ ] T017 Observe D+1/D+3 only if a service is deployed; no-build requires no runtime observation.
- [ ] T018 Synchronize evidence, roadmap, calendar, interface/technology strategy and development log without presenting blocked/no-build as deployed software.

## Requirement Coverage

| Requirement | Tasks |
| --- | --- |
| FR-001 | T001-T004, T016 |
| FR-002 | T002-T005 |
| FR-003 | T006-T007, T012, T014-T016 |
| FR-004 | T007, T009, T012, T014-T016 |
| FR-005 | T002-T004, T008, T010, T012 |
| FR-006 | T008, T012, T015 |
| FR-007 | T010-T012, T015 |
| FR-008 | T004, T010, T013 |
| FR-009 | T006, T009, T014-T015 |
| FR-010 | T007-T008, T012, T014-T017 |
| FR-011 | T004, T009, T014, T018 |
| FR-012 | T002-T004, T010, T016 |
| FR-013 | T002-T005 |
| FR-014 | T003-T004, T010-T013 |
| FR-015 | T006, T014-T015 |
| FR-016 | T007, T012, T015 |
| FR-017 | T008, T012, T015 |
| FR-018 | T008-T009, T012, T014-T015 |
| FR-019 | T001, T005, T017-T018 |
| SC-001 | T002-T003, T016 |
| SC-002 | T002-T005 |
| SC-003 | T006-T009, T012, T014-T016 |
| SC-004 | T002, T010, T013, T016 |
| SC-005 | T009, T014, T016-T017 |
| SC-006 | T002-T004, T016 |
| SC-007 | T006, T009, T014-T015 |
| SC-008 | T007-T008, T012, T014-T015 |
| SC-009 | T005, T018 |

## Dependencies And Execution Order

Specs 025 and 028 precede the scorecard. T001 blocks rather than estimates
missing interfaces. The no-build decision completes T005 and skips T006-T017 as
not applicable. If approved, all red contracts T006-T010 precede dependency or
source addition; T011 cannot run to learn or prototype before the gate.

## Definition Of Done

- [ ] All applicable T001-T018 tasks are complete with evidence; conditional
  tasks are explicitly marked not applicable after a proven no-build decision.
- [ ] Acceptance scenarios and negative paths pass.
- [ ] No real config, state, database, logs or secrets enter Git.
- [ ] Action-policy and polling-offset invariants pass when applicable.
- [ ] Runtime activation and observation are recorded; blocked checks remain open.
- [ ] Roadmap, delivery calendar, strategy docs and development log agree.
