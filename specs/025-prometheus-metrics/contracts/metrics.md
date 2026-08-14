# Contract: Metrics Snapshot And Exposition

## Snapshot Schema V1

```text
schema_version: 1
generated_ts: finite epoch seconds
monitor:
  process_start_ts, tick_sequence, last_tick_completed_ts
  telegram_poller_ts, telegram_sender_ts, queue_depth
miners[]:
  miner_id, sample_ts, responded, rate_ths, threshold_ths
  state, active_boards, expected_boards
  episode_active, episode_duration_seconds
  acquisition_quality, acquisition_latency_seconds
telegram:
  enqueued_total, sent_total, send_error_total
  dropped_total, bypass_total, fallback_total
collector:
  status, age_seconds
acquisition:
  epoch_duration_seconds
```

Optional numeric values use JSON `null`; NaN and Infinity are invalid. Miner
rows are sorted by configured order and `miner_id` is a logical configured ID,
never a host or address.

## Enums

- miner state: `OK`, `LOW`, `OFFLINE`, `HASHBOARD`, `UNKNOWN`;
- acquisition quality: `valid`, `partial`, `invalid`, `timeout`, `error`, `late`;
- collector status: `ok`, `partial`, `failed`, `stale`;
- Telegram outcome: `enqueued`, `sent`, `error`, `dropped`, `bypass`, `fallback`.

Unknown enum values make the snapshot invalid. They do not create dynamic
labels.

## Prometheus Families

| Name | Type | Labels | Snapshot source/meaning |
| --- | --- | --- | --- |
| `miner_alerts_snapshot_valid` | gauge | none | 1 only when current parse/schema/freshness is valid |
| `miner_alerts_snapshot_age_seconds` | gauge | none | non-negative age, available when timestamp parses |
| `miner_alerts_snapshot_schema_version` | gauge | none | supported numeric schema |
| `miner_alerts_exporter_scrape_duration_seconds` | gauge | none | duration of current collection |
| `miner_alerts_monitor_up` | gauge | none | 1 for a fresh valid completed-tick snapshot |
| `miner_alerts_monitor_process_start_time_seconds` | gauge | none | process start epoch |
| `miner_alerts_monitor_tick_sequence_total` | counter | none | completed tick sequence; resets on process restart |
| `miner_alerts_monitor_last_tick_timestamp_seconds` | gauge | none | completed tick epoch |
| `miner_alerts_telegram_poller_age_seconds` | gauge | none | scrape time minus poller timestamp |
| `miner_alerts_telegram_sender_age_seconds` | gauge | none | scrape time minus sender timestamp |
| `miner_alerts_telegram_queue_depth` | gauge | none | bounded current queue depth |
| `miner_alerts_telegram_messages_total` | counter | `outcome` | six fixed process-lifetime delivery counters |
| `miner_alerts_collector_age_seconds` | gauge | none | current collector age |
| `miner_alerts_collector_status` | gauge | `status` | one-hot four-value status |
| `miner_alerts_acquisition_epoch_duration_seconds` | gauge | none | latest authoritative fleet epoch duration |
| `miner_alerts_miner_responded` | gauge | `miner` | 1 when authoritative signal responded |
| `miner_alerts_miner_rate_ths` | gauge | `miner` | finite current hashrate; omitted when null |
| `miner_alerts_miner_threshold_ths` | gauge | `miner` | configured threshold |
| `miner_alerts_miner_sample_age_seconds` | gauge | `miner` | scrape time minus authoritative sample time |
| `miner_alerts_miner_state` | gauge | `miner,state` | one-hot five-value confirmed state |
| `miner_alerts_miner_active_boards` | gauge | `miner` | active boards; omitted when unknown |
| `miner_alerts_miner_expected_boards` | gauge | `miner` | expected board count |
| `miner_alerts_miner_episode_active` | gauge | `miner` | active irregular episode flag |
| `miner_alerts_miner_episode_duration_seconds` | gauge | `miner` | current active duration; 0 when inactive |
| `miner_alerts_miner_acquisition_quality` | gauge | `miner,quality` | one-hot six-value Spec 022 quality |
| `miner_alerts_miner_acquisition_latency_seconds` | gauge | `miner` | authoritative request latency |

Help strings are stable English descriptions. Unit suffixes follow Prometheus
conventions. Metric renames, label additions or semantic changes require a
snapshot/contract compatibility decision.

## Stale Or Invalid Snapshot

When missing, malformed, unsupported or older than
`metrics_snapshot_stale_seconds`, expose only:

- `miner_alerts_snapshot_valid 0`;
- `miner_alerts_snapshot_age_seconds` when calculable;
- `miner_alerts_exporter_scrape_duration_seconds`.

Do not expose monitor, collector, Telegram or miner values from a stale payload.

## Cardinality

- Global maximum: 23 series.
- Per configured miner: 20 series.
- Current four-miner contract: 103 series maximum.
- Test safety ceiling: 128 total series.

No event, incident, episode, firmware, reason, error, URL or free-text label is
allowed.

## Security And Topology

- Exporter receives only the read-only snapshot directory.
- Exporter has no host-published port; Prometheus reaches it on the internal
  Compose network.
- Prometheus and Grafana bind host ports only to `127.0.0.1`.
- Containers do not mount config/state/SQLite/logs/repository root or Docker
  socket.
- Grafana credentials stay in ignored local environment configuration.
- No component exposes POST/action/config routes.

## Failure And Safety Contract

- Snapshot generation and HTTP serving are outside state/action semantics.
- Exporter/Prometheus/Grafana outage cannot affect the monitor.
- SQLite remains canonical for incident/audit history.
- Metrics are never consumed by auto-reboot or manual-action authorization.
