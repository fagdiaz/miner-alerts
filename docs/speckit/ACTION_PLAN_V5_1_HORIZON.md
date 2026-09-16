# 🚀 PLAN DE ACCIÓN HORIZONTE V5.1 & AUDITORÍA DE SEGURIDAD OPERATIVA (SPECS 067 A 070)

**Proyecto**: Miner Alerts Monitor  
**Fecha de Publicación**: 15 de Septiembre de 2026  
**Línea Base Certificada**: Release V5.0.3 (1062 tests PASS, 0 fallos, 0 regresiones, Windows Service `MinerAlerts` activo en PID de producción)  
**Objetivo del Documento**: Establecer el plan de acción exhaustivo, mapa de dependencias, auditoría de concurrencia y especificaciones técnicas para que **Claude Sonnet 4.6 (Thinking)** pueda auditar, realizar QA de alto razonamiento, proponer mejoras defensivas y guiar la implementación segura de las próximas especificaciones.

---

## 🗺️ 1. ESTADO ACTUAL Y BALANCE DE LO IMPLEMENTADO

Las iniciativas del ciclo post-V5.0 han sido completamente implementadas, auditadas y puestas en producción:

| Spec | Módulo Principal | Logro / Capacidad Incorporada | Estado | Tests Unitarios |
| :--- | :--- | :--- | :---: | :---: |
| **Spec 061** | `app/core/event_store.py` | Resiliencia SQLite WAL Mode, PRAGMA synchronous NORMAL, quick_check asíncrono en arranque, auto-aislamiento de base corrupta y pool multi-lector con retroceso exponencial ante `SQLITE_BUSY_SNAPSHOT`. | **Cerrado** | 11 tests PASS |
| **Spec 062** | `app/governance/preset_balancer.py` | HW Error Tripwire (`hw_error_rate_pct >= 0.5%` AND `hw_errors_delta_10m >= 200`), candado de 48h (`hw_error_locked_preset`), interlock anti-cascada post-reboot y tarjeta móvil <= 32 columnas. | **Cerrado** | 10 tests PASS |
| **Spec 063** | `app/governance/fan_governor.py` | Gobernador Térmico con Conciencia Estacional, extracción de `inlet_temp_c` sin requests HTTP extra, resolución pura `resolve_seasonal_parameters()` y 3 guardarraíles térmicos inviolables. | **Cerrado** | 14 tests PASS |
| **Spec 064** | `app/telegram/charts.py` | Gráficos visuales multi-miner por grupo eléctrico (`elevator_1`, `elevator_2`, `fleet`), renderizado en RAM con `matplotlib` (`Agg`), selectores inline `[1h][6h][24h][7d]` y actualización in-place `editMessageMedia`. | **Cerrado** | 11 tests PASS |
| **Spec 065** | `app/core/engine.py` | Pipeline declarativo de hooks en `CoreSupervisoryEngine` (`HookStage` 7 etapas ordenadas), contención individual defensiva de excepciones, modelo de tiempo monotónico estricto `poll_seconds = max(0, interval - elapsed)` y sincronización atómica de estado. | **Cerrado** | 48 tests PASS |
| **Spec 066** | `app/miner_monitor.py` | Cold-Boot Fleet Grace Period (`PROP-001`), ventana de gracia post-arranque de 180s (`WARMING_UP`), supresión activa de streaks y timers de falla durante el booteo de NAND y autotuning de ASICs, tarjeta unificada `🟢 FLOTA RESTABLECIDA` y cero falsas alarmas. | **Cerrado** | 15 tests PASS |

**Total Actual Certificado**: **1062 tests PASS** (34.4s). Cero fallos, cero regresiones.

---

## 🎯 2. INVENTARIO COMPLETO DE LO PENDIENTE (SPECS 067 A 070)

```mermaid
flowchart TD
    subgraph Fase7 ["Fase 7: Resiliencia de Red & Diagnóstico Forense (P2/P3)"]
        S067["Spec 067: Latido de Gateway y Supresión de Tormentas (PROP-005)<br/>(Supresión de Alertas por Parpadeo de Switch Ethernet)"]
        S068["Spec 068: Canal IPC Alta Frecuencia Monitor ↔ Watchdog (PROP-007)<br/>(Named Pipes \\.\\pipe\\MinerAlertsWatchdog para Detección en <15s)"]
    end

    subgraph Fase8 ["Fase 8: Salud Profunda de Hardware & Desacoplamiento Final"]
        S069["Spec 069: Telemetría Profunda por Cadena & Predictive Chain Break (PROP-008)<br/>(Detección Temprana de Fallas I2C y Desbalance de Potencia)"]
        S070["Spec 070: Modularización Core Fase B (ST-05)<br/>(Sustitución de inspect.getsource por Behavioral Harness)"]
    end

    S067 --> S068
    S067 --> S069
    S069 --> S070
```

