# Evidence: Vnish Telemetry And Reboot Decision Audit

**Status**: Implementation and local validation complete
**Service activation**: Completed by the controlled Spec 017 rollout.

## Static Validation

### Python compilation

```powershell
& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py app\\event_store.py app\\restart_intelligence.py app\\vnish_telemetry.py tools\\miner_diagnostics.py tools\\diagnostics_baseline.py tools\\incident_report.py
```

Result: PASS, exit code 0 with no compiler output.

### Shared config and diagnostics dry run

```powershell
& ".\\.venv\\Scripts\\python.exe" -c "import json,pathlib; json.loads(pathlib.Path('app/config.example.json').read_text(encoding='utf-8')); print('config.example.json: OK')"
& ".\\.venv\\Scripts\\python.exe" tools\\miner_diagnostics.py --config app\\config.example.json --out "$env:TEMP\\miner-alerts-spec007-dryrun" --dry-run
```

Result: PASS. JSON parsed and the read-only diagnostics dry run wrote its temp output.

### Repository hygiene

`git diff --check`: PASS; only expected Git CRLF conversion warnings were emitted.

`git check-ignore -v` confirmed ignore coverage for:

- `app/config.json`
- `app/state.json`
- `data/miner_alerts.db`, `-wal`, and `-shm`
- `logs/out.log`

## Unit Validation

```powershell
& ".\\.venv\\Scripts\\python.exe" -m unittest discover -s tests -v
```

Result: PASS, 30 tests. Coverage includes:

- schema-v1 to schema-v2 migration with prior sample preservation;
- normalized Vnish fields from `STATS[1]` and malformed/missing values;
- retention, reopen, concurrency, and storage-failure containment;
- all nine audit result values;
- `/why@BotName` parsing and preservation of the existing first-entry board signal;
- read-only report correlation and rejection of writes;
- existing restart classification, Telegram history, and QA Hashcore block tests.

The report CLI also returned exit code 0 against a temporary schema-v2 database.

### Speckit QA

Initial and final HIGH-risk preflight runs with builds: PASS. Final result:

```text
Status=PASS; checklist=10/10; git-diff-check=PASS; python-py-compile=PASS
```

## Runtime Validation

`Get-Service -Name MinerAlerts` reports `Running`. The service was intentionally
not restarted, so it continues running the previously loaded code. CIM PID detail
was blocked by Windows ACL (`Access denied`); no stop/start command was attempted.

The following remain explicitly unverified until the planned end-of-day restart:

- startup log `EVENT_STORE ... schema=2`;
- first persisted production telemetry/decision rows;
- live `/why` and `/why 23` Telegram replies;
- production-service migration of the local schema-v1 database.

## Safety Review

- Existing state transition conditions and auto-reboot gate ordering were not changed.
- `read_stats_snapshot` preserves the previous first-entry active-board signal and only exposes the same response to the observational parser.
- Decision writes occur around existing branch results and cannot invoke Hashcore.
- `/why` and `tools/incident_report.py` read local SQLite only.
- The report opens SQLite with `mode=ro`.
- No raw ASIC response or secret-bearing config data is persisted.
- Chain voltage is explicitly labeled as non-AC evidence.
- A pre-existing invalid-signal policy risk was documented in the roadmap and was not silently changed in this feature.
