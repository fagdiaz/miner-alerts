# Implementation Plan: Spec 064 — Telemetría Visual y Gráficos Comparativos Multi-Miner en Telegram (UX-01)

**Branch**: `codex/022-adaptive-acquisition` | **Date**: 2026-09-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/064-multi-miner-charts/spec.md`

---

## Summary

Implementar gráficos multi-miner por grupo eléctrico, selector interactivo de rango temporal in-place mediante `editMessageMedia`, y blindaje de memoria en `matplotlib`:
- **Fase A (Consultas de Grupo & Renderizado Multi-Miner)**:
  * Implementar `fetch_group_chart_data()` y `render_group_chart_png()` en `app/telegram/charts.py`.
  * Diseñar gráfico dual: hashrate en panel superior y temperaturas de chip en panel inferior con colores coordinados.
  * Extender `ChartCommand` en `app/telegram/commands/diagnostics.py` para resolver grupos eléctricos (`elevator_1`, `elevator_2`).
- **Fase B (Teclado Inline & Actualización In-Place)**:
  * Añadir acción `chart_range` a `parse_callback_data()` en `app/telegram/callbacks.py`.
  * Crear `build_chart_range_keyboard(target, current_hours)` en `app/telegram/charts.py`.
  * Implementar `edit_telegram_photo()` en `app/miner_monitor.py` usando `editMessageMedia` con `multipart/form-data` y `attach://file_0`.
  * Integrar manejo de callback `chart_range` en `_handle_callback_query()`.
- **Fase C (Blindaje de Memoria & Batería de Pruebas)**:
  * Verificar higiene de recursos con `plt.close(fig)` en todos los paths de renderizado.
  * Desarrollar suite en `tests/test_multi_miner_charts.py` incluyendo prueba de estabilidad de memoria tras 100 renders.
  * Validar 985+ tests sin regresiones y servicio Windows `MinerAlerts` activo.

---

## Technical Context

**Language/Version**: Python 3.12 (virtualenv en Windows 11)
**Modules**:
- `app/telegram/charts.py` (Data fetch, generación de gráficos matplotlib, teclado inline).
- `app/telegram/commands/diagnostics.py` (Manejador del comando `/chart`).
- `app/telegram/callbacks.py` (Gramática y parseo de callbacks).
- `app/miner_monitor.py` (Método `edit_telegram_photo` y dispatcher de callbacks).
- `tests/test_multi_miner_charts.py` (Suite de pruebas exhaustivas).
**Target Platform**: Windows 11 Pro / Servicio Windows `MinerAlerts`.

---

## Constitution Check

1. **Principio 1 (Monitoreo Continuo & Seguridad de Hardware)**: ✅ La visualización gráfica opera de forma no bloqueante y de solo lectura sobre `telemetry_samples` en SQLite, sin perturbar el ciclo de control de 30s.
2. **Principio 2 (Zero Peticiones HTTP Extras a Mineros)**: ✅ Los gráficos se construyen exclusivamente a partir de las muestras históricas ya persistidas en SQLite (`EventStore`). Cero tráfico de red hacia los mineros.
3. **Principio 3 (Higiene de Recursos en Windows)**: ✅ Uso mandatorio del backend `Agg` y `plt.close(fig)` en bloques `finally` para prevenir fugas de GDI/memoria en el servicio persistente de Windows.
