# miner-alerts

Monitor de mineros ASIC (API 4028) con alertas por Telegram, cambios de estado agrupados, deteccion de reboots y hashboards caidos. Pensado para correr en Windows con PowerShell y evitar spam.

**Documentacion del proyecto**
- Programa completo de Specs 001-030 (Release v2.0.0): `docs/speckit/SPEC_PROGRAM.md`.
- Prioridades y features: `docs/speckit/ROADMAP.md`.
- Calendario de implementacion, observacion y fixes: `docs/speckit/DELIVERY_PLAN.md`.
- Decisiones tecnologicas: `docs/speckit/TECHNOLOGY_STRATEGY.md`.
- Operacion y validacion: `docs/speckit/RUNBOOK.md`.
- Plan de expansion V3 y Telegram Max: `docs/speckit/V3_EXPANSION_PLAN.md`.
- Historial de specs completadas: `docs/audit/DEVELOPMENT_LOG.md`.

**Requisitos**
- Windows + PowerShell
- Python 3.9+
- Acceso de red al puerto 4028 de los mineros

**Setup**
```powershell
cd "F:\02-ASIC - mineros\miner-alerts"
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

**Configuracion**
- Copia `app/config.example.json` a `app/config.json`.
- Completa `telegram.bot_token` y `telegram.chat_id`.
- `app/config.json` y `app/state.json` NO se commitean.
- `qa_mode` se controla en `app/config.json` (local). `app/config.example.json` queda con defaults prod.
- Override opcional de ruta config: `MINER_ALERTS_CONFIG` o `CONFIG_PATH`.
- En el log de arranque aparece `CONFIG path=...` con el archivo efectivamente leido.

Tabla de claves principales (valores por defecto en `app/config.example.json`):
| Clave | Descripcion |
| --- | --- |
| `poll_seconds` | Intervalo de consulta en segundos. |
| `telegram.poll_timeout_seconds` | Long polling de Telegram (segundos). |
| `telegram.poll_sleep_seconds` | Pausa corta entre polls (segundos). |
| `threshold_ths` | Umbral de hashrate en TH/s. |
| `fails_before_alert` | Lecturas consecutivas para LOW/OFFLINE. |
| `recovery_successes` | Lecturas OK consecutivas para RECOVERED. |
| `alert_cooldown_seconds` | Legacy, actualmente no se usa. |
| `expected_boards` | Cantidad esperada de hashboards. |
| `notify_startup` | Enviar STARTUP con snapshot del primer tick. |
| `notify_offline` | Permite notificar OFFLINE. |
| `offline_is_actionable` | Si es false, OFFLINE solo se loguea. |
| `notify_reboot` | Habilita deteccion de reboot por Elapsed. |
| `reboot_cooldown_seconds` | Cooldown de reboot por minero. |
| `reboot_window_seconds` | Ventana para reboot si cae a LOW/OFFLINE. |
| `notify_initial_non_ok` | Si `notify_startup=false`, puede notificar el estado inicial no OK. |
| `state_change_coalesce_seconds` | Espera breve para agrupar cambios relacionados antes de enviarlos. |
| `notify_persistent_outage` | Repite alertas acotadas mientras un minero siga LOW/OFFLINE/HASHBOARD. |
| `persistent_outage_schedule_seconds` | Edades del episodio para recordatorios: 5, 10, 15, 30, 60 y 120 minutos. |
| `persistent_outage_repeat_seconds` | Intervalo horario despues de completar el escalamiento. |
| `hashcore` | Configuracion del Hashcore Toolkit CLI (reboot/restart). |
| `diagnosis_stale_seconds` | Antiguedad maxima de una muestra para `/diagnose`. |
| `diagnosis_firmware_window_hours` | Ventana de evidencia Vnish considerada reciente por `/diagnose`. |
| `diagnosis_collector_stale_seconds` | Antiguedad maxima de una corrida del colector antes de marcarla stale. |
| `vnish_log_utc_offset_hours` | Offset UTC fijo opcional para timestamps Vnish; `null` usa la zona local del host. |

**Telegram**
- Crear bot con `@BotFather` y obtener token.
- Obtener `chat_id` con `@userinfobot` o via `https://api.telegram.org/bot<TOKEN>/getUpdates`.
- Comandos disponibles:
  - `/help`, `/status`, `/info [all|miner]`, `/selftest`.
  - `/events [miner]`, `/event <id>`, `/e<ID>`, `/why [miner]` (historial local).
  - `/health [all|miner]` (baseline estable por minero).
  - `/quality [all|miner]` (shares, errores y estado de cadenas por intervalo).
  - `/firmware [all|miner]` (evidencia Vnish normalizada almacenada localmente).
  - `/diagnose [all|miner]` (senal, calidad, firmware, eventos y decisiones desde SQLite).
  - `/chart [miner|fleet] [horas]` (grafico PNG visual nativo de hashrate, umbral y temperaturas).
  - `/snooze <miner|all> [minutos]` (silencia alertas y suspende autorreinicios por mantenimiento; default: 60m).
  - `/unsnooze <miner|all>` (reactiva inmediatamente la supervisión normal).
  - `/snoozed` (lista los mineros silenciados y tiempo restante).
  - `/digest` (resumen ejecutivo 24h de uptime, hashrate, J/TH, shares, eventos y backup; alias: `/summary`).
  - `/fans [all|miner]` (supervisión de ventiladores, RPM, PWM %, temperatura máxima y margen térmico a 85°C; alias: `/fan`).
  - `/efficiency [all|miner]` (supervisión de eficiencia energética en Joules por Terahash J/TH y potencia total; alias: `/eff`).
  - `/presets [all|miner]` (supervisión de frecuencias MHz, tensión V y estado de autotuning Vnish; alias: `/preset`, `/profile`).
  - `/reboot` (guiado) y `/rb<ID>` (seleccion click-safe) -> piden confirmacion.
  - `/reboot_no_ok` -> preview bulk; `/c<code>` confirma de forma click-safe.
  - `/restart <miner>` -> pide confirmacion.
  - `/confirm reboot <miner> <code>` y `/confirm restart <miner> <code>`.
