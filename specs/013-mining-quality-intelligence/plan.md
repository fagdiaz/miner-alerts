# Implementation Plan: Mining Quality Intelligence

## Technical Context

- Python standard library only: dataclasses, math, mappings, SQLite.
- Existing API 4028 `summary` and `stats` responses already fetched once per tick.
- Existing `VnishTelemetry`, schema-v2 `EventStore`, Telegram dispatcher, and
  static dashboard.
- Fresh read-only evidence from four deployed S19j Pro miners confirms accepted,
  rejected, stale, hardware-error, `chain_stateN`, and `chain_faultN` fields.
- Windows service remains on the previously loaded build until end-of-day rollout.

## Constitution Check

- Production safety: PASS; assessment is observational and cannot authorize actions.
- Configuration source: PASS; only example defaults may change.
- Telegram controls: PASS; `/quality` is read-only and deterministic.
- Auto-reboot gates: PASS; state machine and action policy are out of scope.
- Windows compatibility: PASS; standard library and repository virtualenv only.
- Evidence completion: REQUIRED before commit.

## Design

1. Add a pure quality normalizer for summary counters and already-fetched Vnish stats.
2. Extend normalized Vnish evidence with bounded chain-state/fault indicators.
3. Add an additive schema-v3 migration and persist quality columns in telemetry samples.
4. Compare newest and prior samples only when uptime/counters are monotonic.
5. Derive interval reject/stale percentages and hardware-error deltas.
6. Give current chain faults/non-mining evidence precedence over interval warnings.
7. Add `/quality [all|miner]` using SQLite only and command-delivery semantics.
8. Reuse the analyzer in dashboard cards and keep the Docker generator read-only.

## Safety Boundaries

- No state-machine, auto-reboot, cooldown, startup-guard, QA, or Hashcore changes.
- No additional network request in the monitor tick or Telegram handler.
- No raw API response, pool identity, worker, password, or token persistence.
- Counter resets degrade to learning and cannot create a negative or critical rate.
- Thresholds affect advice only and cannot trigger an action or notification.

## Validation Strategy

- TDD for normalization, delta/reset handling, severity, schema migration, command,
  and dashboard parity.
- Static source checks for no live IO/actions in the quality command helper.
- Targeted and complete unittest suites plus `py_compile`.
- Performance check over 2,000 samples.
- Docker dashboard build/generation smoke if dashboard integration changes.
- Speckit QA, diff check, config JSON parse, service status, and no-restart evidence.
