# Tasks — Spec 068: Canal IPC Monitor ↔ Watchdog vía Named Pipes (PROP-007)

**ID**: 068  
**Rama**: `codex/022-adaptive-acquisition`  
**Estado**: Completada & Certificada  

---

### Fase A: Módulo IPC Local en Windows

- [x] **T001**: Crear `app/ipc/__init__.py` y `app/ipc/watchdog_pipe.py` con `WatchdogIPCServer` y `WatchdogIPCClient`:
  - Soporte de Named Pipes en Windows (`CreateNamedPipeW`, `ConnectNamedPipe`, `DisconnectNamedPipe`) vía `ctypes.windll.kernel32`.
  - Descriptor de seguridad explícito (SDDL `D:(A;;GRGW;;;WD)`) para evitar `ERROR_ACCESS_DENIED` al conectar desde usuarios locales no elevados.
  - Fallback automático a Socket TCP Loopback `127.0.0.1:4029` con `SO_REUSEADDR` si Named Pipe falla por permisos de Windows NT o colisión de puerto.
  - Protocolo de texto plano: `PING <nonce>` -> `PONG <nonce> <tick_sequence> <uptime> <last_tick_elapsed_s>`.
  - Timeout estricto $\le 100\text{ ms}$ por operación.
  - Cierre explícito de sockets y handles en bloques `finally`.
  - Conexión local efímera de desbloqueo ("wake-up connect") en `stop()` para liberar `ConnectNamedPipe` sin bloquear el shutdown del servicio.
  - Hilo daemon con `threading.Event` para parada controlada en $<200\text{ ms}$.
- [x] **T002**: Implementar helper de diagnóstico forense `dump_thread_frames(output_dir: Path) -> Path` capturando `sys._current_frames()` con `traceback.print_stack()`.

### Fase B: Integración en Monitor y Watchdog

- [x] **T003**: Integrar `WatchdogIPCServer` en `app/miner_monitor.py:main()` de forma aditiva:
  - Instanciar condicionalmente según `"watchdog_ipc_enabled"` (default: true).
  - Callback suministrando `(tick_sequence, process_start_ts, last_tick_duration)`.
  - Parada en `finally` de `main()`.
  - **Invariante Crítico**: Preservar intactos los 37 tests de inspección textual `inspect.getsource(main)`.
- [x] **T004**: Actualizar `tools/monitor_watchdog.py`:
  - Incorporar sondeo de alta frecuencia (<15s) vía `WatchdogIPCClient.ping()`.
  - Máquina de estados de 3 intentos fallidos consecutivos (intervalos de 5s / 2s).
  - Si 3 intentos fallan y el PID existe en Windows:
    * Llamar `dump_thread_frames()`.
    * Ejecutar `Restart-Service -Name MinerAlerts -Force`.
    * Despachar alerta de emergencia a Telegram.
- [x] **T005**: Documentar parámetros en `app/config.example.json`.

### Fase C: Pruebas Unitarias y Validación

- [x] **T006**: Crear `tests/test_watchdog_ipc.py` con $\ge 10$ pruebas unitarias (16 pruebas implementadas y pasando):
  - `test_ipc_server_start_and_stop`
  - `test_ipc_client_ping_pong_roundtrip`
  - `test_ipc_client_handles_server_timeout`
  - `test_ipc_deadlock_detection_via_stale_tick_sequence`
  - `test_ipc_fallback_to_loopback_socket`
  - `test_ipc_socket_and_handle_cleanup_on_error`
  - `test_ipc_shutdown_wake_up_unblock`
  - `test_dump_thread_frames_creates_valid_log`
  - `test_probe_ipc_and_recover_ok`
  - `test_probe_ipc_and_recover_deadlock`
  - `test_probe_ipc_and_recover_unresponsive_process_alive`
  - `test_probe_ipc_and_recover_missing_process`
- [x] **T007**: Chequeo de sintaxis: `py_compile app/ipc/watchdog_pipe.py tools/monitor_watchdog.py app/miner_monitor.py`.
- [x] **T008**: Ejecución de suite de regresión completa: **1176 tests PASS** (0 fallos, 0 errores, 0 regresiones en 34.4s).

### Fase D: Documentación y Cierre

- [x] **T009**: Registrar comandos y evidencia en `specs/068-watchdog-ipc-pipe/evidence.md`.
- [x] **T010**: Agregar entrada en `docs/audit/DEVELOPMENT_LOG.md`.
- [x] **T011**: Actualizar `docs/speckit/ROADMAP.md` y `prompt.txt`.
