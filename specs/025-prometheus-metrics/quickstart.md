# Quickstart: Prometheus Metrics And Grafana

**Status**: Planned validation procedure; referenced implementation files do not exist yet.

## Preconditions

- Specs 021 and 022 have completed their acceptance and observation gates.
- Docker Desktop availability is verified or native exporter validation is used.

## Static And Automated Validation

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_metrics_snapshot tests.test_metrics_exporter
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
& ".\.venv\Scripts\python.exe" -m py_compile app\metrics_snapshot.py app\miner_monitor.py tools\metrics_exporter.py
docker compose -f docker-compose.observability.yml config
docker compose -f docker-compose.observability.yml up --build -d
docker compose -f docker-compose.observability.yml ps
```

## Controlled Runtime Validation

1. Generate healthy, stale and malformed sanitized snapshots.
2. Scrape exporter and audit metric names, labels and series count.
3. Provision Grafana from empty volumes and verify panels.
4. Stop Compose and prove monitor operation is unchanged.
5. Observe D+1/D+3 resource and retention behavior.

## Evidence To Capture

- Metric contract and cardinality count.
- Secret/address scan of snapshot and scrape.
- Compose config and pinned image versions.
- CPU, memory, scrape time and disk growth.
- Dashboard screenshots/queries and D+1/D+3 notes.
