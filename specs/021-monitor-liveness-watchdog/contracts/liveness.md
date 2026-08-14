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
- When collection raises unexpectedly and an output path was supplied, the
  observer MUST still write a sanitized failure envelope with only a stable
  reason and exception type; exception messages are not persisted.
- Successful and failure reports MUST replace their destination atomically so
  interruption cannot leave a partial JSON artifact that looks authoritative.
- The task installer MUST read back principal, executable, arguments and next
  run time after registration and fail if the installed definition diverges.

## Failure And Safety Contract

- No miner API, Hashcore, state-machine or reboot import is allowed.
- Missing/malformed evidence is unhealthy or unknown, never healthy.
- Recovery proof includes mutex and startup guard.

## Compatibility

- Existing monitor startup, commands and action policy remain unchanged.
- Heartbeat evolution is schema-versioned and backward-safe.
