# Quickstart: Vnish Log Intelligence

Install the pinned project dependency:

```powershell
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
```

Dry-run one bounded collection:

```powershell
& ".\.venv\Scripts\python.exe" tools\vnish_log_collector.py --config app\config.json --dry-run --tabs status --idle-timeout 1 --max-bytes 262144
```

Persist normalized events:

```powershell
& ".\.venv\Scripts\python.exe" tools\vnish_log_collector.py --config app\config.json --tabs status,miner,autotune,system
```

Validate:

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\vnish_logs.py app\event_store.py app\miner_monitor.py tools\vnish_log_collector.py tools\operations_dashboard.py
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -v
git diff --check
```
