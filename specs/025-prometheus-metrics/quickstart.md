# Quickstart: Prometheus Metrics And Grafana

**Status**: Planned validation procedure; referenced implementation files do not exist yet.

## Preconditions

- Specs 021 and 022 have completed their acceptance and observation gates.
- Docker Desktop availability is verified or native exporter validation is used.
- Snapshot production remains disabled while red contracts and exporter
  fixtures run.

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
2. Scrape exporter and audit the exact 26-family allowlist, labels and series
   count (`<=103` expected current fleet, `<=128` hard test ceiling).
3. Provision Grafana from empty volumes and verify panels.
4. Prove stale/malformed snapshots expose health only and no cached miner data.
5. Audit Compose for loopback binds, internal exporter and prohibited mounts.
6. Stop Compose and prove monitor operation is unchanged.
7. Observe D+1/D+3 resource and retention behavior.

## Evidence To Capture

- Metric contract and cardinality count.
- Secret/address scan of snapshot and scrape.
- Compose config and pinned image versions.
- CPU, memory, scrape time and disk growth.
- Snapshot write latency and stale/malformed behavior.
- Dashboard screenshots/queries and D+1/D+3 notes.
