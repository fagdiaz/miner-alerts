# Miner Alerts Delivery Plan

**Planning baseline**: 2026-08-13
**Planning horizon**: 2026-08-13 to 2026-12-20
**Source program**: `docs/speckit/SPEC_PROGRAM.md`
**Source backlog**: `docs/speckit/ROADMAP.md`

## Purpose

This is the estimated implementation, observation and bug-fix calendar. It is
not evidence of completion. Dates move when runtime findings require more time;
safety gates are not compressed to recover an estimate.

## Scheduling Rules

1. Only one monitor-runtime or action-adjacent spec may be active in production.
2. Read-only discovery may overlap only when it does not change the monitor or
   consume the same operator maintenance window.
3. Every production-affecting release has implementation, controlled activation,
   D+1/D+3 review and a documented fix window.
4. High-risk work starts with red contracts and QA no-action proof.
5. P0/P1 incidents stop roadmap work. Containment and focused regression take
   precedence over calendar dates.
6. Friday after 16:00 local time is documentation/read-only work only, except an
   explicitly approved emergency containment.
7. A code change during soak resets affected validation and observation clocks.

## Estimated Calendar

| Spec / package | Implementation window | Activation and review/fix window | Exit gate |
| --- | --- | --- | --- |
| Spec 020 closeout | 2026-08-13 to 2026-08-14 | 2026-08-15 to 2026-08-17 | Elevated restart, new PID, read-only smoke, controlled episode proof and no open P0/P1. |
| Spec 030 messaging quality | Closed 2026-08-13 | Runtime activation and repository push passed 2026-08-13 (`2afd65e`) | New PID/mutex/startup guard plus `/help`, detail, `/status` and `/events` smoke. |
| Spec 021 liveness | Implemented 2026-08-13; activation pending | Activation through 2026-08-14; D+1/D+3 through 2026-08-17 | Kill/hang/stale-worker tests, SCM recovery, mutex/startup guard, D+1/D+3. |
| Spec 022 acquisition | 2026-08-28 to 2026-09-06 | 2026-09-07 to 2026-09-10 | Shadow comparison, bounded requests/latency, unchanged state/action/offset, D+1/D+3. |
| Spec 023 evidence fusion | 2026-09-11 to 2026-09-20 | 2026-09-21 to 2026-09-24 | Known-incident replay, no unsupported confirmed cause, bounded query and D+1/D+3. |
| Spec 024 electrical discovery | 2026-09-25 to 2026-10-02 | 2026-10-03 to 2026-10-05 | Supported adapter with 72-hour shadow proof, or explicit blocked hardware decision. |
| Spec 025 metrics/Grafana | 2026-10-06 to 2026-10-15 | 2026-10-16 to 2026-10-19 | Redaction/cardinality/resource proof, rebuild from files, outage isolation, D+1/D+3. |
| Spec 026 Hashcore inventory | 2026-10-20 to 2026-10-26 | 2026-10-27 to 2026-10-29 | Complete risk matrix, sanitized artifacts, timeout/no-window and unchanged action scope. |
| Spec 028 backup/restore | 2026-10-30 to 2026-11-08 | 2026-11-09 to 2026-11-12 | Scheduled verified backup, retention/path proof and successful staging restore. |
| Spec 027 interface decision | 2026-11-13 to 2026-11-22 | 2026-11-23 to 2026-11-26 | No-build decision, or local read-only MVP workflow/security/outage proof. |
| Spec 029 release stabilization | 2026-11-27 to 2026-12-06 | 2026-12-07 to 2026-12-20 | 72-hour soak, seven-day final review, restore and documentation baseline; no P0/P1. |

## Milestones

| Date | Milestone | Evidence required |
| --- | --- | --- |
| 2026-08-17 | Spec 020 release gate closed | Spec 020 T020, runtime logs and observed Telegram behavior. |
| 2026-08-27 | Monitor self-liveness protected | Watchdog and SCM kill/hang/recovery evidence. |
| 2026-09-10 | Acquisition contract stable | Authoritative envelope and shadow comparison. |
| 2026-09-24 | Incident assessment available | Deterministic replay and confidence audit. |
| 2026-10-05 | Electrical decision made | Supported source or explicit blocked dependency. |
| 2026-10-19 | Local observability available | Prometheus/Grafana isolation and resource evidence. |
| 2026-10-29 | Hashcore surface known | Complete conservative inventory. |
| 2026-11-12 | Recoverability proven | Verified backup plus staging restore. |
| 2026-11-26 | Interface scope closed | No-build or approved local read-only MVP evidence. |
| 2026-12-20 | V2 release decision | Complete matrix, soak, docs audit and approve/block record. |

## Review And Bug-Fix Rhythm

| Frequency | Activity | Output |
| --- | --- | --- |
| After every activation | Verify PID, mutex, config path/hash, QA mode, startup guard, EventStore, worker/heartbeat freshness and no immediate action. | Active spec `evidence.md`. |
| D+1 | Inspect false/missed alerts, command delivery, sample age, service health, database and auxiliary errors. | D+1 evidence plus issue priority. |
| D+3 | Repeat reliability review and close or extend the observation gate. | D+3 decision in evidence. |
| Wednesday | Triage P0/P1/P2 and recalculate later dates/dependencies. | Roadmap/calendar update when needed. |
| Friday | Full regression and documentation sweep; late deployment only for read-only or emergency work. | Test and `git diff --check` evidence. |
| First Monday monthly | Reliability review: missed/false alerts, restarts, actions, liveness, storage and collector health. | SQLite/metrics report and development-log summary. |

## Bug Priority And Response

| Priority | Definition | Response target | Calendar effect |
| --- | --- | --- | --- |
| P0 | Unsafe/duplicate action, missed sustained outage, secrets exposure, monitor unavailable or data-loss risk. | Immediate triage and same-day containment. | Stop all roadmap work; focused hotfix and full safety regression. |
| P1 | False critical alert, command silence, stale/contradictory status, delayed incident evidence or restore failure. | Within one working day. | Resolve in current review window; later dates move. |
| P2 | Wording, non-critical dashboard/log issue or documentation gap. | Weekly triage. | Batch into next read-only/docs window. |

## Definition Of Ready

A package starts only when:

- its predecessor exit gate and required D+1 review are complete;
- requirements, plan, tasks, contracts and checklist have no unresolved critical
  inconsistency;
- hardware/API samples exist or the work is explicitly discovery-only;
- action authority, rollback, validation and observation are written;
- elevated access, Docker or device access required for the package is available;
- no open production P0/P1 invalidates the baseline.

## Definition Of Done

A package closes only when:

- all tasks and acceptance scenarios have exact evidence;
- targeted/full tests and applicable syntax/config/PowerShell checks pass;
- state/action/polling invariants pass where relevant;
- controlled activation is observed when a long-lived component changed;
- backup/restore or rollback proof exists where persistence/runtime changes;
- D+1/D+3 (and longer package-specific soak) has no unresolved P0/P1;
- evidence, roadmap, calendar, strategy docs and development log agree;
- real config, state, backups, logs, credentials and addresses remain outside Git.

## Calendar Change Policy

- Update this file and `ROADMAP.md` in the same documentation change.
- Record the trigger and dependency impact in the active spec evidence.
- Do not backdate missed work or report an expired estimate as completed.
- Re-run the cross-spec dependency sweep when a package is split, added,
  reordered, blocked or deferred.
