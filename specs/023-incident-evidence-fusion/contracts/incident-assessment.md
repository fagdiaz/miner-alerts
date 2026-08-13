# Contract: Incident Assessment

## Purpose

Define deterministic normalization, confidence language and shared read-only rendering.

## Inputs

- Persisted incident or episode identity.
- Bounded telemetry, quality, firmware, collector and action records.
- Versioned rules and freshness limits.

## Outputs

- Chronological evidence facts.
- Findings, hypotheses, contradictions and missing evidence.
- Persisted assessment identity and shared rendering.

## Failure And Safety Contract

- No miner IO or Hashcore call during assessment.
- Timing alone never confirms causality.
- Stale or unknown-clock evidence lowers confidence.

## Compatibility

- Existing event and diagnosis views remain available.
- Schema migration is additive for old readers.
