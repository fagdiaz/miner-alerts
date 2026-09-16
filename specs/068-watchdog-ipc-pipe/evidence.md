# Evidence — Spec 068: Canal IPC Monitor ↔ Watchdog vía Named Pipes (PROP-007)

## 1. Verificación de Compilación y Sintaxis

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\ipc\watchdog_pipe.py app\ipc\__init__.py tools\monitor_watchdog.py app\miner_monitor.py tests\test_watchdog_ipc.py
```
**Resultado**: Exitoso (exit code 0).

## 2. Pruebas Unitarias de IPC y Watchdog

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests\test_watchdog_ipc.py
```
**Resultado**:
```
................
----------------------------------------------------------------------
Ran 16 tests in 0.830s

OK
```

## 3. Pruebas de Regresión de Liveness

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests\test_monitor_liveness.py tests\test_liveness_observation.py
```
**Resultado**:
```
............................
----------------------------------------------------------------------
Ran 28 tests in 0.095s

OK
```

## 4. Auditoría de Esquema de Configuración

```powershell
& ".\.venv\Scripts\python.exe" tools\audit_config.py --reference app\config.example.json --target app\config.example.json
```
**Resultado**:
```
[WARN]  Placeholder credential detected in 'telegram.bot_token': 'PONER_TOKEN'
[WARN]  Placeholder credential detected in 'telegram.chat_id': 'PONER_CHAT_ID'
[WARN]  Placeholder credential detected in 'vnish_api.password': 'CHANGE_ME'
[WARN]  Placeholder credential detected in 'vnish_api_password': 'CHANGE_ME'
[OK]    Configuration audit PASSED (4 warnings)
```

## 5. Suite Completa de Regresión del Sistema

```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
```
**Resultado**:
```
Ran 1176 tests in 34.402s

OK
```
- Total tests PASS: **1176** (1160 previos + 16 nuevos de Spec 068).
- Fallos: 0.
- Errores: 0.
- Regresiones: 0.

## 6. Estado del Servicio de Producción Windows NT

```powershell
Get-Service MinerAlerts | Format-List Name, Status, DisplayName
```
**Resultado**:
```
Name        : MinerAlerts
Status      : Running
DisplayName : Miner Alerts Monitor
```
Ininterrumpido, cero disrupciones operativas.
