# Research: Prometheus Metrics And Grafana

## Baseline Findings

- Prometheus uses HTTP text exposition and supports gauge/counter/histogram primitives.
- Each label set creates a time series and high cardinality has direct resource cost.
- Grafana supports file-provisioned data sources and dashboards.
- OpenTelemetry Collector adds value mainly when multiple services/signals/export targets justify a pipeline.

## Decisions

1. Adopt Prometheus and Grafana for read-only operational observability.
2. Keep the HTTP exporter out of the monitor process.
3. Containerize only exporter, Prometheus and Grafana.
4. Defer OTel until multi-service tracing or multiple telemetry backends exist.
5. Mount only the snapshot directory into the exporter; never mount live SQLite
   or the repository root.
6. Use a fixed metric family/label allowlist and one formula-based cardinality
   budget instead of discovering metrics dynamically from JSON keys.
7. Drop stale miner series instead of caching the last good payload.

## Rejected Or Deferred Alternatives

- Embedding an HTTP server in miner_monitor.py because it increases monitor blast radius.
- Mounting live config or SQLite into containers because it exposes secrets or file-lock complexity.
- Dynamic event IDs and free text as labels because they are unbounded.
- React dashboard because Grafana already serves this workflow.
- Dynamic JSON-to-metric conversion because unknown keys/labels break
  compatibility and cardinality bounds.
- Exporting error/reason text as labels because finite logs/SQLite already own
  diagnostic detail.

## External Validation Sources

- Prometheus exposition: https://prometheus.io/docs/instrumenting/exposition_formats/
- Prometheus instrumentation/cardinality: https://prometheus.io/docs/practices/instrumentation/
- Grafana provisioning: https://grafana.com/docs/grafana/latest/administration/provisioning/
- OpenTelemetry Collector: https://opentelemetry.io/docs/collector/
