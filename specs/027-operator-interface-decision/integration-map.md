# Integration Map: Operator Interface Decision

## Existing Surfaces

| Surface | Current capability | Authority | Availability boundary |
| --- | --- | --- | --- |
| Telegram | Remote alerts, status/detail queries and confirmed actions. | Only operator action/control plane. | Production bot/polling. |
| Static HTML | Self-contained fleet, incident, firmware, quality and decision report from SQLite `mode=ro`. | Read-only; no network, monitor or Hashcore imports. | Generated file; not a web service. |
| Grafana (Spec 025) | Planned local current/trend/liveness view from sanitized metrics. | Read-only; metrics are non-canonical. | Not eligible until Spec 025 runtime proof. |
| CLI reports | Local diagnostics and incident reports. | Read-only operator/developer tools. | Not a primary scored UI. |

The current static generator already bounds input windows/rows, escapes HTML and
uses SQLite URI `mode=ro`. It is a valid existing interface, not a prototype to
replace automatically.

## Decision Dependency Flow

```text
Spec 025 Grafana runtime proof ----+
                                   +--> fixed workflow scorecard --> no_build
Spec 028 staging restore proof ----+                         |
                                                             +--> exact failed P1 fields
                                                                      |
                                                                      v
                                                       conditional FastAPI MVP
```

No dependency/source/service file may be added before the scorecard decision.

## Conditional Process Boundary

If and only if `fastapi_mvp` is approved:

- process is native Windows and independent of `MinerAlerts`;
- startup accepts an explicit database path and binds exactly to `127.0.0.1`;
- SQLite opens `file:...?mode=ro`, sets `PRAGMA query_only=ON` and uses a short
  busy timeout; `immutable=1` is prohibited for the live WAL database;
- no `app/config.json`, `state.json`, Telegram token, miner credential or raw
  firmware log is read;
- no import path reaches `app.miner_monitor`, Hashcore, `requests`, `subprocess`
  or ASIC sockets;
- proxy headers and CORS are disabled; no LAN/public bind is accepted;
- process termination cannot stop, delay or change the monitor.

## Conditional Route Allowlist

Routes are generated only for exact fields approved by the scorecard and may be
a subset of this maximum set:

| Route | Method | Bound |
| --- | --- | --- |
| `/health` | GET/HEAD | One service/database freshness record. |
| `/miners` | GET/HEAD | At most 200 sanitized current projections. |
| `/miners/{miner_id}` | GET/HEAD | One projection; logical configured ID only. |
| `/incidents` | GET/HEAD | Default 50, max 200, max 30-day window, cursor ordered. |
| `/incidents/{incident_id}` | GET/HEAD | One bounded facts/assessment projection. |
| `/assessments` | GET/HEAD | Default 50, max 200, max 30-day window. |
| `/history/{miner_id}` | GET/HEAD | Max 30 days and max 200 downsampled/page records. |

POST, PUT, PATCH, DELETE, action, confirmation, config, miner proxy, arbitrary
SQL/export and raw-log routes are prohibited. OpenAPI cannot contain them.

## Query And Error Boundary

- Default page size 50; maximum 200.
- Maximum history window 30 days.
- Stable ordering is event/sample timestamp then integer ID; opaque cursors may
  encode only those values.
- Unsupported schema, busy database, missing database, stale source, invalid
  cursor/filter and row/time limit violations have finite reason codes.
- Responses never include SQL, tracebacks, paths, IPs, host fields, credentials
  or raw persisted payloads.
- Database/schema errors return within 2 seconds and do not retry against the
  monitor or miners.

## No-Build Artifact Boundary

When `no_build` wins, these remain absent:

- `app/operator_api.py` and `app/operator_views.py`;
- `templates/operator/`;
- `tests/test_operator_api.py`;
- `requirements-interface.txt`;
- interface service/task installation files.

The completed decision, scorecard and evidence are the deliverable.
