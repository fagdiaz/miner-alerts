# Tasks: Incident History And Restart Intelligence

**Input**: Design documents from `specs/006-incident-history/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/telegram-history.md`, `quickstart.md`

**Tests**: Deterministic tests are required because this feature adds persistence,
restart classification, Telegram routing, and production notifications.

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Verify database, WAL, SHM, test-cache, config, state, logs, and diagnostics artifacts remain excluded in `.gitignore` and `.dockerignore`
- [x] T002 Create the standard-library test package structure in `tests/`

---

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T003 [P] Add restart attribution tests for manual, automatic, unexpected, skewed, and expired actions in `tests/test_restart_intelligence.py`
- [x] T004 [P] Add persistence, filtering, reopen, retention, and failure-containment tests in `tests/test_event_store.py`
- [x] T005 Implement the versioned SQLite event store, schema, WAL setup, indexes, bounded queries, and safe error callback in `app/event_store.py`
- [x] T006 Implement pure restart classification over an existing restart signal in `app/restart_intelligence.py`

**Checkpoint**: Durable storage and classification pass independently of the monitor.

---

## Phase 3: User Story 1 - Detect Unexpected Restarts (Priority: P1)

**Goal**: Produce a durable, evidence-rich unexpected-restart incident without changing any action decision.

**Independent Test**: An existing uptime-reset signal without a recent action records one `unexpected` event and renders one dedicated alert; expected action cases are classified but do not masquerade as unexpected.

- [x] T007 [US1] Add event-store initialization, safe disable fallback, attribution settings, and lifecycle logging in `app/miner_monitor.py`
- [x] T008 [US1] Correlate the existing `reboot_reason` with existing action timestamps and record restart events in `app/miner_monitor.py`
- [x] T009 [US1] Render and enqueue a dedicated unexpected-restart Telegram notification with incident ID and evidence in `app/miner_monitor.py`
- [x] T010 [US1] Verify the existing state machine and complete auto-reboot condition block are unchanged except for observation hooks in `app/miner_monitor.py`

**Checkpoint**: Unexpected restart detection works independently; no historical record affects an action.

---

## Phase 4: User Story 2 - Preserve Operational Evidence (Priority: P1)

**Goal**: Preserve bounded samples and normalized operational events across service restarts.

**Independent Test**: Samples and state/action events survive store reopen; sampling is interval-bounded and cleanup removes only expired rows.

- [x] T011 [US2] Add interval-bounded telemetry sample writes after existing miner observations in `app/miner_monitor.py`
- [x] T012 [US2] Record existing state transitions as normalized events without changing transition logic in `app/miner_monitor.py`
- [x] T013 [US2] Record existing auto-reboot success/failure outcomes without changing Hashcore invocation or gates in `app/miner_monitor.py`
- [x] T014 [US2] Run startup and daily retention cleanup through safe event-store calls in `app/miner_monitor.py`

**Checkpoint**: Operational evidence is durable and bounded while monitoring remains available on storage failure.

---

## Phase 5: User Story 3 - Query Incidents From Telegram (Priority: P2)

**Goal**: Let the operator query recent history and incident detail from Telegram without live miner I/O.

**Independent Test**: `/events`, `/events <miner>`, and `/event <id>` produce deterministic local replies for valid, empty, invalid, and unavailable cases.

- [x] T015 [P] [US3] Add compact event-list and event-detail render tests in `tests/test_event_store.py`
- [x] T016 [US3] Register real `events` and `event` commands, help text, and command-like delivery metadata in `app/miner_monitor.py`
- [x] T017 [US3] Add `/events` and `/events <miner>` routing backed only by the event store in `app/miner_monitor.py`
- [x] T018 [US3] Add `/event <id>` routing and deterministic invalid/unavailable/not-found replies in `app/miner_monitor.py`
- [x] T019 [US3] Verify every new Telegram reply uses `is_command=True`, `dbg_update_id`, and `dbg_cmd` in `app/miner_monitor.py`

**Checkpoint**: Telegram history is usable and cannot invoke ASIC or Hashcore I/O.

---

## Phase 6: User Story 4 - Control Retention And Operations (Priority: P3)

**Goal**: Provide production-safe defaults, bounded disk usage, and visible storage health.

**Independent Test**: Defaults initialize a repository-local store, retention is bounded, ignored runtime files stay untracked, and disabling storage leaves monitoring operational.

- [x] T020 [US4] Add production-safe event-store, sampling, retention, attribution, and notification defaults in `app/config.example.json`
- [x] T021 [US4] Add database runtime artifacts to `.gitignore` and `.dockerignore` without excluding source or specs
- [x] T022 [US4] Document database behavior, Telegram history commands, restart classifications, and rollback in `docs/speckit/RUNBOOK.md`

---

## Phase 7: Polish & Cross-Cutting Validation

- [x] T023 Run `py_compile`, all `unittest` tests, `git diff --check`, and Speckit QA preflight; record exact output in `specs/006-incident-history/evidence.md`
- [x] T024 Validate Telegram command routing statically and, when possible, under `DBG_TELEGRAM=1` with `DBG_TELEGRAM_COMMANDS_ONLY=1`; record blocked runtime checks in `specs/006-incident-history/evidence.md`
- [x] T025 Verify QA mode cannot execute real actions and that startup guard, sustained LOW, cooldown, reboot window, and max-window conditions remain present in `app/miner_monitor.py`
- [x] T026 Update completed backlog items in `docs/speckit/ROADMAP.md`
- [x] T027 Insert one newest-first Spec 006 entry in `docs/audit/DEVELOPMENT_LOG.md` and verify date ordering
- [x] T028 Confirm `git status --short` contains no runtime database, config, state, log, cache, or diagnostics artifact
- [x] T029 Restart the `MinerAlerts` Windows service only after validation and record PID/status or the exact permissions blocker in `specs/006-incident-history/evidence.md`

## Dependencies & Execution Order

- Phase 1 precedes all implementation.
- T003 and T004 can run in parallel; T005 and T006 implement their tested contracts.
- User Story 1 depends on T005-T006.
- User Story 2 depends on the event-store integration from User Story 1 but remains independently testable through persistence tests.
- User Story 3 depends on T005 query APIs, not on live miner I/O.
- User Story 4 can proceed after configuration names stabilize.
- Phase 7 follows all implemented stories.

## Definition Of Done

- [x] All required tasks are marked `[X]`.
- [x] Restart classification and persistence tests pass.
- [x] No database record can trigger an action.
- [x] Existing action gates and confirmation flows remain intact.
- [x] History commands always reply and perform local reads only.
- [x] Runtime database artifacts remain outside Git.
- [x] Evidence, roadmap, and development log are current.
