# Data Model: Vnish Log Intelligence

## Firmware Event

- `id`: local integer identifier.
- `collected_ts`: local epoch when observed.
- `source_ts_text`: firmware timestamp retained as bounded text without timezone conversion.
- `miner_key`, `miner_name`, `host`: existing fleet identity.
- `source_tab`: one of `status`, `miner`, `autotune`, `system`.
- `source_fingerprint`: SHA-256 of source identity and raw line, used only for dedupe.
- `category`: transition, restart, chain, thermal, power, fan, pool_network.
- `severity`: info, warning, critical.
- `code`: stable taxonomy identifier.
- `summary`: generated bounded operator text, never the raw line.

## Constraints

- Unique `(miner_key, source_tab, source_fingerprint)`.
- Source timestamp and summary have strict maximum lengths.
- Unknown lines do not create records.
- Retention uses `collected_ts` and existing event retention days.

## Collection Result

- miner/tab
- bytes received
- lines inspected
- events parsed
- events inserted
- duplicates ignored
- bounded error category
