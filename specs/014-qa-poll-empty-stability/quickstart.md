# Quickstart: QA Poll-Empty Stability

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_telegram_polling_stability -v
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -v
git diff --check
```

Expected result: the idle block contains `POLL_EMPTY` but no references to `action` or `cmd_start`; all tests pass and `MinerAlerts` remains running.
