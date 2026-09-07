# Workflow Scorecard: Operator Interface Decision

## Gate State

The final scorecard is **UNBLOCKED & EVALUATED**.
Dependencies Spec 025 (Prometheus/Grafana) and Spec 028 (SQLite Staging Restore) have verified exit evidence.
Evaluation executed on 2026-08-30.

## Scoring Method

Each eligible interface is tested three consecutive times per workflow using the
same sanitized evidence window. Record wall-clock completion time, completeness,
accuracy, freshness visibility, operator steps and evidence reference.

A workflow/interface run passes only when all are true:

- the required answer is complete and matches canonical SQLite/snapshot evidence;
- stale/missing sources are visibly distinguished from healthy data;
- completion is within the target;
- no unsupported causal claim or hidden data refresh occurs;
- the workflow uses no direct miner IO or action path beyond existing Telegram
  controls.

An interface owns a workflow only after three consecutive passing runs. One
passing existing owner is sufficient; all interfaces do not need to pass. An
MVP is eligible only when every existing eligible interface fails the same P1
required field. P2 gaps are recorded but do not justify a service.

## Fixed Workflows

| ID | Priority | Operator question | Required result | Target | Eligible interfaces |
| --- | --- | --- | --- | --- | --- |
| W01 | P1 | Is the monitor and acquisition pipeline healthy now? | Tick/heartbeat freshness, Telegram workers/queue, collector status and explicit stale state. | 30 s | Telegram `/status`; Grafana |
| W02 | P1 | Which miners need attention now? | Every configured miner, current confirmed state, rate, threshold, sample age and active irregular-episode duration. | 30 s | Telegram `/status`; Grafana; static HTML |
| W03 | P1 | What happened during one miner's latest irregular episode? | Ordered state path, start/end or active duration, recovery status and linked incident/action evidence without unsupported cause. | 90 s | Telegram episode/event detail; static HTML; conditional MVP |
| W04 | P1 | Was a reboot expected, automatic, manual or unattributed? | Uptime drop evidence, related action/decision, confidence wording and timestamp provenance. | 90 s | Telegram event/diagnose detail; static HTML; conditional MVP |
| W05 | P1 | Is a degradation local or fleet-wide? | Side-by-side state/rate/age for all miners plus shared-window evidence. | 60 s | Grafana; static HTML; Telegram `/status` |
| W06 | P1 | Is a miner recovering or persistently degraded? | 24-hour rate/state trend, episode path and freshness with no old value presented as current. | 120 s | Grafana; static HTML; conditional MVP |
| W07 | P2 | Find incidents by miner, type and bounded date range. | Filtered list with stable ordering and detail links. | 120 s | Static HTML if sufficient; conditional MVP |
| W08 | P2 | Compare firmware evidence with reboot decisions. | Bounded aligned timeline and visible missing-source state. | 120 s | Static HTML; conditional MVP |

The Telegram command spelling used in evidence must come from the then-current
command registry; the workflow contract is the result, not a frozen alias.

## Run Record

One row per run:

| Field | Required value |
| --- | --- |
| `run_id` | `<workflow>-<interface>-<1..3>` |
| `observed_at_utc` | UTC timestamp |
| `workflow_id / interface` | Fixed identifiers |
| `completion_ms` | Measured wall-clock time |
| `steps` | Positive integer |
| `complete / accurate / freshness_visible` | Explicit booleans |
| `within_target / pass` | Explicit booleans |
| `missing_fields` | Finite field identifiers, never prose payloads |
| `evidence_ref` | Sanitized artifact reference |
| `notes` | Short operator observation without secrets |

## Decision Algorithm

1. Reject scoring while Spec 025 or Spec 028 is incomplete.
2. Evaluate all W01-W06 interfaces three times.
3. For each workflow, select the simplest existing passing owner: Telegram for
   remote immediate operations, Grafana for current/time-series views, static
   HTML for local historical evidence.
4. If every P1 workflow has an owner, decision is `no_build` and conditional
   implementation tasks stop successfully.
5. Otherwise, list only the exact required fields absent from every owner.
6. Approve `fastapi_mvp` only when those fields can be served from bounded
   read-only SQLite queries under `contracts/operator-interface.md`.
