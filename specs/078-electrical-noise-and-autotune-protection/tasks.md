# Tasks: Spec 078 — Supresión de Ruido Eléctrico en Elevadores, Watchdog Anti-Autotune Stall y Gobernanza Térmica Solar

- [x] T001: Extender `app/governance/elevator_budget.py` incorporando:
  - Ventana de reposo post-incidente de 300s (`incident_quiet_window_s = 300.0`, `record_group_incident`, `is_group_in_incident_quiet`).
  - Envolvente térmica solar (`evaluate_solar_thermal_envelope` para ventana 11:00-17:00 hs con techo 2500W y corte preventivo a 82°C).
  - Soporte de matriz de hardware individual (`get_miner_max_hardware_preset` y acotación en `choose_optimal_pair_presets` y `can_facility_transition_miner`).
- [x] T002: Desarrollar pruebas unitarias en `tests/test_elevator_budget.py` cubriendo la ventana de reposo de 300s post-incidente, la envolvente térmica solar 11:00-17:00 hs y la restricción de hardware de silicio individual por minero.
- [x] T003: Integrar compuertas de `max_hardware_preset` (`ACTION_HOLD_HARDWARE_LIMIT`) y reposo post-incidente (`ACTION_HOLD_INCIDENT_QUIET`) en `app/governance/preset_balancer.py`.
- [x] T004: Implementar en `app/miner_monitor.py`:
  - Watchdog anti-autotune stall (`autotune_timeout_s = 600`, hashrate $< 20\text{ TH/s}$ desencadena rescate con `safe_set_miner_preset`, alerta a Telegram y cerrojo de subida).
  - Registro de incidentes de grupo (`record_group_incident`) ante eventos de reinicio inesperado o contingencia.
  - Orquestación de la envolvente solar durante la franja 11:00-17:00 hs.
- [x] T005: Desarrollar suite de pruebas unitarias dedicada `tests/test_autotune_watchdog.py` validando la detección de autotune stall, la acción de desescalada de rescate con auto-restart, el cerrojo de preset y la emisión de alertas.
- [x] T006: Actualizar `app/config.example.json` documentando `max_hardware_preset`, `autotune_timeout_s` e `incident_quiet_window_s`.
- [x] T007: Ejecutar validación de compilación (`py_compile`) y suite de regresión completa ($\ge 1300$ tests PASS, 0 fallos, 0 regresiones).
- [x] T008: Documentar evidencia en `specs/078-electrical-noise-and-autotune-protection/evidence.md`, actualizar `docs/audit/DEVELOPMENT_LOG.md` y `docs/speckit/ROADMAP.md`.
- [x] T009: Presentar el resumen de certificación y plan de despliegue al usuario.
