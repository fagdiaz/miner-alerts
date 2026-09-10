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
| Spec 020 closeout | Closed 2026-08-13 (`e502ab9`) | Runtime activation and observation passed | Elevated restart, new PID, read-only smoke, controlled episode proof and no open P0/P1. |
| Spec 030 messaging quality | Closed 2026-08-13 | Runtime activation and repository push passed 2026-08-13 (`2afd65e`) | New PID/mutex/startup guard plus `/help`, detail, `/status` and `/events` smoke. |
| Spec 021 liveness | Implemented, activated and SCM recovery-proven 2026-08-13 | D+1 passed 2026-08-15 (86,700s); D+3 through 2026-08-17 | Kill/hang/stale-worker tests, one controlled SCM recovery, new PID/mutex/startup guard/heartbeat and D+1/D+3. |
| Spec 022 acquisition | T006 sequential fallback wiring & compact UX completed 2026-08-15 | Activation only after Spec 021 D+3, then shadow/review window | Shadow comparison, bounded requests/latency, unchanged state/action/offset, D+1/D+3. |
| Spec 023 evidence fusion | 2026-09-11 to 2026-09-20 | 2026-09-21 to 2026-09-24 | Known-incident replay, no unsupported confirmed cause, bounded query and D+1/D+3. |
| Spec 024 electrical discovery | 2026-09-25 to 2026-10-02 | 2026-10-03 to 2026-10-05 | Supported adapter with 72-hour shadow proof, or explicit blocked hardware decision. |
| Spec 025 metrics/Grafana | 2026-10-06 to 2026-10-15 | 2026-10-16 to 2026-10-19 | Redaction/cardinality/resource proof, rebuild from files, outage isolation, D+1/D+3. |
| Spec 026 Hashcore inventory | 2026-10-20 to 2026-10-26 | 2026-10-27 to 2026-10-29 | Metadata-only/zero-process proof, complete risk matrix for evidenced commands, sanitized artifacts, exact allowlist timeout/no-window proof when available, and unchanged action scope; blocked invocation is valid while the allowlist is empty. |
| Spec 028 backup/restore | 2026-10-30 to 2026-11-08 | 2026-11-09 to 2026-11-12 | Scheduled verified backup, retention/path proof and successful staging restore. |
| Spec 027 interface decision | Closed 2026-08-30 (`no_build`) | Scorecard executed; all P1 workflows passed by Telegram/Grafana/HTML; conditional paths absent | Three-run fixed P1 scorecard passed, no-build formal decision recorded. |
| Spec 029 release stabilization | Closed 2026-09-07 (`approved`) | Terminal dependency manifest, R001-R025, restore drill and 267.2h continuous soak verified | Complete matrix R001-R025 pass, 0 open P0/P1, approve decision. |
| Spec 031 callbacks | Closed 2026-09-07 | 1-Tap inline keyboards on episode alerts & 2-step reboot | 14 unit tests PASS, single-use token registry. |
| Spec 032 charts | Closed 2026-09-07 | In-memory visual PNG curves via `/chart` | 6 unit tests PASS, 0 disk files. |
| Spec 033 snooze | Closed 2026-09-07 | `/snooze`, `/unsnooze`, `/snoozed`, 1-Tap alert button | 12 unit tests PASS, auto-reboot hard block. |
| Spec 034 digest | Closed 2026-09-07 | Daily executive digest at 08:00 AM & `/digest` | 10 unit tests PASS, 27.2ms query latency. |
| Spec 035 cooling | Closed 2026-09-07 | `/fans`, thermal headroom to 85°C, `COOLING_WARNING` | 14 unit tests PASS, streak filter. |
| Spec 036 efficiency | Closed 2026-09-07 | `/efficiency`, J/TH real-time tracking, `EFFICIENCY_WARNING` | 12 unit tests PASS, streak filter. |
| Spec 037 presets | Closed 2026-09-07 | `/presets`, Vnish autotuning & downclock tracking | 11 unit tests PASS, 1.77ms query latency. |
| Spec 038 v3 release | Closed 2026-09-07 (`approved`) | Multi-threading concurrency audit, thread-safety hardening | 19 concurrency tests PASS, 514 total tests PASS, v3.0.0 approved. |
| Spec 039 fan governor | Closed 2026-09-08 (`approved`) | Vnish fan governor, target 83°C, fail-safe 100%, active in production | 12 concurrency tests PASS, 549 tests PASS. |
| Spec 040 dynamic presets | Closed 2026-09-08 (`approved`) | Preset balancer, elevator cascade & thermal step-down, active in production | 23 tests PASS (14 unit + 9 integration), 576 tests PASS. |
| Spec 041 modular architecture | Closed 2026-09-08 (`approved`) | Modular domain split into app/core, app/vnish, app/governance, app/telegram | 587 tests PASS, 83 payload files. |
| Spec 042 shim purge | Closed 2026-09-08 (`approved`) | Complete purge of 22 shims, direct canonical imports across all tests | 587 tests PASS, 60 payload files. |
| Spec 043 command center | Closed 2026-09-08 (`approved`) | Telegram interactive command center /menu, inline keyboards, 2-step reboot, rich UI | 17 tests PASS, 602 tests PASS, 61 payload files. |
| Spec 044 silent mode | Closed 2026-09-08 (`approved`) | Modo silencio (40%-70% PWM), persistent timer, C1-C4 compliance, thermal guard 83.5°C | 17 tests PASS, 621 tests PASS, active in production under PID 58344. |
| Spec 045 help center | Closed 2026-09-08 (`approved`) | Centro de ayuda móvil /help con categorías interactivas y tarjetas <= 32 cols | 30 tests PASS, 651 tests PASS. |
| Spec 046 mobile cards v1 | Closed 2026-09-09 (`approved`) | Mobile-First layout para /status, /fans, /efficiency, /presets | 12 tests PASS, 663 tests PASS. |
| Spec 047 mobile cards v2 | Closed 2026-09-09 (`approved`) | Mobile-First layout para /balancer, /elevadores, /digest, /snoozed, /events | 24 tests PASS, 687 tests PASS. |
| Spec 048 safe fleet shutdown | Closed 2026-09-09 (`approved`) | Apagado seguro, selector táctil de 1 a 4 mineros, purga térmica 45s, auto-snooze 4h y /resume | 34 tests PASS, 721 tests PASS, validado en maniobra real en vivo. |

