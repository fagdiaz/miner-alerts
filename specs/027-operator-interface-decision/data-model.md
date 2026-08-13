# Data Model: Operator Interface Decision

## WorkflowScore

- `workflow_id`: Stable operator task.
- `interface`: Telegram, static HTML, Grafana or MVP.
- `completion_seconds`: Observed duration.
- `complete / accurate`: Outcome.
- `gap`: Specific unmet requirement.

## InterfaceDecision

- `decision`: no_build or fastapi_mvp.
- `approved_scope`: Exact workflows/resources.
- `evidence_refs`: Scorecard and user validation.
- `review_ts`: Decision time.

## IncidentView

- `incident_id / miner_id`: Sanitized identity.
- `started_ts / ended_ts`: Bounded timeline.
- `state / evidence / assessment`: Read-only projection.
- `freshness`: Source age and quality.

## Invariants

- Decision precedes dependency/source creation.
- All web resources are read-only projections.
- Every query is bounded.
- No action/config/secret surface exists.
