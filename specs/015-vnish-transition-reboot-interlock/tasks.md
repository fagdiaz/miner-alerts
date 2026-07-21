# Tasks: Vnish Transition Reboot Interlock

- [x] T001 [US1] Add failing pure interlock/default/order tests in `tests/test_reboot_safety.py`.
- [x] T002 [US1] Extend `app/reboot_safety.py` with the current-transition interlock and bounded evidence.
- [x] T003 [US1] Wire current Mining Quality transition evidence into the automatic-only gate in `app/miner_monitor.py`.
- [x] T004 [US1] Reset only `low_since_ts` when transition blocks, preserving state/streak/manual flows.
- [x] T005 [US2] Add failing persistence/render tests in `tests/test_reboot_decision_audit.py` and/or `tests/test_event_store.py`.
- [x] T006 [US2] Persist, log, and render `firmware_transition` evidence in `app/miner_monitor.py` and `app/event_store.py`.
- [x] T007 Add the safe default to `app/config.example.json` and operator contract to `docs/speckit/RUNBOOK.md`.
- [x] T008 Run targeted/full tests, `py_compile`, config/diff checks, and Speckit QA with builds.
- [x] T009 Record exact evidence and update roadmap/development log.
- [x] T010 Commit and push without restarting the service.
