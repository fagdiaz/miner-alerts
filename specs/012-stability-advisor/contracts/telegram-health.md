# Telegram Contract: `/health`

## Accepted Inputs

- `/health`: fleet summary.
- `/health all`: fleet summary.
- `/health <miner>`: one configured miner by existing resolver semantics.
- Group suffixes such as `/health@BotName` use the existing parser.

## Output

- Header identifying historical stability analysis.
- One bounded block per selected miner.
- Status, latest rate/temperature/boards and evidence age.
- Baseline range when learned.
- At most three reason lines per miner.
- Chain voltage text explicitly says it is not AC input voltage when relevant.

## Failure Behavior

- Unavailable history: deterministic read-only-unavailable response.
- Unknown miner: deterministic miner-not-found response.
- Insufficient data: `LEARNING n/required`, not `OK`.

## Safety

- Reply uses `is_command=True`, update correlation, and existing queue semantics.
- Handler performs no API 4028, Hashcore, restart, reboot, or write operation.
