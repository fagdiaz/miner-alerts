# Tasks: Spec 067 — Gateway Heartbeat y Supresión de Tormentas de Red

**Status**: Ready  
**Baseline**: 1064 tests PASS  
**Objetivo**: Implementar supresión de tormentas de red local sin regresiones y sin modificar contratos de inspect.getsource(main).

---

## Tasks

### Fase A: Módulo de Latido de Gateway

- [x] **T001**: Crear `app/network/gateway_heartbeat.py` con `GatewayHeartbeatWorker`:
  - Hilo daemon con `threading.Event` para parada limpia
  - `try/finally: sock.close()` en todas las rutas
  - Fallback a `fallback_port=53` si el puerto primario rechaza/timeout
  - Atributos `gateway_online`, `last_gateway_loss_ts`, `consecutive_failures`
  - `is_recently_lost(within_seconds=15.0) -> bool`
  - `try...except Exception` de nivel superior en `_run()` con log estructurado

- [x] **T002**: Actualizar `app/network/__init__.py` para re-exportar `GatewayHeartbeatWorker`.

### Fase B: Integración Aditiva en `miner_monitor.py`

- [x] **T003**: Instanciar `GatewayHeartbeatWorker` en `main()` condicionalmente (`gateway_heartbeat_enabled`), después del bloque del `CoreSupervisoryEngine` y antes del `while True:`.
  - Log estructurado `GATEWAY_HEARTBEAT started host=X port=Y`
  - Si `_gateway_heartbeat` arranca con excepción: log `[WARN]` y continuar sin heartbeat (degradación suave)
  - En el `finally` del loop: llamar `_gateway_heartbeat.stop()` si no es None

- [x] **T004**: Evaluar `_network_storm_active` al inicio de cada tick (después de medir `now_ts`), usando `is_recently_lost()`.
  - Solo para supresión de alertas de desconexión (`STATE_OFFLINE`/`STATE_LOW` caused by offline)
  - No suprimir: alertas de temperatura, governance, hashboard count, auto-reboot
  - Log `[NETWORK_STORM_SUPPRESSED]` con `gateway_lost_since={elapsed:.1f}s` cuando se suprime
  - Log `[NETWORK_STORM_ABSORBED]` cuando el gateway se recupera dentro de la ventana (single log)

### Fase C: Configuración y Tests

- [x] **T005**: Agregar claves a `app/config.example.json`:
  ```json
  "gateway_heartbeat_enabled": false,
  "gateway_host": "192.168.100.1",
  "gateway_port": 80,
  "gateway_fallback_port": 53,
  "gateway_heartbeat_interval_s": 5,
  "network_storm_suppression_seconds": 15
  ```
  Comentar que `gateway_heartbeat_enabled: false` por defecto (opt-in).

- [x] **T006**: Crear `tests/test_gateway_heartbeat.py` con 27 tests:
  - `TestGatewayHeartbeatInit` (5 tests): init, defaults, clamp
  - `TestIsRecentlyLost` (5 tests): todos los casos de la ventana de supresión
  - `TestGatewayLossElapsed` (3 tests): elapsed cuando offline, online, never lost
  - `TestTryConnect` (4 tests): socket close on success/error
  - `TestProbe` (4 tests): fallback port logic
  - `TestWorkerStartStop` (6 tests): ciclo de vida, idempotencia, excepciones

- [x] **T007**: Verificar sintaxis: `py_compile app/miner_monitor.py app/network/gateway_heartbeat.py`

- [x] **T008**: Ejecutar suite completa: **1072 tests PASS, 0 regresiones**.
  - Confirmar `test_auto_reboot_signal_gate`, `test_hashboard_auto_reboot`, `test_reboot_safety`, `test_vnish_hashboard_detection` todos PASS (37 tests invariantes). ✅

### Fase D: Documentación y Cierre

- [x] **T009**: Registrar comandos y evidencia en `specs/067-gateway-heartbeat/evidence.md`.
- [ ] **T010**: Agregar entrada newest-first a `docs/audit/DEVELOPMENT_LOG.md`.
- [ ] **T011**: Actualizar `docs/speckit/ROADMAP.md` con Iniciativa 18 para Spec 067.
- [ ] **T012**: Actualizar `prompt.txt` con handoff para Spec 068 o siguiente prioritaria.
