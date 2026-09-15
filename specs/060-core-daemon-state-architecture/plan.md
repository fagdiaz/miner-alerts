# Implementation Plan: Spec 060 — Monitor Core Daemon & State Manager Architecture (ST-01 / ST-02 - Milestone V5.0)

**Branch**: `codex/022-adaptive-acquisition` | **Date**: 2026-09-15 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/060-core-daemon-state-architecture/spec.md`  

---

## Summary

Desacoplar la infraestructura del bucle principal de supervisión y la persistencia de estado mediante dos fases coordinadas:
- **Fase A (Infraestructura Limpia)**:
  * `app/core/state_manager.py`: `StateManager` con persistencia atómica L1 (`state_lock`) $\rightarrow$ L2 (`_SAVE_STATE_LOCK`).
  * `app/core/context.py`: `MonitorContext` contenedor de dependencias (DI).
  * `app/core/engine.py`: `CoreSupervisoryEngine` con hooks y ciclo de 30s.
  * `app/core/__init__.py`: Exportaciones del core daemon.
- **Fase B (Conexión e Integración en main())**:
  * Instanciar `state_manager` y `monitor_ctx` en `main()` de `app/miner_monitor.py`.
  * Preservar estrictamente el orden y las declaraciones literales de `main()` requeridas por las suites de pruebas (`inspect.getsource(main)`).
  * Crear batería de tests unitarios en `tests/test_core_daemon.py`.
  * Certificar 935/935 tests globales PASS.

---

## Technical Context

**Language/Version**: Python 3.12 (virtualenv en Windows 11)  
**Concurrency Model**:
- Thread L1: `state_lock` (RLock en memoria)
- Thread L2: `_SAVE_STATE_LOCK` (I/O a disco `.tmp`, `.bak`, `os.replace`)
- Background Threads: `telegram_polling_worker`, `telegram_sender_worker`, pool de `BoundedAcquirer`  
**Testing**: `unittest` standard library (`tests/test_*.py`)  
**Target Platform**: Windows 11 Pro / Servicio Windows `MinerAlerts`  

---

## Constitution Check

*GATE: Must pass before implementation.*

1. **Principio 1 (Monitoreo Continuo & Seguridad)**: ✅ La supervisión autoritativa de 30s continúa operando sin interrupción.
2. **Principio 2 (Single Source of Truth para Configuración)**: ✅ `app/config.json` y `app/state.json` no se tocan ni commitean.
3. **Principio 3 (Concurrencia & Jerarquía de Locks)**: ✅ Respeta L1 $\rightarrow$ L2 estricto; fsync se realiza fuera de `state_lock`.
4. **Principio 4 (Inspect Contracts)**: ✅ Las subcadenas requeridas por `test_reboot_safety.py`, `test_auto_reboot_signal_gate.py`, `test_vnish_hashboard_detection.py` se mantienen intactas en `main()`.
5. **Principio 5 (Zero Regresiones)**: ✅ 935/935 tests pasan al 100%.
