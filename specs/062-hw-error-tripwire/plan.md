# Implementation Plan: Spec 062 — HW Error Tripwire & Rollback Automático de Overclock (GOV-01)

**Branch**: `codex/022-adaptive-acquisition` | **Date**: 2026-09-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/062-hw-error-tripwire/spec.md`

---

## Summary

Implementar el mecanismo de protección de silicio mediante un tripwire que monitorea el incremento y la tasa de Hardware Errors en ventanas de 10 minutos consultando `EventStore`:
- **Fase A (Métricas de Dominio Puro & Regla de Tripwire)**:
  * Extender `StabilityMetrics` con `hw_errors_delta_10m`, `hw_error_rate_pct`, `hw_error_lock_until_ts` y `hw_error_locked_preset`.
  * Extender `BalancerConfig` con umbrales `hw_error_rate_threshold_pct = 0.5`, `hw_error_delta_threshold = 200` y `hw_error_lock_hours = 48.0`.
  * Incorporar la regla de disparo `ACTION_STEP_DOWN_HW_ERRORS` e inhibición de `ACTION_STEP_UP_OPTIMIZE` en `evaluate_balancer_step()`.
  * Implementar tarjeta móvil de notificación `render_hw_error_tripwire_card()`.
- **Fase B (Persistencia Atómica & Extracción de Métricas SQLite)**:
  * Extender `MinerState` con `hw_error_lock_until_ts` y `hw_error_locked_preset`.
  * Actualizar `load_state`, `_build_state_payload` y `_serialise_miner_state` en `StateManager`.
  * Extender `extract_miner_stability_metrics()` para consultar sample $T$ y sample $T - 10\text{m}$ en `telemetry_samples`.
- **Fase C (Interlocking Anti-Cascada en Monitor & Suite de Tests)**:
  * Conectar el ajuste de candado en `execute_periodic_balancer()` y la restauración defensiva de preset post-reboot en `miner_monitor.py`.
  * Desarrollar suite de pruebas exhaustiva en `tests/test_hw_error_tripwire.py`.
  * Validar compilación, 946+ tests base sin regresión y servicio en ejecución.

---

## Technical Context

**Language/Version**: Python 3.12 (virtualenv en Windows 11)
**Modules**:
- `app/governance/preset_balancer.py` (Métricas, decisión pura, renderizado de tarjeta).
- `app/core/state_manager.py` (Serialización en StateManager).
- `app/miner_monitor.py` (MinerState, load_state, payload builder, anti-cascade post-reboot).
- `tests/test_hw_error_tripwire.py` (Batería de pruebas unitarias y de integración).
**Database**: SQLite (`telemetry_samples` en `data/miner_alerts.db`).
**Target Platform**: Windows 11 Pro / Servicio Windows `MinerAlerts`.

---

## Constitution Check

*GATE: Must pass before implementation.*

1. **Principio 1 (Monitoreo Continuo & Seguridad)**: ✅ El tripwire nunca bloquea los reinicios automáticos de seguridad por `STATE_LOW` o `STATE_HASHBOARD`. Sólo regula la desescalada de potencia del balanceador.
2. **Principio 2 (Single Source of Truth para Configuración)**: ✅ Los umbrales tienen valores por defecto seguros y pueden configurarse opcionalmente en `app/config.example.json` sin alterar archivos locales.
3. **Principio 3 (Persistencia Atómica & Anti-Deadlock)**: ✅ Los nuevos campos de estado (`hw_error_lock_until_ts`, `hw_error_locked_preset`) se leen y escriben respetando la jerarquía L1 (`state_lock`) y L2 (`_SAVE_STATE_LOCK`) establecida en Spec 060.
4. **Principio 4 (Zero Regresiones)**: ✅ Ninguna de las 946 pruebas existentes sufrirá cambios de comportamiento indeseados; las suites de balancer y governance se preservan al 100%.
