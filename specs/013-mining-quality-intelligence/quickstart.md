# Quickstart: Mining Quality Intelligence

## Validate

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\mining_quality.py app\vnish_telemetry.py app\event_store.py app\miner_monitor.py tools\operations_dashboard.py
& ".\.venv\Scripts\python.exe" -m unittest tests.test_mining_quality tests.test_event_store tests.test_operations_dashboard -v
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -v
```

## Runtime After Controlled Rollout

```text
/quality
/quality 23
/quality all
```

The command reads SQLite only. It does not poll a miner on demand or execute an
action. Before the service restart, production will continue running the previous
build and the schema-v3 database will not exist yet.
