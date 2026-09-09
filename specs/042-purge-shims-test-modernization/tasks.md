# Tasks: Spec 042 - Purga Limpia de Shims y Modernización de Tests en `app/`

## Fase 1: Preparación y Blueprint
- [x] T001 Crear carpeta de especificación `specs/042-purge-shims-test-modernization`, checklist, `spec.md` y `plan.md`.
- [x] T002 Actualizar `.specify/feature.json` a `specs/042-purge-shims-test-modernization`.

## Fase 2: Modernización de Tests y Purga de Shims de Telegram
- [x] T003 Actualizar imports y patches en tests de Telegram (`test_telegram_callbacks.py`, `test_telegram_charts.py`, `test_telegram_messaging.py`, `test_telegram_snooze.py`, `test_daily_digest.py`, `test_controlled_telegram_simulation.py`, `test_compact_ux.py`, etc.) apuntando a `app.telegram`.
- [x] T004 Eliminar shims de telegram: `app/telegram_callbacks.py`, `app/telegram_charts.py`, `app/telegram_messages.py`, `app/telegram_snooze.py`, `app/daily_digest.py`, `app/snooze.py`.
- [x] T005 Ejecutar tests de Telegram y suite completa (587 PASS).

## Fase 3: Modernización de Tests y Purga de Shims de Vnish
- [x] T006 Actualizar imports y patches en tests de Vnish (`test_vnish_client.py`, `test_vnish_presets.py`, `test_vnish_logs.py`, `test_vnish_telemetry.py`, `test_vnish_hashboard_detection.py`, etc.) apuntando a `app.vnish`.
- [x] T007 Eliminar shims de Vnish: `app/vnish_client.py`, `app/vnish_presets.py`, `app/vnish_logs.py`, `app/vnish_telemetry.py`.
- [x] T008 Ejecutar tests de Vnish y suite completa (587 PASS).

## Fase 4: Modernización de Tests y Purga de Shims de Governance
- [x] T009 Actualizar imports y patches en tests de Governance (`test_fan_governor.py`, `test_fan_governor_concurrency.py`, `test_preset_balancer.py`, `test_preset_balancer_integration.py`, `test_fan_health.py`, `test_energy_efficiency.py`, etc.) apuntando a `app.governance`.
- [x] T010 Eliminar shims de Governance: `app/fan_governor.py`, `app/preset_balancer.py`, `app/fan_health.py`, `app/energy_efficiency.py`.
- [x] T011 Ejecutar tests de Governance y suite completa (587 PASS).

## Fase 5: Modernización de Tests y Purga de Shims de Core
- [x] T012 Actualizar imports y patches en tests de Core (`test_acquisition.py`, `test_acquisition_baseline.py`, `test_alert_episodes.py`, `test_event_store.py`, `test_evidence_fusion*.py`, `test_monitor_liveness.py`, `test_metrics_snapshot.py`, `test_mining_quality.py`, `test_reboot_safety.py`, `test_restart_intelligence.py`, `test_stability_profile.py`, etc.) apuntando a `app.core`.
- [x] T013 Eliminar shims de Core: `app/acquisition.py`, `app/alert_episodes.py`, `app/event_store.py`, `app/evidence_fusion.py`, `app/liveness.py`, `app/metrics_snapshot.py`, `app/mining_quality.py`, `app/reboot_safety.py`, `app/restart_intelligence.py`, `app/stability_profile.py`.
- [x] T014 Ejecutar tests de Core y suite completa (587 PASS).

## Fase 6: Certificación Final, Release Audit y Roadmap
- [x] T015 Verificar que en `app/` no quede ningún archivo `.py` suelto excepto `miner_monitor.py` e `__init__.py`.
- [x] T016 Ejecutar suite de tests completa: 587/587 PASS.
- [x] T017 Ejecutar `tools/release_audit.py --check-only` para verificar el nuevo digest de payload de 60 archivos.
- [x] T018 Documentar evidencia en `specs/042-purge-shims-test-modernization/evidence.md`.
- [x] T019 Actualizar `docs/speckit/ROADMAP.md` y `docs/audit/DEVELOPMENT_LOG.md`.
- [x] T020 Actualizar `prompt.txt` y realizar commit de cierre de Spec 042.
