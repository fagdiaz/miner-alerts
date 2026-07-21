# Quickstart: Stability Advisor

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\stability_profile.py app\miner_monitor.py tools\operations_dashboard.py
& ".\.venv\Scripts\python.exe" -m unittest tests.test_stability_profile tests.test_operations_dashboard -v
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -q
```

After the planned controlled service restart and enough persisted samples:

```text
/health
/health 23
/health all
```

The command is read-only. `WATCH` is advisory and does not authorize a reboot.
