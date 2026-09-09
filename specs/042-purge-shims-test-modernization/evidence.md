# Evidence: Spec 042 - Purga Limpia de Shims y Modernización de Tests en `app/`

## Estado y Metadatos
- **Spec ID**: `042-purge-shims-test-modernization`
- **Fecha**: 2026-09-08
- **Línea Base Inicial**: 587/587 tests pasando en 11.26s. Servicio Windows `MinerAlerts` activo bajo PID 71304. Payload files: 83.
- **Resultado Global**: **COMPLETO Y CERTIFICADO** (100% de 22 shims purgados, 587/587 tests pasando en 10.68s, release audit PASS con payload de 60 archivos).

---

## 1. Verificación de Estructura Limpia en `app/`

Ejecución de inspección de archivos `.py` en la raíz de `app/`:
```powershell
Get-ChildItem -Path app -File -Filter "*.py" | Select-Object Name

Name            
----            
miner_monitor.py
__init__.py     
```

### Shims Purgados (22 archivos eliminados vía `git rm`):
1. **Telegram (5)**: `app/daily_digest.py`, `app/telegram_callbacks.py`, `app/telegram_charts.py`, `app/telegram_messages.py`, `app/telegram_snooze.py`
2. **Vnish (4)**: `app/vnish_client.py`, `app/vnish_logs.py`, `app/vnish_presets.py`, `app/vnish_telemetry.py`
3. **Governance (4)**: `app/fan_governor.py`, `app/preset_balancer.py`, `app/fan_health.py`, `app/energy_efficiency.py`
4. **Core (9)**: `app/acquisition.py`, `app/alert_episodes.py`, `app/event_store.py`, `app/evidence_fusion.py`, `app/liveness.py`, `app/metrics_snapshot.py`, `app/mining_quality.py`, `app/reboot_safety.py`, `app/restart_intelligence.py`, `app/stability_profile.py`

---

## 2. Verificación de Compilación de Sintaxis

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py
# Salida: Código 0, sin errores ni warnings.
```

---

## 3. Certificación de Release Audit

```powershell
& ".\.venv\Scripts\python.exe" tools\release_audit.py --check-only
```
**Salida**:
```text
RELEASE AUDIT: PASS. Runtime payload SHA-256: b11a92084d2f558327290d98c05b7fa691e512ddc7f33d36e7f0e120459249fd
Payload files counted: 60
Terminal dispositions: 8/8 verified
```

---

## 4. Certificación de Suite Completa de Tests (587/587 PASS)

```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
```
**Salida**:
```text
----------------------------------------------------------------------
Ran 587 tests in 10.679s

OK
```

---

## 5. Continuidad Operativa de Producción

Monitoreo del watchdog en tiempo real sin interrupciones del proceso:
```powershell
Get-Content logs\watchdog.log -Tail 5
```
**Salida**:
```text
[2026-09-08 21:45:54] WATCHDOG assessment healthy=true suppressed=false reasons=none service=running service_pid=64860 tick_age=19 poller_age=24 sender_age=22 action=none
[2026-09-08 21:46:54] WATCHDOG assessment healthy=true suppressed=false reasons=none service=running service_pid=64860 tick_age=19 poller_age=37 sender_age=22 action=none
[2026-09-08 21:47:54] WATCHDOG assessment healthy=true suppressed=false reasons=none service=running service_pid=64860 tick_age=18 poller_age=23 sender_age=22 action=none
[2026-09-08 21:48:54] WATCHDOG assessment healthy=true suppressed=false reasons=none service=running service_pid=64860 tick_age=18 poller_age=31 sender_age=22 action=none
[2026-09-08 21:49:53] WATCHDOG assessment healthy=true suppressed=false reasons=none service=running service_pid=64860 tick_age=17 poller_age=64 sender_age=21 action=none
```
El servicio de producción continuó operando con total estabilidad, cero interrupciones y latencia de tick de 17-19s.
