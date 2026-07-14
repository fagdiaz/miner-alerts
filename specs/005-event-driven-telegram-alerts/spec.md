# Feature Specification: Event-Driven Telegram Alerts

## User Story

As the operator, I want Telegram to notify me only on meaningful miner events
instead of repeated hourly status summaries, so the bot remains useful and does
not create alert fatigue.

## Scope

In scope:

- Disable degraded hourly status notifications by default.
- Keep hourly degraded reminders available by explicit config.
- Improve `STATE_CHANGE` message readability with event context.
- Preserve manual `/status` command behavior.

Out of scope:

- Changing the state machine.
- Changing auto-reboot gates.
- Changing Telegram command routing, confirmation, or Hashcore execution.
- Creating a database.

## Acceptance Criteria

- `notify_degraded_hourly` defaults to `false` in `config.example.json`.
- Without explicit config opt-in, the monitor does not send `degraded_hourly`
  status summaries every hour.
- LOW/HASHBOARD/OFFLINE/recovery state-change notifications still work.
- Manual `/status` still returns the current snapshot.
- Python syntax validation passes.
