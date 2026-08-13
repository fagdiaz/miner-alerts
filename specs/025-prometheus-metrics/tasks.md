# Tasks: Prometheus Metrics And Grafana

**Input**: Design artifacts from `specs/025-prometheus-metrics/`

**Risk**: MEDIUM

**Tests**: Test-first contracts and runtime evidence are required where behavior changes. `py_compile` alone is insufficient.

## Phase 1: Metric Contract And Red Tests

- [ ] T001 Define metric families, types, finite labels and series budget.
- [ ] T002 [P] Add failing snapshot atomicity/redaction/staleness tests.
- [ ] T003 [P] Add failing exporter exposition/cardinality tests.
- [ ] T004 [P] Add Compose/provisioning static contract tests.
## Phase 2: Snapshot And Exporter

- [ ] T005 [US1] Implement pure sanitized snapshot rendering in app/metrics_snapshot.py.
- [ ] T006 Integrate one best-effort atomic snapshot after completed ticks.
- [ ] T007 [US2] Implement tools/metrics_exporter.py with prometheus_client and no action imports.
## Phase 3: Prometheus And Grafana

- [ ] T008 [US3] Add pinned exporter, Prometheus and Grafana Compose definitions.
- [ ] T009 Provision local-only data source and fleet/liveness/delivery dashboards.
- [ ] T010 Add retention, health checks and documented disabled-by-default rollout config.
## Phase 4: Validation And Rollout

- [ ] T011 Run tests, compile, Compose config, redaction and cardinality audits.
- [ ] T012 Rebuild from empty volumes and test stack outage isolation.
- [ ] T013 Enable snapshot and observe D+1/D+3 resource use.
- [ ] T014 Synchronize evidence, roadmap, calendar, interface/technology docs and development log.

## Dependencies And Execution Order

Heartbeat/acquisition schemas block snapshot design. Contract tests precede monitor integration; exporter precedes Compose; production enablement follows redaction, cardinality and outage-isolation proof.

## Definition Of Done

- [ ] All T001-T014 tasks are complete with evidence.
- [ ] Acceptance scenarios and negative paths pass.
- [ ] No real config, state, database, logs or secrets enter Git.
- [ ] Action-policy and polling-offset invariants pass when applicable.
- [ ] Runtime activation and observation are recorded; blocked checks remain open.
- [ ] Roadmap, delivery calendar, strategy docs and development log agree.