## Milestones

| Date | Milestone | Evidence required |
| --- | --- | --- |
| 2026-08-13 | Spec 020 release gate closed | Spec 020 T020, runtime logs and observed Telegram behavior. |
| 2026-08-14 | Spec 021 D+1 review | Scheduled liveness observation artifact and no open P0/P1. |
| 2026-08-16 | Spec 021 D+3 decision | Repeated liveness evidence and close/extend decision. |
| 2026-09-10 | Acquisition contract stable | Authoritative envelope and shadow comparison. |
| 2026-09-24 | Incident assessment available | Deterministic replay and confidence audit. |
| 2026-10-05 | Electrical decision made | Supported source or explicit blocked dependency. |
| 2026-10-19 | Local observability available | Prometheus/Grafana isolation and resource evidence. |
| 2026-10-29 | Hashcore surface known | Complete conservative inventory. |
| 2026-11-12 | Recoverability proven | Verified backup plus staging restore. |
| 2026-08-30 | Interface scope closed | Scorecard completed; no-build formal decision recorded with zero missing fields. |
| 2026-09-07 | V2 release decision | Complete matrix, 267.2h soak, docs audit and approve record. |
| 2026-09-07 | V3 Telegram Max & Intelligence (Specs 031-037) | All 7 modules implemented, tested and verified. |
| 2026-09-07 | V3 Release Decision (Spec 038) | 514 tests PASS, 267.3h soak, concurrency hardened, v3.0.0 approve record. |
| 2026-09-08 | V3.1 Governance & Autotuning (Specs 039-040) | Fan Governor and Dynamic Preset Balancer active in production. |
| 2026-09-08 | V3.2 Domain Reorganization & Shim Purge (Specs 041-042) | 22 shims purged, clean app/ structure, 587 tests PASS. |
| 2026-09-08 | V3.3 Interactive Control & Silent Mode (Specs 043-044) | RFC approved, 621 tests PASS, release audit verified, active in production under PID 58344. |
| 2026-09-09 | V3.4 Telegram Mobile UX Harmonization (Specs 045-047) | Centro de ayuda, navegación por categorías y todas las tarjetas adaptadas a <= 32 columnas, 687 tests PASS. |
| 2026-09-09 | V3.5 Safe Fleet Shutdown & Electrical Maintenance (Spec 048) | Selector táctil multiselección, purga térmica de 45s, maniobra física real validada en caliente, 721 tests PASS. |

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