- `/help <comando>` muestra uso, ejemplos, atajos oficiales y precauciones desde
  el mismo registro que usa el indice.
- Respuesta inmediata via long polling, sin afectar el loop de mineros.
  - Si Telegram esta lento, la respuesta puede tardar: el monitor no se cuelga porque usa cola de envio.
  - Las respuestas mayores a 3900 caracteres se dividen en partes numeradas y
    ordenadas antes de enviarse.
  - Las respuestas a comandos no usan dedupe/coalescing. Si la cola esta llena,
    realizan un envio directo acotado; un descarte no-comando siempre deja
    `TG QUEUE_DROP` en el log.

**Botones Interactivos en Alertas (Inline Keyboards 1-Tap - Specs 031 / 033)**
- Las alertas de incidentes y episodios incorporan botones táctiles interactivos:
  - `[ 🩺 Diagnosticar ]`: Ejecuta inmediatamente `/diagnose <miner>` sin necesidad de escribir.
  - `[ 📊 Ver Gráfico ]`: Atajo visual para consulta del estado del minero vía `/chart`.
  - `[ 🔄 Reiniciar Minero <ID> ]`: Inicia el flujo interactivo de confirmación segura en 2 pasos.
  - `[ 🔕 Silenciar 1h ]`: Silencia el minero por 60 min; suprime alertas y bloquea autorreinicios durante mantenimiento.
- **Confirmación interactiva en 2 toques (Zero-Typing)**:
  - Al presionar `[ 🔄 Reiniciar Minero 23 ]`, el teclado del mensaje se edita in-situ mostrando:
    `[ ⚠️ CONFIRMAR REINICIO 23 ]` y `[ ❌ Cancelar ]`.
  - El token de confirmación expira estrictamente a los 60 segundos por seguridad física.
  - Al pulsar `[ ❌ Cancelar ]`, el teclado regresa a su estado neutral sin ejecutar acción.
  - Al pulsar `[ ⚠️ CONFIRMAR ]`, se despacha el reinicio guardado y el mensaje se actualiza a `[ ✅ Reinicio Iniciado ]`.

