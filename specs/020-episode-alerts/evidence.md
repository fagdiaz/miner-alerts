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

- Commit `e502ab9` was fast-forwarded and pushed to `origin/main` on 2026-07-21.
- A later startup block proves the committed implementation was activated on
  2026-08-06 at 14:01:55: process PID 7892 acquired the global mutex, loaded the
  repository `app/miner_monitor.py`, read the expected absolute config path,
  selected `qa_mode=false source=config`, enabled the 600-second startup guard,
  and opened EventStore schema 5.
- The working source blobs for `app/miner_monitor.py`, `app/alert_episodes.py`
  and `app/event_store.py` match the three blobs in commit `e502ab9` exactly.
- No Hashcore action or automatic reboot occurred in the first 12 minutes after
  that startup. Subsequent persisted history through 2026-08-13 demonstrates
  live state/restart recording and recovery sequences under the deployed code.
- Read-only API 4028 smoke on 2026-08-13 returned all four configured miners,
  each responding with three active boards and finite above-threshold hashrate.
- Local rendering from those current samples produced four healthy status lines
  and no positive-hashrate plus OFFLINE contradiction. Read-only SQLite smoke
  reported schema 5, rendered `/e531` through `/e524`, and reconstructed a
  bounded related timeline for event 531.
- Telegram Bot API `getMe` and `getWebhookInfo` returned HTTP 200/`ok=true`;
  webhook was unset and pending update count was zero, consistent with polling.

## Security Containment Discovered During Closeout

- Historical `getUpdates` transport exceptions embedded the Telegram request
  URL and therefore copied the bot token into the ignored local stdout log.
  The real token was not found in any tracked file.
- Added `_redact_telegram_token` at every Telegram response/exception logging
  boundary plus a regression test. Targeted closeout is now 52 tests PASS; full
  regression is 118 tests PASS; compilation, example JSON, duplicate-symbol
  scan and `git diff --check` pass.
- The first direct restart attempt on 2026-08-13 was rejected by the Windows
  service ACL before stop; `MinerAlerts` remained `Running` and no second
  monitor was started. A subsequent explicit UAC-approved NSSM restart completed
  successfully at 13:17:17.
- The new monitor process PID 27860 acquired the mutex exactly once, loaded the
  patched source, selected `qa_mode=false source=config`, enabled the 600-second
  startup guard and opened EventStore schema 5. NSSM service PID changed from
  5004 to 16008 and remained `Running`.
- No Hashcore or auto-reboot action was observed after the restart during the
  inspected startup-guard window. The 1,752 log bytes written after activation
  contain zero occurrences of the configured token.
- Outbound Telegram validation delivered one read-only smoke instruction with
  HTTP 200/`ok=true`. The polling update ID did not advance during the following
  75 seconds because the requested commands were not yet sent from the
  authorized user account.

## Final Production Closure - 2026-08-13

- The authorized Telegram account executed `/status`, `/events` and `/e531`
  against the running service. `/status` returned four finite healthy rates,
  `/events` returned the eight newest persisted events with click-safe `/e<ID>`
  links, and `/e531` returned the complete bounded `OK -> OFFLINE -> REINICIO ->
  LOW/HASHBOARD -> OK` related timeline.
- BotFather revoked the credential previously exposed only in the ignored local
  log and issued a replacement. Only local ignored `app/config.json` was updated;
  the replacement token passed Bot API `getMe` before service activation. No
  credential value was added to tracked files or documentation.
- NSSM restarted `MinerAlerts` once after rotation: service PID changed from
  16008 to 36380 and child PID 28448 acquired the global mutex exactly once at
  14:18:19. The process loaded config SHA prefix `14955dc1`, selected
  `qa_mode=false source=config`, retained `qa_allow_real_actions=false`, and
  enabled the 600-second startup guard.
- The first 1,752 bytes after final activation contained zero configured-token
  occurrences, no traceback, no getUpdates exception and no Hashcore or
  auto-reboot action. A new `/status` sent after rotation was consumed and
  answered with four healthy miners, proving inbound polling and outbound
  delivery with the replacement credential.
- Final regression on the activated source: 118 tests PASS, Python compilation
  PASS, `git diff --check` PASS. The earlier D+7 deployed observation and the
  final controlled restart show no open P0/P1 regression attributable to Spec
  020. T020 and the production gate are closed.
