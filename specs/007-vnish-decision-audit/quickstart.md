# Quickstart: Vnish Decision Audit

## Validate Without Restarting The Service

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py app\event_store.py app\vnish_telemetry.py tools\incident_report.py
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -v
& ".\.venv\Scripts\python.exe" tools\incident_report.py --db .\tmp\test.db --hours 24 --format markdown
```

The production Windows service remains on its current process until the explicit
end-of-day restart. A successful compile does not activate this branch.

## Runtime Checks After The Planned Restart

1. Confirm `EVENT_STORE ... schema=2` in service logs.
2. Wait for one configured telemetry sample interval.
3. Send `/why` and `/why 23`; both must reply from local history.
4. Exercise LOW only in QA and verify decision rows for guard outcomes.
5. Generate a local report from `data/miner_alerts.db`.

## Safety

- Do not interpret `chain_voltage_mv_avg` as AC input voltage.
- `/why` and the report are read-only.
- Real Hashcore actions remain behind all existing production gates.
