# Tasks: Operator Interface Decision

**Input**: Design artifacts from `specs/027-operator-interface-decision/`

**Risk**: MEDIUM

**Tests**: Test-first contracts and runtime evidence are required where behavior changes. `py_compile` alone is insufficient.

## Phase 1: Mandatory Decision Gate

- [ ] T001 Define P1/P2 workflows, target times and required evidence.
- [ ] T002 Execute scorecard against Telegram, static HTML and Grafana.
- [ ] T003 Document no-build or exact MVP scope in evidence.md.
- [ ] T004 Stop implementation tasks if no-build is selected.
## Phase 2: Conditional Red Contracts

- [ ] T005 [P] Add failing loopback/read-only/route-method tests.
- [ ] T006 [P] Add failing bounded-query, stale-data and redaction tests.
- [ ] T007 [P] Add workflow-level acceptance tests for only approved gaps.
## Phase 3: Conditional MVP

- [ ] T008 [US2] Implement typed FastAPI read resources over SQLite mode=ro.
- [ ] T009 [US2] Add minimal server-rendered or HTMX views only where approved.
- [ ] T010 [US3] Enforce no action/config routes and local-only startup.
## Phase 4: Validation And Closeout

- [ ] T011 Run tests, compile, OpenAPI, route, dependency and secret audits.
- [ ] T012 Repeat workflow scorecard and test monitor independence.
- [ ] T013 Observe D+1/D+3 if deployed.
- [ ] T014 Synchronize evidence, roadmap, calendar, interface/technology strategy and development log.

## Dependencies And Execution Order

Specs 025 and 028 precede the scorecard. The no-build decision terminates conditional tasks successfully. If approved, red contracts precede source/dependency addition and rollout.

## Definition Of Done

- [ ] All T001-T014 tasks are complete with evidence.
- [ ] Acceptance scenarios and negative paths pass.
- [ ] No real config, state, database, logs or secrets enter Git.
- [ ] Action-policy and polling-offset invariants pass when applicable.
- [ ] Runtime activation and observation are recorded; blocked checks remain open.
- [ ] Roadmap, delivery calendar, strategy docs and development log agree.
