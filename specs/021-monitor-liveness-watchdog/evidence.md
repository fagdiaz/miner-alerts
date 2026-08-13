# Evidence: Monitor Liveness Watchdog

**Status**: Activated; destructive SCM recovery proof and D+1/D+3 observation pending

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
- The destructive failure-action firing test and D+1/D+3 observations remain
  open; do not mark this spec complete from activation alone.
- A destructive recovery attempt was prepared under a 20-minute maintenance
  lease. Direct `taskkill /T /F` of wrapper PID `28376` was denied by Windows
  for all LocalSystem processes, and the elevated launcher did not complete the
  UAC boundary. No process was terminated: wrapper PID `28376`, monitor PID
  `31820` and heartbeat sequence continued unchanged. The lease was explicitly
  cleared; scheduled assessments remained healthy. This is recorded as a host
  elevation blocker, not as SCM recovery proof.

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
