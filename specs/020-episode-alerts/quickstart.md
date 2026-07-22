# Quickstart: Irregular Miner Episodes

## Static validation

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\alert_episodes.py app\event_store.py app\miner_monitor.py
& ".\.venv\Scripts\python.exe" -m unittest tests.test_alert_episodes tests.test_notification_stability tests.test_event_store tests.test_monitor_incidents tests.test_reboot_safety
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
git diff --check
```

## Deterministic episode scenarios

1. `OK -> LOW -> OK` within 30 seconds: one grouped recovered episode, complete sequence.
2. `OK -> OFFLINE -> restart -> HASHBOARD -> LOW -> OK`: opening/restart notice by 30 seconds and one recovery sequence.
3. Continuous OFFLINE: reminders at episode ages 5, 10, 15, 30, 60 and 120 minutes, then hourly.
4. Two miners due together: one Telegram payload.
5. Live 97 TH/s while confirmed OFFLINE: status says `RECUPERANDO`, never `[OFFLINE]`.
6. No response after a previous healthy rate: status says `N/A [OFFLINE]`.
7. `/e<ID>` and `/event <id>` return the same anchor and chronological related timeline.

## Safety regression

- Force QA states only; keep `qa_allow_real_actions=false`.
- Assert no Hashcore subprocess is created.
- Compare auto-reboot decision tests before and after implementation.
- Do not modify `app/config.json` or `app/state.json`.

## Runtime rollout

1. Commit and push the feature after all validation passes.
2. Restart `MinerAlerts` once with elevation.
3. Verify new PID, mutex acquisition, `qa_mode=false`, startup guard, SQLite availability and no immediate Hashcore action.
4. Send `/status` and one known `/e<ID>` read-only command.
5. Record exact evidence in `evidence.md` and `docs/audit/DEVELOPMENT_LOG.md`.