**Confirm code (operativo tradicional)**
- Comando manual de texto: `reboot 23` o `/rb23`.
- Bot responde: `confirm reboot 23 <code>` o enlace click-safe `/c<code>`.
- TTL 60s; si expira, pedir `reboot 23` de nuevo.
- Si el script reinicia, el pending se pierde: hay que reemitir `reboot 23`.

**Notificaciones**
- Se envia Telegram ante eventos relevantes. Los cambios cercanos de uno o varios mineros se agrupan durante una ventana maxima de 30 segundos por defecto.
- Estado OK: hashrate >= threshold.
- Estado LOW: hashrate < threshold por N lecturas.
- Estado OFFLINE: sin respuesta del API 4028 por N lecturas.
- Estado interno HASHBOARD: faltan placas activas segun `stats`; Telegram lo muestra como `PLACAS x/y`.
- LOW/OFFLINE/PLACAS abre un episodio. Si persiste, recuerda a los 5, 10, 15, 30, 60 y 120 minutos, y luego cada hora; vencimientos cercanos se agrupan.
- La recuperacion cierra el episodio con una secuencia breve, por ejemplo `OK -> LOW -> OK` u `OK -> REINICIO -> LOW -> OK`, en vez de mensajes por cada paso.
- `/status` usa la senal actual: nunca combina hashrate positivo con `[OFFLINE]`; durante la histeresis sana muestra `[RECUPERANDO]`.
- Los avisos y `/status` exponen `/e<ID>` cuando hay detalle disponible. El detalle se reconstruye desde SQLite e incluye eventos relacionados de la flota en una ventana acotada.
- Al iniciar, si `notify_startup=true`, se envia un STARTUP con snapshot completo (hashrate y etiquetas).
- El monitor evita instancias duplicadas usando un mutex de sistema (Win32).
- El estado se persiste en `app/state.json` para continuidad (streaks, estado y cooldowns).
- Auto-reboot: si un minero permanece LOW por 10 minutos continuos y supera todos los guardrails, se envia reboot automatico.
  - Limite recomendado: max 3 auto-reboots por 6 horas. Luego entra en degraded mode.
- Degraded mode se registra siempre; el STATUS horario esta deshabilitado por defecto con `notify_degraded_hourly=false`.

**Cooling & Fan Health Intelligence (Spec 035)**
- Supervisión en tiempo real de la disipación térmica y salud mecánica de los ventiladores.
- Comando `/fans` (o alias `/fan`):
  - `/fans`: Tabla completa de la flota con RPM de ventiladores, potencia PWM %, temperatura máxima del chip y margen térmico restante hasta el corte de emergencia (85.0°C).
  - `/fans <miner>`: Diagnóstico profundo individual con recomendaciones operativas (inspección de flujo, limpieza de filtros antipolvo o reemplazo de ventilador).
- Alertas preventivas tempranas:
  - `⚠️ [ENFRIAMIENTO]`: Emite advertencia si un minero sostiene saturación térmica ($T_{\text{max}} \ge 78^\circ\text{C}$ con PWM ≥ 95% o RPM ≥ 5800) durante 3 lecturas consecutivas, permitiendo programar limpieza de filtros antes del disparo térmico a 85°C.
  - `🚨 [VENTILADOR]`: Detecta caídas mecánicas de tacómetro (< 2000 RPM bajo carga) o señal ausente para prevenir daños catastróficos.
  - Cooldown configurable de 1 hora (`cooling_cooldown_seconds: 3600`) para evitar repeticiones innecesarias.

**Hashrate Efficiency & Energy Tracking (Spec 036)**
- Cálculo y seguimiento en tiempo real del ratio energético: $\text{Eficiencia (J/TH)} = \frac{\text{Potencia (Watts)}}{\text{Hashrate (TH/s)}}$.
- Comando `/efficiency` (o alias `/eff`):
  - `/efficiency`: Tabla de la flota con J/TH, potencia individual en Watts, hashrate actual, potencia total de la granja (en kW) y promedio global de eficiencia.
  - `/efficiency <miner>`: Tarjeta de diagnóstico individual con evaluación técnica y recomendaciones ante anomalías de consumo.
