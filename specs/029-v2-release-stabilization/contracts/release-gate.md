# Contract: V2 Release Gate

## Purpose

Define feature freeze, regression, activation, restore, observation and documentation requirements for release approval.

## Inputs

- Accepted/blocked per-spec evidence.
- Frozen candidate identity and clean environment.
- Controlled Windows maintenance window and backup destination.

## Freeze Manifest

The candidate manifest records:

- Git commit/branch and clean tracked status;
- deterministic runtime-payload digest plus sorted included-path records;
- Python executable/version and installed direct dependency versions;
- EventStore schema and `app/config.example.json` hashes;
- sanitized SCM/Scheduled Task executable, argument, account, startup and
  recovery identities;
- terminal disposition/evidence for Specs 021-028;
- prior known-good runtime/service rollback identity.

No real config value, state, database row, log body, token, address, credential
or absolute sensitive path is serialized.

## Severity Contract

- **P0**: unintended/duplicate action, confirmation or QA bypass, monitor/action
  authority duplication, secret exposure, data loss/corruption, unavailable
  monitor without independent detection, or restore/rollback that threatens live
  data. Stop rollout and contain immediately.
- **P1**: missed sustained outage, false critical alert, stale/contradictory state
  presented as current, user command silence, polling replay/skip, persistent
  collector/watchdog evidence gap, restore failure or accepted auxiliary outage
  affecting the monitor. Block release and resolve within the current window.
- **P2**: non-critical wording/layout, optional dashboard or documentation issue
  that does not obscure current health/safety. Track without overriding P0/P1.

Severity cannot be reduced because of schedule. A blocker contains owner spec,
runtime digest, first/last UTC, containment, affected R-IDs and retest evidence.
Closure requires all affected rows pass against the current digest.

## Observation Contract

Observation is one continuous 168-hour window from controlled activation of one
runtime payload. R024 is the checkpoint at or after hour 72; R025 closes at or
after hour 168. Seven daily sanitized reports cover service/process identity,
heartbeat/tick/workers, watchdog cadence/incidents, collector, miner episode and
action/decision counts, Telegram delivery failures and open blockers.

A runtime/config/schema/dependency/service-definition change restarts affected
clocks. Docs/evidence-only changes preserve time only when the payload digest is
identical. Missing/failed daily evidence cannot be inferred as healthy.

## Outputs

- Complete regression matrix.
- Runtime/restore/documentation evidence bundle.
- Explicit release approve or block decision.

## Failure And Safety Contract

- P0/P1 blocks release.
- No new feature during stabilization.
- No production completion without observed service and actions.
- No approval with a missing mandatory R001-R025 result or non-terminal
  dependency disposition.
- No rollback operation overwrites live state/database or weakens safety gates.

## Compatibility

- Prior known-good rollback identity is recorded.
- Conditional no-build/blocked specs remain truthful and do not block when their gates pass.
- Git/docs-only identity may advance during evidence closeout only when the
  runtime-payload digest and observation continuity remain proven.

## Decision

`approve` requires all mandatory/applicable rows pass, valid N/A evidence for
excluded terminal dependencies, successful staging restore, seven continuous
daily reports, unchanged payload digest and zero open P0/P1. Any other state is
`block`; there is no partial approval.
