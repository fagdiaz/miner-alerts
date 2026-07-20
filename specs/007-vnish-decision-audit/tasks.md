# Tasks: Vnish Telemetry And Reboot Decision Audit

## Phase 1 - Specification And Design

- [x] T001 Inspect current stats calls, Vnish diagnostics evidence, SQLite schema, and auto-reboot exits.
- [x] T002 Define normalized telemetry, conservative units, and no-raw-data boundary.
- [x] T003 Define additive schema-v2 migration and reboot-decision model.
- [x] T004 Define `/why` and offline report contracts.
- [x] T005 Pass requirements checklist and cross-artifact analysis.

## Phase 2 - Pure Telemetry

- [x] T006 Implement pure Vnish telemetry normalizer in `app/vnish_telemetry.py`.
- [x] T007 Cover multi-entry, malformed, missing, temperature, chain, fan, and flag cases.
- [x] T008 Reuse one production stats response without changing existing board-state semantics.

## Phase 3 - SQLite Schema V2

- [x] T009 Add transactional `PRAGMA user_version` migration from v1 to v2.
- [x] T010 Add normalized telemetry columns and `reboot_decisions` with indexes.
- [x] T011 Add decision write/latest/list and telemetry report query APIs.
- [x] T012 Extend independent retention and row-count validation.
- [x] T013 Test fresh schema, v1 migration preservation, reopen, concurrency, and failure isolation.

## Phase 4 - Runtime Audit

- [x] T014 Add a small decision-record helper that cannot invoke actions.
- [x] T015 Record `not_low` and `invalid_signal` evaluations.
- [x] T016 Record `startup_guard` and `not_sustained` evaluations.
- [x] T017 Record `cooldown`, `window`, and `qa` before existing exits.
- [x] T018 Record `executed` and `failed` after the existing Hashcore return.
- [x] T019 Verify existing conditions, ordering, values, and `continue` behavior remain unchanged.

## Phase 5 - Operator Surfaces

- [x] T020 Add command registry/parser/handler support for `/why` and `/why <miner>`.
- [x] T021 Ensure `/why` uses local SQLite only and command-delivery semantics.
- [x] T022 Implement deterministic decision rendering with conservative voltage label.
- [x] T023 Implement `tools/incident_report.py` for Markdown and JSON.
- [x] T024 Test report correlation and command outputs without network or Hashcore calls.

## Phase 6 - Configuration And Operations

- [x] T025 Add production-safe decision retention default to `app/config.example.json`.
- [x] T026 Update runbook, roadmap, Speckit index, and development log.
- [x] T027 Record exact validation output in `evidence.md`.
- [x] T028 Run py_compile, all unit tests, config JSON parse, diff check, and Speckit QA.
- [x] T029 Confirm real config/state/database/log artifacts remain ignored.
- [x] T030 Commit and push the feature branch without restarting the running service.
