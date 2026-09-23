# Evidence: Spec 078 — Supresión de Ruido Eléctrico en Elevadores, Watchdog Anti-Autotune Stall y Gobernanza Térmica Solar

## 1. Quality & Regression Verification

### 1.1 Python Syntax Compilation
Command:
```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py
& ".\.venv\Scripts\python.exe" -m py_compile tools\miner_diagnostics.py
```
Output:
- `app\miner_monitor.py`: Exit code 0 (PASS)
- `tools\miner_diagnostics.py`: Exit code 0 (PASS)

### 1.2 Full Unit & Regression Suite Execution
Command:
```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
```
Output:
```
Ran 1322 tests in 40.182s

OK
```
Total: **1322 tests PASS, 0 failures, 0 errors, 0 regressions.**

---

## 2. Test Coverage Breakdown for Spec 078 Modules

1. **`tests/test_elevator_budget.py` (38 tests PASS)**:
   - `test_incident_quiet_window_lifecycle`: Verifica `record_group_incident`, expiración tras 300s y `clear_group_incident`.
   - `test_can_facility_transition_miner_incident_quiet_blocks`: Verifica bloqueo con `reason="INCIDENT_QUIET_WINDOW"`.
   - `test_facility_transition_permission_six_gates`: Verifica las 6 compuertas determinísticas (cooldown, settle, grupo, acometida, quiet post-incidente, hardware ceiling).
   - `test_solar_thermal_envelope_during_day`: Verifica ventana 11:00-17:00 hs con techo fijado a 2500W.
   - `test_solar_thermal_envelope_critical_overheating`: Verifica corte preventivo con chip $\ge 82.0^\circ\text{C}$.
   - `test_solar_thermal_envelope_outside_window`: Verifica retorno a modo valle normal fuera del horario 11:00-17:00 hs.
   - `test_get_miner_max_hardware_preset_default_and_custom`: Verifica precedencia y límite por minero.
   - `test_choose_optimal_pair_presets_respects_hardware_limits`: Verifica que el par nunca promueve un equipo por encima de su techo físico.

2. **`tests/test_preset_balancer.py` (26 tests PASS)**:
   - `test_balancer_respects_hardware_limit_ceiling`: Emite `ACTION_HOLD_HARDWARE_LIMIT` si el minero ya está en su techo de hardware.
   - `test_balancer_respects_incident_quiet_window`: Emite `ACTION_HOLD_INCIDENT_QUIET` si el elevador sufrió un incidente reciente ($< 300\text{s}$).

3. **`tests/test_vnish_client.py` (22 tests PASS)**:
   - `test_read_miner_status_summary`: Verifica extracción de `miner_state`, `miner_state_time`, `hr_realtime_ths`, y degradación con timeout / HTTP error.

4. **`tests/test_autotune_watchdog.py` (9 tests PASS)**:
   - `test_normal_autotune_under_timeout_is_not_stalled`: Autotuning $< 600\text{s}$ no genera alarma.
   - `test_autotune_with_active_hashrate_is_not_stalled`: Autotuning con hashrate nominal $> 20\text{ TH/s}$ no dispara rescate.
   - `test_autotune_stalled_triggers_rescue_action`: Autotuning $> 600\text{s}$ con hashrate $< 20\text{ TH/s}$ gatilla `ACTION_AUTOTUNE_STALLED`.
   - `test_rescue_preset_selection`: Desescala 1 escalón (2700W -> 2500W, 2500W -> 2300W) respetando el techo físico.
   - `test_watchdog_state_record_and_locks`: Activa cerrojo de preset y persiste en diccionario.
   - `test_watchdog_state_serialization_roundtrip`: Serializa y deserializa `from_dict`/`to_dict` con fidelidad 100%.

---

## 3. Configuration & Runtime Safety Verification

- `app/config.example.json`:
  - Documentado `max_hardware_preset` en cada minero.
  - Documentados parámetros de Spec 078: `autotune_timeout_s: 600.0`, `autotune_min_active_hashrate_ths: 20.0`, `incident_quiet_window_s: 300.0`, `solar_thermal_start: "11:00"`, `solar_thermal_end: "17:00"`, `solar_thermal_max_preset: "2500W"`, `solar_thermal_critical_temp_c: 82.0`.
- `app/config.json`:
  - Minero 25 fijado con `"max_hardware_preset": "2500W"` y `"target_power_w": 2500.0`.
  - Mineros 23, 24, 26 configurados con `"max_hardware_preset": "2700W"`.
  - Parámetros de Spec 078 incorporados.
  - Validación JSON: PASS.
