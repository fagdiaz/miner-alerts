# Data Model: Vnish Transition Reboot Interlock

## Current Transition Evidence

- `chains_transitioning_count`: optional non-negative integer from current normalized telemetry.
- `guard_enabled`: boolean configuration, default true.
- Active only when enabled and count is greater than zero.

## Reboot Interlock Decision

- Existing fields remain unchanged.
- New bounded field: `chains_transitioning_count`.
- New reason value: `firmware_transition`.

## Persisted Decision Detail

- `chains_transitioning_count`: integer.
- `firmware_transition_guard_enabled`: boolean.
- No raw firmware strings or payloads.

## State Transition

```text
eligible sustained LOW + transition active
  -> decision firmware_transition
  -> no Hashcore action
  -> low_since_ts = evaluated_ts
  -> state label and streak unchanged
```
