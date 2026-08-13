# Feature Specification: Prometheus Metrics And Grafana

**Feature Branch**: `025-prometheus-metrics`

**Created**: 2026-08-13

**Status**: Planned; not implemented

**Input**: Expose bounded read-only metrics for miner freshness, state, episodes, monitor health and delivery, and provide a local Grafana operations view without creating an action surface.

**Risk Class**: MEDIUM

**Dependencies**: Specs 021 and 022 stable heartbeat and acquisition-quality contracts

## User Scenarios & Testing

### User Story 1 - See fleet health at a glance (Priority: P1)

The operator sees current rate, state, sample age, boards and episode duration in one time-series view.

**Why this priority**: Telegram is effective for alerts but poor for trends and fleet context.

**Independent Test**: Scrape deterministic sanitized snapshots and verify dashboard panels and freshness.

**Acceptance Scenarios**:

1. **Given** fresh metrics exist, **When** Grafana loads, **Then** fleet state and age appear without opening Telegram
2. **Given** the snapshot is stale, **When** Grafana loads, **Then** staleness is explicit rather than showing old values as current

---

### User Story 2 - Observe the monitor itself (Priority: P1)

Tick duration, heartbeat age, acquisition errors, Telegram queue/send failures and collector health are visible.

**Why this priority**: A miner monitor must expose its own failure modes.

**Independent Test**: Feed healthy and degraded component snapshots and verify bounded metrics.

**Acceptance Scenarios**:

1. **Given** Telegram send failures increase, **When** Prometheus scrapes, **Then** the failure counter changes
2. **Given** the monitor heartbeat is stale, **When** the dashboard refreshes, **Then** monitor liveness is visibly degraded

---

### User Story 3 - Operate observability locally (Priority: P2)

Prometheus and Grafana run as isolated auxiliary services with versioned configuration and no secrets from app config.

**Why this priority**: Observability must not increase monitor or credential blast radius.

**Independent Test**: Start the compose stack with sanitized snapshots and verify only localhost UI ports and internal scrape traffic.

**Acceptance Scenarios**:

1. **Given** the observability stack stops, **When** the monitor continues, **Then** polling, Telegram and actions are unaffected
2. **Given** Grafana is opened locally, **When** data sources load, **Then** no Telegram token, chat ID or miner credentials are exposed

### Edge Cases

- Metrics snapshot is missing or malformed.
- Prometheus is unavailable during monitor operation.
- A miner ID or reason label could create high cardinality.
- Counters reset when the monitor restarts.
- Docker Desktop is not installed.

## Requirements

### Functional Requirements

- **FR-001**: The monitor MUST publish an atomic sanitized metrics snapshot and MUST NOT host a new action endpoint.
- **FR-002**: Metrics MUST cover monitor heartbeat/tick, miner current signal and age, confirmed state, board count, episode duration, acquisition health, Telegram delivery and collector health.
- **FR-003**: Metric names and labels MUST be stable, documented and bounded in cardinality.
- **FR-004**: No event ID, error body, free text, hostname, IP, token, chat ID or credential MAY be a metric label.
- **FR-005**: Stale or missing snapshots MUST expose exporter/snapshot health and MUST NOT present old miner values as fresh.
- **FR-006**: The exporter MUST be read-only and MUST NOT import monitor action or Hashcore code.
- **FR-007**: Prometheus and Grafana MUST be optional and their failure MUST NOT affect the monitor.
- **FR-008**: Auxiliary containers MUST use pinned versions, internal networking and localhost-bound user interfaces.
- **FR-009**: Grafana provisioning and dashboards MUST be version-controlled and reproducible.
- **FR-010**: SQLite remains the incident/audit source; Prometheus retention is operational and not canonical.
- **FR-011**: Resource use, scrape duration and series count MUST be measured before production enablement.

### Key Entities

- **MetricsSnapshot**: Atomic sanitized current monitor and fleet values.
- **MetricFamily**: Stable name, type, help, labels and source.
- **ScrapeHealth**: Snapshot age, parse status and exporter scrape duration.
- **DashboardProvision**: Versioned Grafana data source and panel definition.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A scrape never contains secrets, addresses, free-text evidence or unbounded IDs.
- **SC-002**: Snapshot staleness becomes visible within two expected fleet ticks.
- **SC-003**: Series count stays below the documented budget at current fleet scale.
- **SC-004**: Stopping the full observability stack does not alter monitor tests or runtime behavior.
- **SC-005**: Grafana provisioning rebuilds the approved dashboards without manual configuration.

## Assumptions

- Docker Desktop may host auxiliary observability but not the Windows monitor.
- The monitor can atomically emit a small sanitized snapshot after a tick.
- Grafana is local-only in this program.

## Non-Goals

- Using metrics as an action trigger.
- Replacing SQLite incident history.
- Remote/public Grafana exposure or alert-based miner control.
- OpenTelemetry tracing.
