# Evidence: Stability Advisor

**Status**: Implementation and local validation complete.
**Service activation**: Completed by the controlled Spec 017 rollout.

## Test-First Evidence

The first analyzer run failed with `ModuleNotFoundError` for
`app.stability_profile`. Subsequent red phases proved missing dashboard output,
missing Telegram health wiring, and the false-critical hysteresis case before the
corresponding implementation was added.

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_stability_profile tests.test_operations_dashboard -v
```

Result: PASS, 17 targeted tests. Coverage includes robust bands, latest-sample
exclusion, malformed optional values, learning confidence, hard-fault precedence,
soft drift, recovered-signal hysteresis, bounded Telegram output, command parsing,
SQLite-only health rendering, dashboard reuse, escaping, and read-only SQLite.

## Compile And Regression

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py app\event_store.py app\vnish_telemetry.py app\reboot_safety.py app\stability_profile.py tools\operations_dashboard.py
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -q
```

Result: PASS, 68 tests. The only console line was the expected QA Hashcore block
warning from an existing safety test.

## Performance And Output

- Pure analysis of 5,000 deterministic samples: PASS, 17.84 ms.
- Native Windows CLI `tools\operations_dashboard.py --help`: PASS.
- Native fixture generation: PASS, 12,484-byte self-contained HTML.
- Docker image `miner-alerts-dashboard:stability-qa`: build PASS.
- Docker read-only fixture generation: PASS, 12,335-byte HTML.
- Generated files remain under ignored `diagnostics/` paths.

## Safety Evidence

- Static tests prove the analyzer and `/health` path contain no `read_summary`,
  stats/pools/version request, subprocess, Hashcore, or action call.
- `/health` reads bounded samples through `EventStore.list_samples` and replies
  with `is_command=True`, update correlation, and `dbg_cmd="health"`.
- Fleet output is capped at ten miners and reasons are bounded.
- The current sample is never used to train its own baseline.
- A recovered finite signal retained as LOW by state hysteresis is `WATCH`, not
  `CRITICAL`; no state-machine behavior was changed.
- Chain voltage is explicitly labeled as non-AC evidence.
- Auto-reboot, startup guard, cooldown/window, QA, manual confirm, polling, and
  Hashcore blocks have no diff.

## Final Gates And Runtime

- `git diff --check`: PASS.
- Speckit QA with builds: PASS, checklist 8/8.
- `MinerAlerts` Windows service: `Running`, `Automatic`.
- `data/miner_alerts.db`: not present because the service still runs the previous
  build; this correctly leaves live `/health` activation unverified until restart.
- No service restart was attempted.
