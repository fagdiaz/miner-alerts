# Implementation Plan - Spec 055: Auto-Reboot ante Falla de Placa y Recuperación Automática de Hashboard

## User Review Required

> [!IMPORTANT]
> Esta spec introduce la capacidad de auto-recuperar mineros que entran en `STATE_HASHBOARD` (falla de placas 0/3 con hashrate 0.0 TH/s como la ocurrida en el Minero 23). Todos los interlocks constitucionales de seguridad (Guardián de inicio 600s, Cooldown 1800s, Ventana diaria max 3 reinicios, Guardián térmico 85°C y Guardián de flota) se aplican de manera idéntica y sin excepciones.

- [x] Auto-reinicio ante falla total de placas (`active_boards == 0` o `rate_ths == 0.0` durante 10 minutos).
- [x] Falla parcial (`0 < active_boards < expected_boards`) deshabilitada por defecto para evitar ciclos de reinicio en placas con desgaste físico permanente.

---

## Proposed Changes

### Componente 1: Estado y Modelos de Datos (`app/miner_monitor.py` / `MinerState`)
- Agregar campo `hashboard_since_ts: Optional[float] = None` a `MinerState`.
- En el ciclo de actualización de estado:
  - Cuando `new_state == STATE_HASHBOARD`:
    - Si `state.hashboard_since_ts is None`, registrar `state.hashboard_since_ts = now_ts`.
  - Cuando `new_state == STATE_OK`:
    - Resetear `state.hashboard_since_ts = None`.
- Actualizar serialización/deserialización en `to_dict` y `from_dict`.

### Componente 2: Puerta de Evaluación de Auto-Reboot (`app/miner_monitor.py`)
- Modificar `auto_reboot_signal_allows_evaluation`:
  ```python
  def auto_reboot_signal_allows_evaluation(
      new_state: str,
      low_since_ts: Optional[float],
      hashboard_since_ts: Optional[float],
      signal_classification: str,
      active_boards: Optional[int],
      expected_boards: int,
      allow_partial_hashboard: bool = False,
  ) -> bool:
  ```
  - Permitir evaluación si `new_state == STATE_LOW and low_since_ts is not None`.
  - Permitir evaluación si `new_state == STATE_HASHBOARD and hashboard_since_ts is not None` y (`active_boards == 0` o `(allow_partial_hashboard and active_boards < expected_boards)`).
- Eliminar la clasificación forzada de `result="not_low"` cuando `new_state == STATE_HASHBOARD`. En su lugar, registrar `result="hashboard_not_sustained"` o `result="not_hashboard"`.

### Componente 3: Configuración y Valores por Defecto (`app/config.example.json` & `app/config.json`)
- Agregar claves con fallbacks seguros:
  - `"auto_reboot_hashboard_enabled": true`
  - `"auto_reboot_hashboard_sustained_seconds": 600`
  - `"auto_reboot_hashboard_partial_enabled": false`

### Componente 4: Suite de Pruebas Automatizadas (`tests/test_hashboard_auto_reboot.py`)
- Test de elegibilidad ante 0/3 placas.
- Test de respeto del temporizador sostenido (600s).
- Test de respeto del guardián de inicio (600s).
- Test de respeto del cooldown (1800s).
- Test de respeto de ventana diaria (3 reinicios máx).
- Test de bloqueo ante falla de flota.
- Test de verificación de no regresión en `test_auto_reboot_signal_gate.py`.

---

## Verification Plan

### Automated Tests
- Ejecutar `& ".\.venv\Scripts\python.exe" -m unittest discover -s tests`.
- Verificar que todos los tests pasen (840 existentes + nuevos tests).
- Validar compilación con `& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py`.

### Production Rollout & Gate
- Reinicio del servicio Windows `MinerAlerts`.
- Inspección de `logs/out.log` para certificar que ningún minero sufra acciones espurias.
