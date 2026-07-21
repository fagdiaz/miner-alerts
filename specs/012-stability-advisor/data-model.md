# Data Model: Stability Advisor

## MetricBand

- `metric`: stable metric name.
- `sample_count`: finite healthy observations used.
- `median`: robust center.
- `mad`: median absolute deviation.
- `lower` / `upper`: anomaly bounds including minimum noise floors.

## DiagnosticReason

- `code`: stable machine-readable identifier.
- `severity`: `watch` or `critical`.
- `message`: concise operator-facing evidence.
- `observed`, `lower`, `upper`: optional numeric context.

## StabilityAssessment

- `status`: `learning`, `stable`, `watch`, or `critical`.
- `sample_count` / `required_samples` / `confidence`.
- `observed_ts` / `age_seconds`.
- `bands`: bounded mapping of metric name to `MetricBand`.
- `reasons`: ordered tuple of `DiagnosticReason`.

No entity is persisted. Every object is derived read-only from bounded existing
telemetry samples.
