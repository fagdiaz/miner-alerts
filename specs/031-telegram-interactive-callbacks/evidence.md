# Evidence & Verification: Telegram Interactive Callbacks (Spec 031)

**Branch**: `codex/031-telegram-interactive-callbacks`  
**Status**: VERIFIED & CLOSED  
**Date**: 2026-09-07  

---

## 1. Test Invariants & Baseline

- Baseline global suite: 416 unit tests PASS.
- New tests added: 14 dedicated callback unit and integration tests in `tests/test_telegram_callbacks.py`.
- Final global suite: 430 unit tests PASS in 4.336s (0 failures, 0 errors, 0 skips).
- Production monitor PID 38816 running undisturbed (>267h continuous soak).
- Inbound Windows Firewall rules: Ports 3000 and 8080 active.

---

## 2. Python Syntax Validation

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py app\alert_episodes.py app\telegram_callbacks.py tests\test_telegram_callbacks.py
# Exit code: 0 (No syntax or indentation errors)
```

---

## 3. Unit Test Execution Results

```text
& ".\.venv\Scripts\python.exe" -m unittest tests\test_telegram_callbacks.py
[2026-09-07 20:59:19] CB_DISPATCH action=rb_cfm miner=23 token=aa87cb cb_id=cb_101
.[2026-09-07 20:59:19] CB_DISPATCH action=rb_ccl miner=23 token=- cb_id=cb_103
.[2026-09-07 20:59:19] CB_DISPATCH action=rb_cfm miner=23 token=f17ea3 cb_id=cb_104
[2026-09-07 20:59:19] CB_REBOOT_OK miner=23 host=192.168.100.23
.[2026-09-07 20:59:19] CB_DISPATCH action=rb_req miner=23 token=- cb_id=cb_102
.[2026-09-07 20:59:19] CB_AUTH_FAIL cb_id=cb_100 from_id=9999999 expected=1206728163
..........
----------------------------------------------------------------------
Ran 14 tests in 0.016s

OK
```

Full regression run:
```text
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
Ran 430 tests in 4.336s
OK
```

---

## 4. Security and Protocol Invariant Verification

| Invariant | Test Method | Result | Evidence |
|---|---|---|---|
| **Chat ID Authentication** | Synthetic `callback_query` with `from_id=9999999` | PASS | `CB_AUTH_FAIL cb_id=cb_100 from_id=9999999 expected=1206728163`; `answerCallbackQuery` returns `show_alert=True, text='⛔ Acceso no autorizado'`. Zero actions executed. |
| **Token Expiration (60s)** | Synthetic confirmation with aged token | PASS | `consume_token` returns `token_expired`; `answerCallbackQuery` returns `show_alert=True, text='⏱️ El token de confirmación ha expirado.'`. |
| **Two-Step Safe Reboot** | Request `rb_req:23` followed by confirmation `rb_cfm:<token>:23` | PASS | Message inline markup dynamically edited to confirmation prompt; single-tap reboots are 100% prevented. |
| **Cancellation Flow** | Tap `rb_ccl:23` | PASS | Message restored to default action bar, token invalidated. |
| **64-Byte API Constraint** | Grammar length validation across all action types | PASS | All generated `callback_data` strings are ≤ 32 bytes (well within 64-byte Telegram limit). |
