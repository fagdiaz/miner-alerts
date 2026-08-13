# Tasks: Telegram Messaging Quality

**Input**: Design artifacts from `specs/030-telegram-messaging-quality/`

**Risk**: MEDIUM

**Tests**: Test-first contracts and full action-policy regression are required.

## Phase 1: Baseline And Red Contracts

- [x] T001 Record observed production `/help`, episode, `/status`, `/events` and `/e<ID>` behavior in `specs/030-telegram-messaging-quality/evidence.md`.
- [x] T002 [P] Add failing split/normalization/redaction tests in `tests/test_telegram_messaging.py`.
- [x] T003 [P] Add failing help registry and click-safe alias tests in `tests/test_telegram_messaging.py`.
- [x] T004 [P] Add failing queue-pressure and command-bypass tests in `tests/test_telegram_messaging.py`.
- [x] T005 Capture action-policy and episode-cadence invariant baselines in `specs/030-telegram-messaging-quality/evidence.md`.

## Phase 2: User Story 1 - Actionable Messages

- [x] T006 [US1] Implement pure text normalization, category and bounded splitting in `app/telegram_messages.py`.
- [x] T007 [US1] Align episode headings/detail presentation in `app/alert_episodes.py` without timing changes.
- [x] T008 [US1] Add actionable evidence links to auto-action outcome messages in `app/miner_monitor.py` without changing decisions.

## Phase 3: User Story 2 - Reliable Command Delivery

- [x] T009 [US2] Apply bounded parts through the existing `send_telegram` integration in `app/miner_monitor.py`.
- [x] T010 [US2] Harden full-queue admission so command replies are never silently dropped in `app/miner_monitor.py`.
- [x] T011 [US2] Add unconditional bounded queue outcome logs and preserve no-retry behavior in `app/miner_monitor.py`.

## Phase 4: User Story 3 - Accurate Help

- [x] T012 [US3] Extend central command metadata with official click-safe aliases in `app/miner_monitor.py`.
- [x] T013 [US3] Render compact UTF-8-safe `/help` and command detail from the registry in `app/miner_monitor.py`.
- [x] T014 [US3] Remove promoted legacy/hyphen syntax from command replies while preserving parser compatibility in `app/miner_monitor.py`.

## Phase 5: User Story 4 - Noise And Regression Control

- [x] T015 [US4] Prove episode cadence/grouping and healthy-default silence remain unchanged in `tests/test_notification_stability.py` and `tests/test_alert_episodes.py`.
- [x] T016 [US4] Prove all command responses remain `is_command=true` and notification dedupe remains scoped in `tests/test_telegram_messaging.py`.

## Phase 6: Validation And Rollout

- [x] T017 Run targeted/full tests, compilation, JSON, duplicate-symbol, secret and diff checks; record exact results in `specs/030-telegram-messaging-quality/evidence.md`.
- [x] T018 Execute QA command/delivery scenarios with real actions disabled and record evidence.
- [x] T019 Update README, runbook, roadmap and development log with only verified behavior.
- [x] T020 Commit/push only on request, restart once, smoke read-only commands and complete observation evidence.

## Dependencies And Execution Order

- T001-T005 establish baseline and red contracts.
- T006 precedes T007-T011.
- T012-T014 can proceed after T003 and must precede final command smoke.
- T015-T020 are mandatory release gates.

## Definition Of Done

- [x] All user messages meet the documented taxonomy and size contract.
- [x] Commands never enter notification dedupe or disappear silently under tested pressure.
- [x] Help displays only real official click-safe commands.
- [x] Episode timing and all monitor/action policies remain unchanged.
- [x] Runtime read-only smoke and delivery evidence are recorded.
