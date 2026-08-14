# Workflow Scorecard: Operator Interface Decision

## Gate State

The final scorecard is **BLOCKED** until Spec 025 Grafana runtime evidence and
Spec 028 staging restore proof are complete. Current-interface baselines may be
recorded before then, but cannot approve FastAPI or close no-build.

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

## Current Baseline

On 2026-08-13 the existing static generator read the production SQLite database
in read-only mode and produced an ignored 50,741-byte self-contained HTML file
in 2,860 ms. Its five targeted safety/render tests passed. This proves generator
availability only; visual/operator workflow completion and Grafana comparison
remain unverified, so it is not a final scorecard pass.
