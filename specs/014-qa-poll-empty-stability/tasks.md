# Tasks: QA Poll-Empty Stability

- [x] T001 [US1] Confirm the defect and its presence in the parent commit in `app/miner_monitor.py`.
- [x] T002 [US1] Add a failing source regression test in `tests/test_telegram_polling_stability.py`.
- [x] T003 [US1] Remove only the invalid command-duration log from `POLL_EMPTY` in `app/miner_monitor.py`.
- [x] T004 [US1] Run targeted/full tests, `py_compile`, diff checks, and source invariants.
- [x] T005 Record exact evidence in `specs/014-qa-poll-empty-stability/evidence.md`.
- [x] T006 Update `docs/audit/DEVELOPMENT_LOG.md` and `docs/speckit/ROADMAP.md`.
- [x] T007 Commit and push without restarting the service.
