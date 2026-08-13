# Contract: Electrical Source And Samples

## Purpose

Define the discovery gate, normalized measurements and advisory incident boundary.

## Inputs

- Physical device documentation and read-only endpoint evidence.
- Bounded source responses with model-specific mapping.

## Outputs

- Capability report or explicit blocked result.
- Normalized measurements and collector health.
- Advisory incident facts.

## Failure And Safety Contract

- No protocol write operation.
- No secret in output.
- No action decision consumes electrical evidence.

## Compatibility

- Core monitor operates when the source is disabled or absent.
- Electrical tables are additive and optional.