- Clasificación de eficiencia: Óptima ($\le 28.5\text{ J/TH}$), Normal ($28.5 - 31.5$), Elevada ($31.5 - 35.0$) y Degradada ($> 35.0\text{ J/TH}$).
- Alerta preventiva `⚠️ [EFICIENCIA]`: Detecta consumo anómalo prolongado ($> 35.0\text{ J/TH}$ durante 3 lecturas) para advertir sobre chips descalibrados o caídas de tensión por cadena antes de un apagado total.

**Vnish Preset & Autotuning Tracking (Spec 037)**
- Monitoreo dinámico de frecuencias operativas (`frequency_mhz_avg`), tensión de cadena (`chain_voltage_mv_avg`) y potencia.
- Comando `/presets` (o alias `/preset`, `/profile`):
  - `/presets`: Tabla consolidada con MHz, tensión (V), Watts, TH/s, perfil inferido (ej. `~2700W (516 MHz)`) y estado de calibración (`🟢 ESTABLE`, `🟡 AUTOTUNING`, `🟠 DOWNCLOCK`).
  - `/presets <miner>`: Ficha diagnóstica profunda con historial reciente de eventos de firmware (`firmware_events`) y recomendaciones técnicas.
- Alerta preventiva `ℹ️ [PERFIL/AUTOTUNE]`: Notifica inmediatamente si el firmware reduce la frecuencia operativa ($\ge 25\text{ MHz}$ respecto al perfil nominal) o entra en calibración por inestabilidad o temperatura.

**Vnish log intelligence (read-only)**
- Instalar dependencias: `& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt`.
- Probar sin persistencia: `& ".\.venv\Scripts\python.exe" tools\vnish_log_collector.py --config app\config.json --dry-run --tabs status --idle-timeout 1 --max-bytes 262144`.
- Persistir eventos normalizados: `& ".\.venv\Scripts\python.exe" tools\vnish_log_collector.py --config app\config.json --tabs status,miner,autotune,system`.
- El colector procesa mineros y tabs secuencialmente, sin reintentos ni acciones. Conserva el tail mas reciente dentro de limites, guarda solo categoria, severidad, codigo, resumen generado, timestamp normalizado y fingerprint; no guarda lineas crudas, workers ni payloads del firmware.
- `/firmware`, `/firmware all` y `/firmware <miner>` consultan SQLite solamente. No abren conexiones a los mineros ni ejecutan Hashcore.
- `/diagnose`, `/diagnose all` y `/diagnose <miner>` correlacionan muestras, calidad, eventos, decisiones y salud del colector desde SQLite. El resultado es asesor y nunca autoriza acciones.
- El colector es una CLI separada: el monitor de produccion no mantiene WebSockets Vnish abiertos.
- Cada corrida persistida deja un resumen acotado en `collector_runs`; schema SQLite actual: v5.

Programar la recoleccion cada 30 minutos como tarea separada del usuario actual:

```powershell
& ".\tools\install_vnish_collector_task.ps1" -WhatIf
& ".\tools\install_vnish_collector_task.ps1" -IntervalMinutes 30
Start-ScheduledTask -TaskPath "\MinerAlerts\" -TaskName "MinerAlertsVnishCollector"
Get-ScheduledTaskInfo -TaskPath "\MinerAlerts\" -TaskName "MinerAlertsVnishCollector"
```

La tarea ejecuta `.venv\Scripts\pythonw.exe` directamente, sin crear una consola
PowerShell, usa `IgnoreNew` y conserva una ejecucion maxima de 10 minutos. No
mantiene un daemon, no reintenta y no ejecuta Hashcore. Se registra con
`LogonType Interactive`: corre mientras el usuario que la instalo tiene una
sesion iniciada.

