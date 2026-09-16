# Evidencia de Validación: Spec 062 — HW Error Tripwire & Rollback Automático de Overclock (GOV-01)

## 1. Validación de Sintaxis Python
```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py app\governance\preset_balancer.py app\governance\__init__.py app\core\state_manager.py tests\test_hw_error_tripwire.py
```
- **Resultado**: 100% OK (cero errores, compilación limpia).

## 2. Validación de Pruebas Unitarias e Integración (Spec 062)
```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests/test_hw_error_tripwire.py -v
```
- **Resultado**: **13/13 tests PASS** en 0.143s.
  * `test_tripwire_triggers_when_both_thresholds_exceeded`: Disparo correcto de `ACTION_STEP_DOWN_HW_ERRORS` desescalando de 2700W a 2500W cuando la tasa de error supera el 0.5% y el delta acumulado en 10m es >= 200 errores.
  * `test_tripwire_does_not_trigger_if_rate_below_threshold`: Supresión de disparo falso si la tasa de error es inferior a 0.5% a pesar de delta elevado.
  * `test_tripwire_does_not_trigger_if_delta_below_threshold`: Supresión de disparo falso si el delta es inferior a 200 a pesar de tasa porcentual elevada.
  * `test_tripwire_at_minimum_preset_emits_locked_min`: En el escalón mínimo (1600W), emite `ACTION_LOCKED_MIN` con `requires_write=False`.
  * `test_lockout_enforcement_forces_step_down_if_preset_exceeds_locked`: Si el firmware reporta un preset superior al candado durante las 48h, fuerza el retorno inmediato a `hw_error_locked_preset`.
  * `test_lockout_inhibits_step_up_during_lock`: Bloqueo estricto de cualquier intento de `ACTION_STEP_UP_OPTIMIZE` mientras el candado de 48h permanezca activo.
  * `test_step_up_resumes_after_lock_expiry`: Reanudación normal de la optimización ascendente una vez expirado el candado de 48h.
  * `test_extract_stability_metrics_calculates_10m_delta_and_rate`: Cálculo no volátil de errores y shares comparando muestra $T$ contra muestra $T - 10\text{m}$ en la base de datos SQLite `telemetry_samples`.
  * `test_extract_stability_metrics_handles_counter_reset_post_reboot`: Manejo seguro y sin deltas negativos ante reseteos de contadores de hardware por reinicio de ASIC.
  * `test_card_width_strict_limit_32_columns`: Tarjeta vertical de notificación Telegram `render_hw_error_tripwire_card()` estrictamente adaptada a pantallas móviles con longitud máxima `<= 32` caracteres por línea.
  * `test_state_serialization_roundtrip`: Persistencia no volátil en `state.json` y roundtrip de `hw_error_lock_until_ts` y `hw_error_locked_preset` en `load_state`, `_build_state_payload` y `_serialise_miner_state`.
  * `test_auto_reboot_interlocks_not_blocked_by_hw_error_lock`: El candado del tripwire nunca bloquea los reinicios automáticos de salud operativa (`STATE_LOW` / `STATE_HASHBOARD`).
  * `test_execute_balancer_cycle_tripwire_and_telegram_dispatch`: Ciclo completo de balanceador disparando tripwire, activando candado de 48h y despachando tarjeta de notificación a Telegram.

## 3. Validación Global de Regresiones en el Proyecto
```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
```
- **Resultado**: **959 tests PASS** en 15.671s (0 fallos, 0 errores, 0 regresiones sobre la línea base de 946 tests).

## 4. Estado del Servicio en Producción (Windows Service)
```powershell
Get-Service -Name "MinerAlerts"
```
- **Resultado**: `Running` (`Miner Alerts Monitor`). Operación continua y sin perturbaciones.

## 5. Matriz de Entregables por Fase
- [x] **Fase A: Dominio Puro de Balancer y Regla de Tripwire**:
  * Extensiones en `StabilityMetrics` (`hw_errors_delta_10m`, `hw_error_rate_pct`, `hw_error_lock_until_ts`, `hw_error_locked_preset`).
  * Configuración en `BalancerConfig` (`hw_error_rate_threshold_pct: 0.5`, `hw_error_delta_threshold: 200`, `hw_error_lock_hours: 48.0`).
  * Regla de disparo `ACTION_STEP_DOWN_HW_ERRORS`, forzado defensivo post-reboot e inhibición de step-up en `evaluate_balancer_step()`.
  * Tarjeta vertical Mobile-First Telegram `render_hw_error_tripwire_card()`.
- [x] **Fase B: Persistencia de Candado y Extracción de Métricas SQLite**:
  * Extensión de `MinerState` y serialización atómica en `app/miner_monitor.py` y `app/core/state_manager.py`.
  * Extracción persistente en `extract_miner_stability_metrics()` consultando `telemetry_samples` de SQLite para muestra actual vs muestra de hace 10 minutos.
- [x] **Fase C: Interlock Anti-Cascada y Batería de Pruebas**:
  * Integración en `execute_balancer_cycle()` activando el candado de 48h y despachando alertas Telegram.
  * Interlock anti-cascada en `refresh_vnish_overclock_settings` y en el ciclo de monitoreo defensivo tras reinicio de minero (`reboot_reason`).
  * Suite de pruebas `tests/test_hw_error_tripwire.py` (13 tests PASS).
  * Validación global de 959 tests y servicio Windows en estado `Running`.
