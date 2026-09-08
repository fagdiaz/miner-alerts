# Tasks: Spec 039 - Vnish Thermal & Acoustic Fan Governor

## Fase 1: Deteccion y Visibilidad de Modo (Quick Win)
- [x] **T001**: [P1] Extender app/vnish_telemetry.py para parsear fan_mode y fan_pwm desde STATS de la API 4028.
- [x] **T002**: [P1] Actualizar app/fan_health.py (CoolingAssessment) para incluir el campo fan_mode y renderizado de texto.
- [x] **T003**: [P1] Actualizar build_fans_table_text y build_miner_fan_detail_text para mostrar [Manual: <PWM>%] o [Auto].
- [x] **T004**: [P1] Anadir tests unitarios para la extraccion y renderizado de modo de ventilador en tests/test_fan_health.py.

## Fase 2: Cliente Seguro Vnish REST API
- [x] **T005**: [P1] Crear app/vnish_client.py con metodos unlock_miner, lock_miner, get_cooling_settings y set_manual_fan_duty.
- [x] **T006**: [P1] Implementar safe_set_fan_duty con bloque try ... finally para garantizar la ejecucion de lock_miner.
- [x] **T007**: [P1] Implementar enmascaramiento de contrasenas y tokens en cualquier log o representacion de cadena.
- [x] **T008**: [P1] Desarrollar suite de tests unitarios con mocks para app/vnish_client.py (tests/test_vnish_client.py).

## Fase 3: Algoritmo de Lazo Cerrado (Gobernador Termico)
- [x] **T009**: [P1] Crear app/fan_governor.py con los modelos de datos GovernorConfig, GovernorDecision y la funcion pura compute_governor_step.
- [x] **T010**: [P1] Implementar logica de escalones graduales (+-2% a +-3%) y banda muerta [81.0, 82.5] degrees C.
- [x] **T011**: [P1] Implementar regla de escape de emergencia a 100% ante T_max >= 83.0 degrees C.
- [x] **T012**: [P1] Implementar respeto estricto de la ventana de asentamiento (dwell time) y piso minimo (PWM_min = 75%).
- [x] **T013**: [P1] Desarrollar suite de tests unitarios exhaustiva para app/fan_governor.py (tests/test_fan_governor.py).

## Fase 4: Integracion en Monitor y Comandos Telegram
- [x] **T014**: [P1] Integrar la evaluacion del gobernador en el bucle principal de app/miner_monitor.py tras la adquisicion.
- [x] **T015**: [P1] Anadir comandos Telegram /governor (estado), /gov set <temp>, /gov on y /gov off.
- [x] **T016**: [P1] Anadir persistencia de estado del gobernador en app/state.json bajo state_lock.
- [x] **T017**: [P1] Actualizar app/config.example.json con los nuevos campos documentados.

## Fase 5: Concurrencia, Pruebas de Estres y Documentacion
- [x] **T018**: [P1] Desarrollar tests de concurrencia y timeouts de red para el gobernador (tests/test_fan_governor_concurrency.py).
- [x] **T019**: [P1] Verificar 100% de pase de tests unitarios globales sin regresiones (549/549 PASS).
- [x] **T020**: [P1] Registrar evidencia de validacion en specs/039-vnish-fan-governor/evidence.md.
- [x] **T021**: [P1] Actualizar docs/audit/DEVELOPMENT_LOG.md y docs/speckit/ROADMAP.md.
