# Contract: Operator Workflow And Conditional API

## Purpose

Define the no-build decision gate and, only if approved, the local read-only API boundary.

## Inputs

- Fixed workflow scorecard across current interfaces with three runs per
  eligible P1 pair.
- Read-only SQLite data and assessment contracts.

## Outputs

- No-build or scoped-MVP decision.
- Conditional typed read-only resources and local views.

## Decision Contract

- `blocked`: Spec 025 or Spec 028 exit evidence is incomplete.
- `no_build`: every P1 workflow has at least one existing owner with three
  consecutive complete, accurate, freshness-visible runs within target.
- `fastapi_mvp`: at least one exact P1 required field fails across every
  existing eligible interface and is satisfiable from bounded SQLite data.

P2 convenience, technology-learning goals, remote access and action controls do
not qualify an MVP. A decision record includes dependency evidence, all run
records, selected owner per workflow, exact failed fields and reviewer/time.

## Conditional API Contract

The maximum route set is defined by `integration-map.md`; the approved route set
must be a subset. Only GET/HEAD is permitted. Lists default to 50 and cap at 200;
history caps at 30 days and uses stable timestamp-plus-ID cursors.

SQLite opens in URI `mode=ro`, immediately enables `PRAGMA query_only=ON`, checks
supported schema and fails closed on busy/missing/incompatible data. A live WAL
database is not opened with `immutable=1`.

The server binds exactly to `127.0.0.1`, disables proxy trust and CORS, and
rejects non-loopback configuration before listening. It reads no runtime config
and imports no monitor, Telegram, Hashcore, miner network or subprocess code.

Errors use finite reason codes and sanitized operator text. SQL, tracebacks,
filesystem paths, host/IP fields, credentials and raw firmware evidence are not
returned.

## Failure And Safety Contract

- Loopback binding only.
- No miner, action, Hashcore or config mutation imports.
- Bounded queries and redacted errors.
- Database and request failures return within 2 seconds without retries into
  monitor/miner paths.
- Stale data remains visible as stale and is never relabeled current.

## Compatibility

- Telegram remains the action channel.
- Static HTML and Grafana remain valid even if the MVP is absent.
- Stopping or deleting a conditional MVP leaves monitor service, polling,
  Telegram delivery, SQLite writes and Hashcore actions unchanged.
