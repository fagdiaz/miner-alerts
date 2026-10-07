# Tasks: Descomposición y Modularización del Monolito (`miner_monitor.py`)

**Feature**: `087-monolith-decoupling`  
**Baseline**: 1520 tests PASS, 75 subtests PASS  
**Target Outcome**: Reducción neta de `miner_monitor.py` de 9.074 L a $\le 500$ L en 5 fases acotadas.

---

## Fase 1: Desacoplamiento de Callbacks de Telegram (~1.450 L eliminadas)

- [ ] **T001** [P1] [Riesgo Bajo]: Migrar `_handle_command_center_callback` (L3755-L4261) de `miner_monitor.py` a `app/telegram/command_center.py` y actualizar dependencias internas.
- [ ] **T002** [P1] [Riesgo Bajo]: Migrar `_handle_help_callback` (L4262-L4307) a `app/telegram/help_center.py`.
- [ ] **T003** [P1] [Riesgo Bajo]: Migrar `_handle_diagnostic_callback` (L4308-L4547) y `_handle_callback_query` (L4548-L5228) a `app/telegram/callbacks.py`.
- [ ] **T004** [P1] [Riesgo Bajo]: Actualizar `app/telegram/router.py` para enrutar directamente a las funciones dentro de `app.telegram.*` sin pasar por `miner_monitor.py`.
- [ ] **T005** [P1] [Riesgo Bajo]: Crear shims de compatibilidad en `miner_monitor.py` re-exportando los handlers y verificar que `tests/test_telegram_callbacks.py` pase al 100%.

---

## Fase 2: Extracción de Gobernanza Restante (Spec 087) (~850 L eliminadas)

- [ ] **T006** [P1] [Riesgo Medio]: Crear `app/governance/balancer_cycle.py` y extraer `execute_balancer_cycle` (L3362-L3614).
- [ ] **T007** [P1] [Riesgo Medio]: Extraer `check_autotune_watchdog` (L3615-L3754) como `execute_autotune_watchdog_cycle` en `app/governance/autotune_watchdog.py`.
- [ ] **T008** [P1] [Riesgo Bajo]: Re-exportar ambas funciones en `miner_monitor.py` y conectarlas en el bucle principal.
- [ ] **T009** [P1] [Riesgo Bajo]: Validar con `tests/test_governor_cycle.py` y `tests/test_autotune_watchdog.py` sin regresiones.

---

## Fase 3: Extracción de Telemetría de Cadenas & Sockets ASIC (~1.000 L eliminadas)

- [ ] **T010** [P1] [Riesgo Medio]: Crear `app/hardware/chain_collector.py` y migrar `_async_collect_chain_telemetry` y `_async_evaluate_predictive_chain_break` (L2944-L3361).
- [ ] **T011** [P1] [Riesgo Bajo]: Eliminar funciones duplicadas de socket 4028 (`read_summary`, `read_stats_snapshot`, etc.) en `miner_monitor.py` reutilizando `app/network/cgminer_client.py`.
- [ ] **T012** [P1] [Riesgo Bajo]: Mover formateadores de texto (`build_stability_health_text`, `build_mining_quality_text`, etc.) a `app/telegram/fleet_cards.py`.
- [ ] **T013** [P1] [Riesgo Bajo]: Validar suite de hardware y telemetría (`test_chain_health.py`, `test_mining_quality.py`).

---

## Fase 4: Modernización del Test Legacy de `inspect.getsource(main)`

- [ ] **T014** [P1] [Riesgo Bajo]: Refactorizar `TestStartupGraceInvariantContracts` en `tests/test_startup_grace_period.py:218-250`.
- [ ] **T015** [P1] [Riesgo Bajo]: Reemplazar las aserciones de índices de texto (`source.index(...)`) por llamadas al `SupervisoryBehavioralHarness` asegurando equivalencia funcional 100%.
- [ ] **T016** [P1] [Riesgo Bajo]: Ejecutar `pytest tests/test_startup_grace_period.py` y certificar que no dependa del texto plano de `main()`.

---

## Fase 5: Conversión del Bucle `main()` en Pipeline de Hooks Declarativo (~4.800 L eliminadas)

- [ ] **T017** [P0] [Riesgo Medio]: Encapsular la inicialización de `main()` (bootstrap, IPC pipe, EventStore, mutex) en `CoreSupervisoryEngine.initialize()`.
- [ ] **T018** [P0] [Riesgo Medio]: Conectar las lógicas internas del `while True:` a los hooks declarativos correspondientes (`PreTick`, `Acquisition`, `Detection`, `Governance`, `Actuator`, `Persistence`, `PostTick`) en `app/core/engine.py`.
- [ ] **T019** [P0] [Riesgo Medio]: Reducir `main()` en `app/miner_monitor.py` a $\le 500$ líneas invocando `engine.run_forever()`.
- [ ] **T020** [P0] [Riesgo Alto]: Ejecutar suite completa `pytest -q` garantizando $\ge 1520$ tests PASS, correr `preflight_stabilize.ps1` (8/8 gates PASS), reiniciar servicio NSSM en Windows y certificar cero anomalías en planta.
