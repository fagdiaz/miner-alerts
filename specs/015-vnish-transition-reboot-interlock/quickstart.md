# Quickstart: Vnish Transition Reboot Interlock

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_reboot_safety tests.test_reboot_decision_audit tests.test_event_store -v
& ".\.venv\Scripts\python.exe" -m py_compile app\reboot_safety.py app\event_store.py app\miner_monitor.py
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -v
& ".\.venv\Scripts\python.exe" -c "import json,pathlib; json.loads(pathlib.Path('app/config.example.json').read_text(encoding='utf-8'))"
git diff --check
```

Static acceptance: the transition interlock appears after sustained LOW and before cooldown/Hashcore; manual action branches contain no transition check.
