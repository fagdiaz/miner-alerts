# Data Model: Vnish Operations Automation

## firmware_events schema v5 additions

- `source_ts_epoch REAL NULL`: parsed source wall-clock timestamp.
- `source_clock TEXT NOT NULL`: `system_local`, `fixed_utc_offset`, or `unparsed`.

Existing uniqueness remains `(miner_key, source_tab, source_fingerprint)`.
Duplicate collection may fill missing timestamp metadata but cannot add a row.

## collector_runs

- start/end timestamp and status.
- attempted/succeeded/failed miner-tab counts.
- parsed/inserted/duplicate/failed event counts.
- truncated-stream count.
- generated bounded summary only.

No raw line, token, worker, payload or command output is stored.
