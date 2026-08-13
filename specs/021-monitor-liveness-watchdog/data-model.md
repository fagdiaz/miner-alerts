# Data Model: Monitor Liveness Watchdog

## MonitorHeartbeat

- `schema_version`: Parser compatibility.
- `pid`: Current monitor process.
- `process_start_ts`: Restart identity.
- `tick_sequence`: Strictly increasing completed-tick counter.
- `last_tick_completed_ts`: Written only after fleet completion.
- `telegram_poller_ts / telegram_sender_ts`: Worker progress.
- `queue_depth`: Bounded backlog indicator.
- `collector_age_seconds`: Latest known Vnish collector age.

## LivenessIncident

- `reason_code`: Stable classification.
- `opened_ts / last_seen_ts / closed_ts`: Lifecycle.
- `last_notified_ts`: Deduplication state.
- `evidence`: Sanitized ages and service/process observations.

## MaintenanceLease

- `expires_ts`: Automatic expiry.
- `reason`: Short operator reason.

## Invariants

- Tick sequence never decreases within one process.
- Heartbeat is never an action trigger.
- Maintenance cannot outlive its lease.
- No entity stores Telegram tokens, miner credentials or full config.
