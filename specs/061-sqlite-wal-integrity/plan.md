# Implementation Plan: Spec 061 — Resiliencia SQLite WAL Mode & Integrity Check (ST-03)

**Branch**: `codex/022-adaptive-acquisition` | **Date**: 2026-09-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/061-sqlite-wal-integrity/spec.md`

---

## Summary

Fortalecer la resiliencia física y transaccional de SQLite en `EventStore` (`app/core/event_store.py`) mediante tres fases ordenadas por riesgo:
- **Fase A (Integridad Asíncrona & Límite de Espacio)**:
  * Implementar el hilo de fondo `_integrity_check_worker` que corre `PRAGMA quick_check;` de forma asíncrona tras abrir la conexión.
  * Añadir cuarentena atómica de base corrupta (`miner_alerts_corrupt_<epoch>.db`) y auto-recreación limpia con esquema v7.
  * Añadir `PRAGMA max_page_count = 262144;` en `_initialize()`.
- **Fase B (Gestión de Checkpointing en Windows NTFS)**:
  * Implementar `EventStore.checkpoint_wal(mode: str)` con soporte para `PASSIVE` (horario) y `TRUNCATE` (diario fuera de pico).
  * Integrar invocaciones en los ciclos de mantenimiento de `app/miner_monitor.py`.
- **Fase C (Pool de Lectura & Tolerancia BUSY_SNAPSHOT)**:
  * Exponer `create_readonly_connection(db_path)` con `mode=ro`.
  * Implementar `execute_readonly_with_retry` con backoff exponencial (100ms/200ms/400ms) ante `SQLITE_BUSY_SNAPSHOT`.
  * Crear suite de pruebas exhaustiva en `tests/test_event_store_wal_resilience.py`.

---

## Technical Context

**Language/Version**: Python 3.12 (virtualenv en Windows 11)
**Storage Engine**: SQLite 3 (WAL mode, `synchronous=NORMAL`, esquema v7)
**Concurrency Model**:
- Thread Monitor (Escritura): Hilo principal adquiriendo `self._lock` en `EventStore`.
- Thread Integrity (Arranque): Hilo daemon de una sola ejecución ejecutando `PRAGMA quick_check;`.
- External Readers: Herramientas de diagnóstico y exporters abriendo conexiones independientes en `mode=ro`.
**Testing**: `unittest` standard library (`tests/test_event_store_wal_resilience.py`)
**Target Platform**: Windows 11 Pro / Servicio Windows `MinerAlerts`

---

## Constitution Check

*GATE: Must pass before implementation.*

1. **Principio 1 (Monitoreo Continuo & Seguridad)**: ✅ `PRAGMA quick_check;` es estrictamente asíncrono y no retrasa en ni un solo milisegundo el primer tick de telemetría ni el Startup Guard.
2. **Principio 2 (Single Source of Truth para Configuración)**: ✅ `app/config.json` y `app/state.json` permanecen intactos.
3. **Principio 3 (Windows NTFS Compatibility)**: ✅ El checkpoint diario `TRUNCATE` garantiza que el archivo `.db-wal` no acumule páginas huérfanas retenidas por locks de Windows.
4. **Principio 4 (Zero Regresiones)**: ✅ La API pública existente de `EventStore` (`record_telemetry_sample`, `record_action_outcome`, etc.) no sufre cambios de firma ni comportamiento. Todos los 935 tests deben continuar pasando al 100%.
