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
- A versioned, sanitized D+0/D+1/D+3 observation report combining service,
  heartbeat, watchdog cadence and read-only SQLite evidence.

## Observation Gate

- `tools/observe_liveness.py` MUST reject D+1 before 24 hours and D+3 before
  72 hours from the supplied recovery timestamp.
- The gate MUST be read-only except for an explicitly requested report under an
  ignored output path.
- A passing report requires a running service, fresh heartbeat/workers,
  continuous healthy watchdog assessments, a closed incident, fresh telemetry
  persistence, a successful latest collector run and no automatic action since
  the observation start.
- The report MUST contain no token, configured miner host or Telegram payload.

## Failure And Safety Contract

- No miner API, Hashcore, state-machine or reboot import is allowed.
- Missing/malformed evidence is unhealthy or unknown, never healthy.
- Recovery proof includes mutex and startup guard.

## Compatibility

- Existing monitor startup, commands and action policy remain unchanged.
- Heartbeat evolution is schema-versioned and backward-safe.
