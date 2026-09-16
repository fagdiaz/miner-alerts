# Tasks: Spec 067 — Gateway Heartbeat y Supresión de Tormentas de Red

**Status**: Ready  
**Baseline**: 1064 tests PASS  
**Objetivo**: Implementar supresión de tormentas de red local sin regresiones y sin modificar contratos de inspect.getsource(main).

---

## Tasks

### Fase A: Módulo de Latido de Gateway

- [ ] **T001**: Crear `app/network/gateway_heartbeat.py` con `GatewayHeartbeatWorker`:
  - Hilo daemon con `threading.Event` para parada limpia
  - `try/finally: sock.close()` en todas las rutas
  - Fallback a `fallback_port=53` si el puerto primario rechaza/timeout
  - Atributos `gateway_online`, `last_gateway_loss_ts`, `consecutive_failures`
  - `is_recently_lost(within_seconds=15.0) -> bool`
  - `try...except Exception` de nivel superior en `_run()` con log estructurado

- [ ] **T002**: Actualizar `app/network/__init__.py` para re-exportar `GatewayHeartbeatWorker`.

### Fase B: Integración Aditiva en `miner_monitor.py`

- [ ] **T003**: Instanciar `GatewayHeartbeatWorker` en `main()` condicionalmente (`gateway_heartbeat_enabled`), después del bloque del `CoreSupervisoryEngine` y antes del `while True:`.
  - Log estructurado `GATEWAY_HEARTBEAT started host=X port=Y`
  - Si `_gateway_heartbeat` arranca con excepción: log `[WARN]` y continuar sin heartbeat (degradación suave)
  - En el `finally` del loop: llamar `_gateway_heartbeat.stop()` si no es None

- [ ] **T004**: Evaluar `_network_storm_active` al inicio de cada tick (después de medir `now_ts`), usando `is_recently_lost()`.
  - Solo para supresión de alertas de desconexión (`STATE_OFFLINE`/`STATE_LOW` caused by offline)
  - No suprimir: alertas de temperatura, governance, hashboard count, auto-reboot
  - Log `[NETWORK_STORM_SUPPRESSED]` con `gateway_lost_since={elapsed:.1f}s` cuando se suprime
  - Log `[NETWORK_STORM_ABSORBED]` cuando el gateway se recupera dentro de la ventana (single log)

### Fase C: Configuración y Tests

- [ ] **T005**: Agregar claves a `app/config.example.json`:
  ```json
  "gateway_heartbeat_enabled": false,
  "gateway_host": "192.168.100.1",
  "gateway_port": 80,
  "gateway_fallback_port": 53,
  "gateway_heartbeat_interval_s": 5,
  "network_storm_suppression_seconds": 15
  ```
  Comentar que `gateway_heartbeat_enabled: false` por defecto (opt-in).

- [ ] **T006**: Crear `tests/test_gateway_heartbeat.py` con ≥ 12 tests:
  - `test_worker_starts_and_stops_cleanly`
  - `test_gateway_online_when_connect_succeeds`
  - `test_gateway_offline_when_connect_fails`
  - `test_is_recently_lost_true_after_failure`
  - `test_is_recently_lost_false_after_recovery`
  - `test_is_recently_lost_false_when_never_lost`
  - `test_consecutive_failures_count`
  - `test_fallback_port_attempted_after_primary_fails`
  - `test_socket_closed_even_on_exception`
  - `test_worker_exception_does_not_propagate_to_caller`
  - `test_storm_suppression_window_expires`
  - `test_network_storm_integration_with_monitor_context`

- [ ] **T007**: Verificar sintaxis: `py_compile app/miner_monitor.py app/network/gateway_heartbeat.py`

- [ ] **T008**: Ejecutar suite completa: ≥ 1064 + nuevos tests PASS, 0 regresiones.
  - Confirmar `test_auto_reboot_signal_gate`, `test_hashboard_auto_reboot`, `test_reboot_safety`, `test_vnish_hashboard_detection` todos PASS (37 tests invariantes).

### Fase D: Documentación y Cierre

- [ ] **T009**: Registrar comandos y evidencia en `specs/067-gateway-heartbeat/evidence.md`.
- [ ] **T010**: Agregar entrada newest-first a `docs/audit/DEVELOPMENT_LOG.md`.
- [ ] **T011**: Actualizar `docs/speckit/ROADMAP.md` con Iniciativa 18 para Spec 067.
- [ ] **T012**: Actualizar `prompt.txt` con handoff para Spec 068 o siguiente prioritaria.
