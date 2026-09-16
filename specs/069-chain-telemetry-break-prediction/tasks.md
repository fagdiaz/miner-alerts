# Tasks — Spec 069: Telemetría Profunda por Cadena & Diagnóstico Predictivo Chain Break (PROP-008)

**ID**: 069  
**Rama**: `codex/022-adaptive-acquisition`  
**Estado**: Pendiente  

---

### Fase A: Base de Datos & Consultas de Series Temporales

- [ ] **T001**: Añadir índice compuesto `ix_chain_telemetry_miner_chain_time` en `app/core/event_store.py` (`miner_key, chain_id, observed_ts DESC`).
- [ ] **T002**: Implementar helper de consulta en solo lectura `fetch_chain_samples_window(miner_key, chain_id, since_ts)` con reintentos defensivos ante `SQLITE_BUSY_SNAPSHOT`.

### Fase B: Motor de Diagnóstico Predictivo

- [ ] **T003**: Extender `app/governance/chain_health.py` con `PredictiveChainEngine` y dataclass `PredictiveChainRisk`:
  - Condición de significancia estadística mínima: $N \ge 24$ muestras requeridas en la ventana de 12 horas.
  - Evaluación de ventana deslizante de 12h: persistencia $\ge 90\%$ de fallos I2C si $N \ge 24$.
  - Extracción y tracking de ubicaciones físicas de sensores con falla (`loc`).
  - Detección de déficit de placa $\ge 10\%$ sostenido por $\ge 3\text{h}$ con placas hermanas nominales.
- [ ] **T004**: Implementar discriminador de grupo eléctrico (`correlate_electrical_group`) para aislar perturbaciones en `elevator_1` y `elevator_2` con fallback seguro ante configuraciones sin grupo.
- [ ] **T005**: Crear formateador de tarjeta Telegram para alertas preventivas de riesgo de hardware ($\le 32$ columnas).

### Fase C: Integración en Monitor & Configuración

- [ ] **T006**: Integrar ciclo de evaluación horaria en `app/miner_monitor.py`:
  - Deduplicación por cadena con enfriamiento de 24 horas (`state.chain_warnings_ts`).
  - Despacho de alerta Telegram solo si no está en cooldown.
  - Preservación estricta de invariantes de `inspect.getsource(main)`.
- [ ] **T007**: Actualizar `app/config.example.json` con claves de configuración predictiva (`chain_sensor_error_min_samples: 24`).

### Fase D: Pruebas Unitarias y Validación

- [ ] **T008**: Crear `tests/test_chain_predictive_rules.py` con $\ge 14$ pruebas:
  - `test_persistent_i2c_sensor_error_triggers_risk`
  - `test_insufficient_samples_ignores_evaluation`
  - `test_transient_i2c_sensor_error_ignored`
  - `test_same_sensor_loc_tracked_consistently`
  - `test_board_hashrate_deficit_triggers_risk`
  - `test_electrical_group_disturbance_suppresses_board_alert`
  - `test_missing_electrical_group_safe_fallback`
  - `test_cooldown_prevents_duplicate_telegram_alerts`
- [ ] **T009**: Crear benchmark de consulta SQLite `tests/test_chain_query_performance.py` certificando tiempo $< 15\text{ ms}$.
- [ ] **T010**: Chequeo de sintaxis `py_compile app/governance/chain_health.py app/core/event_store.py app/miner_monitor.py`.
- [ ] **T011**: Ejecución de suite completa de regresión: $\ge 1110$ tests PASS, 0 fallos, 0 regresiones.

### Fase E: Documentación y Cierre

- [ ] **T012**: Registrar comandos y evidencia en `specs/069-chain-telemetry-break-prediction/evidence.md`.
- [ ] **T013**: Agregar entrada en `docs/audit/DEVELOPMENT_LOG.md`.
- [ ] **T014**: Actualizar `docs/speckit/ROADMAP.md` y `prompt.txt`.
