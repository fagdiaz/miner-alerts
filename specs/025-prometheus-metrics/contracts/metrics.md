# Contract: Metrics Snapshot And Exposition

## Purpose

Define sanitized snapshot, stable metric families, cardinality budget and local-only topology.

## Inputs

- Spec 021 heartbeat/liveness fields.
- Spec 022 acquisition envelopes and current episode/state summary.

## Outputs

- Versioned atomic snapshot.
- Prometheus text endpoint inside the observability network.
- Provisioned Grafana dashboards.

## Failure And Safety Contract

- No secrets or action imports.
- Stale snapshots fail visibly.
- Container outage cannot affect monitoring.

## Compatibility

- SQLite stays canonical.
- Metric changes require a documented compatibility/version decision.
