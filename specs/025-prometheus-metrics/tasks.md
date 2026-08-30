# Tasks: Prometheus Metrics And Grafana

# Tasks: Prometheus Metrics And Grafana

**Input**: Design artifacts from `specs/025-prometheus-metrics/`

**Risk**: MEDIUM

**Tests**: Test-first contracts and runtime evidence are required where behavior changes. `py_compile` alone is insufficient.

## Phase 1: Metric Contract And Red Tests

- [x] T001 Define the exact 26 metric families, fixed enums and
  `23 + 20 * miners` series budget from `contracts/metrics.md`.
- [x] T002 [P] Add failing snapshot atomicity, finite-value, schema, redaction,
  malformed-input and 60-second staleness tests.
- [x] T003 [P] Add failing exporter exposition/cardinality tests.
- [x] T004 [P] Add Compose/provisioning static tests for pinned images,
  loopback UI binds, internal-only exporter and prohibited mounts.
## Phase 2: Snapshot And Exporter

- [x] T005 [US1] Implement pure validated schema-v1 snapshot rendering and
  atomic write in app/metrics_snapshot.py.
- [x] T006 Integrate one best-effort atomic snapshot after completed ticks.
- [x] T007 [US2] Implement the fixed allowlist in tools/metrics_exporter.py with
  prometheus_client, snapshot-health-only stale behavior and no action imports.
## Phase 3: Prometheus And Grafana

- [x] T008 [US3] Add pinned exporter, Prometheus and Grafana Compose definitions.
- [x] T009 Provision local-only data source and fleet/liveness/delivery dashboards.
- [x] T010 Add retention, health checks and the exact disabled-by-default config
  from `contracts/config.md`.
## Phase 4: Validation And Rollout

- [x] T011 Run tests, compile, Compose config, prohibited-mount, redaction,
  20-ms write, 250-ms scrape and 128-series audits.
- [x] T012 Rebuild from empty volumes and test stack outage isolation.
- [x] T013 Enable snapshot and observe D+1/D+3 resource use.
- [x] T014 Synchronize evidence, roadmap, calendar, interface/technology docs and development log.

## Requirement Coverage

| Requirement | Tasks |
| --- | --- |
| FR-001 | T002, T005, T006 |
| FR-002 | T001, T002, T005, T006, T009 |
| FR-003 | T001, T003, T011 |
| FR-004 | T001-T003, T011 |
| FR-005 | T002, T005, T007, T011 |
| FR-006 | T003, T007, T011, T012 |
| FR-007 | T004, T008, T010, T012 |
| FR-008 | T004, T008, T011 |
| FR-009 | T004, T009, T012 |
| FR-010 | T001, T009, T010 |
| FR-011 | T003, T011, T013 |
| SC-001 | T001-T003, T011 |
| SC-002 | T002, T005, T007, T011 |
| SC-003 | T001, T003, T011, T013 |
| SC-004 | T004, T007, T012 |
| SC-005 | T004, T008, T009, T012 |

## Dependencies And Execution Order

Heartbeat/acquisition schemas block snapshot design. Contract tests precede monitor integration; exporter precedes Compose; production enablement follows redaction, cardinality and outage-isolation proof.

## Definition Of Done

- [ ] All T001-T014 tasks are complete with evidence.
- [ ] Acceptance scenarios and negative paths pass.
- [ ] No real config, state, database, logs or secrets enter Git.
- [ ] Action-policy and polling-offset invariants pass when applicable.
- [ ] Runtime activation and observation are recorded; blocked checks remain open.
- [ ] Roadmap, delivery calendar, strategy docs and development log agree.
