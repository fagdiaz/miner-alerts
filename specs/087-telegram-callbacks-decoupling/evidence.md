# Evidence: Spec 087 — Desacoplamiento de Callbacks de Telegram

**Feature**: `087-telegram-callbacks-decoupling`  
**Fecha de Certificación**: 2026-10-07 18:42 UTC-3  
**Estado**: COMPLETADA Y CERTIFICADA (PASS)

---

## 1. Verificación de Compilación de Sintaxis

```powershell
& ".\.venv\Scripts\python.exe" -c "
import py_compile
for p in ['app/miner_monitor.py', 'app/telegram/command_center.py', 'app/telegram/help_center.py', 'app/telegram/callbacks.py', 'app/telegram/router.py']:
    py_compile.compile(p, doraise=True)
    print('OK:', p)
"
```
**Resultado**:
```text
OK: app/miner_monitor.py
OK: app/telegram/command_center.py
OK: app/telegram/help_center.py
OK: app/telegram/callbacks.py
OK: app/telegram/router.py
```

---

## 2. Reducción de Líneas en Monolito

```powershell
git diff --stat app/miner_monitor.py
```
**Resultado**:
```text
 app/miner_monitor.py | 1516 +-------------------------------------------------
 1 file changed, 4 insertions(+), 1512 deletions(-)
```
Líneas de `app/miner_monitor.py` antes: 9.160 LOC  
Líneas de `app/miner_monitor.py` después: 7.652 LOC  
Reducción neta: **-1.508 LOC**.

---

## 3. Suite Completa de Pruebas (Pytest Regression)

```powershell
& ".\.venv\Scripts\python.exe" -m pytest -q
```
**Resultado**:
```text
1522 passed, 75 subtests passed in 41.49s
0 failed, 0 errors.
```

---

## 4. Preflight Stabilization Gate (8/8 Gates PASS)

```powershell
& ".\.agents\skills\speckit-stabilize\scripts\preflight_stabilize.ps1"
```
**Resultado**:
```json
{
    "Status":  "PASS",
    "Timestamp":  "2026-10-07 18:42:10",
    "FeatureDir":  "F:\\02-ASIC - mineros\\miner-alerts\\specs\\087-telegram-callbacks-decoupling",
    "TotalGates":  8,
    "FailedCount":  0,
    "Gates":  [
        {"Name": "git-diff-check", "Status": "PASS", "Severity": "P1"},
        {"Name": "secret-leak-and-untracked-configs", "Status": "PASS", "Severity": "P0"},
        {"Name": "python-syntax-compilation", "Status": "PASS", "Severity": "P0"},
        {"Name": "config-example-alignment", "Status": "PASS", "Severity": "P2"},
        {"Name": "pytest-regression-suite", "Status": "PASS", "Severity": "P0", "Summary": "1522 passed, 75 subtests passed in 41.49s"},
        {"Name": "windows-nssm-service-health", "Status": "PASS", "Severity": "P1"},
        {"Name": "fleet-live-connectivity", "Status": "PASS", "Severity": "P1"},
        {"Name": "speckit-dod-compliance", "Status": "PASS", "Severity": "P2"}
    ]
}
```

---

## 5. Verificación de Servicio NSSM en Producción

```powershell
nssm restart MinerAlerts
nssm status MinerAlerts
```
**Resultado**:
```text
SERVICE_RUNNING
```
Telemetría de inicio en `logs/out.log`:
- Reconstitución de gobernanza: `master=True`, `reason=operator_lock_fans_only`
- Conexión a mineros: Socket 4028 OK en 192.168.100.23, .24, .25, .26
- Telemetría de cadenas y heartbeat activos sin excepciones.
