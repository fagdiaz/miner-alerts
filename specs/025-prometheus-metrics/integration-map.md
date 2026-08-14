# Integration Map: Prometheus Metrics And Grafana

## Purpose

Map observability onto the current Windows runtime without adding an HTTP
server, database reader or action path to the monitor process.

## Current Producers

| Evidence | Current owner | Spec 025 use |
| --- | --- | --- |
| Completed tick, process start, poller/sender freshness and queue depth | `MonitorHeartbeat` in `app/liveness.py` | Copy sanitized scalar values after a completed tick |
| Current miner state/rate/boards/sample time | authoritative monitor tick | Copy the already-calculated result; never poll a miner again |
| Episode active/duration | `IrregularEpisodeCoordinator` | Copy current bounded episode projection |
| Telegram delivery outcomes | existing enqueue/sender paths | Increment finite process-lifetime counters only; do not copy text/body |
| Collector status/age | current collector run/heartbeat evidence | Copy status enum and age |
| Acquisition quality/latency | Spec 022 authoritative envelope | Copy stable quality enum and finite latency |

## Runtime Topology

```text
MinerAlerts Windows service
  -> atomic diagnostics/metrics/current.json

Docker read-only bind: diagnostics/metrics/
  -> metrics-exporter (internal port only)
  -> Prometheus (127.0.0.1 host bind)
  -> Grafana (127.0.0.1 host bind)
```

The containers do not mount `app/config.json`, `app/state.json`, SQLite, logs,
the repository root, Hashcore, miner credentials or the Docker socket.

## Planned Integration Anchors

| File/anchor | Integration | Boundary |
| --- | --- | --- |
| `app/metrics_snapshot.py` | Pure typed snapshot construction, validation and atomic write | Standard library only; no Prometheus dependency |
| `app/miner_monitor.py` after completed authoritative tick | Best-effort one snapshot write using values already in memory | No network, no miner IO, no state/action decision |
| Telegram enqueue/sender outcomes | Update finite in-memory counters | No payload retention, no delivery-policy change |
| `tools/metrics_exporter.py` | Read/validate one snapshot and expose fixed metric families | No monitor import, SQLite, Telegram or action import |
| `docker-compose.observability.yml` | Isolated optional exporter/Prometheus/Grafana topology | Localhost UIs; exporter internal only |
| Grafana provisioning | Versioned data source and dashboards | No manual production-only dashboard state |

## Snapshot Write Contract

1. Capture one `generated_ts` after a completed fleet tick.
2. Build a complete immutable payload from current in-memory values.
3. Validate finite numbers, enums, logical miner IDs and cardinality budget.
4. Write UTF-8 JSON to a same-directory temporary file, flush/fsync and
   atomically replace `diagnostics/metrics/current.json`.
5. On any error, log one bounded warning and leave the previous file untouched.

Snapshot production is best-effort. Failure cannot delay the next tick, change
state or terminate the monitor. The implementation must measure the 20 ms write
budget rather than hide overruns.

## Exporter Read Contract

1. Open the configured snapshot path read-only for each scrape.
2. Parse and validate schema/enums/finite values.
3. Calculate age from scrape time and `generated_ts`.
4. If valid and fresh, expose the fixed global and per-miner families.
5. If missing, malformed, unsupported or stale, expose only exporter/snapshot
   health metrics and no miner values from the old snapshot.
6. Do not cache a prior valid miner payload across a stale/malformed read.

This makes staleness explicit and avoids presenting historical values as
current health.

## Stable Metric Families

Exact names, types and labels are defined in `contracts/metrics.md`. Labels are
limited to:

- `miner`: configured logical ID from a finite current fleet;
- `state`: fixed state enum;
- `quality`: Spec 022 fixed quality enum;
- `status`: fixed collector status enum;
- `outcome`: fixed Telegram delivery outcome enum.

No reason text, exception type, event/episode ID, host, address, pool, user,
firmware string or timestamp is a label.

## Cardinality Budget

The v1 contract exposes at most 23 global series plus 20 series per configured
miner:

```text
series_budget(N) = 23 + 20 * N
```

At the current four-miner scale the hard contract is at most 103 series. Tests
allow a safety ceiling of 128 to catch accidental additions. Any future metric
or label changes this formula and requires a contract/version review before
rollout.

## Failure Isolation

| Failure | Monitor result | Exporter/dashboard result |
| --- | --- | --- |
| Snapshot write fails | Warning only; tick/action behavior unchanged | Prior file eventually becomes stale |
| Snapshot missing/malformed | No monitor effect | Snapshot health 0; no miner series |
| Exporter stopped | No monitor effect | Prometheus target down |
| Prometheus stopped | No monitor effect | Grafana data unavailable |
| Grafana stopped | No monitor effect | Metrics remain scrapeable locally |
| Docker unavailable | Native monitor remains complete | Use fixture/native exporter validation; feature stays disabled |

## Activation And Rollback

1. Implement snapshot and exporter with snapshot production disabled.
2. Validate deterministic fixtures, secret/address scan and 128-series ceiling.
3. Enable native snapshot only and observe write latency/no monitor effect.
4. Start pinned Compose stack and rebuild provisioning from empty volumes.
5. Stop the entire stack and prove monitor/Telegram/actions remain unchanged.
6. Roll back by disabling snapshot and stopping Compose; no source data or
   SQLite migration is involved.
