# Evidence: Monitor Liveness Watchdog

**Status**: Activated; SCM recovery proof passed; D+1/D+3 observation pending

## Planning Baseline

- Spec package generated on 2026-08-13.
- Dependency gate: Spec 020 production activation, smoke and initial soak.
- Risk class: HIGH.
- No production code, local config, state, service or miner was changed by specification generation.

## Runtime Baseline - 2026-08-13

- `MinerAlerts` is `RUNNING` and automatic under NSSM. Wrapper PID `32796` owns
  one monitor child PID `36396`; the child logged
  `mutex=Global\\MinerAlertsMonitor_fagdiaz acquired=True` once.
- Current startup proves the real script path, ignored config hash `14955dc1`,
  `qa_mode=false`, startup guard 600 seconds, conservative auto-reboot
  interlocks and EventStore schema 5.
- Existing source has one monitor loop, one Telegram poller thread and one
  sender thread, but no cross-process heartbeat or independent worker-freshness
  contract. Therefore SCM `RUNNING` cannot distinguish a completed-tick stall.
- `sc.exe qfailure MinerAlerts` reports reset period `0` and no configured
  recovery command/actions. NSSM `AppExit Default` is `Restart`; this baseline
  was captured read-only and no SCM setting was changed.
- Spec 030 read-only smoke immediately before this baseline returned `/help`,
  `/help reboot_no_ok`, `/status` and `/events`; all four miners were healthy.

## Required Evidence Before Completion

- Exact tests and compilation.
- Before/after SCM failure-action export.
- Sanitized heartbeat samples.
- Watchdog open/recovery logs and delivery.
- New PID, mutex, startup guard and no-action proof.

## Runtime Rollout

- A bounded 15-minute maintenance lease was created before the controlled
  rollout and explicitly cleared after healthy scheduled assessments.
- A direct non-elevated `Restart-Service` attempt was denied by Windows and did
  not change the running service or PID. After explicit approval of the SYSTEM
  task, SCM policy and production restart blast radius, one elevated activation
  completed at `2026-08-13T15:37:07-03:00`.
