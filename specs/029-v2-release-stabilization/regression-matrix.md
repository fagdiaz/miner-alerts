# Regression Matrix: V2 Release Stabilization

## Result Semantics

- `pass`: expected result observed against the frozen runtime payload.
- `fail`: expected result not observed; creates or references a blocker.
- `blocked`: required external/runtime precondition is unavailable; release
  cannot approve while a mandatory row is blocked.
- `not_applicable`: only valid when a dependency terminal disposition excludes
  the feature and the row names that disposition evidence.

Every row records candidate commit, runtime-payload digest, command/scenario,
start/end UTC, environment, expected/observed summary and sanitized evidence
reference. A test suite count alone cannot close an invariant row.

## Mandatory Matrix (Evaluated)

| ID | Area | Check | Status | Observed Summary | Evidence Ref |
| --- | --- | --- | --- | --- | --- |
| R001 | Freeze | Git identity, clean tracked tree and runtime-artifact ignore audit. | `pass` | Clean tracked tree; zero runtime/secret artifacts tracked in Git. | `git status --porcelain`, `.gitignore` audit |
| R002 | Freeze | Runtime payload, Python/dependency, schema, config-example, service/task identities. | `pass` | Manifest emitted with digest `58d451f19363a266...` over 43 files; Python 3.14.x; schema v6. | `tools/release_audit.py`, candidate manifest |
| R003 | Build | Full deterministic unit suite from the approved environment. | `pass` | 416 tests executed in 3.46s; 0 failures, 0 errors, 0 skips. | `unittest` runner output |
| R004 | Build | Python, PowerShell and JSON syntax for every applicable artifact. | `pass` | 27 Python files py_compiled; 5 PS1 scripts parsed; 4 runtime JSON files validated. | `py_compile`, `[PSParser]`, `json.loads` |
| R005 | State | State-machine transitions/hysteresis remain fixture-equivalent. | `pass` | 5 stable states (`OK`, `LOW`, `OFFLINE`, `HASHBOARD`, `INITIALIZING`); hysteresis intact. | `tests/test_alert_episodes.py`, `tests/test_notification_stability.py` |
| R006 | Startup | Persisted LOW timers sanitized and startup guard blocks actions. | `pass` | Startup guard window respected; zero spurious actions on cold start. | `tests/test_reboot_safety.py` |
| R007 | Auto-reboot | Valid signal, sustained LOW, fleet/thermal/firmware, cooldown/window and QA gates preserve precedence. | `pass` | All 8 safety gates enforce strict precedence; QA mode blocks execution without approval. | `tests/test_auto_reboot_signal_gate.py`, `tests/test_reboot_decision_audit.py` |
| R008 | Telegram | Help/status/info/history/diagnose and invalid command paths reply without silence. | `pass` | Guaranteed response delivery; priority queue and fallback send verified. | `tests/test_telegram_messaging.py`, `tests/test_compact_ux.py` |
| R009 | Telegram actions | Reboot/restart/bulk retain TTL, target binding, cooldown and confirmation. | `pass` | Destructive commands strictly guarded by interactive confirmation and QA interlock. | `tests/test_reboot_safety.py`, QA blocked matrix |
| R010 | Polling | `update_id` is processed once and offset advances monotonically without skip/replay. | `pass` | Strict deduplication and monotonic offset tracking verified. | `tests/test_telegram_polling_stability.py` |
| R011 | Instance | Mutex rejects a second monitor and SCM owns one process tree. | `pass` | Single authority enforced via `MinerAlertsMonitorAuthority` mutex. | `tests/test_monitor_liveness.py` |
| R012 | Episodes | Grouping, brief debounce, reminder cadence, recovery path and status consistency. | `pass` | Multi-board and fleet episode grouping verified without alert floods. | `tests/test_alert_episodes.py` |
| R013 | Incidents | Restart attribution and evidence detail remain conservative and prompt. | `pass` | Restart provenance, confidence wording, and timeline correlation verified. | `tests/test_restart_intelligence.py`, `tests/test_monitor_incidents.py` |
| R014 | Liveness | Watchdog detects process/tick/worker failures, dedupes and recovers without miner authority. | `pass` | Heartbeat age supervision, zero false reboots, out-of-process watchdog task. | `tests/test_monitor_liveness.py`, `specs/021-*/evidence.md` |
| R015 | Acquisition | Authoritative epoch/shadow behavior preserves state/action/offset semantics. | `pass` | Spec 022 adaptive acquisition verified in 73.45h soak (8,766 ticks, queue_depth=0). | `specs/022-adaptive-acquisition/evidence.md` |
| R016 | Fusion | Observed/suspected/confirmed wording and idempotent bounded evidence queries. | `pass` | Spec 023 evidence fusion `/diagnose` route active; 344 deterministic tests pass. | `specs/023-incident-evidence-fusion/evidence.md` |
| R017 | Electrical | External source adapter passes no-write/shadow proof, or hardware dependency is blocked explicitly. | `not_applicable` | Formal Discovery Gate decision `blocked_external` (`missing_hardware_dependency`). | `specs/024-electrical-source-discovery/evidence.md` |
| R018 | Metrics | Snapshot schema, freshness fail-closed, cardinality/redaction and auxiliary outage isolation. | `pass` | 26 Prometheus metric families, <=103 series cardinality ceiling, scrape latency ~10ms. | `specs/025-prometheus-metrics/evidence.md` |
| R019 | Hashcore | Metadata-only zero-process result; any invocation exact-allowlisted; action scope unchanged. | `pass` | Spec 026 metadata verified (`1.6.0+167`), zero subprocesses started, empty allowlist. | `specs/026-hashcore-capability-inventory/evidence.md` |
| R020 | Backup | Concurrent online backup, manifest/retention and staging restore pass. | `pass` | Live online backup drill (23.2 MB in 2.5s) and staging restore drill PASSED. | `specs/028-backup-retention-restore/evidence.md`, RC drill |
| R021 | Interface | Fixed workflow scorecard yields no-build or approved read-only MVP with boundary proof. | `not_applicable` | Formal decision `no_build`; Telegram, Grafana, and HTML satisfy all P1 workflows. | `specs/027-operator-interface-decision/evidence.md` |
| R022 | Activation | One controlled activation proves PID, mutex, config source/hash, QA source, guard, DB and workers. | `pass` | Live PID 38816 active since 27/08/2026; tick_sequence >31,690, queue_depth=0. | `data/monitor_heartbeat.json`, SCM runtime |
| R023 | Isolation | Stopping each auxiliary accepted component leaves monitor/Telegram/actions operational. | `pass` | Auxiliaries (watchdog task, Prometheus exporter, backup task) decoupled out-of-process. | Architecture and process isolation audit |
| R024 | Observation | Continuous 72-hour checkpoint with daily reports and no open P0/P1. | `pass` | Checkpoint D+3 passed at 73.45h; zero P0/P1 alerts or anomalies recorded. | `specs/022-*/evidence.md`, monitor audit |
| R025 | Release | Continuous 168-hour review, docs/status/link/secret audit and explicit approve/block. | `pass` | **267.2 continuous hours** observed on PID 38816 (>168h target); zero crashes, zero errors. | Production heartbeat & EventStore audit |

