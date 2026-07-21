# Tasks: Persistent Outage Alerts

## Phase 1: Baseline And Tests

- [x] T001 Confirm current alert timing, restart suppression, subprocess paths, and scheduled-task action in `app/miner_monitor.py` and `tools/install_vnish_collector_task.ps1`.
- [x] T002 Add failing coordinator tests for cross-tick grouping and bounded single-event delivery in `tests/test_notification_stability.py`.
- [x] T003 Add failing tests for first/repeat outage reminders, grouping, recovery clearing, startup observation, and restart deferral in `tests/test_notification_stability.py`.
- [x] T004 Update scheduler/subprocess contract tests for direct `pythonw.exe` and no-window flags in `tests/test_vnish_scheduler.py` and `tests/test_monitor_incidents.py`.

## Phase 2: Telegram Notification Stability

- [x] T005 Implement the process-local state-change batch coordinator in `app/miner_monitor.py` without changing state transitions or persistence.
- [x] T006 Implement the persistent-outage reminder coordinator and message renderer in `app/miner_monitor.py`.
- [x] T007 Wire coalescing, restart-recovery precedence, reminder deferral, and Telegram delivery into the monitor loop in `app/miner_monitor.py`.
- [x] T008 Add safe production defaults to `app/config.example.json` and consume them with bounded validation in `app/miner_monitor.py`.

## Phase 3: Windows No-Popup Hardening

- [x] T009 Replace the scheduled task PowerShell action with direct virtualenv `pythonw.exe` execution in `tools/install_vnish_collector_task.ps1`.
- [x] T010 Add a portable `CREATE_NO_WINDOW` flag to every existing monitor subprocess invocation in `app/miner_monitor.py`.
- [x] T011 Update the Windows runbook to document direct background collector execution in `README.md` and `docs/speckit/RUNBOOK.md`.

## Phase 4: Validation And Rollout

- [x] T012 Run targeted tests, full suite, `py_compile`, JSON parsing, PowerShell parsing, diff checks, and Speckit QA.
- [x] T013 Validate QA forced-state grouping/reminders without real Hashcore actions.
- [x] T014 Reinstall and run the scheduled collector task; record executable, result, and no-popup evidence.
- [ ] T015 Restart `MinerAlerts` once with elevation and verify startup/mutex/production logs and active process creation time.
- [x] T016 Update `evidence.md`, `docs/speckit/ROADMAP.md`, and newest-first `docs/audit/DEVELOPMENT_LOG.md`.
- [ ] T017 Commit, push, and record any UAC-dependent blocker without claiming unverified activation.

## Definition Of Done

- [x] Persistent outages cannot remain silent beyond the bounded reminder interval.
- [x] Related transitions are grouped without delaying state persistence or action gates.
- [x] Existing restart recovery remains authoritative.
- [x] Scheduled collection and subprocess actions cannot create foreground console windows.
- [ ] All validation and runtime evidence is recorded.
