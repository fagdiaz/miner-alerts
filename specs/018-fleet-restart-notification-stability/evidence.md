# Evidence: Fleet Restart Notification Stability

## Incident Baseline

- At `2026-07-21 00:06:06..00:06:10`, Vnish firmware evidence recorded
  `miner_stopped` on miners 23, 24, 25 and 26, followed by firmware
  initialization and controlled cooling/mining startup events.
- Monitor logs contain no Hashcore action during `00:00..00:20`; reboot-decision
  rows contain only `not_low` and `not_sustained` outcomes.
- The first scheduled collector run after rollout started at `00:15:30`, after
  the fleet restart. Earlier collector smoke completed at `23:46:34`.
- The monitor therefore observed but did not initiate the fleet restart. The
  available evidence cannot distinguish an external update/control action from
  a power event, so the prior definitive title was not supported.
- The scheduled task was paused at `14:xx` during triage; `MinerAlerts` remained
  `Running` and `Automatic`.

## Validation

- Red targeted run failed because the coordinator/formatter and hidden/30-minute
  scheduler contracts did not yet exist.
- Targeted restart/scheduler suite after implementation: 12 tests PASS.
- Full suite: 104 tests PASS.
- `py_compile` passed for the monitor, event store, restart intelligence,
  collector and dashboard.
- `config.example.json` parsed, both PowerShell scripts parsed, top-level monitor
  symbols had zero duplicates, and `git diff --check` passed.
- Speckit QA high-risk preflight: PASS, 11/11 checklist items closed.

## Collector Rollout

- Existing task was paused during triage while the `MinerAlerts` service stayed
  `Running`/`Automatic`.
- Reinstalled the task at a 30-minute interval. The registered action includes
  `-WindowStyle Hidden`, keeps the repository working directory and remains
  `IgnoreNew` with a ten-minute execution limit.
- Manual read-only run and the immediately scheduled run both completed with
  `LastTaskResult=0`; the persisted run reported `ok`, 16/16 streams, zero
  failures and zero truncation.
- Latest persisted samples before service rollout showed all four miners `OK`
  at 94.80-99.48 TH/s.

## Pending Final Gate

- Feature commits `7d246fa` and `105abcd` were pushed on the feature branch,
  fast-forwarded into `main`, and published to `origin/main`.
- The direct service restart was rejected by Windows service ACLs before any
  stop occurred. The elevated UAC attempt was explicitly cancelled by Windows.
- `MinerAlerts` remains `Running`/`Automatic` on the prior process tree created
  at `2026-07-20 23:51:06`; no partial stop or duplicate monitor was created.
- Activation of the new notification behavior and post-restart startup evidence
  remain blocked only on one approved elevated restart of `MinerAlerts`.
