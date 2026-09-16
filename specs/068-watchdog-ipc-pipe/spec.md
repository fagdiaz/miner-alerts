# Spec 068: Canal IPC Alta Frecuencia Monitor ↔ Watchdog vía Named Pipes (PROP-007)

**ID**: 068  
**Módulos**: `app/ipc/watchdog_pipe.py` (nuevo), `tools/monitor_watchdog.py`, `app/miner_monitor.py`  
**Riesgo**: Medio (Concurrencia IPC en Windows, gestión de handles y permisos)  
**Prioridad**: P3 (Media/Baja)  
**Estado**: Especificado  
**Dependencias**: Spec 021 (Liveness Watchdog), Spec 060 (Core Daemon Architecture), Spec 065 (Supervisory Hooks)  

---

## 1. Contexto y Problema

Actualmente, la supervisión de salud del monitor depende de dos mecanismos desacoplados:
1. Escritura periódica de `data/monitor_heartbeat.json` por el bucle principal de `miner_monitor.py` (Spec 021).
2. Ejecución programada del script independiente `tools/monitor_watchdog.py` cada 2-5 minutos mediante el Programador de Tareas de Windows.

### Brecha Operativa:
- **Latencia de Detección Excesiva (2 a 5 minutos)**: Si el proceso de `miner_monitor.py` sufre un deadlock de hilos en Python (ej. contención de `state_lock`, bloqueo en llamadas de red sin timeout a nivel C de socket, o GIL congelado en extensiones nativas), el watchdog tarda varios minutos en detectar la ausencia de latido.
- **Falta de Diferenciación entre Proceso Zombie y Tick Colgado**: `sc.exe queryex` reporta que el servicio está `RUNNING` mientras exista el PID, aun cuando el hilo de supervisión principal esté completamente congelado en un bucle cerrado o deadlock.
- **Ausencia de Diagnóstico Forense**: Cuando un watchdog finalmente reinicia el servicio con `Restart-Service`, el estado de los hilos de Python se pierde irremediablemente, impidiendo conocer en qué línea de código ocurrió el deadlock.

---

## 2. Arquitectura de Solución

### Componente 1: Servidor IPC Ultraliviano en el Monitor (`app/ipc/watchdog_pipe.py`)
Un hilo daemon dedicado dentro de `miner_monitor.py` expone un canal de comunicación local de alta frecuencia para que el watchdog sondee el estado del proceso en tiempo real:
- **Transporte Primario**: Named Pipe nativo en Windows (`\\.\pipe\MinerAlertsWatchdog`) implementado con `ctypes.windll.kernel32` (`CreateNamedPipeW`, `ConnectNamedPipe`, `DisconnectNamedPipe`), evitando requerir la librería binaria externa `pywin32`.
- **Transporte de Fallback**: Loopback Socket TCP local (`127.0.0.1:4029`) con `SO_REUSEADDR` activado automáticamente si la creación del pipe falla por restricciones de Windows NT o colisión de puerto.
- **Permisos y Descriptor de Seguridad (QA-068-01)**: Creación de un `SECURITY_DESCRIPTOR` explícito con SDDL `D:(A;;GRGW;;;WD)` (Allow Read/Write to Everyone local) vía `advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW`. Esto evita terminantemente el fallo `ERROR_ACCESS_DENIED (5)` cuando el servicio corre bajo `NT AUTHORITY\SYSTEM` y el watchdog es ejecutado por un usuario local o tarea programada.
- **Desbloqueo Limpio en Parada (QA-068-02)**: Para evitar que el hilo servidor quede congelado de forma indefinida en una llamada síncrona a `ConnectNamedPipe` durante el apagado del servicio, el método `server.stop()` realiza una conexión local efímera de desbloqueo ("wake-up connect") que garantiza la liberación inmediata del kernel y la terminación del hilo en $<200\text{ ms}$.

### Componente 2: Protocolo Ping-Pong Estricto & Detección de Deadlock
1. El cliente watchdog envía una línea de texto plano:
   ```
   PING <nonce>\n
   ```
2. El servidor responde inmediatamente en menos de 100 ms:
   ```
   PONG <nonce> <tick_sequence> <uptime_s> <last_tick_elapsed_s>\n
   ```
