# Evidence: Operator Interface Decision

**Status**: Completed and Closed (`no_build` Decision)

## Planning Baseline

- Spec package generated on 2026-08-13.
- Dependency gate: Spec 025 Grafana evaluation and Spec 028 backup/restore proof.
- Risk class: MEDIUM.
- No production code, local config, state, service or miner was changed by specification generation.

## Dependencies Verification (T001)

- **Spec 025 (Prometheus & Grafana)**:
  * Snapshot generator `app/metrics_snapshot.py`, HTTP exporter `tools/metrics_exporter.py`, Docker Compose `docker-compose.observability.yml`, and 3 Grafana dashboards (`fleet_overview.json`, `monitor_liveness.json`, `telegram_delivery.json`) implemented and tested.
  * Monitor snapshot hook integrated (T006). Gate D+3 passed. Exit evidence verified in `specs/025-prometheus-metrics/evidence.md`.
- **Spec 028 (Backup, Retention & Restore)**:
  * Backup tool `tools/event_store_backup.py` and task installer `tools/install_backup_task.ps1` implemented.
  * Real staging restore drill executed over 20.4 MB production database in 6.2s (`passed`). Exit evidence verified in `specs/028-backup-retention-restore/evidence.md`.
- **Result**: Dependencies gate is **PASSED / UNBLOCKED**.

## Workflow Scorecard Evaluation (T002 - T003)

Full scorecard recorded in `workflow-scorecard.md`:
- **30 Timed Repetitions** executed across eligible interfaces for all P1 workflows (W01 to W06).
- Every run was verified for completeness, accuracy, explicit freshness visibility, and completion within the target window.
- **Simplest Passing Owners**:
  * **W01** (Monitor & pipeline health): **Telegram `/status`** (2.1s << 30s target; confirmed by Grafana `monitor_liveness.json` at 1.4s).
  * **W02** (Miners needing attention): **Telegram `/status`** (2.2s << 30s target; confirmed by static HTML at 2.9s).
  * **W03** (Latest irregular episode): **Telegram `/diagnose`** (3.3s << 90s target; confirmed by static HTML at 11.0s).
  * **W04** (Reboot provenance & cause): **Telegram `/diagnose`** (3.2s << 90s target; confirmed by static HTML at 9.2s).
  * **W05** (Local vs fleet-wide degradation): **Grafana (`fleet_overview.json`)** (2.7s << 60s target; confirmed by static HTML at 4.0s).
  * **W06** (Recovery vs persistent degradation): **Grafana (`fleet_overview.json`)** (4.1s << 120s target; confirmed by static HTML at 15.0s).
- **Missing Fields Count**: Exactly **0** required P1 fields are missing across existing interfaces.

## Formal Decision (T004)

- **Decision**: **`no_build`**
- In strict adherence to FR-002, FR-013, and `contracts/operator-interface.md`:
  > "If existing interfaces meet all P1 workflow targets, the spec MUST close with no new web service."
- No new web service (FastAPI, Uvicorn, HTMX, or React) is justified or authorized.

## Conditional Path Absence Audit (T005)

Audit confirmed that zero conditional source files, dependencies, or services have been added:
- `app/operator_api.py`: **ABSENT**
- `app/operator_views.py`: **ABSENT**
- `templates/operator/`: **ABSENT**
- `tests/test_operator_api.py`: **ABSENT**
- `requirements-interface.txt`: **ABSENT**
- Conditional Windows Service: **ABSENT**

## Test Suite Verification

- Full test suite: **404/404 tests PASS** in 3.8s (0 failures, 0 errors, 0 skips).
- Zero regressions introduced.
- Production monitor (PID 38816) remained 100% untouched and uncoupled throughout this evaluation.

## Runtime Rollout

- `no_build` decision requires no production deployment or post-implementation observation window (FR-019, T017).
- Spec 027 is complete and closed.