- `MinerAlertsWatchdog` was installed under `\MinerAlerts\` as a hidden
  `pythonw.exe` SYSTEM task with `IgnoreNew`; its first forced execution ended
  `Ready` with result `0`.
- Pre-change SCM settings were exported locally to ignored artifact
  `service-recovery-before-20260813-153652.txt`. The active policy has reset
  period 86400 seconds and restart delays 60s, 60s and 300s.
- The service wrapper changed to PID `28376`; one monitor child PID `31820`
  acquired the existing global mutex and logged the 600-second startup guard,
  `qa_mode=false`, `qa_allow_real_actions=false`, config hash `14955dc1` and
  EventStore schema 5.
- Heartbeat schema 1 appeared on the first completed tick. A later sample had
  tick sequence 5, tick age 18s, poller age 19s, sender age 21s, queue depth 0
  and collector age 1667s.
- Scheduled watchdog assessments at 15:37:03, 15:37:52 and 15:38:52 were
  healthy with no reason codes and no incident. The last assessment occurred
  after maintenance was cleared.
- A one-shot independent Telegram delivery returned success and was observed as
  `PRUEBA WATCHDOG`; it explicitly stated that no miner action was executed.
- `/status` through the restarted monitor returned all four miners healthy at
  98.25, 101.02, 99.62 and 100.47 TH/s.
- The post-start log contained no auto-reboot, Hashcore call, traceback or error.
- D+1/D+3 observations remain open; do not mark this spec complete from
  activation and recovery proof alone.
- A destructive recovery attempt was prepared under a 20-minute maintenance
  lease. Direct `taskkill /T /F` of wrapper PID `28376` was denied by Windows
  for all LocalSystem processes, and the elevated launcher did not complete the
  UAC boundary. No process was terminated: wrapper PID `28376`, monitor PID
  `31820` and heartbeat sequence continued unchanged. The lease was explicitly
  cleared; scheduled assessments remained healthy. This initial attempt is
  retained as evidence that non-elevated process control could not cross the
  LocalSystem boundary; it was superseded by the controlled proof below.

## Controlled SCM Recovery Proof - 2026-08-13

- A bounded maintenance lease was active before one elevated, tree-scoped
  termination of service wrapper PID `28376` and monitor PID `31820` at
  `2026-08-13T17:22:14-03:00`. No miner or Hashcore action was requested.
- SCM reported `STOPPED` during the configured first 60-second delay, then
  `START_PENDING` at `17:23:14` and `RUNNING` at `17:23:19` with new wrapper
  PID `35836`.
- The replacement monitor PID `35788` published heartbeat schema 1, tick 1 at
  `17:23:22`. Startup logs proved the same global mutex, config hash `14955dc1`,
  `qa_mode=false`, `qa_allow_real_actions=false`, startup guard 600 seconds and
  EventStore schema 5.
- During the outage the watchdog classified
  `service_stopped,process_missing` and suppressed notification under the
  maintenance lease. After recovery it returned to healthy with no incident or
  action. Maintenance was then cleared explicitly; the next scheduled
  assessment remained healthy and unsuppressed.
- `sc.exe qfailure MinerAlerts` still reported reset 86400 seconds and restart
  delays 60s, 60s and 300s. The ignored pre-change rollback export remains
  available locally.
- A post-recovery heartbeat sample reported monitor PID `35788`, tick sequence
  5, tick age 15s, poller age 16s, sender age 18s and queue depth 0. The service
  log contained no auto-reboot, Hashcore invocation, traceback or runtime error
  in the recovery window.
- Telegram emitted one fresh `STARTUP` message with all four miners healthy;
  a subsequent `/status` response reported all four between 97.60 and
  101.33 TH/s.
- Recovery proof result: `PASS`. The only remaining release gate is the
  time-bound D+1/D+3 observation.

## D+0 Post-Recovery Observation - 2026-08-13

- At `19:15-03:00`, almost two hours after recovery, `MinerAlerts` remained
  `RUNNING` on wrapper PID `35836`; heartbeat schema 1 remained on monitor PID
  `35788` with tick sequence 225, tick age 2s, poller age 45s, sender age 5s and
  queue depth 0.
- The watchdog produced 114 consecutive assessments from `17:23:53` through
  `19:15:53`, all healthy, unsuppressed, with `reasons=none` and `action=none`.
  Its persisted incident state was closed with zero notifications.
- Only one post-recovery mutex acquisition exists in the service log:
  monitor PID `35788`, global mutex acquired. The launcher PID `26324` and
  monitor PID `35788` are the expected virtualenv shim/runtime pair, not two
  monitor authorities.
- Read-only SQLite inspection since recovery found 92 telemetry samples, zero
  operational events, zero reboot decisions and four successful collector
  runs. Latest fleet samples were all `OK` at 95.86-101.05 TH/s; the latest
  collector run completed 16/16 streams with zero failures.
- The post-recovery service-log slice contained zero `HASHCORE`,
  `AUTO-REBOOT`, traceback, Telegram delivery error or application error
  entries. The historical `err.log` was unchanged after startup and contains
  no new runtime exception.
- Full regression remained 148/148 PASS; monitor/liveness/watchdog
  `py_compile` and `git diff --check` passed.
- Direct CIM and ScheduledTasks metadata queries from the non-elevated shell
  remained access denied. This did not affect the observation: `sc queryex`,
  the minute-cadence watchdog log, heartbeat and prior elevated installation
  evidence all remained consistent.
- D+0 result: `PASS`. D+1 and D+3 remain intentionally open until their real
  observation windows elapse.

## Reproducible Observation Gate - 2026-08-13

- Added `tools/observe_liveness.py`, a standard-library, read-only observer for
  D+0/D+1/D+3. It reads sanitized heartbeat/watchdog state, `sc queryex`, the
  watchdog log and SQLite through `mode=ro`; it imports no monitor, miner API or
  Hashcore authority.
- The versioned report checks the real elapsed-time gate, current service and
  worker freshness, watchdog cadence and age distributions, closed incident
  state, telemetry persistence, latest collector result and absence of
  automatic actions. Optional JSON output is written only when requested under
  ignored `artifacts/`.
- Seven deterministic tests cover localized service parsing, observation-window
  filtering, cadence/statistics, early-window rejection, action detection,
  clock skew, stale watchdog/persistence, collector failure and hidden task
  installer safety.
- Live D+0 execution returned exit code 0. It observed 148 watchdog samples at
  full cadence, zero unhealthy/reason/action assessments, wrapper PID `35836`,
  monitor PID `35788`, fresh workers, 120 telemetry samples, five collector
  runs, no operational/reboot records and a current all-OK fleet.
- A deliberate D+1 execution before 24 hours returned exit code 2 with
  `observation_window_incomplete`, proving the calendar gate cannot be closed
  early. No runtime process, service, task, miner or config was changed.
- Post-tool regression: full suite 155/155, Speckit QA preflight,
  `py_compile`, JSON parse, authority/redaction/ignore scans and
  `git diff --check` all passed.

## Automatic D+1/D+3 Capture - 2026-08-13

- Added `tools/install_liveness_observation_tasks.ps1` with dry-run and
  uninstall modes. It creates only two one-shot, hidden `pythonw.exe` tasks and
  has no service-control, Telegram, miner API or Hashcore authority.
- The first non-elevated registration was denied by Windows. The installer was
  hardened with terminating `-ErrorAction Stop` so a denied registration can no
  longer print a misleading success plan.
- One UAC-elevated installation then succeeded. Both tasks run as `SYSTEM` with
  `ServiceAccount`, `Highest`, `IgnoreNew`, `StartWhenAvailable` and a five-minute
  execution limit; neither has run early (`0x41303`, not yet run).
- `MinerAlertsLivenessD1` is `Ready` for 2026-08-14 17:28 ART and writes ignored
  `artifacts/spec021-d1-observation.json`.
- `MinerAlertsLivenessD3` is `Ready` for 2026-08-16 17:28 ART and writes ignored
  `artifacts/spec021-d3-observation.json`.
- Both start five minutes after the exact 24/72-hour boundaries, use the same
  recovery timestamp and remain available after missed start time. Installation
  did not restart or alter `MinerAlerts`, its watchdog or any miner.

## Implementation And Deterministic Validation - 2026-08-13

- Added versioned, atomically replaced heartbeat state with PID, process start,
  completed tick sequence/time, poller/sender freshness, queue depth and
  collector age. The call runs after state persistence and before the tick
  sleep; its entire enrichment/write path is best-effort and cannot terminate
  monitoring.
- Added independent service/process/tick/worker/collector classification,
  clock-skew handling, bounded maintenance leases, incident dedupe/reminders,
  recovery closure and sanitized rendering. UTF-8 BOM input is accepted for
  Windows-authored JSON.
- Added a read-only watchdog CLI. It imports no monitor, miner API or Hashcore
  action authority, has no retries, keeps failed deliveries retryable, and
  makes `--no-notify` non-consuming for incident delivery state.
- Added a hidden `pythonw.exe` Scheduled Task installer with `IgnoreNew`, a
  two-minute execution limit, one-minute cadence and optional explicit SCM
  recovery plus ignored rollback export.
- `tests.test_monitor_liveness`: 19/19 PASS.
- Reboot/Telegram safety regression subset: 26/26 PASS.
- Final full suite: 148/148 PASS.
- `py_compile` for monitor/liveness/watchdog/diagnostics, config JSON parse,
  PowerShell parser and `git diff --check`: PASS.
- AST duplicate top-level symbols: zero. Tracked Telegram token-shaped strings:
  zero. Config/state/heartbeat/watchdog/log/artifact paths: ignored by Git.
- Synthetic no-action scenarios classified exactly:
  `kill=service_stopped,process_missing`, `hang=tick_stale`, and
  `stale_worker=telegram_poller_stale,telegram_sender_stale`.
- Source authority scan found no Hashcore, miner API, miner address or monitor
  action import in the watchdog.
