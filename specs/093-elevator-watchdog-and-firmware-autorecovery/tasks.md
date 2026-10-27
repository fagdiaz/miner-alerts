# Tasks: Spec 093 — Watchdog de Elevadores Eléctricos, Corrección de Rachas y Auto-Recuperación de Firmware

**Feature**: `093-elevator-watchdog-and-firmware-autorecovery`  
**Dependencies**: Arquitectura V6.0 (`specs/091-core-daemon-hookification`)  
**Target Outcome**: Detección determinista de OFFLINE, alerta inmediata de caída de elevador y auto-recuperación de firmware stock.

---

## Tareas de Implementación

- [x] **T001** [P0] [Riesgo Medio]: Corregir el reseteo de `offline_streak` y `low_streak` en `DetectionHook.execute` (`app/core/engine.py`), asegurando que solo se reinicien al recuperarse a `STATE_OK` desde un estado anómalo o cuando `responded=True`.
- [x] **T002** [P0] [Riesgo Medio]: Crear `app/governance/firmware_recovery.py` implementando el reinicio seguro de Bitmain stock `/cgi-bin/reboot.cgi`, el fallback escalonado a `FirmwareFlasher` (`C:\asicto\asicto-s19jpro-bb-nand-v1.2.6-install.tar.gz`) y la restauración del perfil dorado (`data/miner_profiles/`).
- [x] **T003** [P0] [Riesgo Medio]: Conectar `process_phase_drop_cycle` en `app/core/pipeline.py` para emitir la alerta `⚡ DISPARO DE CIRCUITO` cuando un elevador completo pierda energía.
- [x] **T004** [P0] [Riesgo Medio]: Conectar el disparador de `process_stock_firmware_fallback` en `app/core/pipeline.py` / `DetectionHook` cuando se reporte `stock_firmware_fallback_detected`.
- [x] **T005** [P0] [Riesgo Bajo]: Crear suite de pruebas exhaustiva en `tests/test_spec093_elevator_and_firmware_recovery.py`.
- [x] **T006** [P0] [Riesgo Alto]: Validar compilación de sintaxis (`py_compile`) y ejecutar la suite completa de pruebas (`pytest tests/`) certificando $\ge 1530$ tests PASS (0 fallos).
- [x] **T007** [P0] [Riesgo Medio]: Ejecutar preflight QA de `speckit-qa` (`.agents/skills/speckit-qa/scripts/preflight.ps1`).
- [x] **T008** [P0] [Riesgo Alto]: Reiniciar el servicio Windows NSSM `MinerAlerts` y verificar adquisición normal y logs limpios.
- [x] **T009** [P0] [Riesgo Alto]: Ejecutar la compuerta de certificación y release `speckit-stabilize` (`preflight_stabilize.ps1` 8/8 gates PASS).
- [x] **T010** [P0] [Riesgo Bajo]: Documentar la sesión en `docs/audit/DEVELOPMENT_LOG.md`, actualizar `docs/speckit/ROADMAP.md` y refrescar `prompt.txt`.
