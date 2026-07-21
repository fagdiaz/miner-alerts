# Telegram Contract: Diagnose

## `/diagnose`

Returns a bounded fleet diagnosis from SQLite.

## `/diagnose all`

Same fleet view, including healthy miners.

## `/diagnose <miner>`

Returns current persisted sample freshness/state/rate, latest operational event,
latest reboot decision, fresh Vnish evidence and collector freshness.

## Safety

- No live miner or WebSocket IO.
- No Hashcore call.
- No state mutation or action recommendation that bypasses confirmation.
