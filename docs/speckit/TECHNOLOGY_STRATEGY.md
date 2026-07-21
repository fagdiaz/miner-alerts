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

## Decision Gate For Any New Technology

Before adding a new dependency or framework, answer:

- What production risk does it reduce?
- What operator workflow does it improve?
- Can it be read-only first?
- Does it avoid secrets in git?
- Does it work on Windows?
- Can it be validated without touching real reboot/restart actions?
- Is it broadly used in the current market?
