# Evidencia Operativa - Spec 081: Watchdog de Reinicio de Minado Pendiente y Armonización Térmica

## 1. Evidencia Empírica de Causa Raíz en Producción (Minero 24)

- **Estado Previo a la Intervención**:
  * `/config/cgminer.conf`: `preset: "2700"`, `top_preset: "2700"`.
  * `/api/v1/perf-summary`: `current_preset: {'name': '2500', 'pretty': '2500 watt ~ 92 TH'}`.
  * `/api/v1/status`: `restart_required: True`.
  * Consumo real de cadenas: **2498 W** (C1=835W, C2=832W, C3=831W).
  * Frecuencia de chips: **481.2 - 483.2 MHz**.
  * Hashrate entregado: **92.42 TH/s**.
  * Fan Governor: **100% PWM** clavado incondicionalmente por `ACTION_RECOVERY_MAX_COOLING` (`2498W < 2580W`).
  * Uptime continuo sin restart: 32.7 horas.

## 2. Resolución Empírica Aplicada

1. **Ejecución de Reinicio Suave de Minado**:
   ```python
   from app.vnish.client import safe_restart_mining
   ok, err = safe_restart_mining('192.168.100.24', 'admin')
   ```
   - Respuesta: `ok: True, err: None`.
   - Duración del proceso: ~15-20 segundos. El sistema operativo Linux y la placa de control no se reiniciaron; solo se recargó el proceso cgminer.

2. **Telemetría Verificada Post-Reinicio**:
   - `GET /api/v1/status`: `restart_required: False`.
   - `GET /api/v1/perf-summary`: `current_preset: {'name': '2700', 'pretty': '2700 watt ~ 96 TH'}`.
   - Frecuencias de cadenas: escaladas de 482 MHz a **517.2 - 518.1 MHz**.
   - Consumo de cadenas: escalado de 2498W a **2699 W** (idéntico a Miners 23, 25, 26).
   - Hashrate: escalado a **97.66 TH/s** (en ascenso hacia 100 TH/s).
   - Temperaturas de chips: 51°C - 69°C (margen térmico seguro).
   - Fan Governor: `ACTION_RECOVERY_MAX_COOLING` desactivado de inmediato; transición a `HOLD_DWELL` y lazo cerrado de temperatura.

3. **Estado Global de la Flota a 2700W**:
   - S19JPRO-23: 99.73 TH/s | Cadenas: 2698 W | Fans: 92% | Temps: 60-78°C
   - S19JPRO-24: 97.12 TH/s | Cadenas: 2699 W | Fans: Dwell/Lazo cerrado | Temps: 51-69°C
   - S19JPRO-25: 100.17 TH/s | Cadenas: 2699 W | Fans: 92% | Temps: 60-79°C
   - S19JPRO-26: 97.98 TH/s | Cadenas: 2699 W | Fans: 92% | Temps: 59-77°C
   - **Total Flota**: **395.00 TH/s** (10,795 W de potencia en cadenas).

## 3. Verificación de Pruebas Unitarias y Regresión Global

- **Suite Unitaria Dedicada**:
  `tests/test_restart_required_watchdog.py`: 11 tests PASS (100%).
  * `test_restart_not_required`: PASS
  * `test_handled_by_degraded_auto_restart`: PASS
  * `test_thermal_pause_active`: PASS
  * `test_miner_warming_up`: PASS
  * `test_chip_temp_too_high`: PASS
  * `test_soak_window_active`: PASS
  * `test_cooldown_active`: PASS
  * `test_ready_for_preset_restart`: PASS
  * `test_governor_adapts_target_power_when_restart_required`: PASS
  * `test_serialize_spec_081_fields`: PASS
  * `test_get_overclock_settings_includes_restart_required`: PASS

- **Suite Completa de Regresión**:
  `pytest tests/ -q`:
  * 1440 passed, 75 subtests passed in 45.34s (100% PASS, 0 failures).

- **Sintaxis Python**:
  `py_compile app\miner_monitor.py app\vnish\client.py app\core\state_manager.py`: Código de salida 0.

