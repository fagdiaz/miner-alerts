# Research: Operator Interface Decision

## Baseline Findings

- Telegram is the existing remote control surface.
- Static HTML already provides local incident/fleet summaries.
- Grafana is optimized for time-series dashboards and should be evaluated first.
- FastAPI provides typed validation and automatic OpenAPI documentation.
- A remote or action UI would require substantially broader security design.

## Decisions

1. Use a no-build gate before framework adoption.
2. Select FastAPI only for an unmet local read-only query workflow.
3. Prefer server-rendered HTML/HTMX over React at this scope.
4. Keep web actions and remote exposure outside this planning horizon.

## Rejected Or Deferred Alternatives

- React by default because it adds build/runtime complexity without a proven workflow.
- Dockerizing access to live SQLite because file/locking and path complexity add risk.
- Web action buttons because they duplicate dangerous Telegram controls.
- Public LAN binding without an authentication/security spec.

## External Validation Sources

- FastAPI features and OpenAPI: https://fastapi.tiangolo.com/features/
- Grafana dashboards: https://grafana.com/docs/grafana/latest/visualizations/dashboards/
- Grafana provisioning: https://grafana.com/docs/grafana/latest/administration/provisioning/
