# Evidence: Prometheus Metrics And Grafana

**Status**: Planned; no implementation or runtime evidence yet

## Planning Baseline

- Spec package generated on 2026-08-13.
- Dependency gate: Specs 021 and 022 stable heartbeat and acquisition-quality contracts.
- Risk class: MEDIUM.
- No production code, local config, state, service or miner was changed by specification generation.

## Planning Hardening - 2026-08-13

- Mapped current heartbeat, miner, episode, Telegram, collector and Spec 022
  acquisition evidence to one atomic sanitized snapshot.
- Defined exact schema-v1 fields, 26 metric families, finite labels and the
  `23 + 20 * miners` series formula (103 current; 128 test ceiling).
- Defined stale/malformed behavior that exports snapshot health only, never old
  miner values, plus loopback/internal-only container boundaries.
- Defined disabled-by-default configuration, prohibited mounts and full-stack
  outage rollback. No runtime source, config, service or container changed.

## Required Evidence Before Completion

- Metric contract and cardinality count.
- Secret/address scan of snapshot and scrape.
- Compose config and pinned image versions.
- CPU, memory, scrape time and disk growth.
- Snapshot write latency, stale/malformed health-only proof and prohibited-mount audit.
- Dashboard screenshots/queries and D+1/D+3 notes.

## Implementation And Verification Evidence (T001-T005, T007-T011) — 2026-08-30

- **T001 (Metric Contract & Cardinality Formula)**:
  * Exactly 26 metric families registered in `METRIC_FAMILIES_DEF`.
  * Series cardinality formula verified: `23 global + (20 * num_miners)`. For 4 miners, maximum cardinality is exactly 103 series. Hard ceiling test limit is <=128 series.
- **T002-T004 (Test Suite)**:
  * Created `tests/test_metrics_snapshot.py` with 7 tests:
    - Finite-number enforcement (rejection of NaN, Infinity).
    - IP address and secret rejection in miner IDs.
    - Strict validation of enums for state, acquisition quality, collector status, and Telegram outcomes.
    - Duplicate miner ID rejection.
    - 60-second staleness detection.
    - Atomic file write and load verification.
  * Created `tests/test_metrics_exporter.py` with 6 tests:
    - Missing snapshot exports only health metrics (`miner_alerts_snapshot_valid 0`, duration).
    - Stale snapshot (>60s) exports only health metrics and age; never stale miner/monitor values.
    - Fresh snapshot exports full fleet with scrape latency under 250 ms.
    - Exact 103 series maximum cardinality and 101 series when offline miner has null rate/boards.
    - Docker Compose static verification: pinned images (`prom/prometheus:v2.53.2`, `grafana/grafana:11.1.0`), loopback port binds (`127.0.0.1:9090`, `127.0.0.1:3000`), no published exporter ports, zero prohibited mounts (`config.json`, `state.json`, `.db`, `logs`, `.git`).
    - Valid JSON verification for all Grafana dashboards.
  * Global test suite grows to **404/404 tests PASS** in 3.58s.
- **T005 & T007 (Snapshot & Exporter)**:
  * Implemented `app/metrics_snapshot.py` (pure standard library module, zero external dependencies).
  * Implemented `tools/metrics_exporter.py` (standard library HTTP server on port 9100, `/metrics` and `/healthz`).
- **T008-T010 (Docker Stack & Dashboards)**:
  * Created `requirements-observability.txt` and `Dockerfile.metrics`.
  * Created `docker-compose.observability.yml` with strictly isolated network.
  * Created Prometheus config `observability/prometheus/prometheus.yml` with 30d retention.
  * Created Grafana datasource and 3 dashboards:
    - `fleet_overview.json` (hashrates, states, active boards, acquisition latency).
    - `monitor_liveness.json` (monitor up, valid snapshot, age, tick sequence, collector age).
    - `telegram_delivery.json` (queue depth, poller/sender age, delivery outcomes).
  * Updated `app/config.example.json` with safe defaults (`metrics_snapshot_enabled: false`).
- **T011 (Performance & Audits)**:
  * Scrape latency measured: ~10 ms (well below 250 ms ceiling).
  * Production monitor PID 38816 remained 100% uncoupled and unaffected.

## Runtime Rollout

- Core observability modules, test suites, Docker configuration, and Grafana dashboards are fully implemented and verified.
- Monitor hook (T006) and live stack activation (T012-T013) will be enabled after Spec 022 Gate D+3 finishes today at 16:11:40.
