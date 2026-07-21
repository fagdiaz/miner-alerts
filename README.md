# miner-alerts

Monitor de mineros ASIC (API 4028) con alertas por Telegram, cambios de estado agrupados, deteccion de reboots y hashboards caidos. Pensado para correr en Windows con PowerShell y evitar spam.

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
| `hashcore` | Configuracion del Hashcore Toolkit CLI (reboot/restart). |

**Telegram**
- Crear bot con `@BotFather` y obtener token.
- Obtener `chat_id` con `@userinfobot` o via `https://api.telegram.org/bot<TOKEN>/getUpdates`.
- Comandos disponibles:
  - `/help`, `/status`, `/info [all|miner]`, `/selftest`.
  - `/events [miner]`, `/event <id>`, `/why [miner]` (historial local).
  - `/health [all|miner]` (baseline estable por minero).
  - `/quality [all|miner]` (shares, errores y estado de cadenas por intervalo).
  - `/firmware [all|miner]` (evidencia Vnish normalizada almacenada localmente).
  - `/reboot` (guiado) y `/rb<ID>` (seleccion click-safe) -> piden confirmacion.
  - `/reboot_no_ok` -> preview bulk; `/c<code>` confirma de forma click-safe.
  - `/restart <miner>` -> pide confirmacion.
  - `/confirm reboot <miner> <code>` y `/confirm restart <miner> <code>`.
- Respuesta inmediata via long polling, sin afectar el loop de mineros.
  - Si Telegram esta lento, la respuesta puede tardar: el monitor no se cuelga porque usa cola de envio.

**Confirm code (operativo)**
- Comando: `reboot 23`.
- Bot responde: `confirm reboot 23 <code>`.
- TTL 60s; si expira, pedir `reboot 23` de nuevo.
- Si el script reinicia, el pending se pierde: hay que reemitir `reboot 23`.

**Notificaciones**
- Se envia Telegram ante eventos relevantes, en un unico mensaje agrupado por ciclo.
- Estado OK: hashrate >= threshold.
- Estado LOW: hashrate < threshold por N lecturas.
- Estado OFFLINE: sin respuesta del API 4028 por N lecturas.
- Estado HASHBOARD: boards activos < `expected_boards` (segun `stats`).
- Al iniciar, si `notify_startup=true`, se envia un STARTUP con snapshot completo (hashrate y etiquetas).
- El monitor evita instancias duplicadas usando un mutex de sistema (Win32).
- El estado se persiste en `app/state.json` para continuidad (streaks, estado y cooldowns).
- Auto-reboot: si un minero permanece LOW por 10 minutos continuos y supera todos los guardrails, se envia reboot automatico.
  - Limite recomendado: max 3 auto-reboots por 6 horas. Luego entra en degraded mode.
- Degraded mode se registra siempre; el STATUS horario esta deshabilitado por defecto con `notify_degraded_hourly=false`.

**Vnish log intelligence (read-only)**
- Instalar dependencias: `& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt`.
- Probar sin persistencia: `& ".\.venv\Scripts\python.exe" tools\vnish_log_collector.py --config app\config.json --dry-run --tabs status --idle-timeout 1 --max-bytes 262144`.
- Persistir eventos normalizados: `& ".\.venv\Scripts\python.exe" tools\vnish_log_collector.py --config app\config.json --tabs status,miner,autotune,system`.
- El colector procesa mineros y tabs secuencialmente, sin reintentos ni acciones. Guarda solo categoria, severidad, codigo, resumen generado y fingerprint; no guarda lineas crudas, workers ni payloads del firmware.
- `/firmware`, `/firmware all` y `/firmware <miner>` consultan SQLite solamente. No abren conexiones a los mineros ni ejecutan Hashcore.
- El colector es una CLI separada: el monitor de produccion no mantiene WebSockets Vnish abiertos.

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
- Comandos Telegram `health`, `quality` y `firmware` leen historial SQLite sin IO al minero.
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
  - Telegram: `help/status/info/selftest/health/quality/firmware` responden en <5s tipicamente.
  - Reboot/restart: `reboot 23` -> confirmar con `confirm reboot 23 <code>` (timeout 60s, cooldown 10 min).
  - Auto-reboot: forzar LOW sostenido y verificar disparo (QA: `qa_low_seconds=60`).
  - Degraded: forzar 3 auto-reboots en ventana y observar STATUS horario (06:00-00:00 AR).
- Simula OFFLINE con un puerto incorrecto y confirma transicion a OFFLINE y luego RECOVERED.
- Simula LOW subiendo `threshold_ths` y confirma LOW y RECOVERED.

**Release checklist**
1. `& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py`
2. Ejecutar bot en produccion y verificar startup.
3. Telegram: `help/status/info/selftest/health/quality/firmware`.
4. (Opcional) `reboot 23` + confirm (si queres probar).
5. `git status` / `git diff`
6. commit + push

**Comandos utiles**
- Instalar: `pip install -r requirements.txt`
- Ejecutar: `python app\miner_monitor.py`
- Debug: `python app\debug_4028.py <IP>`
