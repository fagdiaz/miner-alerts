# Spec 067: Latido de Gateway y Supresión de Tormentas por Fallo de Red Local (PROP-005)

**ID**: 067  
**Módulos**: `app/network/gateway_heartbeat.py` (nuevo), `app/miner_monitor.py`  
**Riesgo**: Bajo  
**Prioridad**: P2 (Media)  
**Estado**: Especificado  
**Dependencias**: Spec 065 (pipeline de hooks activo), Spec 066 (grace period post-arranque)  

---

## Contexto y Problema

El discriminador de caídas de fase (Spec 051) ya verifica conectividad del gateway cuando ocurre una caída unísona de mineros. Sin embargo, hay una brecha operativa:

**Escenario problemático**: Un switch Ethernet local o access point doméstico sufre un microcorte de 5-15 segundos (reinicio de firmware, recalculación STP, actualización automática). En ese lapso, las 4 conexiones TCP 4028 hacia los mineros fallan por timeout simultáneamente, pudiendo desencadenar:
- `STATE_OFFLINE` en los 4 mineros antes de que expire el startup_grace
- Alertas de desconexión en Telegram (falsos positivos)
- En el peor caso, conatos de auto-reboot si el timing coincide con streaks acumulados

**Eventos conocidos en producción**: Registrados en log con patrón `responded=False` en los 4 mineros simultáneamente durante < 15s seguidos de recuperación limpia.

---

## Arquitectura de Solución

### Componente 1: `GatewayHeartbeatWorker` — Hilo daemon de latido de red

Archivo: `app/network/gateway_heartbeat.py`

```
GatewayHeartbeatWorker
├── Hilo daemon independiente (no bloquea GIL)
├── Intervalo: cada 5 segundos
├── Método: socket.create_connection(gateway_host, gateway_port, timeout=0.05)
├── Estado atómico: gateway_online: bool (asignación GIL-safe en CPython)
├── Timestamps: last_gateway_loss_ts: Optional[float], last_gateway_ok_ts: float
├── Contador: consecutive_failures: int
└── Método: is_recently_lost(within_seconds=15.0) -> bool
```

**Diseño de la conexión TCP de prueba**:
- Intento de conexión con `timeout=0.05s` (50 ms) — nunca bloquea el GIL significativamente
- Si `OSError` o `TimeoutError`: registra pérdida, incrementa contador
- Si conecta exitosamente: cierra socket inmediatamente con `socket.close()`
- Fallback configurable: si `gateway_port=80` falla, intenta `gateway_port=53` (DNS)

### Componente 2: Ventana de Supresión de Tormentas

Integración en `app/miner_monitor.py`:

```python
# Al inicio del loop, antes de evaluar estado:
network_storm_active = (
    gateway_heartbeat is not None
    and gateway_heartbeat.is_recently_lost(within_seconds=network_storm_suppression_seconds)
)

# Antes de despachar alertas EPISODE_ALERT:
if network_storm_active:
    log(f"[NETWORK_STORM_SUPPRESSED] gateway_lost={elapsed:.1f}s — suprimiendo alerta")
    continue  # skip episode notification
```

**Reglas de la ventana de supresión**:
1. Si `gateway_online = False` **ahora**: suprimir alertas de desconexión (máx `network_storm_suppression_seconds=15`)
2. Si gateway se recuperó en los últimos 15s: registrar `[NETWORK_STORM_ABSORBED]` y descartar
3. Si pérdida supera los 15s Y los mineros continúan inaccesibles: liberar alertas normalmente

### Componente 3: Configuración en `config.json`

```json
{
  "gateway_heartbeat_enabled": true,
  "gateway_host": "192.168.100.1",
  "gateway_port": 80,
  "gateway_heartbeat_interval_s": 5,
  "network_storm_suppression_seconds": 15
}
```

---

## Invariantes de Diseño

1. **No blocking del bucle principal**: El `GatewayHeartbeatWorker` corre en su propio hilo daemon. El acceso al estado (`gateway_online`) es lectura directa de `bool` (atómica en CPython, GIL-safe).
2. **Sin leaks de socket**: Todo socket creado en el worker se cierra con `finally: sock.close()` explícito, incluso ante excepciones.
3. **Supresión conservadora**: Solo se suprimen alertas de `EPISODE_ALERT` de desconexión. Las alertas de LOW hashrate, temperatura y governance se propagan siempre.
4. **Degradación suave**: Si `gateway_heartbeat_enabled = false` o el worker falla en arrancar, el sistema opera exactamente igual que antes (sin supresión). Sin regresión.
5. **Compatibilidad con grace period**: Durante `startup_grace_active`, la supresión de red es redundante pero inocua — los streaks ya están bloqueados.
6. **Sin nuevas dependencias externas**: Usa únicamente `socket` de la stdlib de Python.

---

## Criterios de Aceptación

1. `GatewayHeartbeatWorker` arranca como hilo daemon, no bloquea el loop principal, y actualiza `gateway_online` cada 5s.
2. Ante pérdida de gateway < 15s: alertas de desconexión suprimidas, log `NETWORK_STORM_SUPPRESSED` emitido.
3. Ante recuperación dentro de la ventana: log `NETWORK_STORM_ABSORBED elapsed=Xs` emitido, cero alertas falsas.
4. Ante pérdida > 15s con mineros inaccesibles: alertas propagadas normalmente.
5. Ante gateway habilitado pero inaccesible en arranque: el monitor arranca sin errores, `gateway_online=False` inicialmente.
6. `config.example.json` actualizado con las 5 nuevas claves documentadas.
7. `tests/test_gateway_heartbeat.py`: mínimo 12 tests cubriendo start/stop, pérdida detectada, recuperación, supresión, is_recently_lost, socket leak safety.
8. Suite completa ≥ 1064 + nuevos tests PASS, 0 regresiones.

---

## Puntos de Auditoría de Seguridad (del ACTION_PLAN_V5_1_HORIZON.md)

- ✅ Socket connect de 50ms nunca bloquea el GIL ni retrasará el bucle principal (hilo separado)
- ✅ Cierre de sockets con `socket.close()` explícito en `finally` para evitar leaks en Windows
- ✅ Gateway con puerto HTTP deshabilitado: fallback a puerto 53 (DNS) configurable
- ✅ IP y puerto configurables para entornos con topologías distintas

---

## Riesgos y Mitigaciones

| Riesgo | Mitigación |
|---|---|
| Gateway responde en puertos cerrados pero con RST (false positive online) | TCP connect exitoso = red funcional, aunque el servicio HTTP esté cerrado — correcto para nuestro propósito |
| Gateway con firewall que dropa sin RST (50ms timeout puede ser insuficiente) | Aumentar a 200ms como fallback configurable `gateway_connect_timeout_ms` |
| Supresión de alertas reales (gateway online pero mineros caídos) | La supresión solo aplica si `gateway_online = False`; si el gateway responde, las alertas se propagan normalmente |
