# Spec 042: Purga Limpia de Shims y Modernización de Tests en `app/`

## 1. Visión y Propósito
El objetivo de esta especificación es alcanzar el **ordenamiento máximo posible** en el directorio `app/`. Tras la exitosa modularización de la Spec 041, donde el código productivo fue trasladado a los subpaquetes de dominio (`app/core/`, `app/vnish/`, `app/governance/`, `app/telegram/`), se mantuvieron 22 archivos shims en la raíz de `app/` exclusivamente para preservar la compatibilidad de la suite histórica de pruebas (`tests/`).

Esta especificación actualiza todas las importaciones y referencias de parches (`unittest.mock.patch`) en la suite completa de pruebas para que consuman directamente los subpaquetes de dominio canónicos, permitiendo la **eliminación definitiva de los 22 archivos sueltos** en `app/`.

## 2. Estado Final Objetivo de `app/`
Al concluir la especificación, la estructura de `app/` contendrá exclusivamente:
```text
app/
├── core/             # Red API 4028, SQLite, liveness, métricas y seguridad
├── governance/       # Fan governor y preset balancer por elevador
├── telegram/         # Bot, gráficos, snooze y digests
├── vnish/            # Cliente REST, presets y telemetría firmware
├── __init__.py       # Inicializador del paquete
├── miner_monitor.py  # Orquestador y servicio principal
├── config.example.json # Plantilla de configuración
├── config.json       # Configuración local (gitignored)
└── state.json        # Estado persistente en caliente (gitignored)
```
**Total de archivos `.py` sueltos en `app/`: exactamente 2 (`miner_monitor.py` y `__init__.py`).**

## 3. Alcance de Modificaciones
1. **Actualización de Imports en `tests/`**:
   - `tests/test_acquisition*.py` -> `app.core.acquisition`
   - `tests/test_alert_episodes*.py` -> `app.core.alert_episodes`
   - `tests/test_event_store*.py` -> `app.core.event_store`
   - `tests/test_evidence_fusion*.py` -> `app.core.evidence_fusion`
   - `tests/test_monitor_liveness*.py` -> `app.core.liveness`
   - `tests/test_metrics_snapshot*.py` -> `app.core.metrics_snapshot`
   - `tests/test_mining_quality*.py` -> `app.core.mining_quality`
   - `tests/test_reboot_safety*.py` -> `app.core.reboot_safety`
   - `tests/test_restart_intelligence*.py` -> `app.core.restart_intelligence`
   - `tests/test_stability_profile*.py` -> `app.core.stability_profile`
   - `tests/test_vnish_*.py` -> `app.vnish.client`, `app.vnish.presets`, `app.vnish.logs`, `app.vnish.telemetry`
   - `tests/test_fan_governor*.py` -> `app.governance.fan_governor`
   - `tests/test_preset_balancer*.py` -> `app.governance.preset_balancer`
   - `tests/test_fan_health*.py` -> `app.governance.fan_health`
   - `tests/test_energy_efficiency*.py` -> `app.governance.energy_efficiency`
   - `tests/test_telegram_*.py` -> `app.telegram.callbacks`, `app.telegram.charts`, `app.telegram.messages`, `app.telegram.snooze`, `app.telegram.daily_digest`
2. **Purga de Shims en `app/`**:
   - Eliminación de los 22 archivos fachada mediante `git rm`.
3. **Criterios de Aceptación (DoD)**:
   - 587/587 tests pasando con 0 errores y 0 fallos.
   - `tools/release_audit.py --check-only` pasando al 100%.
   - Servicio en producción ininterrumpido.
