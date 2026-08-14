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
5. Reuse existing diagnosis freshness and action-attribution settings; add only
   a disabled-by-default feature flag, context window and fleet window.
6. Make the pure rule engine consume explicit time and canonical facts so
   historical replay does not depend on the machine clock.
7. Store source table/row references and an evidence digest rather than copying
   source payloads into a second truth store.

## Rejected Or Deferred Alternatives

- LLM root cause because it is non-deterministic.
- Telegram-handler text heuristics because they lose provenance.
- Automatic restart/reboot recommendations because that is a separate action-policy decision.
- Free-text or keyword root-cause scoring because summaries are not stable
  evidence contracts.
- One query per fact because bounded current-scale latency must remain stable as
  history grows.

## External Validation Sources

- SQLite integrity/query documentation: https://www.sqlite.org/pragma.html
- OpenTelemetry deferred baseline: https://opentelemetry.io/docs/collector/
