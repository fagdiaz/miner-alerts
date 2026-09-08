# Tasks: Spec 039 - Vnish Thermal & Acoustic Fan Governor

## Fase 1: Detección y Visibilidad de Modo (Quick Win)
- [ ] **T001**: [P1] Extender `app/vnish_telemetry.py` para parsear `fan_mode` y `fan_pwm` desde STATS de la API 4028.
- [ ] **T002**: [P1] Actualizar `app/fan_health.py` (`CoolingAssessment`) para incluir el campo `fan_mode` y renderizado de texto.
- [ ] **T003**: [P1] Actualizar `build_fans_table_text` y `build_miner_fan_detail_text` para mostrar `[Manual: <PWM>%]` o `[Auto]`.
- [ ] **T004**: [P1] Añadir tests unitarios para la extracción y renderizado de modo de ventilador en `tests/test_fan_health.py`.

## Fase 2: Cliente Seguro Vnish REST API
- [ ] **T005**: [P1] Crear `app/vnish_client.py` con métodos `unlock_miner`, `lock_miner`, `get_cooling_settings` y `set_manual_fan_duty`.
- [ ] **T006**: [P1] Implementar `safe_set_fan_duty` con bloque `try ... finally` para garantizar la ejecución de `lock_miner`.
- [ ] **T007**: [P1] Implementar enmascaramiento de contraseñas y tokens en cualquier log o representación de cadena.
- [ ] **T008**: [P1] Desarrollar suite de tests unitarios con mocks para `app/vnish_client.py` (`tests/test_vnish_client.py`).

## Fase 3: Algoritmo de Lazo Cerrado (Gobernador Térmico)
- [ ] **T009**: [P1] Crear `app/fan_governor.py` con los modelos de datos `GovernorConfig`, `GovernorDecision` y la función pura `compute_governor_step`.
- [ ] **T010**: [P1] Implementar lógica de escalones graduales ($\pm 2\%$ a $\pm 3\%$) y banda muerta $[81.0, 82.5]^\circ\text{C}$.
- [ ] **T011**: [P1] Implementar regla de escape de emergencia a 100% ante $T_{max} \ge 83.0^\circ\text{C}$.
- [ ] **T012**: [P1] Implementar respeto estricto de la ventana de asentamiento (*dwell time*) y piso mínimo ($PWM_{min} = 70\%$).
- [ ] **T013**: [P1] Desarrollar suite de tests unitarios exhaustiva para `app/fan_governor.py` (`tests/test_fan_governor.py`).

## Fase 4: Integración en Monitor y Comandos Telegram
- [ ] **T014**: [P1] Integrar la evaluación del gobernador en el bucle principal de `app/miner_monitor.py` tras la adquisición.
- [ ] **T015**: [P1] Añadir comandos Telegram `/governor` (estado), `/gov set <temp>`, `/gov on` y `/gov off`.
- [ ] **T016**: [P1] Añadir persistencia de estado del gobernador en `app/state.json` bajo `state_lock`.
- [ ] **T017**: [P1] Actualizar `app/config.example.json` y esquema de configuración con las claves del gobernador y credenciales Vnish.

## Fase 5: Concurrencia, Pruebas de Estrés y Documentación
- [ ] **T018**: [P1] Desarrollar tests de concurrencia y timeouts de red para el gobernador (`tests/test_fan_governor_concurrency.py`).
- [ ] **T019**: [P1] Verificar 100% de pase de tests unitarios globales sin regresiones.
- [ ] **T020**: [P1] Registrar evidencia de validación en `specs/039-vnish-fan-governor/evidence.md`.
- [ ] **T021**: [P1] Actualizar `docs/audit/DEVELOPMENT_LOG.md` y `docs/speckit/ROADMAP.md`.
