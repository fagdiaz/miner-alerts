# miner-alerts

Monitor de mineros ASIC (API 4028) con alertas por Telegram, cambios de estado agrupados y detección de reboots. Pensado para correr en Windows con PowerShell y evitar spam.

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

**Configuración**
- Copia `app/config.example.json` a `app/config.json`.
- Completa `telegram.bot_token` y `telegram.chat_id`.
- `app/config.json` NO se commitea.

Tabla de claves principales (valores por defecto en `app/config.example.json`):
| Clave | Descripción |
| --- | --- |
| `poll_seconds` | Intervalo de consulta en segundos. |
| `threshold_ths` | Umbral de hashrate en TH/s. |
| `fails_before_alert` | Lecturas consecutivas para LOW/OFFLINE. |
| `recovery_successes` | Lecturas OK consecutivas para RECOVERED. |
| `alert_cooldown_seconds` | Legacy, actualmente no se usa. |
| `notify_startup` | Enviar STARTUP con snapshot del primer tick. |
| `notify_offline` | Permite notificar OFFLINE. |
| `offline_is_actionable` | Si es false, OFFLINE solo se loguea. |
| `notify_reboot` | Habilita detección de reboot por Elapsed. |
| `reboot_cooldown_seconds` | Cooldown de reboot por minero. |
| `reboot_window_seconds` | Ventana para reboot si cae a LOW/OFFLINE. |
| `notify_initial_non_ok` | Si `notify_startup=false`, puede notificar el estado inicial no OK. |

**Telegram**
- Crear bot con `@BotFather` y obtener token.
- Obtener `chat_id` con `@userinfobot` o via `https://api.telegram.org/bot<TOKEN>/getUpdates`.

**Notificaciones**
- Se envía Telegram solo cuando cambia el estado, en un único mensaje agrupado por ciclo.
- Estados:
- OK: hashrate >= threshold.
- LOW: hashrate < threshold por N lecturas.
- OFFLINE: sin respuesta del API 4028 por N lecturas.
- Al iniciar, si `notify_startup=true`, se envía un STARTUP con snapshot completo (hashrate y etiquetas).

**Ejecución manual**
```powershell
python app\miner_monitor.py
```

**Programador de tareas**
- Crear una tarea que ejecute el comando anterior en el directorio del repo.

**Debug API 4028**
```powershell
python app\debug_4028.py 192.168.100.23
```
Para ayuda: `python app\debug_4028.py -h`.

**Troubleshooting**
- Sin respuesta 4028: verificar red, IP, firewall y puerto con `Test-NetConnection`.
- Telegram no envía: revisar token y `chat_id`.
- Token inválido: regenerar en `@BotFather`.

**QA manual (rápido)**
- Verifica que el log muestre TH/s al menos en un minero.
- Simula OFFLINE con un puerto incorrecto y confirma transición a OFFLINE y luego RECOVERED.
- Simula LOW subiendo `threshold_ths` y confirma LOW y RECOVERED.
- Chequeo sintaxis: `python -m py_compile app\miner_monitor.py app\debug_4028.py`.

**Comandos útiles**
- Instalar: `pip install -r requirements.txt`
- Ejecutar: `python app\miner_monitor.py`
- Debug: `python app\debug_4028.py <IP>`
