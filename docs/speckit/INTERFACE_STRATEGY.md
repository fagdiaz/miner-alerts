# Interface Strategy

**Last reviewed**: 2026-08-13
**Decision spec**: `specs/027-operator-interface-decision`

## Current Interfaces

- **Telegram**: primary remote alerts and the only write/control surface.
- **Static HTML dashboard**: implemented read-only fleet, incident, quality and
  decision views generated from SQLite.
- **CLI reports**: diagnostics, incident and Vnish collection workflows.

Telegram remains appropriate for urgent operational interaction, but it is not
the ideal surface for trends, fleet comparison or long timelines.

## Interface Boundaries

| Need | Preferred surface | Reason |
| --- | --- | --- |
| Immediate alert and acknowledgement | Telegram | Remote, concise and already operational. |
| Confirmed reboot/restart | Telegram only | Existing TTL confirmation, QA gates and audit path. |
| Current fleet overview | Static HTML now; Grafana later | Better side-by-side comparison without action risk. |
| Time-series trends and freshness | Grafana after Spec 025 | Purpose-built queries and visualization. |
| Incident evidence | Telegram `/e<ID>` plus dashboard | Fast mobile detail and richer local timeline. |
| Ad-hoc read-only API | FastAPI only if justified | Typed local API and OpenAPI, but another service to operate. |

## Planned Decision Path

### Current - Static Read-Only Dashboard

Already implemented. It validates the data contract without a server, auth or
new action path. Near-term work should improve data freshness and observability,
not replace this UI.

### Spec 025 - Prometheus And Grafana

The native monitor writes a sanitized atomic snapshot. A separate exporter,
Prometheus and Grafana run as optional auxiliary containers with local-only host
ports. They receive no config secrets, live database mount or action capability.
This is the preferred next interface investment because it improves trends and
monitor observability without changing the control plane.

### Spec 027 - FastAPI Decision Gate

After operator use of static HTML and Grafana, time a written workflow scorecard.
If every P1 workflow passes, close Spec 027 as `no-build`. Build a FastAPI MVP
only for an explicitly failed local read-only workflow.

The scorecard is fixed in `specs/027-operator-interface-decision/workflow-scorecard.md`:
three consecutive runs per eligible P1 interface, exact required fields and
30/60/90/120-second targets. One passing existing owner is sufficient. P2
convenience or adopting a popular framework is not a build justification. Until
Spec 025 Grafana and Spec 028 restore evidence pass, the decision is `blocked`.

If built:

- bind only to `127.0.0.1`;
- disable proxy trust/CORS and allow only exact GET/HEAD routes;
- read SQLite with `mode=ro` plus `query_only` through default-50/max-200,
  maximum-30-day queries; do not use `immutable=1` on the live WAL database;
- expose no tokens, miner credentials or raw firmware logs;
- keep every endpoint read-only;
- add HTMX only for a proven interaction need;
- do not adopt React solely for technology exposure.

If no-build wins, FastAPI/Uvicorn/HTMX dependencies, source, templates and a
Windows service remain absent. The decision artifact itself closes the spec.

## Controlled Actions UI

Not planned through the v2 horizon ending 2026-12-20. A future action UI would require authentication,
authorization, confirmation TTL, audit logs, CSRF protection, local/network
exposure design and exact parity with Telegram guardrails. Until a separate spec
proves those controls, no web reboot/restart endpoint is allowed.

## Decision

Keep Telegram as the control plane. Evolve analysis through static HTML and
Grafana first. Spec 027 may validly close with no code. FastAPI is conditional,
HTMX is optional for a proven filter/refresh need, and React remains deferred.