---

### Spec 067: Latido de Gateway y Supresión de Tormentas por Fallo de Red Local (`PROP-005`)

* **Prioridad**: P2 (Media) | **Riesgo**: Bajo | **Módulos**: `app/network/gateway_heartbeat.py`, `app/miner_monitor.py`
* **Contexto y Problema**:
  - El discriminador de caídas de fase (Spec 051) verifica la conectividad del gateway cuando ocurre una caída unísona.
  - Sin embargo, si un switch Ethernet local o access point hogareño sufre un microcorte o reinicio rápido (parpadeo de 5 a 10 segundos) o un recalculo de Spanning Tree Protocol (STP), las conexiones TCP API 4028 hacia los 4 mineros fallan simultáneamente por timeout de socket.
  - Esto puede originar conatos de alertas de desconexión antes de que el monitor certifique si el fallo es de los equipos o de la infraestructura de red local.
* **Arquitectura de Solución**:
  1. **Worker Ultraliviano de Latido de Gateway (`GatewayHeartbeatWorker`)**:
     - Hilo daemon independiente que ejecuta cada 5 segundos un intento de conexión TCP no bloqueante (timeout de 50 ms) hacia el router local (`192.168.100.1:80` o `:53`).
     - Mantiene un estado booleano atómico `gateway_online: bool` y marca de tiempo `last_gateway_loss_ts: Optional[float]`.
  2. **Ventana de Supresión de Tormentas (Storm Suppression Window)**:
     - Si `gateway_online` pasa a `False` o si la conectividad con el router se interrumpió en los últimos 15 segundos:
       - Se activa el estado de supresión de tormentas de red (`network_storm_suppression = True`).
       - Se congelan temporalmente los despachos de alertas `EPISODE_ALERT` hacia Telegram.
       - Si el enlace se restablece dentro de la ventana de 15 segundos, se registra un log estructurado `[NETWORK_STORM_SUPPRESSED] Transitorio de enlace Ethernet local absorbido (delta={elapsed:.1f}s)` y se descarta el conato sin alarmar al operador.
       - Si la pérdida de red supera los 15 segundos y los mineros continúan inaccesibles, se permite la propagación de la alerta correspondiente.
* **Puntos de Auditoría Requeridos para Sonnet**:
  - Garantizar que el socket connect de 50 ms nunca bloquee el GIL ni retrase el bucle principal.
  - Verificar que el cierre de sockets use `socket.close()` explícito para evitar leaks de descriptores de archivo (handles) en Windows.
  - Proteger contra gateways que tengan puertos HTTP deshabilitados (permitir configurar IP y puerto, fallback a DNS port 53 o ICMP ping opcional).

---

### Spec 068: Canal IPC de Alta Frecuencia Monitor ↔ Watchdog vía Named Pipes (`PROP-007`)

