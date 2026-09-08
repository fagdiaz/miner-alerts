# Evidencia de Validación: Spec 039 - Vnish Thermal & Acoustic Fan Governor

## Estado Actual
- **Fase**: FASES 1, 2 Y 3 COMPLETADAS Y CERTIFICADAS (Pendiente Fase 4 Integración Monitor / Concurrencia).
- **Fecha**: 2026-09-08
- **Proceso en Producción**: PID 88348 activo y saludable (>1.718 ticks).

## Relevamiento en Hardware Real
- Endpoint `/api/v1/summary` verificado en `192.168.100.23` a `26`.
- Modo actual confirmado: `mode: "manual"`, `param: 100%`, `fan_min_duty: 40`, `decrease_temp: 84`.
- Autenticación `POST /api/v1/unlock` validada exitosamente con password de operador.
- Lectura autenticada `GET /api/v1/settings` y cierre `POST /api/v1/lock` probados sin efectos colaterales.

## Auditoría Arquitectónica Pre-Implementación (Claude Sonnet 4.6 Thinking)
- Veredicto: AUTORIZADO para Fases 1, 2 y 3 (dry_run: true).
- Hardening incorporado:
  - R1: Dwell adaptativo (90s base, 120s para holds consecutivos >= 3) con banda muerta [81.0, 82.5]°C.
  - R2: HTTP Concurrency vía ThreadPoolExecutor(max_workers=4) con 2.5s por request y 5.0s global flota.
  - R3: Fallback fail-safe explícito a 100% ante /gov off, >= 3 fallos consecutivos o excepción.
  - R4: Piso mínimo elevado de 70% a 75%.

## Evidencia de Tests Unitarios (Fases 1 a 3)
1. **Fase 1 (Visibilidad de Modo)**:
   - `tests/test_fan_health.py`: 15 tests pasados (incluye `test_fan_mode_rendering_in_table_and_detail`).
   - Parseo de `fan_mode` y `fan_pwm` verificado en `app/vnish_telemetry.py`.
2. **Fase 2 (Cliente REST Seguro)**:
   - `tests/test_vnish_client.py`: 11 tests pasados (mock HTTP, 401, timeout, clamping [40, 100], garantía de lock en finally).
3. **Fase 3 (Algoritmo Determinista del Gobernador)**:
   - `tests/test_fan_governor.py`: 11 tests pasados (spike de emergencia a 83.0°C, dwell adaptativo, deadband, step-up +3%, step-down -2%, failsafe fault).
4. **Higiene de Recursos Gráficos**:
   - `app/telegram_charts.py`: `try ... finally: plt.close(fig)` implementado en todas las funciones generadoras para prevenir fugas de descriptores GDI y memoria OpenBLAS en Windows.
5. **Suite Global de Regresión**:
   - `& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"`: 537/537 tests pasados exitosamente en 6.62s. Zero regresiones.
