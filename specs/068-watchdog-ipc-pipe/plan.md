# Plan de Implementación — Spec 068: Canal IPC Monitor ↔ Watchdog vía Named Pipes (PROP-007)

**ID**: 068  
**Rama**: `codex/022-adaptive-acquisition`  
**Estado**: Planificado  

---

## 1. Arquitectura Técnica y Estructura de Clases

### 1.1 Módulo `app/ipc/watchdog_pipe.py`

```python
class WatchdogIPCServer:
    """Servidor IPC ultraliviano para sondeo de vida y diagnóstico forense."""
    def __init__(
        self,
        pipe_name: str = r"\\.\pipe\MinerAlertsWatchdog",
        fallback_port: int = 4029,
        timeout_s: float = 0.1,
        get_status_callback: Optional[Callable[[], Tuple[int, float, float]]] = None,
    ) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def _run_named_pipe(self) -> None: ...
    def _run_socket_fallback(self) -> None: ...

class WatchdogIPCClient:
    """Cliente utilizado por tools/monitor_watchdog.py para sondear el monitor en <15s."""
    def __init__(
        self,
        pipe_name: str = r"\\.\pipe\MinerAlertsWatchdog",
        fallback_port: int = 4029,
        timeout_s: float = 0.1,
    ) -> None: ...
    def ping(self) -> Tuple[bool, Optional[int], Optional[float], Optional[str]]: ...
```

### 1.2 Mecanismo de Volcado Forense (`app/core/forensics.py` o helper en IPC)
Función pura para capturar el estado interno de todos los hilos en ejecución:
```python
def dump_thread_frames(output_dir: Path) -> Path:
    """Captura los stack traces de todos los hilos activos sin abortar el proceso."""
    frames = sys._current_frames()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = output_dir / f"deadlock_forensics_{timestamp}.log"
    with open(target, "w", encoding="utf-8") as f:
        for thread_id, frame in frames.items():
            f.write(f"\n--- Thread {thread_id} ---\n")
            traceback.print_stack(frame, file=f)
    return target
```

---

## 2. Puntos de Integración

1. **`app/miner_monitor.py`**:
   - En `main()`, junto al `CoreSupervisoryEngine`, instanciar `WatchdogIPCServer` pasando un callback que retorne `(tick_sequence, process_start_ts, last_tick_duration)`.
   - En el `finally` de `main()`, invocar `server.stop()`.
   - Mantener invariante estricto de literales en `inspect.getsource(main)`.

2. **`tools/monitor_watchdog.py`**:
   - Integrar sondeo de alta frecuencia mediante `WatchdogIPCClient.ping()`.
   - Si el ping falla 3 veces consecutivas:
     * Registrar causa en `logs/watchdog.log`.
     * Ejecutar `Restart-Service -Name MinerAlerts -Force`.
     * Enviar notificación Telegram de alerta crítica.

---

## 3. Plan de Verificación & Testing

1. **Pruebas de Protocolo (`tests/test_watchdog_ipc.py`)**:
   - Handshake PING/PONG con nonce dinámico.
   - Manejo de timeout cuando el socket/pipe no responde en 100 ms.
   - Prueba de reconexión y desconexión limpia sin fugas de handles.
2. **Pruebas de Fallback**:
   - Simular fallo en `CreateNamedPipeW` y verificar que el servidor cambia limpiamente a socket TCP loopback `127.0.0.1:4029`.
3. **Pruebas de Detección de Deadlock**:
   - Simular congelamiento del `tick_sequence` y verificar que el cliente reporta fallo de supervisión.
4. **Validación Global**:
   - Ejecutar la suite completa garantizando $\ge 1072$ tests PASS (cero regresiones).
   - `py_compile` en todos los archivos modificados.
