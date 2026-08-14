# Contract: Metrics Configuration

## Native Monitor Defaults

```json
{
  "metrics_snapshot_enabled": false,
  "metrics_snapshot_path": "diagnostics/metrics/current.json",
  "metrics_snapshot_stale_seconds": 60
}
```

| Key | Validation | Invalid behavior |
| --- | --- | --- |
| `metrics_snapshot_enabled` | boolean | disable snapshot |
| `metrics_snapshot_path` | non-empty local path; must resolve outside tracked source files | disable and log one warning |
| `metrics_snapshot_stale_seconds` | finite integer 30 to 300 | use default 60 and log one warning |

The path is resolved by the same explicit runtime-path policy used by other
diagnostic artifacts. It is not derived from a container path.

## Exporter/Compose Configuration

The auxiliary exporter receives only non-secret operational settings:

- snapshot mount/path;
- stale threshold;
- internal listen port;
- scrape timeout shorter than the Prometheus scrape interval.

Grafana credentials are local ignored environment values with placeholders in
the tracked example. No Telegram token, chat ID, miner credential, host/IP or
Hashcore path is passed to the observability stack.

## Rollback

Set `metrics_snapshot_enabled=false` and stop the optional Compose project.
Existing snapshots may be deleted as ignored runtime artifacts; SQLite and
monitor state are unchanged.
