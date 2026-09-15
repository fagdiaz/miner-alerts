# Feature Specification: Spec 060 — Monitor Core Daemon & State Manager Architecture (ST-01 / ST-02 - Milestone V5.0)

**Feature Directory**: `specs/060-core-daemon-state-architecture`  
**Created**: 2026-09-15  
**Status**: Implemented & Certified (Phases A & B)  
**Initiative**: ST-01 / ST-02 (Horizonte V5.0 — Core Modularization)  
**Input**: Desacoplar el bucle principal de supervisión y la persistencia de estado fuera de variables globales procedurales en `app/miner_monitor.py` mediante una arquitectura de contenedor de dependencias (`MonitorContext`), un gestor atómico de persistencia con jerarquía estricta L1/L2 (`StateManager`) y un orquestador del ciclo de 30s con hooks desacoplados (`CoreSupervisoryEngine`), asegurando cero regresiones en los 928 tests y preservando los contratos de inspección estática en Windows.

---

## User Scenarios & Testing

### User Story 1 - Persistencia Atómica con Jerarquía Anti-Deadlock L1->L2 (Priority: P1)

Como desarrollador del sistema de monitoreo, deseo que la construcción del payload de estado en memoria ocurra bajo `state_lock` (L1), pero que el volcado a disco y sincronización física (`os.fsync`) ocurra fuera de `state_lock` bajo `_SAVE_STATE_LOCK` (L2) a través de `StateManager`, para eliminar retrasos de 10-200ms en Windows NTFS y prevenir cualquier riesgo de contención o deadlock con los hilos de Telegram o telemetría.

**Why this priority**: Garantiza la integridad del archivo `state.json` y elimina la contención de locks en el hilo autoritativo.

**Independent Test**: Invocar `StateManager.save(states, last_update_id)` verificando que crea `state.json`, genera copia de seguridad `state.json.bak` y libera `state_lock` antes de iniciar el I/O a disco.

---

### User Story 2 - Inyección de Dependencias Limpia con MonitorContext (Priority: P1)

Como arquitecto del software, deseo que todas las dependencias en tiempo de ejecución (configuración, locks, rutas, cola de Telegram, gestores de estado y gobernanza) estén encapsuladas en `MonitorContext`, eliminando el acoplamiento a variables globales mutables y permitiendo pruebas unitarias sin dependencias externas.

**Why this priority**: Base estructural del Milestone V5.0 para desacoplar el core del entrypoint del servicio.

---

### User Story 3 - Orquestación Desacoplada del Ciclo Supervisor con Hooks (Priority: P2)

Como mantenedor del servicio de monitoreo, deseo una abstracción `CoreSupervisoryEngine` que estructure el ciclo autoritativo de 30s en fases ordenadas y hooks registrados, devolviendo métricas de ejecución (`TickResult`) para telemetría y diagnósticos.

---

## Functional Requirements

1. **FR-01 (StateManager)**:
   - Crear `app/core/state_manager.py` con `StateManager`.
   - Implementar `build_payload` (en memoria bajo `state_lock`), `flush_payload` (I/O bajo `flush_lock`), `save` (coordinación atómica L1->L2), `get_state` y `update_state`.
2. **FR-02 (MonitorContext)**:
   - Crear `app/core/context.py` con `@dataclass MonitorContext` y la fábrica `build_monitor_context`.
   - Encapsular dependencias: `config`, `state_path`, `miners`, `bot_token`, `chat_id`, `state_lock`, `telegram_queue`, `state_manager`, `event_store`, flags QA, gobernanza, etc.
3. **FR-03 (CoreSupervisoryEngine)**:
   - Crear `app/core/engine.py` con `CoreSupervisoryEngine` y `TickResult`.
   - Soporte para registro de hooks `register_tick_hook`, ejecución de ticks y parada controlada `shutdown()`.
4. **FR-04 (Integración Aditiva en main())**:
   - Instanciar `state_manager` y `monitor_ctx` en `main()` de `app/miner_monitor.py`.
   - Preservar al 100% los contratos de inspección estática (`inspect.getsource(main)`) requeridos por las suites de pruebas existentes.
5. **FR-05 (Pruebas Unitarias)**:
   - Crear `tests/test_core_daemon.py` validando la persistencia de `StateManager`, validación de `MonitorContext` y ejecución de hooks de `CoreSupervisoryEngine`.
