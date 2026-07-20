# Tasks: Fleet-Aware Auto-Reboot Safety

- [x] T001 Confirm current auto-reboot gate order and available Vnish evidence in `app/miner_monitor.py`.
- [x] T002 Define pure thermal and fleet interlock contracts in `specs/010-fleet-reboot-safety/spec.md`.
- [x] T003 Add failing boundary and policy-wiring tests in `tests/test_reboot_safety.py`.
- [x] T004 Implement the pure evaluator in `app/reboot_safety.py`.
- [x] T005 Capture and publish completed per-tick signal classifications in `app/miner_monitor.py` without added IO.
- [x] T006 Insert interlocks after startup/sustained checks and before cooldown/window/QA/Hashcore.
- [x] T007 Record and render `fleet_incident` and `high_temperature` evidence through existing SQLite decisions.
- [x] T008 Add safe defaults to `app/config.example.json` without touching `app/config.json`.
- [x] T009 Run targeted tests, full suite, py_compile, diff check, and Speckit HIGH-risk QA.
- [x] T010 Update evidence, development log, roadmap, commit, and push without restarting the service.
