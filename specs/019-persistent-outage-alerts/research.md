# Research: Persistent Outage Alerts

## Confirmed Baseline

- Confirmed OFFLINE currently depends on `fails_before_alert`; production local config uses one failure and the normal poll is 30 seconds.
- Recovery already requires `recovery_successes`, so persistent reminders can rely on confirmed `MinerState.state` without new miner IO.
- Current STATE CHANGE grouping is limited to one monitor tick. It cannot combine staggered transitions across adjacent ticks.
- Restart recovery suppression is separate and must remain higher priority than generic transition delivery.
- The scheduled collector currently launches `powershell.exe` with `-WindowStyle Hidden` under an interactive principal. Console creation can still steal focus briefly.
- The production virtualenv contains `pythonw.exe`, allowing the scheduled task to avoid a console process entirely.
- Hashcore and selftest use `cmd.exe` through `subprocess.run`; Windows `CREATE_NO_WINDOW` can suppress those consoles without changing command semantics.

## Decisions

1. Use a 30-second state-change coalescing default because it spans one normal polling interval while confirmed outage detection already provides hysteresis.
2. Use a first reminder at 15 minutes and repeats every 30 minutes to avoid both silence and per-tick spam.
3. Track reminders in memory from confirmed state observations; do not add state fields or database migrations.
4. Preserve every transition line within a batch rather than redefining state semantics.
5. Clear generic buffered transitions when a restart recovery summary is emitted.
6. Execute the scheduled collector directly with `pythonw.exe`; keep the PowerShell wrapper for manual/runbook use only.
7. Apply a portable subprocess creation flag at all existing monitor call sites.
