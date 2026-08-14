# Research: Operator Interface Decision

## Baseline Findings

- Telegram is the existing remote control surface.
- Static HTML already provides local incident/fleet summaries.
- The existing generator is self-contained, opens SQLite URI `mode=ro`, bounds
  rows/windows, escapes persisted text and imports no monitor/network/subprocess
  path. It generates a file and is not a listening service.
- Grafana is optimized for time-series dashboards and should be evaluated first.
- FastAPI provides typed validation and automatic OpenAPI documentation.
- A remote or action UI would require substantially broader security design.

## Decisions

1. Use a no-build gate before framework adoption.
2. Select FastAPI only for an unmet local read-only query workflow.
3. Prefer server-rendered HTML/HTMX over React at this scope.
4. Keep web actions and remote exposure outside this planning horizon.
5. Require three consecutive timed runs per eligible P1 workflow/interface and
   approve an MVP only for exact fields missed by every existing owner.
6. If built, use GET/HEAD allowlisted routes, loopback IPv4 only, no proxy/CORS,
   SQLite `mode=ro` plus `query_only`, 50/200 pagination and 30-day windows.
7. Do not use SQLite `immutable=1` against the live WAL database because it may
   ignore changes/sidecars; read-only/query-only is the required boundary.

## Rejected Or Deferred Alternatives

- React by default because it adds build/runtime complexity without a proven workflow.
- Dockerizing access to live SQLite because file/locking and path complexity add risk.
- Web action buttons because they duplicate dangerous Telegram controls.
- Public LAN binding without an authentication/security spec.
- Approving FastAPI because it is popular or educational rather than because a
  P1 workflow has a measured unresolved field.
- A generic SQL/export endpoint or raw firmware-log browser.
- Mounting live SQLite into a UI container or importing the monitor to reuse
  runtime objects.

## External Validation Sources

- FastAPI features and OpenAPI: https://fastapi.tiangolo.com/features/
- Grafana dashboards: https://grafana.com/docs/grafana/latest/visualizations/dashboards/
- Grafana provisioning: https://grafana.com/docs/grafana/latest/administration/provisioning/
