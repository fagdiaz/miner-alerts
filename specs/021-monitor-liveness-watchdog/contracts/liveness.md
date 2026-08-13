# Contract: Monitor Liveness And Recovery

## Purpose

Define the cross-process heartbeat, watchdog classifications and safe service-recovery boundary.

## Inputs

- Atomic heartbeat snapshot.
- Windows service/process status.
- Bounded watchdog state and optional maintenance lease.

## Outputs

- One liveness open/reminder/recovery notification.
- Always-on watchdog log with reason and evidence age.
- Read-only health rendering.

## Failure And Safety Contract

- No miner API, Hashcore, state-machine or reboot import is allowed.
- Missing/malformed evidence is unhealthy or unknown, never healthy.
- Recovery proof includes mutex and startup guard.

## Compatibility

- Existing monitor startup, commands and action policy remain unchanged.
- Heartbeat evolution is schema-versioned and backward-safe.
