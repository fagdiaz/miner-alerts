# Implementation Plan: Descomposición y Modularización del Monolito

**Feature**: `087-monolith-decoupling`  
**Baseline**: 1520 tests PASS, 75 subtests PASS  
**Final Size Target**: `app/miner_monitor.py` $\le 500$ LOC  

---

## 1. Technical Architecture & Target State

```
miner-alerts/
├── app/
│   ├── core/                  # Motor de supervisión, estados, base de datos y hooks
│   │   ├── engine.py          # CoreSupervisoryEngine (pipeline declarativo de 7 etapas)
│   │   ├── context.py         # MonitorContext (estado tipado inmutable/mutable seguro)
│   │   ├── state_manager.py   # Persistencia L1/L2, atomic flush y lock hierarchy
│   │   └── hooks/             # Implementaciones de etapas (PreTick, Detection, etc.)
│   ├── governance/            # Políticas de control térmico, ventiladores y balance
│   │   ├── governor_cycle.py  # Fan Governor (Spec 085)
│   │   ├── balancer_cycle.py  # Dynamic Preset Balancer (Fase 2)
│   │   ├── autotune_cycle.py  # Autotune Stall Watchdog (Fase 2)
│   │   └── thermal_guard.py   # Closed-loop emergency tripwire
│   ├── hardware/              # Telemetría de bajo nivel y recolección
│   │   ├── chain_collector.py # Mapeo asíncrono de chips y predicción de rotura (Fase 3)
│   │   └── socket_client.py   # Wrappers de protocolo TCP 4028 (Fase 3)
│   ├── telegram/              # Subsistema interactivo móvil completo
│   │   ├── callbacks.py       # Despacho y ejecución de botones inline (Fase 1)
│   │   ├── command_center.py  # Vistas de menú (/menu), parada y reanudación
│   │   ├── router.py          # Despachador de comandos y callbacks desacoplado
│   │   └── poller.py          # Bucle de transporte getUpdates
│   └── miner_monitor.py       # Orquestador liviano (<500 LOC): bootstrap y loop runner
```

---

## 2. Phase-by-Phase Technical Blueprint

### Fase 1: Desacoplamiento de Callbacks de Telegram (~1.450 L eliminadas)
* **Acción**:
  1. Mover `_handle_command_center_callback` de `miner_monitor.py` a `app/telegram/command_center.py`.
  2. Mover `_handle_help_callback` a `app/telegram/help_center.py`.
  3. Mover `_handle_diagnostic_callback` y `_handle_callback_query` a `app/telegram/callbacks.py`.
  4. Actualizar `app/telegram/router.py` para invocar estos handlers directamente dentro del paquete `telegram` en lugar de re-importarlos desde `miner_monitor.py`.
  5. En `app/miner_monitor.py`, reemplazar las 1.450 líneas con re-exports simples:
     ```python
     from app.telegram.command_center import _handle_command_center_callback
     from app.telegram.help_center import _handle_help_callback
     from app.telegram.callbacks import _handle_diagnostic_callback, _handle_callback_query
     ```
* **Verificación**: `pytest tests/test_telegram_callbacks.py tests/test_controlled_telegram_simulation.py` (PASS).

---

### Fase 2: Extracción de Gobernanza Restante (Spec 087) (~850 L eliminadas)
* **Acción**:
  1. Crear `app/governance/balancer_cycle.py`:
     - Mover `execute_balancer_cycle` (L3362-L3614).
     - Parámetros limpios: recibe `GovernanceContext` o parámetros tipados y despacha a `set_preset`.
  2. En `app/governance/autotune_watchdog.py`:
     - Mover `check_autotune_watchdog` (L3615-L3754) como `execute_autotune_watchdog_cycle`.
  3. En `miner_monitor.py`, re-exportar ambas funciones e invocarlas desde sus nuevos módulos.
* **Verificación**: `pytest tests/test_reboot_decision_audit.py tests/test_autotune_watchdog.py` (PASS).

---

### Fase 3: Extracción de Telemetría de Cadenas & Sockets ASIC 4028 (~1.000 L eliminadas)
* **Acción**:
  1. Crear `app/hardware/chain_collector.py` y mover `_async_collect_chain_telemetry` y `_async_evaluate_predictive_chain_break`.
  2. Eliminar funciones duplicadas de socket 4028 (`read_summary`, `read_stats_snapshot`, etc.) en `miner_monitor.py` y re-exportar las implementaciones canónicas existentes en `app/network/cgminer_client.py`.
  3. Mover formateadores de texto de diagnóstico (`build_stability_health_text`, etc.) a `app/telegram/fleet_cards.py`.
* **Verificación**: `pytest tests/test_chain_health.py tests/test_network_protocols.py` (PASS).

---

### Fase 4: Modernización del Test Legacy de `inspect.getsource(main)`
* **Acción**:
  1. En `tests/test_startup_grace_period.py`:
     - Reemplazar la prueba estricta de orden de strings (`source.index("elif startup_guard_active")`) por la invocación del `SupervisoryBehavioralHarness` (validando que el comportamiento funcional de precedencia de startup guard sea idéntico sin forzar texto en `main`).
  2. Desbloquear formalmente la refactorización de `main()`.
* **Verificación**: `pytest tests/test_startup_grace_period.py` (PASS).

---

### Fase 5: Conversión de `main()` en Pipeline de Hooks Declarativo (~4.800 L eliminadas)
* **Acción**:
  1. Migrar las etapas del bucle procedural `while True:` hacia los hooks ya existentes en `app/core/engine.py`:
     - `PreTickHook`: Sincronización temporal y liveness.
     - `AcquisitionHook`: Adquisición paralela de sockets y VNish.
     - `DetectionHook`: Clasificación de estados y rachas de anomalía.
     - `GovernanceHook`: Fan governor, balancer y contingencia de elevadores.
     - `ActuatorHook`: Ejecución de reinicios y cambios de preset.
     - `PersistenceHook`: Volcado seguro de estado a disco y SQLite.
  2. Reducir `main()` a:
     ```python
     def main() -> None:
         config = load_config()
         init_logger_from_config(config)
         mutex = acquire_mutex_or_exit(_mutex_name())
         try:
             engine = CoreSupervisoryEngine(config)
             engine.register_standard_hooks()
             engine.run_forever()
         finally:
             release_mutex()
     ```
  3. `app/miner_monitor.py` alcanza su tamaño objetivo: **$\le 500$ líneas**.
* **Verificación**: Suite global `pytest -q` (1520 tests PASS), `preflight_stabilize.ps1` (8/8 gates PASS).
