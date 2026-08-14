# Data Model: Operator Interface Decision

## WorkflowScore

- `workflow_id`: Stable operator task.
- `interface`: Telegram, static HTML, Grafana or MVP.
- `completion_seconds`: Observed duration.
- `steps`: Positive operator interaction count.
- `complete / accurate / freshness_visible / within_target`: Explicit outcomes.
- `missing_fields`: Finite required-field identifiers.
- `evidence_ref`: Sanitized run evidence.
- `pass`: Conjunction of all pass dimensions.

## InterfaceDecision

- `decision`: blocked, no_build or fastapi_mvp.
- `dependency_evidence`: Spec 025 and 028 exit references.
- `workflow_owners`: Passing existing owner for each P1 workflow.
- `approved_scope`: Exact workflows/resources.
- `failed_fields`: Exact P1 fields absent from every existing interface.
- `evidence_refs`: Scorecard and user validation.
- `reviewed_at_utc / reviewer`: Decision audit fields.

## ApiHealth

- `status`: ok, stale, database_missing, database_busy or schema_unsupported.
- `generated_at_utc / database_age_seconds`: Sanitized freshness.
- `schema_version / supported`: Finite compatibility state.
- `reason_code`: Stable reason without local exception text.

## ReadOnlyMinerView

- `miner_id`: Logical configured ID; no host/IP.
- `state / responded / rate_ths / threshold_ths`: Current projection.
- `sample_at_utc / sample_age_seconds / stale`: Visible freshness.
- `episode_active / episode_duration_seconds`: Current irregular episode.

## IncidentView

- `incident_id / miner_id`: Sanitized identity.
- `started_ts / ended_ts`: Bounded timeline.
- `state / evidence / assessment`: Read-only projection.
- `freshness`: Source age and quality.

## Page

- `items`: At most 200 typed projections.
- `next_cursor`: Opaque timestamp-plus-ID cursor or null.
- `limit`: Requested/effective bound.
- `window_start_utc / window_end_utc`: At most 30 days.

## Invariants

- Decision precedes dependency/source creation.
- All web resources are read-only projections.
- Every query is bounded.
- No action/config/secret surface exists.
- P1 scorecard rows have exactly three runs per eligible pair before decision.
- No-build creates no conditional runtime artifacts.
- Cursors cannot contain SQL, free text, filesystem paths or credentials.
