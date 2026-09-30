# Tasks - Spec 080: Firmware Settings Corruption Watchdog & Assisted Recovery

## Fase 1: Motor de Detección de Salud de Firmware
- [x] **T1.1**: Implementar `check_miner_settings_health(host, password, timeout=2.5)` en `app/vnish/client.py`.
- [x] **T1.2**: Exportar `check_miner_settings_health` en `app/vnish/__init__.py`.

## Fase 2: Botonera Interactiva y Notificaciones
- [x] **T2.1**: Implementar `build_firmware_corruption_keyboard(miner_id)` en `app/telegram/fleet_cards.py`.
- [x] **T2.2**: Integrar la rutina de supervisión de salud de configuración en el ciclo periódico de `app/miner_monitor.py`.
- [x] **T2.3**: Registrar el evento operacional `firmware_settings_corrupted` en `data/miner_alerts.db` ante fallas detectadas.

## Fase 3: Pruebas Unitarias y Certificación
- [x] **T3.1**: Crear suite de tests `tests/test_firmware_corruption_watchdog.py`.
- [x] **T3.2**: Ejecutar la suite completa de pruebas de regresión (`pytest tests/ -q`) garantizando 100% PASS.
- [x] **T3.3**: Documentar la resolución empírica en `evidence.md` y `DEVELOPMENT_LOG.md`.
- [x] **T3.4**: Ejecutar `speckit-stabilize` y dejar actualizado `prompt.txt`.
