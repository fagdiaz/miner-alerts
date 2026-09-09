# Implementation Plan: Spec 042 - Purga Limpia de Shims y Modernización de Tests en `app/`

## 1. Estrategia de Ejecución por Etapas
Para mantener la seguridad estricta y zero regressions:

### Etapa 1: Dominio Telegram (`app.telegram`)
- Actualizar tests de Telegram (`test_telegram_callbacks.py`, `test_telegram_charts.py`, `test_telegram_messaging.py`, `test_telegram_snooze.py`, `test_daily_digest.py`, `test_controlled_telegram_simulation.py`, etc.).
- Eliminar los shims de telegram: `app/telegram_callbacks.py`, `app/telegram_charts.py`, `app/telegram_messages.py`, `app/telegram_snooze.py`, `app/daily_digest.py`, `app/snooze.py`.
- Validar tests.

### Etapa 2: Dominio Vnish (`app.vnish`)
- Actualizar tests de Vnish (`test_vnish_client.py`, `test_vnish_presets.py`, `test_vnish_logs.py`, `test_vnish_telemetry.py`, `test_vnish_hashboard_detection.py`, etc.).
- Eliminar los shims de Vnish: `app/vnish_client.py`, `app/vnish_presets.py`, `app/vnish_logs.py`, `app/vnish_telemetry.py`.
- Validar tests.

### Etapa 3: Dominio Governance (`app.governance`)
- Actualizar tests de Governance (`test_fan_governor.py`, `test_fan_governor_concurrency.py`, `test_preset_balancer.py`, `test_preset_balancer_integration.py`, `test_fan_health.py`, `test_energy_efficiency.py`, etc.).
- Eliminar shims de governance: `app/fan_governor.py`, `app/preset_balancer.py`, `app/fan_health.py`, `app/energy_efficiency.py`.
- Validar tests.

### Etapa 4: Dominio Core (`app.core`)
- Actualizar tests de Core (`test_acquisition.py`, `test_acquisition_baseline.py`, `test_alert_episodes.py`, `test_event_store.py`, `test_evidence_fusion*.py`, `test_monitor_liveness.py`, `test_metrics_snapshot.py`, `test_mining_quality.py`, `test_reboot_safety.py`, `test_restart_intelligence.py`, `test_stability_profile.py`, etc.).
- Eliminar los shims de core: `app/acquisition.py`, `app/alert_episodes.py`, `app/event_store.py`, `app/evidence_fusion.py`, `app/liveness.py`, `app/metrics_snapshot.py`, `app/mining_quality.py`, `app/reboot_safety.py`, `app/restart_intelligence.py`, `app/stability_profile.py`.
- Validar tests.

### Etapa 5: Auditoría de Release, Limpieza y Certificación
- Validar que `app/` contiene solo los 4 paquetes + `__init__.py` + `miner_monitor.py`.
- Ejecutar suite completa (587 tests).
- Ejecutar `tools/release_audit.py --check-only`.
- Actualizar documentación y roadmap.
