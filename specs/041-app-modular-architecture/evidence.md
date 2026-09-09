# Evidence: Spec 041 - Arquitectura Modular y Reorganización de Dominios en `app/`

## Estado y Metadatos
- **Spec ID**: `041-app-modular-architecture`
- **Fecha de Inicio**: 2026-09-08
- **Línea Base Inicial**: 587/587 tests pasando en 11.58s. Servicio Windows `MinerAlerts` activo bajo PID 71304.
- **Resultado Global**: COMPLETADO Y CERTIFICADO (Fases 1 a 6 exitosas)

---

## 1. Línea Base Pre-Migración

```text
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
Ran 587 tests in 11.586s
OK
```

```text
& ".\.venv\Scripts\python.exe" tools\release_audit.py --check-only
RELEASE AUDIT: PASS. Runtime payload SHA-256: 810e41c17a914e0999d44e5ba22b151a0db10812a632a54e2a2838aea33089e4
Payload files counted: 55
Terminal dispositions: 8/8 verified
```

---

## 2. Registro de Fases de Migración

### Fase 2: Dominio Telegram (`app/telegram/`) - [COMPLETADA]
- **Archivos migrados**:
  * `app/telegram_callbacks.py` -> `app/telegram/callbacks.py`
  * `app/telegram_charts.py` -> `app/telegram/charts.py`
  * `app/telegram_messages.py` -> `app/telegram/messages.py`
  * `app/telegram_snooze.py` -> `app/telegram/snooze.py`
  * `app/daily_digest.py` -> `app/telegram/daily_digest.py`
- **Subpaquete creado**: `app/telegram/__init__.py` con re-exportaciones canónicas de los 5 submódulos y alias retrocompatibles (`TokenRegistry = CallbackTokenRegistry`).
- **Shims retrocompatibles creados**: 5 shims en `app/` preservando acceso sin quiebres (incluyendo `_connect_ro` para compatibilidad de tests de concurrencia).
- **Validación sintáctica**:
  ```powershell
  & ".\.venv\Scripts\python.exe" -m py_compile app\telegram\__init__.py app\telegram\callbacks.py app\telegram\charts.py app\telegram\messages.py app\telegram\snooze.py app\telegram\daily_digest.py app\telegram_callbacks.py app\telegram_charts.py app\telegram_messages.py app\telegram_snooze.py app\daily_digest.py
  # Retorno: 0 (OK)
  ```
- **Validación de Suite de Tests**:
  ```text
  Ran 587 tests in 10.887s
  OK
  ```
- **Auditoría de Release**:
  ```text
  RELEASE AUDIT: PASS. Runtime payload SHA-256: 097ddf9de957c87e97fcd9984e10bdbb8724632852eedaf5867de85cae2323bd
  Payload files counted: 61
  Terminal dispositions: 8/8 verified
  ```

### Fase 3: Dominio Vnish (`app/vnish/`) - [COMPLETADA]
- **Archivos migrados**:
  * `app/vnish_client.py` -> `app/vnish/client.py`
  * `app/vnish_presets.py` -> `app/vnish/presets.py`
  * `app/vnish_logs.py` -> `app/vnish/logs.py`
  * `app/vnish_telemetry.py` -> `app/vnish/telemetry.py`
- **Subpaquete creado**: `app/vnish/__init__.py` con re-exportaciones canónicas de los 4 submódulos.
- **Shims retrocompatibles con module aliasing (`sys.modules[__name__] = _impl`)**: Garantizan compatibilidad completa tanto para imports tradicionales como para monkey-patching dinámico (`unittest.mock.patch("app.vnish_client.unlock_miner")`).
- **Validación sintáctica**:
  ```powershell
  & ".\.venv\Scripts\python.exe" -m py_compile app\vnish\__init__.py app\vnish\client.py app\vnish\presets.py app\vnish\logs.py app\vnish\telemetry.py app\vnish_client.py app\vnish_presets.py app\vnish_logs.py app\vnish_telemetry.py
  # Retorno: 0 (OK)
  ```
- **Validación de Suite de Tests**:
  ```text
  Ran 587 tests in 10.856s
  OK
  ```
- **Auditoría de Release**:
  ```text
  RELEASE AUDIT: PASS. Runtime payload SHA-256: 3476c415a6195dcb3249a4149ea9dafdb29633d3ad3096ca870dca9b1dd8e9ee
  Payload files counted: 66
  Terminal dispositions: 8/8 verified
  ```

### Fase 4: Dominio Governance (`app/governance/`) - [COMPLETADA]
- **Archivos migrados**:
  * `app/fan_governor.py` -> `app/governance/fan_governor.py`
  * `app/preset_balancer.py` -> `app/governance/preset_balancer.py`
  * `app/fan_health.py` -> `app/governance/fan_health.py`
  * `app/energy_efficiency.py` -> `app/governance/energy_efficiency.py`
- **Subpaquete creado**: `app/governance/__init__.py` con re-exportaciones canónicas de los 4 submódulos.
- **Shims retrocompatibles con module aliasing (`sys.modules[__name__] = _impl`)**: Preservan 100% la compatibilidad hacia atrás para imports legados y suite de pruebas unitarias.
- **Validación sintáctica**:
  ```powershell
  & ".\.venv\Scripts\python.exe" -m py_compile app\governance\__init__.py app\governance\fan_governor.py app\governance\preset_balancer.py app\governance\fan_health.py app\governance\energy_efficiency.py app\fan_governor.py app\preset_balancer.py app\fan_health.py app\energy_efficiency.py
  # Retorno: 0 (OK)
  ```
