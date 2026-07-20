# Data Model: Incident History And Restart Intelligence

## Schema Version

- SQLite `PRAGMA user_version = 1`.
- Initialization is idempotent.
- Future changes use forward-only migrations before increasing `user_version`.

## Entity: TelemetrySample

Purpose: bounded evidence of what the monitor observed for one miner.

| Field | Type | Rules |
|---|---|---|
| id | integer | Primary key |
| observed_ts | real | Unix timestamp, required |
| miner_key | text | Stable `name|host:port`, required |
| miner_name | text | Display-safe miner name, required |
| host | text | Miner host, required |
| state | text | Current machine state, required |
| responded | integer | 0 or 1, required |
| rate_ths | real/null | Last observed hashrate |
| threshold_ths | real | Active threshold, required |
| active_boards | integer/null | Observed active hashboards |
| expected_boards | integer | Configured expected boards |
| elapsed_seconds | integer/null | Miner uptime evidence |

Indexes: `(miner_key, observed_ts DESC)` and `observed_ts`.

## Entity: OperationalEvent

Purpose: durable, normalized evidence for significant monitor occurrences.

| Field | Type | Rules |
|---|---|---|
| id | integer | Primary key and Telegram incident identifier |
| occurred_ts | real | Unix timestamp, required |
| miner_key | text/null | Stable miner identity when applicable |
| miner_name | text/null | Operator-facing name |
| host | text/null | Miner host |
| event_type | text | `restart_detected`, `state_transition`, `auto_reboot_success`, `auto_reboot_failed` |
| severity | text | `info`, `warning`, or `critical` |
| classification | text/null | `expected_manual`, `expected_auto`, or `unexpected` |
| previous_state | text/null | State before event |
| new_state | text/null | State after event |
| rate_ths | real/null | Signal at event time |
| threshold_ths | real/null | Active threshold |
| previous_elapsed | integer/null | Uptime before reset |
| current_elapsed | integer/null | Uptime after reset |
| action_source | text/null | `manual`, `auto`, or null |
| action_ts | real/null | Related action time |
| summary | text | Compact operator summary, required |
| details_json | text | Sanitized extension fields only |

Indexes: `(occurred_ts DESC)`, `(miner_key, occurred_ts DESC)`, and
`(event_type, occurred_ts DESC)`.

## Restart Classification

Input:

- Existing non-empty restart reason from the monitor.
- Detection timestamp.
- Existing `last_manual_reboot_ts` and `last_auto_reboot_ts`.
- Attribution window and clock-skew tolerance.

Rules:

1. Ignore action timestamps beyond allowed future clock skew.
2. Keep actions whose clamped age is inside the attribution window.
3. Choose the newest qualifying action.
4. Map newest manual action to `expected_manual`.
5. Map newest automatic action to `expected_auto`.
6. When none qualifies, classify `unexpected`.

State transition: classification is immutable once the event is stored.

## Retention

- Samples: delete when `observed_ts` is older than configured sample retention.
- Events: delete when `occurred_ts` is older than configured event retention.
- Cleanup runs at initialization and no more than once per 24 hours per process.
- `VACUUM` is not automatic because it can block the running monitor.

## Security And Privacy

- No Telegram token, chat ID, miner credential, config payload, or raw Telegram
  payload is stored.
- `details_json` contains only explicitly supplied sanitized scalar evidence.
- Database and WAL/SHM files are runtime artifacts excluded from Git.
