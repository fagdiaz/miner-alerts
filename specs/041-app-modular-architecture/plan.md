# Implementation Plan: Spec 041 - Arquitectura Modular y Reorganización de Dominios en `app/`

## 1. Arquitectura de Módulos y Grafo de Dependencias

```text
                                  +---------------------------------------+
                                  |         app/miner_monitor.py          |
                                  |     (Entrypoint & Orquestador)        |
                                  +---+---------------+---------------+---+
                                      |               |               |
             +------------------------+               |               +------------------------+
             |                                        |                                        |
             v                                        v                                        v
+---------------------------+    +---------------------------+    +---------------------------+
|       app/telegram/       |    |      app/governance/      |    |        app/vnish/         |
|---------------------------|    |---------------------------|    |---------------------------|
| - callbacks.py            |    | - fan_governor.py         |    | - client.py               |
| - charts.py               |    | - preset_balancer.py      |    | - presets.py              |
| - messages.py             |    | - fan_health.py           |    | - logs.py                 |
| - snooze.py               |    | - energy_efficiency.py    |    | - telemetry.py            |
| - daily_digest.py         |    +-------------+-------------+    +-------------+-------------+
+-------------+-------------+                  |                                |
              |                                v                                v
              +-----------------------> +---------------------------+ <---------+
                                        |         app/core/         |
                                        |---------------------------|
                                        | - acquisition.py          |
                                        | - event_store.py          |
                                        | - alert_episodes.py       |
                                        | - evidence_fusion.py      |
                                        | - liveness.py             |
                                        | - metrics_snapshot.py     |
                                        | - mining_quality.py       |
                                        | - reboot_safety.py        |
                                        | - restart_intelligence.py |
                                        | - stability_profile.py    |
                                        +---------------------------+
```

### Reglas de Dependencia entre Paquetes
1. **`app/core/`**: Es la capa base fundamental (almacenamiento SQLite, adquisición de red 4028, episodios). No depende de ningún otro subpaquete.
2. **`app/vnish/`**: Capa de integración de firmware. Puede depender de utilidades puras de `app/core/` si lo requiere, pero es autocontenido.
3. **`app/governance/`**: Algoritmos de decisión térmica y balanceo. Consume datos de `app/vnish/` y telemetría de `app/core/`.
4. **`app/telegram/`**: Capa de presentación y control de usuario. Consume modelos de `app/core/`, `app/governance/` y genera respuestas hacia la API de Telegram.
5. **`app/miner_monitor.py`**: Orquesta el bucle de producción invocando a los 4 subdominios.

---

## 2. Fases de Ejecución Iterativa

### Fase 1: Dominio Telegram (`app/telegram/`)
- Crear directorio `app/telegram/`.
- Mover archivos:
  * `telegram_callbacks.py` -> `app/telegram/callbacks.py`
  * `telegram_charts.py` -> `app/telegram/charts.py`
  * `telegram_messages.py` -> `app/telegram/messages.py`
  * `telegram_snooze.py` -> `app/telegram/snooze.py`
  * `daily_digest.py` -> `app/telegram/daily_digest.py`
- Crear `app/telegram/__init__.py` con re-exportaciones claras.
- Crear shims en `app/` para cada archivo movido (`app/telegram_callbacks.py`, etc.).
- **Validación Gate**: `py_compile` y ejecución de 587 tests (`Ran 587 tests ... OK`).
- Commit atómico.

### Fase 2: Dominio Vnish (`app/vnish/`)
- Crear directorio `app/vnish/`.
- Mover archivos:
  * `vnish_client.py` -> `app/vnish/client.py`
  * `vnish_presets.py` -> `app/vnish/presets.py`
  * `vnish_logs.py` -> `app/vnish/logs.py`
  * `vnish_telemetry.py` -> `app/vnish/telemetry.py`
- Crear `app/vnish/__init__.py` con re-exportaciones canónicas.
- Crear shims en `app/` (`app/vnish_client.py`, etc.).
- **Validación Gate**: `py_compile` y ejecución de 587 tests.
- Commit atómico.

### Fase 3: Dominio Governance (`app/governance/`)
- Crear directorio `app/governance/`.
- Mover archivos:
  * `fan_governor.py` -> `app/governance/fan_governor.py`
  * `preset_balancer.py` -> `app/governance/preset_balancer.py`
  * `fan_health.py` -> `app/governance/fan_health.py`
  * `energy_efficiency.py` -> `app/governance/energy_efficiency.py`
- Crear `app/governance/__init__.py`.
- Crear shims en `app/`.
- **Validación Gate**: `py_compile` y ejecución de 587 tests.
- Commit atómico.

### Fase 4: Dominio Core (`app/core/`)
- Crear directorio `app/core/`.
- Mover archivos:
  * `acquisition.py` -> `app/core/acquisition.py`
  * `event_store.py` -> `app/core/event_store.py`
  * `alert_episodes.py` -> `app/core/alert_episodes.py`
  * `evidence_fusion.py` -> `app/core/evidence_fusion.py`
  * `liveness.py` -> `app/core/liveness.py`
  * `metrics_snapshot.py` -> `app/core/metrics_snapshot.py`
  * `mining_quality.py` -> `app/core/mining_quality.py`
  * `reboot_safety.py` -> `app/core/reboot_safety.py`
  * `restart_intelligence.py` -> `app/core/restart_intelligence.py`
  * `stability_profile.py` -> `app/core/stability_profile.py`
- Crear `app/core/__init__.py`.
- Crear shims en `app/`.
- **Validación Gate**: `py_compile` y ejecución de 587 tests.
- Commit atómico.

### Fase 5: Modernización Progresiva de Imports y Limpieza
- En `app/miner_monitor.py` y `tools/`, actualizar las declaraciones `from app.<shim> import ...` para consumir directamente desde los subpaquetes (`from app.telegram import ...`, `from app.governance import ...`, etc.).
- Validar que tanto los tests como el ejecutable funcionen de forma idéntica.

### Fase 6: Cierre, Auditoría y Documentación
- `release_audit.py --check-only` para verificar el estado de release.
- Registrar evidencia completa en `evidence.md`.
- Añadir entrada en `docs/audit/DEVELOPMENT_LOG.md`.
- Sincronizar `docs/speckit/ROADMAP.md`.
