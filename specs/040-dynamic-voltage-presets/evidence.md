# Evidencia de Validación: Spec 040 - Dynamic Power & Preset Balancer

## Estado Actual
- **Fase**: FASES 1, 2 Y 3 COMPLETADAS Y CERTIFICADAS (Fase 4 Integración en Monitor Pendiente).
- **Fecha**: 2026-09-08
- **Proceso en Producción**: PID 101508 activo y saludable en V3.1.0 (>15 ticks continuos, 0 errores, ~59MB RAM).

## Evidencia Operativa en Hardware Real
- Caídas observadas en log de minero 24:
  `[PROFILE_CHANGE_ALERT] miner=24 status=DOWNCLOCKED freq=440.532`
- Comprobación de que la inestabilidad en elevadores sensibles y picos de temperatura causan downclockings y reinicios frecuentes, justificando el desescalado preventivo hacia presets estables.

## Evidencia de Tests Unitarios (Fases 1 a 3)
1. **Fase 1 (Cliente REST Vnish Presets)**:
   - `tests/test_vnish_client.py`: 15/15 tests PASS. Cubre lectura de presets, posteo atómico de presets y ciclo garantizado de `lock` con `finally`.
2. **Fase 2 y 3 (Motor Determinista y Pruebas Unitarias)**:
   - `tests/test_preset_balancer.py`: 9/9 tests PASS en 0.001s:
     * `test_compute_effective_hashrate`: Demuestra matemáticamente que operar a 93 TH/s (2500W) sin reinicios genera más hashrate neto (93.0 TH/s) que forzar a 98 TH/s (2700W) con 3 reinicios diarios (89.96 TH/s netos).
     * `test_step_down_on_frequent_restarts`: $\ge 2$ reinicios en 24h fuerza desescalado de 2700W a 2500W.
     * `test_step_down_at_minimum_preset_locks`: En 1600W no desescala más.
     * `test_group_cascade_step_down`: 2 mineros en el mismo elevador reiniciándose juntos activan desescalado grupal preventivo.
     * `test_step_up_after_soak_stability`: 80h de uptime, 0 reinicios en 72h y margen $\ge 4^\circ\text{C}$ promueve subida controlada de preset.
     * `test_step_up_blocked_by_insufficient_thermal_headroom`: Margen $< 4^\circ\text{C}$ frena la subida.
     * `test_step_up_capped_at_max_preset`: Techo máximo de operador respetado rígidamente.
3. **Suite Global de Regresión**:
   - `& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"`: **562/562 tests PASS** en 7.81s (0 fallos, 0 errores, 0 regresiones).