* **Prioridad**: P3 (Baja) | **Riesgo**: Medio | **Módulos**: `app/ipc/watchdog_pipe.py`, `tools/monitor_watchdog.py`
* **Contexto y Problema**:
  - Actualmente, el watchdog fuera de proceso ([`tools/monitor_watchdog.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/tools/monitor_watchdog.py)) se invoca periódicamente mediante el Programador de Tareas de Windows leyendo `data/monitor_heartbeat.json` y ejecutando `sc.exe queryex`.
  - Aunque este mecanismo es robusto y desacoplado, su latencia de detección es de 2 a 5 minutos.
  - Si el monitor entra en un deadlock de hilos, bloqueo del GIL en una llamada nativa o bucle de CPU cerrado, el watchdog tarda demasiado en actuar.
* **Arquitectura de Solución**:
  1. **Servidor Named Pipe Local en Windows**:
     - Dentro del monitor, un hilo daemon abre el pipe `\\.\pipe\MinerAlertsWatchdog` en modo dúplex no bloqueante.
  2. **Protocolo Ping-Pong Estricto**:
     - El cliente watchdog envía `PING <nonce>\n`.
     - El monitor responde `PONG <nonce> <tick_sequence> <uptime>\n` en menos de 100 ms.
  3. **Diagnóstico Forense Acelerado (<15s)**:
     - Si el pipe no responde en 3 intentos consecutivos (intervalos de 5s):
       - Si el proceso Python existe en Windows (`Get-Process -Id <pid>`):
         - Certeza matemática de deadlock o cuelgue de hilos.
         - Toma minidump de depuración (o traza de hilos vía `sys._current_frames()`) y ejecuta reinicio inmediato con `Restart-Service -Name MinerAlerts`.
* **Puntos de Auditoría Requeridos para Sonnet**:
  - Gestión segura de Named Pipes en Windows (`pywin32` vs wrappers estándar en `ctypes` o fallback a sockets Unix/localhost para evitar dependencias binarias externas complejas).
  - Aseguramiento de permisos ACL en el pipe para que sólo procesos locales del mismo usuario/SYSTEM puedan interactuar.

---

### Spec 069: Telemetría Profunda por Cadena & Diagnóstico Predictivo Chain Break (`PROP-008`)

* **Prioridad**: P1 (Alta) | **Riesgo**: Medio | **Módulos**: `app/governance/chain_health.py`, `app/vnish/chain_collector.py`, `tools/analyze_chain_breaks.py`
* **Contexto y Problema**:
  - Durante el incidente del 2026-09-12 (Evento 940), el Minero 24 sufrió un reinicio abrupto tras registrar `chain_break` en el firmware Vnish.
  - La inspección de `/api/v1/chains` reveló que el Minero 24 presenta un fallo persistente en el sensor térmico I2C de la **Cadena 2 (Board 2)**: `{"state": "error", "board": 39, "chip": 54, "loc": 28}`.
  - Actualmente, el colector registra muestras en la tabla `chain_telemetry_samples` pero el monitor carece de un evaluador preventivo en tiempo real que anticipe la desconexión de la placa.
* **Arquitectura de Solución**:
  1. **Regla 1 — Alerta Preventiva de Fallo de Bus I2C**:
     - Si cualquier sensor térmico de una cadena reporta `state: error` durante más de 12 horas consecutivas, emitir advertencia preventiva en Telegram:
       `⚠️ RIESGO DE CHAIN BREAK: Minero 24 Cadena 2 — Sensor I2C (loc 28) en fallo continuo por >12h.`
  2. **Regla 2 — Detección de Desbalance / Caída de Hashrate por Cadena**:
     - Si una placa individual rinde $< 92\%$ de su nominal mientras las otras 2 placas rinden $100\%$, identificar degradación de chips o caída de tensión en dominio.
  3. **Regla 3 — Aislamiento Causal Cruzado (Elevador vs Placa)**:
     - Correlacionar reinicios con el comportamiento del grupo eléctrico (`elevator_1` vs `elevator_2`) para distinguir matemáticamente si un corte fue originado por armónicos/tensión en la fase o por fallo físico del silicio en la cadena.
* **Puntos de Auditoría Requeridos para Sonnet**:
  - Optimización de las consultas SQL sobre `chain_telemetry_samples` para garantizar que la evaluación histórica tome menos de 15 ms.
  - Asegurar que la colección asíncrona no compita por el lock de base de datos durante checkpoints WAL.

---

### Spec 070: Modularización del Core Fase B — Desacoplamiento Seguro de `inspect.getsource(main)` (`ST-05`)

* **Prioridad**: P2 (Media) | **Riesgo**: Alto (Regresión de Tests Legados) | **Módulos**: `app/miner_monitor.py`, `app/core/engine.py`, `tests/`
* **Contexto y Problema**:
  - Actualmente, 4 suites de tests verifican la estructura textual de `main()` mediante `inspect.getsource(main)`:
    1. `tests/test_auto_reboot_signal_gate.py` (`state.low_since_ts = None`, orden de puertas).
    2. `tests/test_hashboard_auto_reboot.py` (`elif (\n new_state == STATE_HASHBOARD`, orden de los 6 interlocks).
    3. `tests/test_reboot_safety.py` (orden startup < sustained < interlocks < cooldown < window < hashcore).
    4. `tests/test_vnish_hashboard_detection.py` (`active_boards < expected_boards` antes de `rate_ths < threshold_ths`).
  - Esto obliga a mantener el bucle procedural en `main()` en lugar de mover la lógica a `AcquisitionHook`, `DetectionHook` y `ActuatorHook`.
* **Estrategia Inviolable de Migración**:
  - **Paso 1**: Crear tests de comportamiento funcional (behavioral tests) equivalentes sobre `CoreSupervisoryEngine` utilizando `MonitorContext` mockeado, verificando exactamente los mismos 6 interlocks y reglas de transición.
  - **Paso 2**: Demostrar que los behavioral tests pasan al 100% y tienen paridad funcional idéntica con los tests textuales.
  - **Paso 3**: Solo tras certificar la paridad y con aprobación explícita, refactorizar gradualmente los tests de inspección y migrar las etapas procedurales hacia hooks desacoplados.
  - **Regla Inviolable**: `len(tests_pass)` sólo puede crecer ($\ge 1062$), jamás decrecer.

---

## 🔍 3. GUÍA DE AUDITORÍA DE SEGURIDAD & QA PARA CLAUDE SONNET 4.6 (THINKING)

Cuando Claude Sonnet tome el control de la sesión, debe ejecutar una auditoría de alto razonamiento sobre los siguientes puntos críticos:

### A. Auditoría de Concurrencia y Jerarquía de Locks
1. **Verificación de Bloqueos L1 y L2**:
   - `state_lock` (RLock, Nivel 1): Protege el diccionario `states` en memoria.
   - `_SAVE_STATE_LOCK` (Lock, Nivel 2): Protege la escritura en disco de `state.json`.
   - **Regla Inviolable**: Ninguna operación de I/O bloqueante (disco, red, socket, `fsync`) debe realizarse manteniendo adquirido `state_lock`. Verificar que `state_manager.save()` extrae el snapshot bajo lock y ejecuta el volcado fuera de él.
2. **Ciclo de Vida de Hilos Daemon**:
   - Auditar todos los hilos lanzados con `daemon=True`:
     * `AutoRestart_{name}`
     * `TripwireRestore_{name}`
     * `ChainTelemetryReactive_{name}`
     * `ChainTelemetryTransition_{name}`
     * `telegram_sender_worker`
     * `telegram_polling_worker`
   - Verificar que **cada uno de ellos** posea una barrera total de captura de excepciones `try ... except Exception as exc:` con log estructurado para evitar caídas silenciosas o hilos huérfanos.

### B. Auditoría de Estado y Sincronización en el Pipeline de Hooks
1. **Sincronización Context ↔ Globals**:
   - Comprobar que en `miner_monitor.py` antes de invocar `_supervisory_engine.execute_tick()`, todos los objetos mutables compartidos se sincronicen:
     ```python
     monitor_ctx.last_daily_digest_date = _LAST_DAILY_DIGEST_DATE
     monitor_ctx.governance = _GLOBAL_INTERVENTION_GOV
     ```
   - Verificar que los hooks lean preferentemente de `tick_data` (inyectado en el ciclo) antes que de atributos potencialmente congelados en `context`.
2. **Garantía Invariante de Etapa PERSISTENCE**:
   - Comprobar que en `app/core/engine.py:execute_tick`, la etapa `PERSISTENCE` se ejecute indefectiblemente antes de `POST_TICK` y que ambas se ejecuten incluso si todas las etapas anteriores arrojan excepciones simuladas.

### C. Auditoría de Protocolo de Red & Sockets en Windows
1. **Timeouts Acotados**:
   - Comprobar que ninguna llamada de socket (`Api4028Transport`, `VnishClient`, `HashcoreClient`) quede sin timeout explícito ($\le 5.0\text{s}$).
2. **Subprocess Windowless en Windows**:
   - Comprobar que toda invocación de `subprocess.run` o `subprocess.Popen` en Windows (`hashcore_client.py`, `monitor_watchdog.py`) incluya el flag `creationflags=subprocess.CREATE_NO_WINDOW` para evitar la aparición de ventanas de consola parpadeantes.

---

## 🛠️ 4. COMANDOS DE VALIDACIÓN Y SUITES DE PRUEBA CERTIFICADAS

Para verificar la integridad del repositorio en cualquier momento, ejecutar:

```powershell
# 1. Chequeo de sintaxis Python (0 errores requeridos)
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py app\core\engine.py app\core\state_manager.py

# 2. Higiene de formato Git (0 errores de espacios en blanco)
git diff --check

# 3. Script de Preflight QA de Miner Alerts (Status: PASS requerido)
& powershell.exe -ExecutionPolicy Bypass -File .agents\skills\speckit-qa\scripts\preflight.ps1 -RunBuilds

# 4. Verificación de Invariantes Constitucionales (37 tests PASS)
& ".\.venv\Scripts\python.exe" -m unittest tests.test_auto_reboot_signal_gate tests.test_hashboard_auto_reboot tests.test_reboot_safety tests.test_vnish_hashboard_detection -v

# 5. Suites Enfocadas de Hooks y Grace Period (66 tests PASS)
& ".\.venv\Scripts\python.exe" -m unittest tests.test_supervisory_hooks tests.test_startup_grace_period -v

# 6. Suite Completa de Regresión del Proyecto (1062 tests PASS en ~34s)
& ".\.venv\Scripts\python.exe" -m unittest discover tests

# 7. Estado del Servicio de Producción en Windows
Get-Service -Name MinerAlerts
Get-Content -Path logs\out.log -Tail 30
```

---

*Plan de Acción archivado formalmente en `docs/speckit/ACTION_PLAN_V5_1_HORIZON.md` como base de trabajo certificada para la auditoría y ejecución de Claude Sonnet 4.6 (Thinking).*
