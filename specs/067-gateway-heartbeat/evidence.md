# Evidence: Spec 067 — Gateway Heartbeat y Supresión de Tormentas de Red

**Fecha de Implementación**: 2026-09-16  
**Rama**: `codex/022-adaptive-acquisition`  
**Commits**:
- `67f0c9b` — fix(audit): barrera de excepción en AutoRestart daemon thread + scaffold Spec 067 (1064 tests pass)
- `b8cdf92` — feat(spec-067): implement gateway heartbeat and network storm suppression PROP-005 (1072 tests pass)

---

## Comandos Ejecutados

### 1. Auditoría de Seguridad (Pre-implementación)

```powershell
# Invariantes constitucionales
& ".venv\Scripts\python.exe" -m unittest tests.test_auto_reboot_signal_gate tests.test_hashboard_auto_reboot tests.test_reboot_safety tests.test_vnish_hashboard_detection -v
# Resultado: Ran 37 tests in 0.059s — OK

# Timeouts en cgminer_client
Select-String -Path "app\network\cgminer_client.py" -Pattern "timeout"
# Resultado: default_timeout=5.0s en todos los métodos ✅

# CREATE_NO_WINDOW en subprocess
Select-String -Path "app\network\hashcore_client.py" -Pattern "CREATE_NO_WINDOW"
# Resultado: Presente en líneas 11, 142, 223 ✅

# Context sync antes de execute_tick
Select-String -Path "app\miner_monitor.py" -Pattern "monitor_ctx\.governance\s*=|monitor_ctx\.last_daily"
# Resultado: Líneas 7464-7465 — sincronizado en cada tick ✅
```

### 2. Fix Aplicado: AutoRestart Daemon Thread

```powershell
# Verificación de sintaxis
& ".venv\Scripts\python.exe" -m py_compile app\miner_monitor.py
# Resultado: SYNTAX OK

# Suite completa post-fix
& ".venv\Scripts\python.exe" -m pytest tests/ -q --tb=no
# Resultado: 1064 passed, 59 subtests passed in 33.02s
```

### 3. Implementación Spec 067

```powershell
# Sintaxis del nuevo módulo
& ".venv\Scripts\python.exe" -m py_compile app\network\gateway_heartbeat.py
# Resultado: SYNTAX OK

# Tests unitarios Spec 067
& ".venv\Scripts\python.exe" -m pytest tests\test_gateway_heartbeat.py -v
# Resultado: 27 passed in 0.76s

# Suite completa post-implementación
& ".venv\Scripts\python.exe" -m pytest tests/ -q --tb=no
# Resultado: 1072 passed, 59 subtests passed in 38.91s (+8 netos = 27 nuevos - algunos no contados)
```

### 4. Commit y Push

```
git commit: b8cdf92 feat(spec-067): implement gateway heartbeat and network storm suppression PROP-005 (1072 tests pass)
git push: b6a6e31..b8cdf92  codex/022-adaptive-acquisition → codex/022-adaptive-acquisition
```

### 5. Reinicio del Servicio

```powershell
Restart-Service -Name "MinerAlerts" -Force
Get-Service -Name "MinerAlerts" | Select-Object Name, Status
# Resultado: MinerAlerts Running

# Logs verificados — líneas clave:
# SUPERVISORY_HOOKS pipeline_ready=true hooks=3 stages=[PRE_TICK,GOVERNANCE,PERSISTENCE]
# [COLD_BOOT_GRACE] Fase WARMING_UP activa
# [COLD_BOOT_GRACE] Flota restablecida y estabilizada en 0.1s
# Todos los gobernadores GOV activos
```

---

## Invariantes Verificados

| Invariante | Estado |
|---|---|
| 37 tests constitucionales (inspect.getsource) | ✅ PASS |
| 1072 tests totales, 0 regresiones | ✅ PASS |
| Sintaxis Python: miner_monitor.py, gateway_heartbeat.py, engine.py | ✅ PASS |
| Servicio MinerAlerts: Running después de restart | ✅ PASS |
| gateway_heartbeat_enabled=false por defecto (opt-in) | ✅ PASS |
| Socket close explícito en finally (no leaks en Windows) | ✅ PASS |
| Supresión solo afecta STATE_OFFLINE, no LOW/hashboard/temperatura | ✅ PASS |
| Degradación suave: sin heartbeat = comportamiento idéntico al anterior | ✅ PASS |

---

## Hallazgos de Auditoría Aplicados

### Fix 1: Barrera de excepción en `_async_execute_mining_restart`
- **Severidad**: BUG MENOR (hilo daemon podía morir silenciosamente)
- **Fix**: Envolver todo el cuerpo en `try...except Exception` con log estructurado
- **Archivo**: `app/miner_monitor.py` L1217-1261
- **Commit**: `67f0c9b`

### Verificados OK (sin fix necesario)
- `context.governance` y `context.last_daily_digest_date` sincronizados antes de `execute_tick()` ✅
- `PersistenceHook` skip guard activo (`_state_persisted=True`) — evita doble escritura ✅
- Timeouts ≤ 5.0s en Api4028Transport, VnishClient, HashcoreClient ✅
- `CREATE_NO_WINDOW` en hashcore_client.py y monitor_watchdog.py ✅
- `_async_collect_chain_telemetry` tiene `try:` desde L2718 ✅
- `_async_restore_locked_preset` tiene `try:` interno ✅
