# Miner Alerts Technology Strategy

**Last reviewed**: 2026-09-07 (Release v2.0.0 Normalized)
**Program**: `docs/speckit/SPEC_PROGRAM.md`

## Principle

New technology should be added only when it reduces operational risk, improves
diagnostics, or creates a clear learning path with market value. Miner Alerts is
production-adjacent, so the default is conservative: add read-only tooling first,
then controlled automation.

## Current Baseline

- Python: appropriate for ASIC API tooling, Telegram polling, CLI automation and
  fast diagnostics.
- API 4028: adaptive acquisition with authoritative typed envelopes is the source of
  truth for availability, hashrate, uptime and boards.
- Vnish WebSockets: bounded read-only log acquisition in a separate scheduled
  process; not a replacement for miner health samples.
- SQLite schema v5: operational history, diagnostics, decision audit, and online hot backups.
- Windows service/process: appropriate while Hashcore Toolkit CLI is local and
  Windows-based.
- Watchdog: independent out-of-process monitor liveness supervision and SCM recovery.
- Prometheus + Grafana: auxiliary metrics exporter and local dashboards for long-term trends.
- Docker: appropriate for isolated read-only tools, reports and auxiliary metrics
  dashboards; not used for the main monitor while Hashcore CLI and
  Windows service integration remain host-local.

## Acquisition And Supervision Decision

WebSockets do not remove the need to supervise the monitor and do not provide a
complete current sample unless the remote firmware publishes every required
field. The deployed API 4028 endpoint is pull-oriented, so the target design is
hybrid rather than a protocol rewrite:

- Keep conservative API 4028 polling for current state.
- Stagger and measure requests with adaptive acquisition envelopes.
- Use Vnish WebSockets for asynchronous firmware evidence only.
- Independent heartbeat/watchdog ensures stalled poll loops are detected out of process.
- Mark data stale explicitly; never reuse an old rate as current evidence.

This follows the same operational principle used by Prometheus: pull-based
collection remains a contemporary monitoring model when freshness and target
failure are meaningful signals.

## Implemented And Evaluated Technology Path

### Docker

Implemented for:

- Spec 025's isolated metrics exporter, Prometheus and Grafana stack (`observability/docker-compose.metrics.yml`).
- Read-only diagnostics collectors and static report generation.

Do not use for:

- The production monitor process.
- Hashcore Toolkit actions that depend on Windows-local installation paths.

### FastAPI (Evaluated & Closed: `no_build`)

Status:

- Formally evaluated under Spec 027 (Operator Interface Decision).
- 30 timed runs across workflows W01-W06 confirmed that Telegram, Grafana, and the static HTML dashboard cover 100% of operator needs with zero missing fields.
- Decision: **`no_build`**. A web server framework was rejected to avoid unnecessary attack surface, dependencies, and operational overhead.

### SQLite (Implemented: Online Hot Backup & Retention)

Status:

- SQLite schema v5 is the operational and incident store through v2.
- Spec 028 implemented online hot backups via SQLite backup API (`tools/event_store_backup.py`), union retention (14 daily / 8 weekly / 12 monthly), and safe staging restore drills.
- Live database is never overwritten automatically.

### Prometheus + Grafana (Implemented)

Status:

- Implemented under Spec 025.
- The native monitor writes an atomic sanitized snapshot (`data/metrics_snapshot.json`).
- Standalone exporter (`tools/metrics_exporter.py`) serves metrics on port 9108 with bounded cardinality.
- Pinned Compose stack provides local dashboards for fleet overview and monitor liveness.
- Telegram remains the sole action and control plane; Grafana is strictly read-only.

Prometheus does not replace API 4028 acquisition. A local exporter converts the
monitor's stable evidence into an HTTP scrape contract.

### MQTT

Potential use:

- Receive electrical measurements from a PDU, UPS, smart meter or edge sensor
  that already publishes MQTT.

Adoption rule:

- Do not add a broker until a real publisher and operational owner exist.
- Treat electrical messages as read-only evidence with source timestamps.
- Never relay existing local SQLite data through MQTT only for novelty.

### OpenTelemetry

Potential use:

- Unify metrics, logs and traces if Miner Alerts becomes several long-lived
  services with more than one observability backend.

Adoption rule:

- Deferred in the current horizon. The OpenTelemetry Collector adds value when
  receiving, processing and exporting multiple telemetry pipelines; one Windows
  monitor plus SQLite does not yet justify that operational layer.

### WebSocket Client

Current use:

- `websocket-client` is isolated to the native read-only Vnish log collector.
- The monitor process does not import it or hold firmware log connections.

Why it matters:

- WebSocket is a standard real-time protocol used across contemporary backend,
  operations and frontend systems.
- A maintained RFC 6455 client handles frames, ping/pong, close behavior and
  socket timeouts more safely than a project-specific implementation.

Adoption rule:

- Keep acquisition bounded, sequential and outside production action paths.
- Do not add retries or permanent workers until collection cost and failure
  behavior are proven from production evidence.

