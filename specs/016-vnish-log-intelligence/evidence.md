# Evidence: Vnish Log Intelligence

## Status

Implementation and read-only validation complete. The running `MinerAlerts`
service was intentionally not restarted; `/firmware` activation remains pending
the final controlled rollout.

## Discovery Evidence

- Vnish version: 1.2.7, S19j Pro, BeagleBone platform.
- Confirmed GET API: summary/chains/metrics.
- Confirmed SPA WebSocket: `/api/v1/logs-ws/{status|miner|autotune|system}`.
- Bounded status stream returned 16,374 bytes in its first fragmented message.
- Observed categories include normal initialization/autotune and a chain-break restart.
- Raw probe output was not persisted or committed.

## Implementation Evidence

- Added pure bounded taxonomy/parser in `app/vnish_logs.py`; no network, action,
  Telegram, subprocess, or file-write dependency.
- Migrated SQLite additively from schema v1/v2/v3 to schema v4 with an idempotent
  `firmware_events` table. Existing tests verify preserved prior rows.
- Added a separate sequential CLI in `tools/vnish_log_collector.py`. The monitor
  never imports `websocket-client` and does not keep firmware-log connections.
- Added bounded SQLite-only `/firmware [all|miner]` and the read-only dashboard
  timeline. Neither path calls API 4028, WebSocket, Hashcore, or action policy.
- Unknown source lines are ignored. Persisted rows contain generated summaries
  and SHA-256 fingerprints, never raw log text.

## Validation

### TDD and automated checks

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_vnish_logs tests.test_event_store tests.test_operations_dashboard
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py app\event_store.py app\vnish_logs.py tools\vnish_log_collector.py tools\operations_dashboard.py
git diff --check
```

- Initial focused run failed because the parser/store/command/dashboard did not
  exist, establishing the red phase.
- Focused result after implementation: 24/24 PASS.
- Final suite after unreachable-miner regression test: 93/93 PASS.
- `py_compile` and `git diff --check`: PASS.
- Static safety check: collector has no HTTP POST or Hashcore call; `/firmware`
  route has no live miner/WebSocket/action IO and uses command delivery semantics.
- Parser benchmark: 5,000 bounded events from 1,420,000 input bytes in 39.48 ms.
- Speckit QA preflight with `-RunBuilds`: PASS, checklist 11/11, diff and compile PASS.

### Dependency and live read-only smoke

```powershell
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
& ".\.venv\Scripts\python.exe" tools\vnish_log_collector.py --config app\config.json --dry-run --tabs status,miner,autotune,system --connect-timeout 2 --idle-timeout 0.3 --max-bytes 65536 --max-lines 1000 --max-events 100
```

- Installed and imported `websocket-client 1.9.0` inside the project venv.
- All 16 miner/tab combinations completed without action or persistence.
- Every miner returned bounded `status`, `autotune`, and `system` data; one
  `miner` tab returned an empty successful stream, which is handled explicitly.
- Some streams reached the 65,536-byte cap and reported `truncated=true` as designed.

### Isolated persistence and dashboard smoke

Two identical bounded `status` collections used
`diagnostics/vnish-log-smoke.db`, which is ignored by Git:

- First pass: 800 inserted, 0 duplicates, 0 failed.
- Second pass: 0 inserted, 800 duplicates, 0 failed.
- Schema version: 4; rows: 800.
- Categories: chain 1, pool/network 6, restart 136, thermal 4, transition 653.
- Maximum generated summary: 41 characters; worker/path/password scan: 0 hits.
- Native dashboard smoke: PASS, firmware timeline present, no remote URLs.
- `docker build -f Dockerfile.dashboard -t miner-alerts-dashboard:spec016 .`: PASS.
- Docker dashboard generation against the isolated DB: PASS, 17,600 bytes and
  firmware timeline present.

## Residual Validation

- Firmware timestamps remain source text because timezone provenance is unknown.
- Taxonomy precision must be observed over production history before any alert or
  auto-reboot policy consumes these events; such coupling is out of scope.
- `/firmware` runtime reply remains unverified until the agreed final service restart.
- `MinerAlerts` remained `Running` with automatic startup throughout this spec.
