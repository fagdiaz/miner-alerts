# Tasks: Vnish Log Intelligence

- [x] T001 [US1] Add failing taxonomy/redaction/fingerprint tests in `tests/test_vnish_logs.py`.
- [x] T002 [US1] Implement the pure bounded parser in `app/vnish_logs.py`.
- [x] T003 [US2] Add failing schema-v3 migration/idempotency/retention tests in `tests/test_event_store.py`.
- [x] T004 [US2] Implement additive schema-v4 `firmware_events` persistence in `app/event_store.py`.
- [x] T005 [US2] Add `websocket-client` and a failing fake-transport collector test.
- [x] T006 [US2] Implement `tools/vnish_log_collector.py` with strict read-only bounds and dry-run.
- [x] T007 [US3] Add failing `/firmware` registration/read-only renderer tests in `tests/test_vnish_logs.py`.
- [x] T008 [US3] Wire bounded SQLite-only `/firmware` in `app/miner_monitor.py`.
- [x] T009 [US3] Add failing dashboard timeline tests and integrate `firmware_events` in `tools/operations_dashboard.py`.
- [x] T010 Update `README.md`, `docs/speckit/RUNBOOK.md`, dependency/container notes, and roadmap.
- [x] T011 Run targeted/full tests, compile, migration/dedupe checks, live read-only smoke, dashboard smoke, and Speckit QA.
- [x] T012 Record exact evidence and add the newest-first development log entry.
- [x] T013 Commit and push without restarting the service.
