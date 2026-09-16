# Implementation Plan: Spec 063 — Gobernador Térmico con Conciencia Estacional (Ambient-Aware Thermal PID) (GOV-02)

**Branch**: `codex/022-adaptive-acquisition` | **Date**: 2026-09-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/063-ambient-thermal-pid/spec.md`

---

## Summary

Implementar la adaptación estacional en el gobernador térmico de lazo cerrado mediante inferencia de temperatura ambiente a partir de los sensores de entrada ya sondeados en la telemetría Vnish:
- **Fase A (Extracción de Telemetría de Entrada & Modelo de Datos)**:
  * Extender `VnishTelemetry` en `app/vnish/telemetry.py` con `inlet_temp_c`.
  * En `normalize_vnish_stats()`, analizar claves de entrada de aire (`temp_in`, `temp_pcb_in`, `temp_inlet`) con filtro de validez $[-10, 60]^\circ\text{C}$.
  * Extender `MinerState` con `inlet_temp_c` y registrar la lectura en el ciclo de monitoreo.
- **Fase B (Dominio Puro: Resolución de Parámetros Estacionales & Guardarraíl Inviolable)**:
  * Extender `GovernorConfig` con umbrales de invierno/verano, pisos de PWM y aceleración estacional.
  * Implementar dataclass `SeasonalGovernorParams` y función pura `resolve_seasonal_parameters(ambient_temp_c, config)` en `app/governance/fan_governor.py`.
  * Enlazar `resolve_seasonal_parameters` en `compute_governor_step(..., ambient_temp_c=None)`.
  * Enforzar matemáticamente los 3 guardarraíles inviolables: techo máx target 82.0°C, piso mín 30% PWM, spike de emergencia a 83.5°C siempre activo hacia 100%.
- **Fase C (Integración en Monitor & Suite de Tests)**:
  * En `execute_governor_cycle()`, computar `ambient_temp_c` del grupo o flota y suministrarlo a `compute_governor_step()`.
  * Exponer opciones estacionales en `app/config.example.json`.
  * Desarrollar suite de pruebas unitarias y de estrés en `tests/test_fan_governor_seasonal.py`.
  * Validar 959+ tests sin regresión y servicio Windows activo.

---

## Technical Context

**Language/Version**: Python 3.12 (virtualenv en Windows 11)
**Modules**:
- `app/vnish/telemetry.py` (Parser de telemetría y campo `inlet_temp_c`).
- `app/governance/fan_governor.py` (Lógica de decisión pura y resolución estacional).
- `app/miner_monitor.py` (MinerState, agregación de $T_{\text{amb}}$ grupal y ciclo de gobernador).
- `tests/test_fan_governor_seasonal.py` (Batería de pruebas exhaustivas).
**Target Platform**: Windows 11 Pro / Servicio Windows `MinerAlerts`.

---

## Constitution Check

1. **Principio 1 (Monitoreo Continuo & Seguridad de Hardware)**: ✅ La adaptación estacional jamás debilita el Thermal Guard de emergencia a 83.5°C / 85.0°C ni reduce la ventilación por debajo del 30% seguro de hardware.
2. **Principio 2 (Zero Peticiones HTTP Adicionales)**: ✅ La temperatura ambiente se extrae exclusivamente de la telemetría ya solicitada cada 30s en `/api/v1/summary`, respetando la estricta cuota de red de la flota.
3. **Principio 3 (Zero Regresiones)**: ✅ Si no hay sensores de entrada o la función se desactiva, el gobernador opera 100% idéntico a la versión anterior (Spec 039/044).
