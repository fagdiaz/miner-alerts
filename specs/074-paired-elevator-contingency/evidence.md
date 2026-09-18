# Evidence: Spec 074 - Paired Elevator Contingency & Inrush Dampener

## 1. Baseline Verification
- Previous Test Suite: 1204 tests PASS (33.8s runtime).
- Production Service: `MinerAlerts` in `RUNNING` status throughout research, lab development, and test suite execution.
- Fleet Status: 4/4 online (~401 TH/s total), 12/12 hashboards active, uninterrupted hashing since 02:41 hs.

## 2. Empirical Incidents Recorded in SQLite (`data/miner_alerts.db`)
- `2026-09-17 00:04:03`: S19JPRO-25 cascade 960s after S19JPRO-26 (elevator_2).
- `2026-09-17 00:26:03`: S19JPRO-23 cascade 780s after S19JPRO-24 (elevator_1).
- `2026-09-17 02:34:03`: S19JPRO-25 cascade 750s after S19JPRO-26 (elevator_2).
- Characteristic: Consistent 750s-960s secondary trip after initial reboot in each 2-miner electrical elevator group.

## 3. Laboratory Test Results (Offline Validation)
- Dedicated Test Suite: `tests/test_paired_elevator_contingency.py`
  - H1 Tests (Name matching & canonical resolution): 3 tests PASS.
  - H2 Tests (Vnish payload top_preset clamping): 2 tests PASS.
  - H3 Tests (Paired inrush dampening & 300s soak restoration): 4 tests PASS.
  - H4 Tests (Fan governor thermal warmup floor & emergency override): 4 tests PASS.
  - Serialization & Backward Compatibility: 2 tests PASS.
  - Total: 15 / 15 tests PASS in 0.002s.

- Full Project Regression Suite:
  - Command: `python -m unittest discover -s tests -p "test_*.py"`
  - Total tests executed: 1219 tests.
  - Result: 1219 PASS, 0 FAIL, 0 ERROR (33.10s runtime).
  - Regressions detected: 0.

## 4. Formal Architectural & Concurrency Audit (Claude Sonnet 4.6 Thinking)
- **Veredicto Formal**: APROBADO con 2 blindajes preventivos implementados.
  - **Punto 1 (Concurrencia llamadas REST en loop principal)**: Dictamen: Aceptable para deploy. Bloqueo acotado (máximo 5.0s en timeout doble de 2.5s), modelo monotónico de sleep que absorbe desviaciones sin acumulación de deuda temporal, y baja frecuencia del evento `unexpected_restart`.
  - **Punto 2 (Semántica de Locks)**: Dictamen: Resuelto. Mutaciones de `states[sk].balancer_preset` y lecturas de `_grp_presets` blindadas estrictamente dentro de `with state_lock:` tanto en `unexpected_restart` como en `soak_tick`. Las llamadas REST externas quedan fuera del lock evitando cualquier contención o deadlock con el hilo de Telegram.
  - **Punto 3 (Serialización y Consistencia)**: Dictamen: Resuelto. Mutaciones de `_ELEVATOR_CONTINGENCY_STATES` envueltas bajo `state_lock` y serialización de estado en `_build_state_payload` protegida con copia atómica vía `list(cont_states.items())`.
  - **Punto 4 (Plan de Despliegue)**: Veredicto final: **APROBADO**. Código 100% certificado y listo para despliegue.

## 5. Producción Desplegada & Verificación en Vivo (2026-09-17 12:54 hs)
- **Comando Ejecutado**: `Restart-Service -Name MinerAlerts -Force` (precedido por lease de mantenimiento en watchdog).
- **Proceso Monitor**: PID 12888 (PPID 39580), mutex `Global\MinerAlertsMonitor_fagdiaz` adquirido exitosamente.
- **Reconstitución de Estado**:
  - `[INTERVENTIONS] Reconstituted intervention governance: master=True`
  - `[CONTINGENCY] Reconstituted elevator contingency: ['elevator_1', 'elevator_2']`
  - `data/monitor_heartbeat.json`: `tick_sequence=3`, `schema_version=1`, `queue_depth=0`.
  - `app/state.json`: Serialización de `elevator_contingency` confirmada con campos `inrush_dampener_*`.
- **Telemetría y Gobernanza en Vivo**:
  - Telemetría de cadena (12/12 cadenas) recolectada e insertada en SQLite cada tick.
  - Fan governor, Adaptive Acquisition (2 workers), watchdog IPC (`\\.\pipe\MinerAlertsWatchdog`) operando al 100% sin advertencias ni errores.
