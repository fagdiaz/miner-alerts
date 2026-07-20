# Research: Incident History And Restart Intelligence

## Decision 1: Use SQLite As The Local Operational Store

**Decision**: Use Python's built-in SQLite driver with WAL, normal synchronous
mode, a bounded busy timeout, explicit schema versioning, and a shared lock.

**Rationale**: The service is single-host, has modest write volume, needs durable
queries and retention, and must remain deployable on Windows without another
service or dependency. SQLite provides transactions and indexes that JSON state
files do not.

**Alternatives considered**:

- Extend `state.json`: rejected because it is runtime state, rewrites whole files,
  and is unsuitable for event history and time-range queries.
- PostgreSQL/TimescaleDB: deferred because it adds service administration and is
  disproportionate for four miners.
- InfluxDB/Prometheus: useful for later high-volume metrics, but does not replace
  the immediate incident/audit store and increases deployment complexity.

## Decision 2: Keep Historical Data Out Of Action Policy

**Decision**: Database records are write-side evidence and read-side diagnostics
only. Existing in-memory/runtime state remains the sole input to auto-reboot.

**Rationale**: This prevents stale history, migration errors, or database failure
from causing an unnecessary reboot and satisfies the production-safety principle.

**Alternatives considered**:

- Use historical patterns to suppress or trigger auto-reboot immediately: rejected
  until enough real evidence exists and a separate safety spec defines behavior.

## Decision 3: Classify Existing Uptime-Reset Signals

**Decision**: Preserve the current uptime-drop criteria and classify an already
detected reset by the newest qualifying successful action timestamp.

**Rationale**: The existing signal is production-proven. Attribution adds meaning
without changing detection sensitivity. Manual and automatic timestamps already
exist in `MinerState` and survive restarts.

**Alternatives considered**:

- Introduce a new reboot detector: rejected because it could change alert behavior.
- Infer solely from LOW/OFFLINE transitions: rejected because those transitions do
  not prove a process/device restart.

## Decision 4: Sample Every Five Minutes By Default

**Decision**: Record telemetry at a configurable 300-second interval with 90-day
retention; retain sparse operational events for 365 days.

**Rationale**: Four miners produce about 104,000 samples over 90 days, enough for
trend and pre-incident analysis while avoiding per-tick growth.

**Alternatives considered**:

- Every 30-second tick: rejected as unnecessary for the first operational baseline.
- Events only: rejected because restart context needs pre/post signal history.

## Decision 5: Telegram History Is Read-Only And Local

**Decision**: Add `/events` and `/event <id>` backed only by SQLite.

**Rationale**: Operators get immediate evidence from the existing interface with
no extra miner traffic, Hashcore calls, or new authentication surface.

**Alternatives considered**:

- Full web dashboard in this spec: deferred until event semantics and retention are
  stable; it requires separate authentication and deployment decisions.
- Live miner reads from history commands: rejected because they add latency and can
  distort incident evidence.

## Missing Project Alignment Documents

The generic Speckit workflow references `docs/project_docs/REQUERIMIENTOS.md`,
`PLAN_DE_MITIGACION_EVALUACION.md`, and `ROADMAP.md`. They are not present in this
repository. Alignment therefore uses the project-specific constitution and
`docs/speckit/ROADMAP.md`, which are the declared sources of truth in `AGENTS.md`.