3. **Discriminador de Deadlock del Bucle Principal**:
   - Si la respuesta `PONG` llega pero `tick_sequence` permanece inmutable durante más de 60 segundos mientras el monitor debería iterar cada 30 segundos, el watchdog determina con certeza matemática que **el hilo IPC responde pero el hilo principal de supervisión está congelado en deadlock**.

### Componente 3: Máquina de Estados de Recuperación & Volcado Forense
El watchdog implementa una máquina de estados de 3 intentos consecutivos con intervalos de 5 segundos:
- **Intento 1 Fallido (5s sin respuesta)**: Estado `WARNING`. Registro en log y reintento en 2 segundos.
- **Intento 2 Fallido (10s sin respuesta)**: Estado `CRITICAL`. Confirmación de falta de respuesta del pipe.
- **Intento 3 Fallido (15s sin respuesta)**: Estado `ACTION_REQUIRED`:
  1. Si el proceso Python de Miner Alerts existe en Windows (`OpenProcess(pid)`):
     - **Volcado Forense**: El monitor registra en disco `logs/deadlock_forensics_<timestamp>.log` capturando `sys._current_frames()` con el traceback completo de cada hilo activo.
     - **Reinicio Forzado**: El watchdog ejecuta `Restart-Service -Name MinerAlerts -Force`.
     - **Notificación Telegram**: Envía alerta estructurada:
       `🚨 WATCHDOG: Miner Alerts colgado (deadlock en hilo de supervisión tras 15s). Volcado forense guardado. Servicio reiniciado con éxito.`
  2. Si el proceso no existe: Notifica caída de proceso y ejecuta `Start-Service -Name MinerAlerts`.

---

## 3. Requisitos Funcionales y Técnicos

1. **RF-01 (Cero Overhead en Main Loop)**: El servidor IPC debe correr en un hilo daemon desacoplado (`name="WatchdogIPCServer"`), sin retener `state_lock` ni demorar el ciclo de adquisición.
2. **RF-02 (Timeout Acotado $\le 100\text{ ms}$)**: Todas las operaciones de lectura/escritura en el pipe o socket de loopback deben tener un timeout estricto de 100 ms para evitar acumulación de bloqueos.
3. **RF-03 (Cero Fugas de Handles)**: Cada conexión entrante de sondeo debe cerrarse de forma explícita (`DisconnectNamedPipe` / `CloseHandle` / `socket.close()`) en un bloque `finally`.
4. **RF-04 (Degradación Suave)**: Si el servidor IPC falla al inicializarse, el monitor continuará funcionando normalmente bajo el mecanismo existente de `data/monitor_heartbeat.json`, registrando un log de advertencia.
5. **RF-05 (Orden de Dependencia y Compatibilidad Invariante)**: La integración en `miner_monitor.py:main()` debe realizarse tras la activación del arnés de comportamiento (Spec 070 Fase A) o de forma puramente aditiva antes del bloque `while True:`, respetando el 100% de los 37 tests constitucionales de `inspect.getsource(main)`.

---

## 4. Configuración (`app/config.example.json`)

```json
{
  "watchdog_ipc_enabled": true,
  "watchdog_ipc_pipe_name": "\\\\.\\pipe\\MinerAlertsWatchdog",
  "watchdog_ipc_fallback_port": 4029,
  "watchdog_ipc_timeout_ms": 100,
  "watchdog_ipc_max_deadlock_tick_age_s": 60.0
}
```

---

## 5. Estrategia de Pruebas Unitarias

- `test_watchdog_pipe_server_start_stop`: Verificación de inicio, escucha y parada limpia del hilo servidor.
- `test_watchdog_pipe_ping_pong_protocol`: Verificación del formato y respuesta rápida ante comandos `PING`.
- `test_watchdog_pipe_deadlock_detection`: Simulación de `tick_sequence` congelado y diagnóstico de fallo de supervisión.
- `test_watchdog_pipe_timeout_and_cleanup`: Comprobación de cierre seguro de handles y liberación de recursos en Windows.
- `test_watchdog_pipe_fallback_loopback_socket`: Comprobación de degradación automática a socket TCP loopback si Named Pipe es rechazado.