- **Validación de Suite de Tests**:
  ```text
  Ran 587 tests in 10.423s
  OK
  ```
- **Auditoría de Release**:
  ```text
  RELEASE AUDIT: PASS. Runtime payload SHA-256: c2e79b27285b84f1eb040886e83863d19bf19dbdae26f25f67f1bfd5f1ca6437
  Payload files counted: 71
  Terminal dispositions: 8/8 verified
  ```

### Fase 5: Dominio Core (`app/core/`) - [COMPLETADA]
- **Archivos migrados**:
  * `app/acquisition.py` -> `app/core/acquisition.py`
  * `app/event_store.py` -> `app/core/event_store.py`
  * `app/alert_episodes.py` -> `app/core/alert_episodes.py`
  * `app/evidence_fusion.py` -> `app/core/evidence_fusion.py`
  * `app/liveness.py` -> `app/core/liveness.py`
  * `app/metrics_snapshot.py` -> `app/core/metrics_snapshot.py`
  * `app/mining_quality.py` -> `app/core/mining_quality.py`
  * `app/reboot_safety.py` -> `app/core/reboot_safety.py`
  * `app/restart_intelligence.py` -> `app/core/restart_intelligence.py`
  * `app/stability_profile.py` -> `app/core/stability_profile.py`
- **Subpaquete y root package inicializados**:
  * `app/__init__.py` para inicializar el paquete raíz y habilitar resolución de imports relativos.
  * `app/core/__init__.py` con re-exportaciones canónicas de los 10 submódulos.
- **Shims retrocompatibles con module aliasing (`sys.modules[__name__] = _impl`)**: Garantizan compatibilidad idéntica de `sys.modules` para monkey-patching en tests y herramientas externas.
- **Validación sintáctica**:
  ```powershell
  & ".\.venv\Scripts\python.exe" -m py_compile app\__init__.py app\core\__init__.py app\core\acquisition.py app\core\alert_episodes.py app\core\event_store.py app\core\evidence_fusion.py app\core\liveness.py app\core\metrics_snapshot.py app\core\mining_quality.py app\core\reboot_safety.py app\core\restart_intelligence.py app\core\stability_profile.py app\acquisition.py app\alert_episodes.py app\event_store.py app\evidence_fusion.py app\liveness.py app\metrics_snapshot.py app\mining_quality.py app\reboot_safety.py app\restart_intelligence.py app\stability_profile.py
  # Retorno: 0 (OK)
  ```
- **Validación de Suite de Tests**:
  ```text
  Ran 587 tests in 10.900s
  OK
  ```
- **Auditoría de Release**:
  ```text
  RELEASE AUDIT: PASS. Runtime payload SHA-256: 0fbf4a2758861ea46b5c4270bb18abc8b2404994e574891241c1fc715b694632
  Payload files counted: 83
  Terminal dispositions: 8/8 verified
  ```

### Fase 6: Modernización de Imports y Certificación Final - [COMPLETADA]
- **Archivos modernizados**:
  * `app/miner_monitor.py`: importaciones superiores e importaciones dinámicas inline actualizadas para importar directamente desde `app.core`, `app.vnish`, `app.telegram`, `app.governance`.
  * `tools/acquisition_baseline.py`: migrado a `from app.core.acquisition import ...`.
  * `tools/metrics_exporter.py`: migrado a `from app.core.metrics_snapshot import ...`.
  * `tools/metrics_sync.py`: migrado a `from app.core.metrics_snapshot import ...`.
  * `tools/monitor_watchdog.py`: migrado a `from app.core.liveness import ...`.
  * `tools/operations_dashboard.py`: migrado a `from app.core.mining_quality import ...` y `from app.core.stability_profile import ...`.
  * `tools/vnish_log_collector.py`: migrado a `from app.core.event_store import ...` y `from app.vnish.logs import ...`.
- **Validación sintáctica**:
  ```powershell
  & ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py tools\acquisition_baseline.py tools\metrics_exporter.py tools\metrics_sync.py tools\monitor_watchdog.py tools\operations_dashboard.py tools\vnish_log_collector.py
  # Retorno: 0 (OK)
  ```
- **Validación de Suite Completa de Tests**:
  ```text
  & ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
  Ran 587 tests in 11.262s
  OK
  ```
- **Auditoría de Release**:
  ```text
  & ".\.venv\Scripts\python.exe" tools\release_audit.py --check-only
  RELEASE AUDIT: PASS. Runtime payload SHA-256: 1d54510535bf6d089af3e84b75835da07b66643388e6d0ea4a2658372672f290
  Payload files counted: 83
  Terminal dispositions: 8/8 verified
  ```
- **Conclusión de Certificación**:
  La reorganización de `app/` en 4 dominios modulares (`app/core/`, `app/vnish/`, `app/governance/`, `app/telegram/`) junto con sus shims retrocompatibles y la modernización canónica de los imports en el monitor principal y herramientas satélite se completó sin una sola regresión en los 587 tests existentes y con cero interrupción de servicio en producción.


