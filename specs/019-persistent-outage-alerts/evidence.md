# Evidence: Persistent Outage Alerts

## Baseline

- Branch created by the mandatory Speckit git feature hook: `019-persistent-outage-alerts`.
- Production-safe config inspection found `poll_seconds=30`, `fails_before_alert=1`, and `qa_mode=false`; secrets were not displayed or modified.
- Existing Telegram state batching covers only one tick and has no persistent outage reminder.
- Existing restart recovery quieting is present and remains the higher-priority delivery policy.
- The collector task installer launches interactive `powershell.exe`; the virtualenv `pythonw.exe` is present.
- Monitor subprocess call sites do not yet request `CREATE_NO_WINDOW`.

## Validation

- Test-first red evidence: targeted suite initially failed on missing notification
  coordinators, PowerShell scheduler action, and absent subprocess no-window flags.
- Targeted green suite:
  `python -m unittest tests.test_notification_stability tests.test_vnish_scheduler tests.test_monitor_incidents`
  -> 21 tests PASS.
- Full suite:
  `python -m unittest discover -s tests -p "test_*.py"` -> 113 tests PASS.
- `python -m py_compile app/miner_monitor.py tools/vnish_log_collector.py` -> PASS.
- `app/config.example.json` JSON parse, both PowerShell script parsers,
  `git diff --check`, AST duplicate-symbol scan, and all four subprocess
  creationflag checks -> PASS.
- Speckit QA with builds -> PASS; checklist 7/7 and no missing artifact.
- QA safety regression confirms Hashcore is blocked before process creation when
  real QA actions are disabled.

## Controlled Collector Rollout

- Reinstalled `\MinerAlerts\MinerAlertsVnishCollector` at 30 minutes.
- Registered action executable is
  `F:\02-ASIC - mineros\miner-alerts\.venv\Scripts\pythonw.exe`; arguments point
  directly to the bounded collector and contain no PowerShell command.
- Manual and immediately scheduled runs completed `Ready`,
  `LastTaskResult=0`; latest persisted collector run is `ok` with 16/16 streams
  and zero failures.
- Next scheduled run was `2026-07-21 21:10:10`.

## Pending Final Gate

- Commit/integration, controlled `MinerAlerts` service restart, and post-restart
  startup evidence remain pending.
