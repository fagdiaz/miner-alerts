# Tasks - Spec 081: Watchdog de Reinicio de Minado Pendiente y Armonización Térmica (PROP-017)

## Fase 1: Función Pura y Modelo de Estado
- [x] **T1.1**: Agregar campos `vnish_restart_required` y `vnish_restart_detected_ts` a `MinerState` en `app/miner_monitor.py`.
- [x] **T1.2**: Implementar la función pura `evaluate_preset_restart_candidate` en `app/miner_monitor.py`.

## Fase 2: Armonización de Fan Governor y Watchdog
- [x] **T2.1**: Actualizar `execute_governor_cycle` en `app/miner_monitor.py` para adaptar `gov_target_pwr = gov_curr_pwr` cuando `vnish_restart_required=True`.
- [x] **T2.2**: Integrar la rutina de evaluación y ejecución del Watchdog en `_async_collect_chain_telemetry` de `app/miner_monitor.py`.

## Fase 3: Pruebas Unitarias, QA y Certificación
- [x] **T3.1**: Crear suite de tests `tests/test_restart_required_watchdog.py`.
- [x] **T3.2**: Ejecutar la suite completa de pruebas de regresión (`pytest tests/ -q`) garantizando 100% PASS.
- [x] **T3.3**: Documentar la resolución y telemetría empírica en `evidence.md`.
- [x] **T3.4**: Ejecutar `speckit-stabilize`, actualizar `DEVELOPMENT_LOG.md`, `ROADMAP.md` y `prompt.txt`.
