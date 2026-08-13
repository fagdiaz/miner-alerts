# Contract: Authoritative And Diagnostic Acquisition

## Purpose

Define sample provenance, epoch completeness and the sole state/action input boundary.

## Inputs

- Configured miners and bounded timeouts.
- Epoch schedule and optional episode diagnostics.

## Outputs

- One authoritative envelope per miner and epoch.
- Optional diagnostic envelopes.
- Bounded health metrics and reason codes.

## Failure And Safety Contract

- State and actions reject diagnostic envelopes.
- Errors never masquerade as current values.
- Per-miner overlap is forbidden.

## Compatibility

- Production authoritative cadence remains 30 seconds.
- Telegram polling offset is outside this scheduler.