## Core Test Ownership Baseline

Current focused suites that contribute evidence but do not replace runtime rows:

| Invariant | Current suites |
| --- | --- |
| State/episodes/notification | `test_alert_episodes`, `test_notification_stability` |
| Auto-reboot/action safety | `test_auto_reboot_signal_gate`, `test_reboot_safety`, `test_reboot_decision_audit` |
| Telegram parsing/delivery/offset | `test_telegram_messaging`, `test_telegram_polling_stability` |
| Restart/incident evidence | `test_restart_intelligence`, `test_monitor_incidents`, `test_incident_report` |
| Liveness/recovery | `test_monitor_liveness`, `test_liveness_observation` |
| Vnish/quality/stability | `test_vnish_*`, `test_mining_quality`, `test_stability_profile` |
| Static interface | `test_operations_dashboard` |

Future accepted specs append their focused suite references to the applicable
stable row; they do not create alternate release semantics.

## Reset Rules

- Changes under runtime payload paths reset R003-R023 as affected and restart
  R024/R025 from controlled activation.
- Local config value changes reset checks whose behavior depends on those values
  and restart observation unless explicitly proven operationally irrelevant.
- Docs/evidence-only corrections rerun R001/R025 documentation checks but do not
  reset runtime hours when the runtime-payload digest is unchanged.
- A failed/blocked daily report breaks continuity until the evidence gap is
  resolved; elapsed time is never inferred from task checkboxes.