### Windows Scheduled Tasks

Current use:

- Run the bounded Vnish collector every 30 minutes outside the monitor process
  through `pythonw.exe`, without a foreground PowerShell console.
- Use native `IgnoreNew` overlap protection and a ten-minute execution limit.
- Persist collector health in SQLite for `/diagnose` and the local dashboard.

Planned use:

- Run the independent Spec 021 watchdog every minute through `pythonw.exe`.
- Run the Spec 028 backup CLI non-interactively with overlap and duration limits.

Why it matters:

- It matches the native Windows service and Hashcore Toolkit deployment.
- It provides production scheduling without adding a Python daemon, broker, or
  framework dependency.

Adoption rule:

- Keep the collector one-shot, sequential, read-only, and independently
  disableable.
- Use current-user interactive scheduling for this deployment; evaluate a
  dedicated service identity separately if unattended collection while logged
  out becomes a requirement.

### HTMX Or Static HTML Reports

Potential use:

- Lightweight local UI without a large frontend stack.
- Read-only dashboard from diagnostics outputs.

Why it matters:

- Lower complexity than React for internal tools.
- Good fit for server-rendered operational dashboards.

Adoption rule:

- Prefer static HTML first.
- Use HTMX only if live filtering or refresh becomes valuable.

### React

Potential use:

- Full local dashboard if interaction complexity grows.

Why it matters:

- Very high market demand.
- Strong ecosystem.

Adoption rule:

- Do not start with React for this project unless dashboard complexity justifies
  it. A static/HTMX dashboard is likely enough for the first read-only interface.

## Near-Term Recommendation

1. Close Spec 020 runtime activation and observation.
2. Implement Spec 021 independent liveness before changing acquisition.
3. Implement Spec 022 bounded authoritative acquisition with typed provenance.
4. Implement Spec 023 deterministic evidence fusion.
5. Run Spec 024 discovery before selecting an electrical protocol.
6. Add Spec 025 Prometheus/Grafana as isolated read-only observability.
7. Complete Spec 026 Hashcore inventory without expanding actions.
8. Prove Spec 028 backup and staged restore.
9. Execute Spec 027's no-build interface gate.
10. Freeze features and close through Spec 029 stabilization.

## Current Adoption Result

The first local interface is a self-contained static HTML dashboard generated
read-only from SQLite. This deliberately validates the data contract and operator
workflow before adding FastAPI, HTMX, React, authentication, or a permanent web
service. Docker support is limited to the standalone generator; the Windows
monitor and Hashcore Toolkit remain native.

The first adaptive analysis uses explainable robust statistics (median and MAD)
from SQLite rather than a machine-learning framework. For this fleet size, that
keeps decisions deterministic, testable, and understandable while establishing
the data quality needed before considering forecasting or anomaly platforms.

Mining Quality Intelligence extends that contract with interval deltas for
accepted/rejected/stale shares, hardware-error growth, and bounded Vnish chain
evidence. It intentionally stays on Python and SQLite: adding Prometheus, Grafana,
or a time-series database before these metric semantics are proven would increase
operations cost without improving the current reboot decision boundary.

Vnish Log Intelligence adds one focused market-standard dependency,
`websocket-client`, only to a separate Windows CLI. Normalized idempotent events
land in the existing SQLite store and feed `/firmware` plus the static dashboard.
This avoids a persistent WebSocket worker, message broker, or streaming platform
until the fleet produces enough evidence to justify that operational complexity.

Vnish Operations Automation keeps that boundary: native Windows Scheduled Tasks
run the one-shot collector with overlap protection, schema v5 records timestamp
provenance and collector health, and `/diagnose` correlates the evidence from
SQLite only. No new service, queue, database server, or action path was added.

Irregular Miner Episodes preserve the same boundary: API 4028 remains the live
signal, SQLite provides on-demand history, and Telegram receives grouped
episodes. The next reliability investment is independent monitor supervision,
not replacing a low-cost four-miner polling loop with permanent sockets.

## Decision Gate For Any New Technology

Before adding a new dependency or framework, answer:

- What production risk does it reduce?
- What operator workflow does it improve?
- Can it be read-only first?
- Does it avoid secrets in git?
- Does it work on Windows?
- Can it be validated without touching real reboot/restart actions?
- Is it broadly used in the current market?

## Primary References

- WebSocket protocol: https://www.rfc-editor.org/info/rfc6455/
- Prometheus pull model: https://prometheus.io/docs/introduction/overview/
- MQTT 5.0 standard: https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html
- OpenTelemetry Collector architecture: https://opentelemetry.io/docs/collector/architecture/
- Grafana provisioning: https://grafana.com/docs/grafana/latest/administration/provisioning/
- FastAPI features: https://fastapi.tiangolo.com/features/
- SQLite online backup: https://www.sqlite.org/backup.html
- Windows service failure actions: https://learn.microsoft.com/windows/win32/api/winsvc/ns-winsvc-service_failure_actionsw