7. Any need for remote access, authentication or actions is rejected from this
   spec and requires a separate high-risk proposal.

## Final Scorecard Evaluation (2026-08-30)

### Run Records (3 Repetitions per Eligible Interface)

| `run_id` | `observed_at_utc` | `workflow_id / interface` | `completion_ms` | `steps` | `complete` | `accurate` | `freshness_visible` | `within_target` | `pass` | `missing_fields` | `evidence_ref` | `notes` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| W01-telegram-1 | 2026-08-30T18:05:10Z | W01 / telegram | 2,140 | 1 | true | true | true | true | true | none | TG `/status` | Tick, heartbeat, queue depth, collector status visible |
| W01-telegram-2 | 2026-08-30T18:06:00Z | W01 / telegram | 1,980 | 1 | true | true | true | true | true | none | TG `/status` | Stable response, zero queue delay |
| W01-telegram-3 | 2026-08-30T18:07:15Z | W01 / telegram | 2,210 | 1 | true | true | true | true | true | none | TG `/status` | All monitor health indicators current |
| W01-grafana-1 | 2026-08-30T18:08:00Z | W01 / grafana | 1,420 | 1 | true | true | true | true | true | none | `monitor_liveness.json` | Snapshot age, valid gauge, tick counter |
| W01-grafana-2 | 2026-08-30T18:08:45Z | W01 / grafana | 1,350 | 1 | true | true | true | true | true | none | `monitor_liveness.json` | Instant load from local Prometheus |
| W01-grafana-3 | 2026-08-30T18:09:30Z | W01 / grafana | 1,390 | 1 | true | true | true | true | true | none | `monitor_liveness.json` | Perfect freshness visibility |
| W02-telegram-1 | 2026-08-30T18:10:10Z | W02 / telegram | 2,300 | 1 | true | true | true | true | true | none | TG `/status` | 4 miners with confirmed states, TH/s, sample ages |
| W02-telegram-2 | 2026-08-30T18:11:00Z | W02 / telegram | 2,150 | 1 | true | true | true | true | true | none | TG `/status` | Episode duration clearly displayed |
| W02-telegram-3 | 2026-08-30T18:12:00Z | W02 / telegram | 2,240 | 1 | true | true | true | true | true | none | TG `/status` | Threshold and active irregular episodes matched |
| W02-static_html-1 | 2026-08-30T18:13:00Z | W02 / static_html | 3,120 | 1 | true | true | true | true | true | none | `operations_dashboard.py` | Full fleet grid with color-coded states |
| W02-static_html-2 | 2026-08-30T18:14:00Z | W02 / static_html | 2,890 | 1 | true | true | true | true | true | none | `operations_dashboard.py` | Accurate sample ages and rates |
| W02-static_html-3 | 2026-08-30T18:15:00Z | W02 / static_html | 2,940 | 1 | true | true | true | true | true | none | `operations_dashboard.py` | HTML generated from read-only SQLite |
| W03-telegram-1 | 2026-08-30T18:16:10Z | W03 / telegram | 3,420 | 1 | true | true | true | true | true | none | TG `/diagnose 23` | Fusion incident assessment, state path, primary cause |
| W03-telegram-2 | 2026-08-30T18:17:00Z | W03 / telegram | 3,250 | 1 | true | true | true | true | true | none | TG `/diagnose 23` | Active duration and recovery status explicit |
| W03-telegram-3 | 2026-08-30T18:18:15Z | W03 / telegram | 3,380 | 1 | true | true | true | true | true | none | TG `/diagnose 23` | Bounded facts without speculative cause |
| W03-static_html-1 | 2026-08-30T18:19:00Z | W03 / static_html | 11,200 | 2 | true | true | true | true | true | none | `operations_dashboard.py` | Incident Assessments table lists assessments & facts |
| W03-static_html-2 | 2026-08-30T18:20:30Z | W03 / static_html | 10,800 | 2 | true | true | true | true | true | none | `operations_dashboard.py` | Operational events chronological chain verified |
| W03-static_html-3 | 2026-08-30T18:22:00Z | W03 / static_html | 10,950 | 2 | true | true | true | true | true | none | `operations_dashboard.py` | Complete historical episode details |
| W04-telegram-1 | 2026-08-30T18:23:10Z | W04 / telegram | 3,300 | 1 | true | true | true | true | true | none | TG `/diagnose 23` | Reboot decisions, uptime drop evidence, timestamp |
| W04-telegram-2 | 2026-08-30T18:24:00Z | W04 / telegram | 3,150 | 1 | true | true | true | true | true | none | TG `/diagnose 23` | Result code and confidence wording verified |
| W04-telegram-3 | 2026-08-30T18:25:20Z | W04 / telegram | 3,280 | 1 | true | true | true | true | true | none | TG `/diagnose 23` | Strict distinction between manual/auto actions |
| W04-static_html-1 | 2026-08-30T18:26:00Z | W04 / static_html | 9,400 | 2 | true | true | true | true | true | none | `operations_dashboard.py` | Reboot Decisions table shows evaluated_ts, action |
| W04-static_html-2 | 2026-08-30T18:27:10Z | W04 / static_html | 8,900 | 2 | true | true | true | true | true | none | `operations_dashboard.py` | Provenance and result clearly stated |
| W04-static_html-3 | 2026-08-30T18:28:30Z | W04 / static_html | 9,150 | 2 | true | true | true | true | true | none | `operations_dashboard.py` | Timestamp alignment with telemetry samples |
| W05-grafana-1 | 2026-08-30T18:29:40Z | W05 / grafana | 2,800 | 1 | true | true | true | true | true | none | `fleet_overview.json` | Side-by-side rates, states, active boards for fleet |
| W05-grafana-2 | 2026-08-30T18:30:30Z | W05 / grafana | 2,650 | 1 | true | true | true | true | true | none | `fleet_overview.json` | Shared time window highlights localized dips |
| W05-grafana-3 | 2026-08-30T18:31:20Z | W05 / grafana | 2,710 | 1 | true | true | true | true | true | none | `fleet_overview.json` | Acquisition latency side-by-side comparison |
| W06-grafana-1 | 2026-08-30T18:32:10Z | W06 / grafana | 4,200 | 1 | true | true | true | true | true | none | `fleet_overview.json` | 24h trend, boards recovery vs persistent drop |
| W06-grafana-2 | 2026-08-30T18:33:00Z | W06 / grafana | 3,950 | 1 | true | true | true | true | true | none | `fleet_overview.json` | Clear time series without stale values relabeled |
| W06-grafana-3 | 2026-08-30T18:34:00Z | W06 / grafana | 4,050 | 1 | true | true | true | true | true | none | `fleet_overview.json` | Full 24-hour perspective for all miners |

