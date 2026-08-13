# Tasks: Irregular Miner Episodes

**Input**: Design documents from `specs/020-episode-alerts/`

**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/telegram-episodes.md`, `quickstart.md`

**Tests**: Test-first changes are required because this feature changes production Telegram timing and presentation while action policy must remain identical.

## Phase 1: Baseline And Safety

- [x] T001 Confirm the real recovery-hysteresis status contradiction, 180-second restart delay, existing SQLite history, and safe config values in `app/miner_monitor.py`, `app/event_store.py`, and `data/miner_alerts.db`.
- [x] T002 [P] Add red pure-unit tests for episode opening, bounded history, closure, grouped notifications and the 5/10/15/30/60/120-minute cadence in `tests/test_alert_episodes.py`.
- [x] T003 [P] Add red status-rendering tests for OFFLINE, LOW, board-loss, recovering and OK evidence in `tests/test_alert_episodes.py`.
- [x] T004 [P] Add red event timeline and `/e<ID>` contract tests in `tests/test_event_store.py` and `tests/test_monitor_incidents.py`.
- [x] T005 Record baseline action-policy tests and QA no-Hashcore behavior in `specs/020-episode-alerts/evidence.md`.

## Phase 2: User Story 1 - Persistent Escalation (P1)

**Goal**: Never lose an active irregular miner while avoiding per-tick spam.

**Independent Test**: An unresolved miner is notified at absolute episode ages 5, 10, 15, 30, 60 and 120 minutes and hourly thereafter; due miners are grouped.

- [x] T006 [US1] Implement bounded episode entities and deterministic escalation in `app/alert_episodes.py`.
- [x] T007 [US1] Replace legacy persistent-outage scheduling with episode notification batches in `app/miner_monitor.py` without changing state transitions or action evaluation.
- [x] T008 [US1] Add production defaults and legacy config fallback in `app/config.example.json` and `app/miner_monitor.py`.

## Phase 3: User Story 2 - Timeline And Recovery (P1)

**Goal**: Present one concise OK-to-OK history instead of intermediate message cascades.

**Independent Test**: Both a short LOW recovery and a restart recovery produce a bounded deduplicated sequence, with multiple miners grouped.

- [x] T009 [US2] Implement initial/update/recovery batch rendering and user-facing board-loss vocabulary in `app/alert_episodes.py`.
- [x] T010 [US2] Capture persisted transition/restart IDs and wire episode history into the monitor loop in `app/miner_monitor.py`.
- [x] T011 [US2] Remove the fixed three-minute restart notice and ten-minute delivery quiet path while preserving restart classification and persisted evidence in `app/miner_monitor.py`.

## Phase 4: User Story 3 - Truthful Status (P1)

**Goal**: Ensure `/status` never contradicts the current signal.

**Independent Test**: A current positive healthy rate with retained OFFLINE/LOW state renders `RECUPERANDO`; a no-response sample renders `N/A [OFFLINE]`.

- [x] T012 [US3] Implement pure current-signal status rendering in `app/alert_episodes.py`.
- [x] T013 [US3] Build monitor snapshots from current evidence and active episode detail references in `app/miner_monitor.py`.

## Phase 5: User Story 4 - Prompt Read-Only Detail (P1)

**Goal**: Report restart evidence after 30 seconds and expose a full persisted timeline on demand.

**Independent Test**: `/e<ID>` and `/event <id>` show the same incident plus bounded chronological related events; restart notices do not wait 180 seconds.

- [x] T014 [US4] Add bounded episode-window queries and chronological timeline rendering in `app/event_store.py`.
- [x] T015 [US4] Add click-safe `/e<ID>` parsing/routing and command-delivery wiring in `app/miner_monitor.py`.
- [x] T016 [US4] Update event-list and episode-alert detail references to click-safe tokens in `app/event_store.py` and `app/alert_episodes.py`.

## Phase 6: Validation And Rollout

- [x] T017 Run targeted tests, full suite, `py_compile`, JSON parsing, duplicate-symbol scan, `git diff --check`, and Speckit QA; record exact results in `specs/020-episode-alerts/evidence.md`.
- [x] T018 Execute controlled QA episode sequences with `qa_allow_real_actions=false` and prove no Hashcore subprocess/action-policy regression in `specs/020-episode-alerts/evidence.md`.
- [x] T019 Update `README.md`, `docs/speckit/RUNBOOK.md`, `docs/speckit/ROADMAP.md`, and newest-first `docs/audit/DEVELOPMENT_LOG.md` with the verified contract.
- [x] T020 Commit, push, restart `MinerAlerts`, verify runtime logs/read-only commands, and close `spec.md`, `tasks.md`, and `evidence.md` only with observed evidence.

## Dependencies And Execution Order

- T001-T005 establish the baseline and red contracts.
- T006-T008 implement escalation before notification-loop replacement.
- T009-T013 depend on the episode model and complete recovery/status behavior.
- T014-T016 can proceed after event IDs are wired by T010.
- T017-T020 are mandatory production closeout gates.

## Definition Of Done

- [x] Every active episode follows the requested reminder cadence and stops on confirmed OK.
- [x] Episode histories are bounded, grouped and persisted facts remain queryable.
- [x] Restart evidence is visible after the short grouping window, not three minutes.
- [x] `/status` cannot show a positive rate as OFFLINE.
- [x] State machine, persistence and all reboot/Hashcore policies are unchanged and regression-tested.
- [x] Real config/state files and secrets are absent from the diff.
- [x] Runtime activation and exact validation evidence are recorded.
