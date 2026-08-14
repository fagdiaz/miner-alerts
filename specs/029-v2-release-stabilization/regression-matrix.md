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

## Mandatory Matrix

| ID | Area | Check | Required evidence |
| --- | --- | --- | --- |
| R001 | Freeze | Git identity, clean tracked tree and runtime-artifact ignore audit. | Commit, status, ignore/secret scan. |
| R002 | Freeze | Runtime payload, Python/dependency, schema, config-example, service/task identities. | Release manifest hashes/versions. |
| R003 | Build | Full deterministic unit suite from the approved environment. | Exact command, count, duration, result. |
| R004 | Build | Python, PowerShell and JSON syntax for every applicable artifact. | Per-file/type result. |
| R005 | State | State-machine transitions/hysteresis remain fixture-equivalent. | State/notification focused tests. |
| R006 | Startup | Persisted LOW timers sanitized and startup guard blocks actions. | Startup fixture plus QA action spy. |
| R007 | Auto-reboot | Valid signal, sustained LOW, fleet/thermal/firmware, cooldown/window and QA gates preserve precedence. | Focused branch matrix, zero unexpected action. |
| R008 | Telegram | Help/status/info/history/diagnose and invalid command paths reply without silence. | QA command matrix and delivery trace. |
| R009 | Telegram actions | Reboot/restart/bulk retain TTL, target binding, cooldown and confirmation. | QA blocked-action matrix; no real action required. |
| R010 | Polling | `update_id` is processed once and offset advances monotonically without skip/replay. | Poll fixture and bounded runtime trace. |
| R011 | Instance | Mutex rejects a second monitor and SCM owns one process tree. | Process/mutex/service evidence. |
| R012 | Episodes | Grouping, brief debounce, reminder cadence, recovery path and status consistency. | Episode fixtures plus controlled read-only smoke. |
| R013 | Incidents | Restart attribution and evidence detail remain conservative and prompt. | Known-event replay and Telegram render. |
| R014 | Liveness | Watchdog detects process/tick/worker failures, dedupes and recovers without miner authority. | Synthetic scenarios plus SCM proof/observation. |
| R015 | Acquisition | Authoritative epoch/shadow behavior preserves state/action/offset semantics. | Spec 022 comparison or disposition evidence. |
| R016 | Fusion | Observed/suspected/confirmed wording and idempotent bounded evidence queries. | Canonical replay or disposition evidence. |
| R017 | Electrical | External source adapter passes no-write/shadow proof, or hardware dependency is blocked explicitly. | Spec 024 terminal evidence. |
| R018 | Metrics | Snapshot schema, freshness fail-closed, cardinality/redaction and auxiliary outage isolation. | Spec 025 tests/runtime or disposition. |
| R019 | Hashcore | Metadata-only zero-process result; any invocation exact-allowlisted; action scope unchanged. | Spec 026 inventory/invariants or disposition. |
| R020 | Backup | Concurrent online backup, manifest/retention and staging restore pass. | Spec 028 production backup and restore report. |
| R021 | Interface | Fixed workflow scorecard yields no-build or approved read-only MVP with boundary proof. | Spec 027 terminal decision. |
| R022 | Activation | One controlled activation proves PID, mutex, config source/hash, QA source, guard, DB and workers. | Sanitized startup/service envelope. |
| R023 | Isolation | Stopping each auxiliary accepted component leaves monitor/Telegram/actions operational. | Per-component outage matrix. |
| R024 | Observation | Continuous 72-hour checkpoint with daily reports and no open P0/P1. | Reports day 1-3 and checkpoint. |
| R025 | Release | Continuous 168-hour review, docs/status/link/secret audit and explicit approve/block. | Reports day 4-7 plus final manifest/decision. |

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
