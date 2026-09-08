# Evidencia de Validación: Spec 040 - Dynamic Power & Preset Balancer

## Estado Actual
- **Fase**: FASES 1, 2, 3, 4 Y 5 COMPLETADAS Y CERTIFICADAS (100% IMPLEMENTADO).
- **Fecha**: 2026-09-08
- **Proceso en Producción Actual**: PID 101508 activo y saludable en V3.1.0 (>15 ticks continuos, 0 errores, ~59MB RAM).
- **Branch**: `codex/022-adaptive-acquisition`

## Evidencia Operativa en Hardware Real
- Caídas observadas en log de minero 24:
  `[PROFILE_CHANGE_ALERT] miner=24 status=DOWNCLOCKED freq=440.532`
- Reinicios simultáneos históricos en elevador eléctrico compartidos entre mineros (ej: mineros 25 y 26 a las `1788829542.097075` en `operational_events`).
- Comprobación de que la inestabilidad en elevadores sensibles y picos térmicos causan downclockings y reinicios frecuentes, justificando el desescalado preventivo hacia presets estables para maximizar el hashrate efectivo ($H_{\text{eff}}$).

## Evidencia de Tests Unitarios y de Integración (Fases 1 a 5)
1. **Fase 1 (Cliente REST Vnish Presets)**:
   - `tests/test_vnish_client.py`: 15/15 tests PASS. Cubre lectura de presets, posteo atómico de presets y ciclo transaccional seguro con garantía `finally` para bloqueo de API.
2. **Fase 2 y 3 (Motor Matemático Determinista)**:
   - `tests/test_preset_balancer.py`: 13/13 tests PASS en 0.002s:
     * `test_compute_effective_hashrate`: Demuestra matemáticamente que operar a 93 TH/s (2500W) sin reinicios genera más hashrate neto (93.0 TH/s) que forzar a 98 TH/s (2700W) con 3 reinicios diarios (89.96 TH/s netos).
     * `test_step_down_on_frequent_restarts`: $\ge 2$ reinicios en 24h fuerza desescalado preventivo.
     * `test_group_cascade_step_down`: 2 mineros en el mismo elevador reiniciándose en ventana de 30m activan desescalado grupal para proteger la fase eléctrica.
     * `test_step_up_after_soak_stability`: 80h de uptime, 0 reinicios en 72h y margen $\ge 4^\circ\text{C}$ promueven optimización ascendente de preset.
     * `test_extract_miner_stability_metrics_against_live_db`: Consulta SQLite en modo `?mode=ro` ejecutada en < 20ms sin bloquear el hilo de monitoreo.
3. **Fase 4 y 5 (Integración en Monitor, Persistencia y Comandos Telegram)**:
   - `tests/test_preset_balancer_integration.py`: 9/9 tests PASS en 1.07s:
     * `test_command_whitelist_contains_balancer`: Verificación de `balancer`, `bal`, `power`, `governor`, `gov` en `CMD_WHITELIST`.
     * `test_state_serialization_preserves_balancer_fields`: Verificación de carga y guardado atómico de `balancer_preset`, `balancer_last_change_ts`, `balancer_last_action`, `balancer_last_reason`.
     * `test_execute_balancer_cycle_dry_run_simulation`: Validación de simulaciones seguras sin llamadas REST a hardware cuando `dry_run: true`.
     * `test_execute_balancer_cycle_active_write`: Validación de llamada a `safe_set_miner_preset` y actualización de estado en hardware activo.
     * `test_execute_balancer_cycle_interval_guard`: Respeto de `preset_balancer_interval_seconds` (1800s) para evitar sobrecarga de consultas.
     * `test_slow_miner_does_not_block_beyond_fleet_timeout`: ThreadPoolExecutor garantiza que mineros lentos/caídos se abandonan a los 5s de timeout de flota sin demorar el tick de 30s.
     * `test_state_lock_concurrency_no_deadlock`: Concurrencia de 5 hilos bajo `state_lock` sin excepciones ni carreras.
     * `test_help_index_includes_balancer_and_governor`: Ayuda `/help` indexa correctamente `/balancer` y `/gov`.
4. **Suite Global de Regresión Completa**:
   - `& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"`: **575/575 tests PASS** en 10.08s (0 fallos, 0 errores, 0 regresiones).
