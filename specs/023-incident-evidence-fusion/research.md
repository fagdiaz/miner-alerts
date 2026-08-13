# Research: Incident Evidence Fusion

## Baseline Findings

- SQLite already stores telemetry, events, decisions, firmware and collector runs.
- Current analyzers are deterministic and read-only.
- Vnish timestamps already carry clock quality.
- Fleet simultaneity is shared-domain evidence, not proof of power cause.

## Decisions

1. Use rule-based versioned fusion instead of machine learning.
2. Persist assessment snapshots for audit reproducibility.
3. Use a 24-hour default context and short configurable fleet windows.
4. Keep the first release on-demand.

## Rejected Or Deferred Alternatives

- LLM root cause because it is non-deterministic.
- Telegram-handler text heuristics because they lose provenance.
- Automatic restart/reboot recommendations because that is a separate action-policy decision.

## External Validation Sources

- SQLite integrity/query documentation: https://www.sqlite.org/pragma.html
- OpenTelemetry deferred baseline: https://opentelemetry.io/docs/collector/
