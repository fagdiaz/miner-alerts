# Tasks: Spec 075 — Recuperación Suave de Hasheo, Headroom Chilling y Blindaje Anticolapso de Fuentes APW12

- [x] T001: Implementar `app/governance/safe_recovery.py` con máquina de estados funcional pura (`SafeRecoveryState`, `RecoveryDecision`, `evaluate_safe_recovery`, ventana pasiva de 120s, pre-clamp a 1800W, e inhibición defensiva ante `stock_firmware_fallback` y `sensor_fault`).
- [x] T002: Incorporar soporte para `boost_cooling` (Headroom Chilling) y calibración de emergencia a 83.0°C en `app/governance/fan_governor.py`.
- [x] T003: Integrar acoplamiento Balancer ↔ Fan Governor en `app/governance/preset_balancer.py` para solicitar enfriamiento proactivo (`boost_cooling_requested`) ante bloqueo térmico en 2500W.
- [x] T004: Conectar la orquestación de recuperación suave (pre-clamp + settle window + inhibición ante `CHAIN_FAULT` / `stock_firmware_fallback`) en el flujo de recuperación de dos niveles en `app/miner_monitor.py` y `app/core/reboot_safety.py`.
- [x] T005: Desarrollar suite completa de pruebas unitarias en `tests/test_safe_recovery.py`, `tests/test_fan_governor.py`, `tests/test_preset_balancer.py` y `tests/test_reboot_safety.py` cubriendo US-01 a US-05 y el incidente de Minero 24.
- [x] T006: Ejecutar suite de regresión completa y validar que se alcancen 1236 tests PASS sin regresiones (0 fallos).
- [x] T007: Ejecutar auditoría exhaustiva de concurrencia, jerarquía de cerrojos (`state_lock`, `_SAVE_STATE_LOCK`, `EventStore._lock`) y desacoplamiento de hilos daemon (`AutoRestart_{name}`).
- [x] T008: Validación, certificación en producción y reinicio del servicio Windows `MinerAlerts`.
