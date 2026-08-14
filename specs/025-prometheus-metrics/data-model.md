# Data Model: Prometheus Metrics And Grafana

## MetricsSnapshot

- `schema_version=1 / generated_ts`: Compatibility and freshness.
- `monitor`: Process start, completed tick sequence/time, poller/sender times
  and queue depth.
- `miners`: Ordered logical ID, authoritative sample time/signal/state/boards,
  episode projection and Spec 022 acquisition quality/latency.
- `telegram`: Six finite process-lifetime delivery counters.
- `collector`: Last status enum and age.
- `acquisition`: Latest authoritative epoch duration.

Numbers are finite or null. The payload contains no host/IP, free text, event
identity, credentials or source payload.

## MetricFamily

- `name`: miner_alerts snake_case name.
- `type`: Gauge or counter unless histogram is justified.
- `help`: Stable meaning.
- `labels`: Finite documented dimensions.
- `source_field`: Snapshot mapping.

V1 exposes exactly 26 family names. Label expansion produces at most 23 global
series plus 20 per configured miner.

## SnapshotHealth

- `valid`: parse, schema, enum, finite-value and freshness result.
- `age_seconds`: scrape time minus `generated_ts` when calculable.
- `error_code`: internal bounded exporter reason used for logs only, never a
  metric label.
- `scrape_duration_seconds`: current collection duration.

## DashboardProvision

- `uid`: Stable dashboard identity.
- `panels`: Fleet, liveness, episodes and delivery views.
- `refresh`: No faster than source cadence.
- `data_source`: Provisioned Prometheus reference.

## Invariants

- No secrets, addresses, incident IDs or free text in snapshot/labels.
- Old snapshot values are not exported as current after the staleness threshold.
- A malformed or stale snapshot exposes only snapshot/exporter health families.
- Exporter and dashboard are read-only.
- Metrics never feed action policy.
