# Evidence: Vnish Operations Automation

## Status

Implementation and controlled production rollout complete; Telegram invocation
of `/diagnose` remains an operator smoke from the real chat.

## Test-First Evidence

- Red parser contract: `parse_vnish_log_text()` rejected
  `source_utc_offset_hours` before implementation.
- Red schema contract: `EventStore.record_firmware_event()` rejected source-time
  metadata and collector-run methods were absent before schema v5.
- Red diagnosis contract: `build_miner_diagnosis_text` was absent before the
  SQLite-only renderer and Telegram wiring.
- Targeted parser/store/scheduler/dashboard suite: 32 tests PASS.
- Full suite after rollout fixes: 101 tests PASS.
- `py_compile` passed for monitor, event store, Vnish parser, collector and
  dashboard; both PowerShell scripts parsed without errors.
- `config.example.json`, `git diff --check`, Speckit QA (11/11) and secret-like
  diff scan passed.
- Scheduler `-WhatIf` resolved the intended target
  `\MinerAlerts\MinerAlertsVnishCollector` without registration.
- Controlled rollout found and reproduced a PowerShell 5.1 launch defect: a
  parameter default referenced `$PSScriptRoot` before it was populated under
  `powershell.exe -File`. The runner now resolves its root in the script body,
  the scheduled action sets its working directory, and a regression test covers
  both contracts.
- NSSM rollout also confirmed that stdout is buffered without a configured file
  logger. The central `log()` fallback now flushes every line so startup and
  safety evidence is visible immediately under service redirection.

## Commands Executed

```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
& ".\tools\install_vnish_collector_task.ps1" -WhatIf
& ".\.venv\Scripts\python.exe" tools\vnish_log_collector.py `
  --config app\config.json `
  --db diagnostics\vnish-tail-smoke-017-live.db `
  --tabs status,miner,autotune,system `
  --connect-timeout 3 --idle-timeout 1 `
  --max-bytes 1048576 --max-lines 20000 --max-events 1000
```

## Live Read-Only Smoke

- Host timezone: `Argentina Standard Time` (`UTC-03:00`); local config leaves
  `vnish_log_utc_offset_hours` unset, therefore rows record
  `source_clock=system_local`.
- Isolated ignored database migrated to schema v5.
- First run: 16/16 miner/tab streams succeeded, 6,600 recognized events parsed,
  6,560 inserted, 40 duplicates, zero failures and zero truncated streams.
- Second run against the same database: 6,600 events parsed, zero inserted,
  6,600 duplicates, zero failures and zero truncation.
- Newest-tail correction recovered much newer evidence for miner 23 and 24 than
  the prior oldest-first capped smoke: both now reach `2026/07/08`; miners 25 and
  26 reach `2026/07/20`.
- All 6,560 stored events have source epoch plus `system_local` provenance.
- Stored data remains normalized: category, severity, code, generated summary,
  timestamp provenance and fingerprint; no raw stream content or secrets.
- Dashboard generated from the isolated live database (17,773 bytes), included
  `Collector Vnish`, and contained no token/password/worker markers.

## Safety Evidence

- Collector remains a separate sequential CLI with no retry and no action path.
- Scheduler scripts call only the one-shot collector and configure `IgnoreNew`.
- `/diagnose` tests assert SQLite-only reads and exclusion of old replayed
  firmware evidence from the current 24-hour window.
- No monitor WebSocket worker, state transition, reboot permission or Hashcore
  action was added.

## Pending Final Gate

No required runtime gate remains.

## Controlled Production Rollout

- Registered `\MinerAlerts\MinerAlertsVnishCollector` for the current user at a
  15-minute interval with `IgnoreNew`, `Limited`, a ten-minute limit and the
  repository working directory.
- Reproduced the initial Task Scheduler failure outside the scheduler, corrected
  the PowerShell 5.1 root resolution, then validated both exact external launch
  and scheduled launch with exit/result `0`.
- Final task state: `Ready`, `LastTaskResult=0`, next run `2026-07-21 00:00:00`.
- Restarted the NSSM `MinerAlerts` service through UAC. Final service state is
  `Running`/`Automatic` with a new process tree.
- Immediate flushed startup evidence confirms the real config path,
  `qa_mode=false source=config`, `qa_allow_real_actions=false`, startup safety
  guard `600` seconds, mutex acquired and event store available at schema v5.
- Production SQLite health after restart: latest sample age 82 seconds, latest
  collector run `ok` (16/16, zero failure/truncation), and zero reboot decisions
  in the first three minutes.
- Direct production-DB rendering of `/diagnose 23` returned 8 bounded lines,
  status `OK`, current rate `98.92 TH/s`, collector `OK`, and no recent evidence
  justifying intervention. This call used SQLite only.
- No real Hashcore/reboot/restart action was requested or executed by this
  rollout. Telegram delivery of `/diagnose` from the operator's phone was not
  automated and remains a manual smoke.
- Feature implementation committed as `7108192` and pushed to
  `origin/codex/017-vnish-operations-automation`.
