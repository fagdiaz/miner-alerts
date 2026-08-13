# Data Model: Prometheus Metrics And Grafana

## MetricsSnapshot

- `schema_version / generated_ts`: Compatibility and freshness.
- `monitor`: Tick, process, worker and queue metrics.
- `miners`: Logical ID, signal, state, board, age and episode metrics.
- `telegram`: Bounded counters and queue health.
- `collector`: Last run age and result.
- `acquisition`: Epoch and per-miner bounded health.

## MetricFamily

- `name`: miner_alerts snake_case name.
- `type`: Gauge or counter unless histogram is justified.
- `help`: Stable meaning.
- `labels`: Finite documented dimensions.
- `source_field`: Snapshot mapping.

## DashboardProvision

- `uid`: Stable dashboard identity.
- `panels`: Fleet, liveness, episodes and delivery views.
- `refresh`: No faster than source cadence.
- `data_source`: Provisioned Prometheus reference.

## Invariants

- No secrets, addresses, incident IDs or free text in snapshot/labels.
- Old snapshot values are not exported as current after the staleness threshold.
- Exporter and dashboard are read-only.
- Metrics never feed action policy.
