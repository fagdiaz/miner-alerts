# Plan: Spec 067 — Gateway Heartbeat y Supresión de Tormentas de Red

**Estado**: READY  
**Baseline**: 1064 tests PASS  
**Rama**: `codex/022-adaptive-acquisition`

---

## Diseño Técnico

### Módulo 1: `app/network/gateway_heartbeat.py`

```python
class GatewayHeartbeatWorker:
    """Hilo daemon de latido de red. Verifica conectividad TCP al gateway cada interval_s.
    
    Estado expuesto (GIL-safe):
        gateway_online: bool
        last_gateway_loss_ts: Optional[float]
        last_gateway_ok_ts: float
        consecutive_failures: int
    """
    
    def __init__(self, host: str, port: int = 80, interval_s: float = 5.0,
                 connect_timeout_s: float = 0.05, fallback_port: int = 53) -> None:
        ...
    
    def start(self) -> None: ...  # Inicia el hilo daemon
    def stop(self) -> None: ...   # Señal de parada (best-effort, daemon)
    def is_recently_lost(self, within_seconds: float = 15.0) -> bool: ...
    
    def _run(self) -> None:
        """Loop principal del worker. try/except Exception total."""
        while not self._stop_event.is_set():
            try:
                sock = socket.create_connection((self._host, self._port), timeout=self._timeout)
            except OSError:
                # Intentar fallback port
                ...
            finally:
                sock.close()  # Explícito, evita leaks en Windows
            time.sleep(self._interval_s)
```

### Módulo 2: Integración en `app/miner_monitor.py`

**Punto de arranque**: Después de la instanciación del `CoreSupervisoryEngine` (línea ~5340).

```python
# Spec 067: Gateway Heartbeat Worker
_gateway_heartbeat: Optional[GatewayHeartbeatWorker] = None
if config.get("gateway_heartbeat_enabled", False):
    from app.network.gateway_heartbeat import GatewayHeartbeatWorker
    _gateway_heartbeat = GatewayHeartbeatWorker(
        host=config.get("gateway_host", "192.168.100.1"),
        port=int(config.get("gateway_port", 80)),
        interval_s=float(config.get("gateway_heartbeat_interval_s", 5.0)),
        fallback_port=int(config.get("gateway_fallback_port", 53)),
    )
    _gateway_heartbeat.start()
    log(f"GATEWAY_HEARTBEAT started host={config.get('gateway_host')} ...")
```

**Punto de evaluación**: En el loop, antes del despacho de `EPISODE_ALERT`:

```python
_network_storm_active = (
    _gateway_heartbeat is not None
    and _gateway_heartbeat.is_recently_lost(
        within_seconds=float(config.get("network_storm_suppression_seconds", 15.0))
    )
)
```

**Supresión en el coordinador de episodios**: Pasar `network_storm_active` al `IrregularEpisodeCoordinator` o suprimir el dispatch de notificación directamente.

### Patrón de supresión aditivo (sin romper invariantes de inspect.getsource)

Para no modificar las cadenas verificadas por los 4 test suites de invariantes:
- La supresión se implementa como un guard **antes** del bloque de `episode_notifications.should_notify()`, sin tocar el bloque de auto-reboot ni los interlocks existentes.
- El flag `_network_storm_active` se evalúa solo para el dispatch de alertas Telegram de `STATE_OFFLINE` y `STATE_LOW`.

---

## Riesgos de Implementación

| Riesgo | Mitigación |
|---|---|
| `socket.create_connection` bloquea > 50ms en Windows | El worker corre en hilo daemon separado — el bucle principal nunca espera |
| Leak de socket si excepción antes del `close()` | Uso de `try/finally: sock.close()` en todas las rutas |
| False positive: gateway caído pero mineros accesibles (internet caído, LAN ok) | `is_recently_lost()` solo aplica a `STATE_OFFLINE` — mineros responden via LAN de todos modos |
| `_network_storm_active` leído con race condition | Lectura de `bool` es atómica en CPython (GIL) — sin lock necesario |
