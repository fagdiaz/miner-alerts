# Interface Strategy

**Last reviewed**: 2026-09-07 (Release v2.0.0 Normalized)
**Decision spec**: `specs/027-operator-interface-decision` (Outcome: `no_build`)

## Current Interfaces

- **Telegram**: primary remote alerts and the only write/control surface.
- **Grafana Dashboards**: implemented local read-only observability stack for
  fleet overview, time-series metrics, and monitor liveness (Spec 025).
- **Static HTML dashboard**: implemented read-only fleet, incident, quality and
  decision views generated from SQLite.
- **CLI reports**: diagnostics, incident and Vnish collection workflows.

Telegram remains appropriate for urgent operational interaction, while Grafana
and static HTML provide deep telemetry and fleet comparison without action risk.

## Interface Boundaries

| Need | Preferred surface | Reason |
| --- | --- | --- |
| Immediate alert and acknowledgement | Telegram | Remote, concise and already operational. |
| Confirmed reboot/restart | Telegram only | Existing TTL confirmation, QA gates and audit path. |
| Current fleet overview | Grafana & Static HTML | Side-by-side comparison without action risk. |
| Time-series trends and freshness | Grafana (Spec 025) | Purpose-built Prometheus queries and visualization. |
| Incident evidence | Telegram `/diagnose`, `/e<ID>` & dashboard | Mobile diagnosis and richer local timeline. |
| Ad-hoc web server / FastAPI | Evaluated & rejected (`no_build`) | Scorecard confirmed zero missing fields; attack surface avoided. |

## Evaluated Decision Path

### Static Read-Only Dashboard (Implemented)

Validates the data contract without a server, authentication or new action path.

### Prometheus And Grafana (Implemented in Spec 025)

The native monitor writes a sanitized atomic snapshot. A standalone exporter and
pinned Docker Compose Prometheus/Grafana stack run with local-only host ports.
They receive no config secrets, live database mount or action capability.

### Spec 027 - FastAPI Decision (Closed: `no_build`)

Executed on 2026-08-30 using the fixed scorecard in
`specs/027-operator-interface-decision/workflow-scorecard.md`.
Three consecutive runs across all six operator workflows (W01-W06) confirmed:
- Every P1 workflow target was satisfied well within thresholds (all < 15s).
- Exactly zero missing fields.
- Telegram, Grafana, and the static HTML dashboard cover 100% of operator needs.
- Formal resolution: **`no_build`**. No FastAPI/Uvicorn/HTMX dependencies or
  services were added.

## Controlled Actions UI

Not planned through the v2 horizon. A future action UI would require authentication,
authorization, confirmation TTL, audit logs, CSRF protection, local/network
exposure design and exact parity with Telegram guardrails. Until a separate spec
proves those controls, no web reboot/restart endpoint is allowed.

## Final Decision

Keep Telegram as the control plane. Deepen analysis through static HTML and
Grafana. Spec 027 closed with `no_build`. No web frameworks or APIs were added.
