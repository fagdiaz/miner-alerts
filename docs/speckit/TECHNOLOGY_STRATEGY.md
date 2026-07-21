# Miner Alerts Technology Strategy

## Principle

New technology should be added only when it reduces operational risk, improves
diagnostics, or creates a clear learning path with market value. Miner Alerts is
production-adjacent, so the default is conservative: add read-only tooling first,
then controlled automation.

## Current Baseline

- Python: appropriate for ASIC API tooling, Telegram polling, CLI automation and
  fast diagnostics.
- Windows service/process: appropriate while Hashcore Toolkit CLI is local and
  Windows-based.
- Docker: appropriate for isolated read-only tools, reports and future local
  dashboards; not yet appropriate for the main monitor while Hashcore CLI and
  Windows service integration remain local.

## Recommended Technology Path

### Docker

Use for:

- Read-only diagnostics collectors.
- Static report generation.
- Future local dashboards that do not execute reboot/restart actions.

Why it matters:

- High market demand.
- Standard for reproducible environments.
- Useful for CI/CD and operations.

Do not use yet for:

- The production monitor process.
- Hashcore Toolkit actions that depend on Windows-local installation paths.

### FastAPI

Potential use:

- Local read-only API over diagnostics snapshots and baseline reports.
- Future dashboard backend.

Why it matters:

- Popular Python web framework.
- Strong async support, OpenAPI docs, typing-first design.
- High demand in automation, AI tooling and internal platforms.

Adoption rule:

- Start read-only.
- Bind local-only by default.
- No reboot/restart endpoints until authentication, audit logs and confirmation
  are designed.

### SQLite Or DuckDB

Potential use:

- Store historical diagnostics snapshots locally.
- Query trend windows for TH/s, temperature, chain voltage, consumption and HW
  errors.

Why it matters:

- SQLite is ubiquitous, reliable and built into Python.
- DuckDB is strong for analytics over local files and time-series-like reports.

Adoption rule:

- Prefer SQLite if the app needs durable operational state.
- Prefer DuckDB or plain JSON/Parquet later if analysis becomes heavier.

### Prometheus + Grafana

Potential use:

- Long-term metrics dashboard for hash, temps, board count and Telegram delivery
  health.

Why it matters:

- Very high operations market demand.
- Industry-standard monitoring stack.

Adoption rule:

- Introduce only after metric names and labels are stable.
- Keep Telegram as the action/control plane.
- Use Grafana read-only at first.

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

- Run the bounded Vnish collector every 30 minutes outside the monitor process in a hidden PowerShell window.
- Use native `IgnoreNew` overlap protection and a ten-minute execution limit.
- Persist collector health in SQLite for `/diagnose` and the local dashboard.

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

1. Keep the monitor stable on Windows.
2. Use Python tools for diagnostics and baseline collection.
3. Use Docker for reproducible read-only tooling.
4. Add a static HTML report before any web server.
5. If a server becomes necessary, choose FastAPI.
6. If long-term metrics become necessary, evaluate Prometheus/Grafana.

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

## Decision Gate For Any New Technology

Before adding a new dependency or framework, answer:

- What production risk does it reduce?
- What operator workflow does it improve?
- Can it be read-only first?
- Does it avoid secrets in git?
- Does it work on Windows?
- Can it be validated without touching real reboot/restart actions?
- Is it broadly used in the current market?
