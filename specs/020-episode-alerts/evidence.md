# Evidence: Irregular Miner Episodes

## Baseline

- Real config inspected only through safe keys: poll 30 seconds, one failure to confirm alert, two successes to confirm recovery; no secrets displayed or changed.
- Current status combines live rate with confirmed state, reproducing the possible `97 TH/s [OFFLINE]` contradiction during recovery hysteresis.
- Current restart notification default is 180 seconds, matching the reported three-minute delay.
- Existing SQLite schema 5 already stores every state transition and uptime-reset incident required for an episode timeline.
- Real miner 25 history demonstrates `OK -> OFFLINE`, restart detection, `OFFLINE -> HASHBOARD -> LOW -> OK` with event IDs 33-40.

## Validation

- Baseline action-policy regression before implementation:
  `python -m unittest tests.test_reboot_safety tests.test_monitor_incidents`
  -> 24 tests PASS; QA guard logged a blocked Hashcore action and the mocked
  subprocess was not called.
- Test-first episode/status/history contracts were added before production code;
  the initial targeted result is recorded after execution below.
- Initial red run failed on the intentionally missing episode coordinator,
  `/e<ID>` alias, and episode-history query before production implementation.
- Targeted closeout:
  `python -m unittest tests.test_alert_episodes tests.test_event_store tests.test_monitor_incidents tests.test_notification_stability tests.test_reboot_safety`
  -> 51 tests PASS.
- Full regression with `QA_ALLOW_REAL_ACTIONS=0`:
  `python -m unittest discover -s tests -p "test_*.py"`
  -> 117 tests PASS. The QA Hashcore test logged `Accion bloqueada por QA`
  and the mocked subprocess remained uncalled.
- Syntax and static validation:
  `python -m py_compile app/alert_episodes.py app/event_store.py app/miner_monitor.py tools/miner_diagnostics.py`,
  example-config JSON parse, `git diff --check`, and AST duplicate-symbol scan
  -> PASS; duplicate top-level symbols: none.
- Action-policy invariant: a deterministic extraction from `# Auto-reboot policy`
  to the state-transition persistence branch is byte-identical to HEAD
  (`AUTO_REBOOT_BLOCK_IDENTICAL=True`, SHA-256 prefix `ff337fa5071a`).
- Speckit QA post-implementation preflight with `-RunBuilds` -> PASS,
  requirements checklist 16/16, diff check PASS, Python compile PASS.
- Production local config was inspected only through non-secret keys. It has
  `qa_mode=false`, `poll_seconds=30`, and no explicit legacy/new episode cadence,
  so the new production defaults apply without editing secrets.

## Implemented Contract

- Initial/restart/recovery events from adjacent miners share one bounded
  30-second notification window.
- Persistent reminders use episode ages 5, 10, 15, 30, 60 and 120 minutes,
  then hourly; nearby due miners share one Telegram message.
- Recovery messages retain a bounded sequence such as `OK -> LOW -> OK` or
  `OK -> REINICIO -> PLACAS 0/3 -> LOW -> OK`.
- `/status` renders only current response/rate/board evidence and uses
  `RECUPERANDO` during confirmed-state hysteresis.
- `/e<ID>` and `/event <id>` read the existing SQLite store and render a bounded
  chronological episode timeline, including related fleet events.
- No schema migration, new dependency, miner IO, Hashcore path, cooldown,
  startup guard, state machine, or polling-offset change was introduced.

## Runtime Rollout

- Pending commit, push, controlled `MinerAlerts` restart, startup log inspection,
  and read-only Telegram smoke.
