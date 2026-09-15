# Runtime & Test Evidence: Spec 058 — Telegram Command Center & Dispatcher Modularization (MT-01)

**Date**: 2026-09-15  
**Branch**: `codex/022-adaptive-acquisition`  
**Status**: APPROVED / ZERO REGRESSIONS  

---

## 1. Objectives Verified

1. **Monolith Reduction**: Extracted ~2,700 lines of procedural command dispatch from `app/miner_monitor.py` into decoupled handler modules under `app/telegram/commands/`.
   - Before: 9,724 lines
   - After: 7,055 lines (-2,669 LOC)
2. **Architecture & Decoupling**:
   - `TelegramRequestContext`: encapsulates bot configuration, state persistence locks, and uniform `send_message(..., is_command=True)` messaging.
   - `BaseCommandHandler`: abstract contract with strict chat_id authentication, alias resolution, and structured logging.
   - `TelegramCommandRouter`: canonical name and alias matching (English and Spanish: `/status`, `/estado`, `/silencio`, `/intervenciones`, `/reiniciar`, `/grafico`, `/placas`, etc.).
   - `TelegramCallbackRouter`: strict auth validation and delegation to callback processors.
   - `app/telegram/poller.py`: isolated transport polling with exponential network backoff.
3. **Safety & Zero Regressions**:
   - Backward compatibility: inspect contracts preserved for test suites.
   - Global test suite grew from 902 tests to **910 tests**, 100% PASS in 13.5s.
   - Windows Service `MinerAlerts` verified RUNNING.

---

## 2. Test Execution Evidence

```powershell
PS F:\02-ASIC - mineros\miner-alerts> & ".\.venv\Scripts\python.exe" -m unittest discover -s tests
...................................................................................................
...................................................................................................
...................................................................................................
...................................................................................................
...................................................................................................
...................................................................................................
...................................................................................................
...................................................................................................
...................................................................................................
....................
----------------------------------------------------------------------
Ran 910 tests in 13.500s

OK
```

### Dedicated Dispatcher Tests (`tests/test_telegram_dispatcher.py`)

```powershell
PS F:\02-ASIC - mineros\miner-alerts> & ".\.venv\Scripts\python.exe" -m unittest tests\test_telegram_dispatcher.py
.[TG_AUTH_FAIL] Unauthorized command /dummy from_id=999999 expected=123456 update_id=1
...[TG_CMD_ERR] Error executing command /fail: Simulated handler crash
Traceback (most recent call last):
  File "F:\02-ASIC - mineros\miner-alerts\app\telegram\router.py", line 73, in dispatch
    return handler.handle(
...
ValueError: Simulated handler crash
....
----------------------------------------------------------------------
Ran 8 tests in 0.127s

OK
```

---

## 3. Production Service Validation

```powershell
PS F:\02-ASIC - mineros\miner-alerts> Get-Service MinerAlerts | Format-List Name, Status, StartType

Name      : MinerAlerts
Status    : Running
StartType : Automatic
```
