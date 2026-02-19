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

Tabla de claves principales (valores por defecto en `app/config.example.json`):
| Clave | Descripcion |
| --- | --- |
| `poll_seconds` | Intervalo de consulta en segundos. |
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

**Telegram**
- Crear bot con `@BotFather` y obtener token.
- Obtener `chat_id` con `@userinfobot` o via `https://api.telegram.org/bot<TOKEN>/getUpdates`.
- Comando disponible: `status` (responde con snapshot actual).
  - Respuesta inmediata via long polling, sin afectar el loop de mineros.

**Notificaciones**
- Se envia Telegram solo cuando cambia el estado, en un unico mensaje agrupado por ciclo.
- Estado OK: hashrate >= threshold.
- Estado LOW: hashrate < threshold por N lecturas.
- Estado OFFLINE: sin respuesta del API 4028 por N lecturas.
- Estado HASHBOARD: boards activos < `expected_boards` (segun `stats`).
- Al iniciar, si `notify_startup=true`, se envia un STARTUP con snapshot completo (hashrate y etiquetas).
- El monitor evita instancias duplicadas usando un mutex de sistema (Win32).
- El estado se persiste en `app/state.json` para continuidad (streaks, estado y cooldowns).

**Ejecucion manual**
```powershell
python app\miner_monitor.py
```

**Programador de tareas**
- Crear una tarea que ejecute el comando anterior en el directorio del repo.
- Configurar "Si la tarea ya se esta ejecutando": No iniciar una nueva instancia.
- Si esta activo por Task Scheduler, no ejecutar manualmente para evitar instancias duplicadas.

**Debug API 4028**
```powershell
python app\debug_4028.py 192.168.100.23
```
Para ayuda: `python app\debug_4028.py -h`.

**Troubleshooting**
- Sin respuesta 4028: verificar red, IP, firewall y puerto con `Test-NetConnection`.
- Telegram no envia: revisar token y `chat_id`.
- Token invalido: regenerar en `@BotFather`.

**Reset / Limpieza**
- Borrar `app/state.json` si cambiaste mucho la configuracion, agregaste/quitaste mineros o queres reiniciar estados y cooldowns.
- El mutex se libera al salir. Si el proceso muere, Windows libera el mutex automaticamente.

**QA manual (rapido)**
- Chequeo sintaxis: `python -m py_compile app\miner_monitor.py`.
- Comando Telegram `status` responde con snapshot.
- Simula OFFLINE con un puerto incorrecto y confirma transicion a OFFLINE y luego RECOVERED.
- Simula LOW subiendo `threshold_ths` y confirma LOW y RECOVERED.

**Comandos utiles**
- Instalar: `pip install -r requirements.txt`
- Ejecutar: `python app\miner_monitor.py`
- Debug: `python app\debug_4028.py <IP>`
