# Quickstart: Telegram Messaging Quality

## Static Validation

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\telegram_messages.py app\alert_episodes.py app\miner_monitor.py
& ".\.venv\Scripts\python.exe" -m unittest tests.test_telegram_messaging tests.test_notification_stability tests.test_alert_episodes tests.test_monitor_incidents tests.test_reboot_safety
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
git diff --check
```

## Deterministic Scenarios

1. Long timeline splits into ordered parts below 3900 characters.
2. `/help` contains every official click-safe command and no promoted legacy hyphen CTA.
3. Command replies bypass dedupe and survive queue pressure or use explicit bounded fallback.
4. Episode replay keeps the exact Spec 020 cadence and grouping.
5. Healthy ticks produce no unsolicited status under production defaults.
6. Logs redact token-like values and expose delivery failures without message payload.

## Runtime Rollout

1. Validate in QA with real actions disabled.
2. Send `/help`, `/status`, `/events`, `/e<ID>` and one invalid confirmation.
3. Verify no `SEND_SKIP` applies to command replies.
4. Restart `MinerAlerts` once and inspect startup guard/mutex.
5. Observe one episode notification/recovery naturally; do not induce a real reboot.