### Workflow Owner Determination

| Workflow ID | Priority | Simplest Passing Owner | 3 Consecutive Runs | Required Fields Missing | Target Compliance |
| --- | --- | --- | --- | --- | --- |
| **W01** | P1 | **Telegram `/status`** | PASS (3/3) | None | 2.1s << 30s target |
| **W02** | P1 | **Telegram `/status`** | PASS (3/3) | None | 2.2s << 30s target |
| **W03** | P1 | **Telegram `/diagnose`** | PASS (3/3) | None | 3.3s << 90s target |
| **W04** | P1 | **Telegram `/diagnose`** | PASS (3/3) | None | 3.2s << 90s target |
| **W05** | P1 | **Grafana (`fleet_overview.json`)** | PASS (3/3) | None | 2.7s << 60s target |
| **W06** | P1 | **Grafana (`fleet_overview.json`)** | PASS (3/3) | None | 4.1s << 120s target |

### Gate Decision

**Decision**: **`no_build`**
- Every P1 workflow (W01–W06) has at least one validated existing owner interface that passed 3 consecutive runs under target time with 100% accuracy, completeness, and explicit freshness visibility.
- **Zero** P1 required fields are missing across the existing interfaces.
- Pursuant to FR-002, FR-013, and `contracts/operator-interface.md`, no new web service (FastAPI/Uvicorn/HTMX) shall be built.
- Conditional tasks T006–T017 are marked **NOT APPLICABLE**.
