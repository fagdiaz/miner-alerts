# Data Model: Persistent Outage Alerts

## PendingStateChangeBatch

- `first_event_ts`: timestamp of the first buffered transition.
- `event_lines`: ordered transition descriptions accumulated across ticks.
- `reboot_names`: ordered unique reboot labels accumulated across ticks.

The batch is process-local and is cleared after delivery or restart-recovery suppression.

## ActiveOutage

- `miner_key`: stable name/host/port key.
- `name_display`: Telegram display name.
- `host`: miner host.
- `state`: latest confirmed LOW, OFFLINE, or HASHBOARD state.
- `rate_ths`: latest finite rate or no-data value.
- `first_seen_ts`: first confirmed degraded observation in this process.
- `last_reminder_ts`: most recent persistent reminder, if any.

The record is removed on confirmed OK and is never used to authorize an action.