**Hashcore Toolkit CLI**
- Configurar en `app/config.json`:
  - `hashcore.cli_path`: ruta a `toolkit_cli.bat`
  - `hashcore.cli_bat_path`: alias de `cli_path` (preferido)
  - `hashcore.working_dir`: carpeta del toolkit
  - `hashcore.settings_path`: ruta a `toolkit_settings.json` (opcional)
  - `hashcore.reboot_args_template`: lista de argumentos (ej: `["reboot", "{host}-{host}"]`)
  - `hashcore.restart_args_template`: lista de argumentos (ej: `["restart", "{host}-{host}"]`)
  - `hashcore.enabled`: true/false
- Para conocer comandos: ejecutar `toolkit_cli.bat --help` y `toolkit_cli.bat help reboot` desde CMD.
- Ejemplo manual:
  - `toolkit_cli.bat reboot 192.168.100.23-192.168.100.23`
  - `toolkit_cli.bat reboot -s "...\toolkit_settings.json" 192.168.100.23-192.168.100.23`

**Ejecucion manual**
```powershell
python app\miner_monitor.py
```
Recomendado (venv):
```powershell
& "F:\02-ASIC - mineros\miner-alerts\.venv\Scripts\python.exe" app\miner_monitor.py
```

**Programador de tareas**
- Crear una tarea que ejecute el comando anterior en el directorio del repo.
- Configurar "Si la tarea ya se esta ejecutando": No iniciar una nueva instancia.
- Si esta activo por Task Scheduler, no ejecutar manualmente para evitar instancias duplicadas.
- Usar ruta completa en "Programa o script": `F:\02-ASIC - mineros\miner-alerts\.venv\Scripts\python.exe`
- En "Iniciar en": `F:\02-ASIC - mineros\miner-alerts`
- Ver un proceso padre/hijo puede deberse al launcher; el mutex evita doble instancia real.

**Produccion (recomendado)**
Config minimo:
```json
{
  "qa_mode": false,
  "qa_allow_real_actions": false,
  "poll_seconds": 30,
  "telegram": {
    "bot_token": "xxx",
    "chat_id": "000000000",
    "poll_timeout_seconds": 25,
    "poll_sleep_seconds": 0.2
  }
}
```

**Pasar de QA a Produccion (local)**
1. En `app/config.json` (NO commitear) setear:
```json
{
  "qa_mode": false
}
```
2. Opcional: borrar `qa_force_state`, `qa_low_seconds`, `qa_poll_seconds` si existen.
3. Reiniciar el script y verificar que NO aparezca `[TICK]` y que el log muestre `qa_mode=false`.

**Windows: por que veo dos python.exe**
- En Windows, `python.exe` puede ser un launcher/shim que crea un proceso hijo real.
- Esto puede verse como padre/hijo aunque el mutex evita doble instancia del monitor.
- Solucion definitiva: instalar Python oficial (python.org) y recrear el venv.

Checklist de verificacion (PowerShell):
- Ver version del ejecutable del venv:
  - `(Get-Item "F:\02-ASIC - mineros\miner-alerts\.venv\Scripts\python.exe").VersionInfo | Format-List *`
- Listar procesos por script:
  - `Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*miner_monitor.py*" } | Select-Object ProcessId,ParentProcessId,CommandLine`

**Si Pylance subraya funciones existentes**
- Select Interpreter -> `F:\02-ASIC - mineros\miner-alerts\.venv\Scripts\python.exe`
- Pylance: Restart Language Server
- Developer: Reload Window
- Verificar que VS Code este abriendo el archivo correcto:
  - `& ".\.venv\Scripts\python.exe" -c "import app.miner_monitor as m; print(m.__file__)"`

**Debug API 4028**
```powershell
python tools\debug_4028.py 192.168.100.23
```
Para ayuda: `python tools\debug_4028.py -h`.

**Troubleshooting**
- Sin respuesta 4028: verificar red, IP, firewall y puerto con `Test-NetConnection`.
- Telegram no envia: revisar token y `chat_id`.
- Si sendMessage tarda ~10s: revisar DNS/firewall/antivirus o bloqueos salientes.
- Token invalido: regenerar en `@BotFather`.

**Reset / Limpieza**
- Borrar `app/state.json` si cambiaste mucho la configuracion, agregaste/quitaste mineros o queres reiniciar estados y cooldowns.
- El mutex se libera al salir. Si el proceso muere, Windows libera el mutex automaticamente.

