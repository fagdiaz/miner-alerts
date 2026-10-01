# Implementation Plan - Spec 081: Watchdog de Reinicio de Minado Pendiente y Armonización Térmica (PROP-017)

## 1. Arquitectura y Diseño Técnico

### 1.1 Modelo de Datos y Atributos de Estado (`MinerState`)
En `app/miner_monitor.py` (y serialización en `app/core/state_manager.py` si aplica):
- `vnish_restart_required: bool = False`
- `vnish_restart_detected_ts: Optional[float] = None`

### 1.2 Lógica Pura: `evaluate_preset_restart_candidate`
Función desacoplada y determinista para evaluar si un minero sano con `restart_required` califica para reinicio suave:
```python
def evaluate_preset_restart_candidate(
    now_ts: float,
    vnish_restart_required: bool,
    is_hash_degraded: bool,
    is_warming_up: bool,
    max_chip_temp_c: Optional[float],
    detected_ts: Optional[float],
    last_restart_ts: Optional[float],
    soak_window_seconds: float = 300.0,
    cooldown_seconds: float = 180.0,
    max_safe_temp_c: float = 80.0,
    thermal_pause_active: bool = False,
) -> Tuple[bool, str]:
    if not vnish_restart_required:
        return False, "restart_not_required"
    if is_hash_degraded:
        return False, "handled_by_degraded_auto_restart"
    if thermal_pause_active:
        return False, "thermal_pause_active"
    if is_warming_up:
        return False, "warming_up"
    if max_chip_temp_c is not None and max_chip_temp_c >= max_safe_temp_c:
        return False, f"chip_temp_too_high_{max_chip_temp_c:.1f}C"
    if detected_ts is not None and (now_ts - detected_ts) < soak_window_seconds:
        return False, f"soak_window_active_{soak_window_seconds - (now_ts - detected_ts):.0f}s"
    if last_restart_ts is not None and (now_ts - last_restart_ts) < cooldown_seconds:
        return False, f"cooldown_active_{cooldown_seconds - (now_ts - last_restart_ts):.0f}s"
    return True, "ready_for_preset_restart"
```

### 1.3 Armonización de Fan Governor
En `execute_governor_cycle`:
```python
gov_target_pwr = None if getattr(state, "silent_mode_active", False) else target_pwr
if getattr(state, "vnish_restart_required", False) and gov_curr_pwr is not None and gov_curr_pwr >= 500.0:
    gov_target_pwr = gov_curr_pwr
```

### 1.4 Integración en Telemetría y Watchdog
- En `_async_collect_chain_telemetry` (o ciclo de status de VNish):
  - Consultar `get_miner_status` / parsear `restart_required`.
  - Actualizar `state.vnish_restart_required` y timestamp inicial `detected_ts`.
  - Evaluar `evaluate_preset_restart_candidate`.
  - Si califica: invocar `safe_restart_mining`, registrar `preset_restart_applied` y emitir Telegram.

---

## 2. Plan de Validación y QA

1. **Pruebas Unitarias (`tests/test_restart_required_watchdog.py`)**:
   - `test_candidate_evaluation_requires_flag`: si `restart_required=False` -> False.
   - `test_candidate_evaluation_blocked_when_degraded`: si `is_hash_degraded=True` -> False.
   - `test_candidate_evaluation_soak_window`: bloqueo si `elapsed < soak_window`.
   - `test_candidate_evaluation_thermal_guard`: bloqueo si `temp >= 80.0°C`.
   - `test_candidate_evaluation_success`: calificación positiva ante condiciones óptimas.
   - `test_fan_governor_effective_target_adaptation`: validación de que el target se adapta a la potencia consumida.
2. **Regresión Global**:
   - Ejecutar `pytest tests/ -q` garantizando 100% PASS sobre la suite completa.
3. **Preflight QA (`speckit-qa`)**:
   - Validación de sintaxis, secretos y consistencia.
