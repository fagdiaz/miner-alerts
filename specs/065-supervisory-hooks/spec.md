# Feature Specification: Spec 065 — Pipeline Declarativo de Hooks en CoreSupervisoryEngine (ST-04)

## Status
- **Date**: 2026-09-15
- **Priority**: P2 (Media) | **Risk**: Medio
- **Modules**: `app/core/engine.py`, `app/core/context.py`, `app/miner_monitor.py`, `tests/test_supervisory_hooks.py`
- **Baseline**: 996 tests PASS, Windows Service `MinerAlerts` Running.

---

## 1. Problem Statement & Motivation
En la Spec 060 (Milestone V5.0) se formalizó el contenedor de dependencias `MonitorContext` y se introdujo la clase `CoreSupervisoryEngine`.
Sin embargo, el ciclo de supervisión de 30 segundos dentro de `main()` en `miner_monitor.py` aún mantiene una estructura monolítica debido a la necesidad de preservar contratos literales evaluados por tests legados basados en `inspect.getsource(main)`.

Para completar la evolución modular de la arquitectura sin riesgos de regresión operativa en producción:
1. **Falta de Pipeline Formal de Etapas**: El motor requiere una abstracción formal de etapas (`HookStage`) y hooks registrables (`SupervisoryHook`), ordenados deterministamente: Pre-Tick, Adquisición, Detección, Gobernanza, Actuación, Persistencia y Post-Tick.
2. **Aislamiento Defensivo de Fallos**: La falla de un hook específico (ej. un actuador o cálculo de métricas) no debe colapsar el ciclo de 30s ni impedir que la etapa de persistencia (`PersistenceHook`) o el latido de liveness se ejecuten.
3. **Control Estricto del Modelo de Tiempo Monotónico**: En Windows, si una etapa (ej. I/O de disco o red) experimenta latencia, el intervalo `poll_seconds` debe descontar exactamente el tiempo transcurrido (`sleep_remaining = max(0.0, poll_seconds - (time.monotonic() - tick_start))`), evitando jitter y deriva temporal.
4. **Preservación Inviolable de Contratos de Test**: Los 4 tests existentes de `inspect.getsource(main)` (`test_auto_reboot_signal_gate`, `test_hashboard_auto_reboot`, `test_reboot_safety`, `test_vnish_hashboard_detection`) deben permanecer 100% compatibles sin una sola regresión (`len(tests_pass) >= 996`).

---

## 2. User Stories
- **US-01 (Pipeline Extensible y Modular)**: Como desarrollador del motor, deseo registrar hooks de supervisión tipados y organizados por etapas en `CoreSupervisoryEngine` para que nuevas capacidades de telemetría y gobierno puedan añadirse de forma limpia y desacoplada.
- **US-02 (Contención y Tolerancia a Fallos)**: Como operador de la flota, requiero que si un hook de actuador o métricas arroja una excepción no controlada, el error se capture en `TickResult.errors` y el ciclo continúe ejecutando la persistencia atómica y el latido sin reiniciar el servicio.
- **US-03 (Determinismo Temporal Monotónico en Windows)**: Como administrador de sistemas, requiero que el ciclo de supervisión mantenga su cadencia estricta de 30s usando `time.monotonic()` sin importar fluctuaciones en la duración del I/O de red o disco.

---

## 3. Functional Requirements

### FR-01: Modelo Declarativo de Hooks y Etapas (HookStage & SupervisoryHook)
- Definir el enum o clases de etapas `HookStage`:
  * `PRE_TICK`: Inicialización de contadores y marcas de tiempo del tick.
  * `ACQUISITION`: Muestreo concurrente de telemetría hacia los mineros.
  * `DETECTION`: Evaluación de máquinas de estado y detección de incidentes.
  * `GOVERNANCE`: Interlocks de seguridad (Blackout Guard, Maintenance Window, Master Switch).
  * `ACTUATOR`: Disparo de acciones sobre hardware (reboot, presets, coolers).
  * `PERSISTENCE`: Volcado atómico a disco vía `StateManager.save()` fuera de locks.
  * `POST_TICK`: Métricas de ciclo, latido de liveness y publicación de estado.
- Implementar la clase base `SupervisoryHook` con interfaz:
  ```python
  class SupervisoryHook:
      name: str
      stage: HookStage
      def execute(self, context: MonitorContext, tick_sequence: int, now_ts: float, tick_data: Dict[str, Any]) -> Optional[Dict[str, Any]]: ...
  ```

### FR-02: Pipeline Dispatcher en CoreSupervisoryEngine
- Extender `CoreSupervisoryEngine` para soportar:
  * `register_hook(hook: SupervisoryHook) -> None` ordenando los hooks por precedencia de `HookStage`.
  * `execute_tick(states: Dict[str, Any], last_update_id_ref: Dict[str, Optional[int]], now_ts: float) -> TickResult`.
  * Contención de excepciones: cada hook se envuelve en bloque defensivo `try ... except Exception as exc:`, registrando el fallo en `TickResult.errors` sin detener la ejecución de las etapas subsiguientes.

### FR-03: Implementación de Hooks Canónicos
- `PersistenceHook`: Encapsula la llamada atómica a `context.state_manager.save(states, last_update_id)`.
- `GovernanceInterlockHook`: Evalúa expiración de temporizadores de gobernanza y guardas de contingencia.
- `TimingGuardHook`: Mide duraciones y valida el cumplimiento del presupuesto temporal por tick.

### FR-04: Modelo Monotónico de Tiempo y Prevención de Deriva
- Verificar que el cálculo de reposo en `run()` use exclusivamente:
  ```python
  elapsed = time.monotonic() - tick_start
  sleep_seconds = max(0.0, poll_seconds - elapsed)
  self._shutdown_event.wait(timeout=sleep_seconds)
  ```
- Si `elapsed >= poll_seconds`, `sleep_seconds = 0.0` y el siguiente tick se inicia sin retraso acumulativo.

### FR-05: Invariante de Contratos de Test
- No modificar las cadenas literales en `main()` de `miner_monitor.py` requeridas por `test_auto_reboot_signal_gate.py`, `test_hashboard_auto_reboot.py`, `test_reboot_safety.py` y `test_vnish_hashboard_detection.py`.
- Integrar la invocación del pipeline de forma aditiva y transparente.

---

## 4. Verification Gate
1. `& ".\.venv\Scripts\python.exe" -m py_compile app\core\engine.py app\core\context.py app\miner_monitor.py`
2. Suite dedicada `tests/test_supervisory_hooks.py` cubriendo:
   - Orden estricto de etapas (Pre-Tick a Post-Tick).
   - Aislamiento de excepciones en hooks.
   - Validación de timing monotónico (simulación de hooks rápidos vs lentos).
   - Persistencia atómica desacoplada.
3. 996+ tests globales PASS sin regresiones.
4. Servicio Windows `MinerAlerts` en estado `Running`.
