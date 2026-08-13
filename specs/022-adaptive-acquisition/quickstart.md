# Quickstart: Adaptive Acquisition Resilience

**Status**: Planned validation procedure; referenced implementation files do not exist yet.

## Preconditions

- Spec 021 has completed its acceptance and observation gates.
- Spec 020 episode/status behavior is production-verified.

## Static And Automated Validation

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_acquisition tests.test_reboot_safety tests.test_telegram_polling_stability
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
& ".\.venv\Scripts\python.exe" -m py_compile app\acquisition.py app\miner_monitor.py
Get-Content app\config.example.json -Raw | ConvertFrom-Json | Out-Null
```

## Controlled Runtime Validation

1. Collect 24 hours of baseline latency, timeout, request and tick metrics.
2. Replay slow, timeout and late endpoints in QA.
3. Run production shadow metrics before enabling bounded acquisition.
4. Observe D+1/D+3 for request volume, age, alert timing and actions.

## Evidence To Capture

- Before/after request, latency and tick report.
- Envelope fixtures for invalid, late and diagnostic handling.
- State, action and Telegram-offset invariants.
- QA and D+1/D+3 runtime logs.