**QA manual (rapido)**
- Chequeo sintaxis: `& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py`.
- Comando Telegram `status` responde con snapshot.
- Comando Telegram `info` / `info all` devuelve datos (depende del firmware).
- Comando Telegram `selftest` responde OK/FAIL.
- Comandos Telegram `health`, `quality`, `firmware` y `diagnose` leen historial SQLite sin IO al minero.
- Comando Telegram `reboot 23` solicita confirmacion y ejecuta reboot al confirmar.

**QA / Pruebas (modo QA)**
- Activar QA:
  - `qa_mode=true` en `app/config.json` (local).
  - Forzar QA por env: `QA_MODE_FORCE=1` + `QA_MODE=true`.
  - Forzar prod por env: `QA_MODE_FORCE=1` + `QA_MODE=false`.
  - Sin `QA_MODE_FORCE`, la variable `QA_MODE` NO afecta (manda config).
- En QA, por defecto NO se ejecutan acciones reales (reboot/restart/auto-reboot):
  - Habilitar con `QA_ALLOW_REAL_ACTIONS=true` (env var) o `qa_allow_real_actions=true` en config.
- **QA puede simular LOW y si habilitas `qa_allow_real_actions`, puede rebootear mineros reales.**
- Overrides utiles:
  - `qa_force_state`: forzar estado por minero (ej: `{ "23": "LOW" }`).
  - `qa_poll_seconds`, `qa_low_seconds`, `qa_auto_reboot_window_seconds` para acelerar pruebas.
- Checklist:
  - `& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py`
  - Mutex: ejecutar dos instancias, la segunda debe salir.
  - Telegram: `help/status/info/selftest/health/quality/firmware/diagnose` responden en <5s tipicamente.
  - Reboot/restart: `reboot 23` -> confirmar con `confirm reboot 23 <code>` (timeout 60s, cooldown 10 min).
  - Auto-reboot: forzar LOW sostenido y verificar disparo (QA: `qa_low_seconds=60`).
  - Degraded: forzar 3 auto-reboots en ventana y observar STATUS horario (06:00-00:00 AR).
- Simula OFFLINE con un puerto incorrecto y confirma transicion a OFFLINE y luego RECOVERED.
- Simula LOW subiendo `threshold_ths` y confirma LOW y RECOVERED.

**Herramientas Auxiliares de Producción (Release v2.0.0)**
- **Supervisión de Liveness (Watchdog)**:
  `& ".\.venv\Scripts\python.exe" tools\monitor_watchdog.py --config app\config.json`
- **Métricas Prometheus**:
  `& ".\.venv\Scripts\python.exe" tools\metrics_exporter.py --config app\config.json --port 9108`
- **Stack Grafana Local**:
  `docker compose -f observability\docker-compose.metrics.yml up -d`
- **Backups Online SQLite**:
  `& ".\.venv\Scripts\python.exe" tools\event_store_backup.py --source-db data\miner_alerts.db --backup-root D:\MinerAlertsBackups --action backup`
- **Simulacro de Restore en Staging**:
  `& ".\.venv\Scripts\python.exe" tools\event_store_backup.py --source-db data\miner_alerts.db --backup-root D:\MinerAlertsBackups --staging-root D:\MinerAlertsStaging --action restore-staging --backup-id <ID> --restore-target D:\MinerAlertsStaging\drill`
- **Auditoría de Release**:
  `& ".\.venv\Scripts\python.exe" tools\release_audit.py --check-only`

**Release checklist**
1. `& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py`
2. Ejecutar bot en produccion y verificar startup y heartbeat.
3. Telegram: `help/status/info/selftest/health/quality/firmware/diagnose`.
4. (Opcional) `reboot 23` + confirm (si queres probar).
5. `tools/release_audit.py --check-only`
6. `git status` / `git diff`
7. commit + push

**Comandos utiles**
- Instalar: `pip install -r requirements.txt`
- Ejecutar: `python app\miner_monitor.py`
- Debug: `python tools\debug_4028.py <IP>`
