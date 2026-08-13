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

## Scheduling And Request Budget

- `poll_seconds=30` is a nominal interval, not proof that the current
  sleep-after-tick loop starts exactly every 30 seconds. Baseline cadence is
  measured before activation.
- One authoritative epoch emits exactly one envelope per configured miner.
- Each miner uses at most one summary and one conditional stats request per
  authoritative epoch, without retry.
- A diagnostic interval uses at most one summary request per eligible miner and
  never requests stats.
- Expired epochs are skipped. Resume creates one current epoch and no catch-up
  burst.

## Failure And Safety Contract

- State and actions reject diagnostic envelopes.
- Errors never masquerade as current values.
- Per-miner overlap is forbidden.
- Manual command IO is not reclassified as authoritative acquisition and keeps
  its existing independent cooldown.

## Compatibility

- Production authoritative cadence remains nominally 30 seconds; activation
  does not replay missed epochs.
- Telegram polling offset is outside this scheduler.
- `adaptive_acquisition_enabled=false` uses the sequential fallback and must
  preserve deterministic state/action parity.
