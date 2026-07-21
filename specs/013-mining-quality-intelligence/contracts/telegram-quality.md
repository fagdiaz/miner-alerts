# Telegram Contract: Quality

## Commands

- `/quality`: bounded fleet summary.
- `/quality all`: same bounded fleet summary.
- `/quality <miner>`: one-miner detail.

## Delivery

- Replies use `is_command=True`, the current update ID, and `dbg_cmd="quality"`.
- No API 4028, HTTP, Hashcore, reboot, or restart call is allowed.
- Missing database/history/miner returns an explicit message.

## Output

- Miner name and status.
- Interval and accepted/rejected/stale deltas when comparable.
- Derived rejected/stale percentages when defined.
- Up to three concise reasons.
