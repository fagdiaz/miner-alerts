# Tasks: Spec 066 — Cold-Boot Fleet Grace Period Post-Arranque (PROP-001)

## Tasks

- [x] **T001**: Actualizar `.specify/feature.json` apuntando a `specs/066-cold-boot-grace`.
- [x] **T002**: Crear especificación (`spec.md`), plan (`plan.md`), tareas (`tasks.md`) y plantilla de evidencia (`evidence.md`).
- [x] **T003**: Actualizar `app/config.example.json` con `"startup_fleet_grace_period_seconds": 180` y `"startup_fleet_grace_threshold_ths": 50.0`.
- [x] **T004**: Implementar la lógica del período de gracia en `app/miner_monitor.py`:
  - Lectura de configuración `startup_fleet_grace_period_seconds` y `startup_fleet_grace_threshold_ths`.
  - Control de estado `startup_grace_active`, supresión de streaks (`offline_streak`, `low_streak`) y reseteo de timers sostenidos durante la fase `WARMING_UP`.
  - Inhibición de emisión de alertas de episodios irregulares durante la ventana activa de gracia.
  - Consolidación temprana con tarjeta `🟢 FLOTA RESTABLECIDA` al superar el umbral en toda la flota.
  - Consolidación por expiración de timeout tras 180s con tarjeta `STARTUP`.
  - Ejecución incondicional de reconciliación de silent mode en `first_tick`.
  - Preservación estricta de literales y orden de interlocks inspeccionados por tests.
  - Sincronización continua de `monitor_ctx.governance = _GLOBAL_INTERVENTION_GOV` en cada tick y soporte en `GovernanceInterlockHook`.
- [x] **T005**: Crear suite de pruebas exhaustivas en `tests/test_startup_grace_period.py`:
  - Parsing de configuración y valores por defecto.
  - Lógica de supresión de streaks en período de gracia.
  - Disparo de tarjeta `🟢 FLOTA RESTABLECIDA` ante recuperación temprana.
  - Disparo de tarjeta `STARTUP` ante expiración de gracia.
  - Comportamiento retrocompatible con `startup_fleet_grace_period_seconds = 0`.
  - Verificación de invariantes `inspect.getsource(main)`.
  - Pruebas adicionales en `tests/test_supervisory_hooks.py` para sincronización de governance.
- [x] **T006**: Ejecución de validaciones de sintaxis (`py_compile`), suite completa de pruebas unitarias (`python -m unittest discover tests`), verificación de preflight y generación de evidencia en `evidence.md` (**1062 tests PASS**).
- [x] **T007**: Documentación en `docs/audit/DEVELOPMENT_LOG.md`, actualización de `docs/speckit/ROADMAP.md` y actualización de `prompt.txt`.
