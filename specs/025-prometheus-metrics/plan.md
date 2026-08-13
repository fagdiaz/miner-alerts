# Implementation Plan: Prometheus Metrics And Grafana

**Branch**: `025-prometheus-metrics` | **Date**: 2026-08-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/025-prometheus-metrics/spec.md`

## Summary

Have the native monitor write a small atomic sanitized metrics snapshot. A separate prometheus_client exporter reads it inside an optional Docker Compose stack with Prometheus and Grafana; only Grafana/Prometheus localhost ports are exposed and no component can act on miners.

## Technical Context

**Language/Version**: Python 3.14.x and PowerShell 5.1

**Primary Dependencies**: prometheus-client in an auxiliary exporter image; pinned Prometheus and Grafana Docker images

**Storage**: Atomic diagnostics/metrics/current.json, Prometheus volume and versioned Grafana provisioning; SQLite remains canonical

**Testing**: `unittest`, deterministic fixtures, contract validation, `py_compile`, and controlled runtime evidence

**Target Platform**: Windows 10, Windows service/Scheduled Tasks, local ASIC network

**Project Type**: Native snapshot producer plus optional three-service Docker observability stack

**Performance Goals**: Snapshot write under 20 ms, scrape under 250 ms, bounded series cardinality

**Constraints**: No real secrets or runtime files in Git; no unproved completion; no action authority outside the existing monitor

**Risk Classification**: MEDIUM - observability must remain isolated, bounded-cardinality and unable to access action paths or secrets

**Scale/Scope**: Current four-miner fleet with bounded behavior for configured growth

## Constitution Check

- **Production Safety First**: PASS by design; the exporter consumes sanitized files only and has no config secrets or action imports.
- **Single Source Of Truth**: PASS; local config/state stay outside Git.
- **Telegram Operational Controls**: PASS; dangerous command confirmation remains unchanged.
- **Auto-Reboot Evidence And Gates**: PASS; existing policy remains authoritative and receives regression coverage.
- **Windows Compatibility**: PASS; validation and rollout are PowerShell/service compatible.
- **Evidence-Based Completion**: PASS by plan; runtime evidence and observation remain mandatory.

## Project Structure

### Documentation

```text
specs/025-prometheus-metrics/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/metrics.md
|-- checklists/requirements.md
|-- tasks.md
`-- evidence.md
```

### Planned Source Scope

```text
app/metrics_snapshot.py
app/miner_monitor.py              # atomic snapshot call only
tools/metrics_exporter.py
requirements-observability.txt
Dockerfile.metrics
docker-compose.observability.yml
observability/prometheus/
observability/grafana/
tests/test_metrics_snapshot.py
tests/test_metrics_exporter.py
```

**Structure Decision**: Separate metric production from HTTP serving. Docker receives only the sanitized snapshot, so the observability stack does not mount config, state or the live SQLite database.

## Phase 0: Research Decisions

See [research.md](research.md). Prometheus text exposition is simple and standard; official guidance requires bounded label cardinality. Grafana file provisioning makes dashboards reproducible. OpenTelemetry is deferred because this topology does not need a multi-signal pipeline.

## Phase 1: Design

- Define a versioned atomic snapshot contract with no secrets or addresses.
- Use prometheus_client only in the auxiliary exporter image.
- Bind Grafana and Prometheus host ports to 127.0.0.1 and keep exporter internal to Compose.
- Use stable miner logical IDs as one bounded label and reason codes from finite enums only.
- Provision dashboards and data source from repository files.

## Rollback And Failure Boundary

- Stopping/removing Compose leaves the monitor unchanged.
- Snapshot write failures log and do not interrupt the fleet tick.
- Metrics snapshot production is independently disabled with a safe default until rollout.

## Post-Design Constitution Check

PASS. No unresolved constitution violation exists. Completion remains conditional on `tasks.md` evidence and the scheduled observation window.
