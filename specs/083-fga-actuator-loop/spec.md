# Feature Specification: FGA Actuator Loop — Conexión FGA → Elevator Budget → VNish

**Feature Branch**: `083-fga-actuator-loop`

**Created**: 2026-10-01

**Status**: Draft

**PROP**: PROP-019

---

## Contexto y Motivación

El Agente de Gobernanza de Planta (**Facility Governance Agent - FGA**), introducido en la Spec 079 (PROP-015), provee modelado térmico empírico de silicio ($R_{th}$), clasificación en cohortes (`COOL`, `STANDARD`, `HOT`) y cálculo de distribución óptima y asimétrica de potencia (`evaluate_asymmetric_allocation`).

Sin embargo, hasta la Spec 082, el FGA ha operado como un motor de diagnóstico pasivo:
1. **Ausencia de Actuador**: Sus decisiones de asignación óptima (`candidate_step`) no se despachan hacia la infraestructura física ni interactúan con el orquestador de elevadores.
2. **Fricción de Telemetría Residual (F-04)**: Cuando un minero tiene un reinicio pendiente (`restart_required=True`), el cálculo de $R_{th}$ utilizando potencia nominal o configurada produce valores distorsionados, falseando la cohorte del minero.
3. **Falta de Trazabilidad Histórica de Acciones**: Las recomendaciones intermedias no quedan registradas en una tabla dedicada de auditoría en la base de datos persistente.
4. **Falta de Ejecución On-Demand**: El operador en Telegram puede consultar `/agent` y `/strategy`, pero no puede solicitar una evaluación y aplicación inmediata (`/agent run`).

Con el contrato de estado inmutable [`MinerGovernanceContext`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/governance_context.py) certificado en la Spec 082, la Spec 083 cierra el lazo: el FGA consume dicho contexto, calcula las recomendaciones con potencia real ejecutada, somete cualquier cambio al control de compuertas eléctricas y térmicas de [`elevator_budget.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/elevator_budget.py) (Gates 0 a 6), ejecuta cambios de preset autorizados mediante VNish, persiste la auditoría en SQLite y provee control interactivo en Telegram.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Optimización Asimétrica Autónoma de la Planta (Priority: P1)

Como operador de la granja minera, deseo que el sistema redistribuya dinámicamente la potencia de los mineros según su eficiencia térmica individual (asignando mayor potencia al silicio frío y menor potencia al silicio cálido) dentro de los límites seguros de los elevadores eléctricos, para maximizar la producción global de hashrate sin requerir intervención manual constante.

**Por qué P1**: Es el núcleo de valor del FGA: pasar de un modelo estático y reactivo a una optimización activa y continua de la flota respetando la capacidad de los transformadores.

**Independent Test**: Simular un entorno donde un minero tiene silicio frío (`COOL`, $R_{th} \le 0.020$) y otro silicio estándar en el mismo elevador, verificar que el FGA genera un `candidate_step` hacia 2700W para el minero frío, que pasa los Gates 0-6 del Elevator Budget, y que se ejecuta la transición si los presupuestos lo permiten.

**Acceptance Scenarios**:

1. **Given** una flota donde un minero califica como `COOL` y los elevadores tienen margen de potencia disponible,
   **When** el lazo de gobernanza FGA evalúa la asignación asimétrica,
   **Then** emite un `candidate_step` para elevar el minero `COOL` a 2700W, verifica las compuertas del `ElevatorBudget` y ejecuta la modulación en el firmware si todas las compuertas (Gates 0 a 6) lo autorizan.

2. **Given** un minero que se encuentra operando con `restart_required=True` y potencia real medida de 2500W,
   **When** el FGA calcula su resistencia térmica $R_{th}$,
   **Then** utiliza la potencia real ejecutada (`current_power_w`) provista por `MinerGovernanceContext` y no el target configurado de 2700W, evitando clasificaciones espurias de cohorte (resolución de F-04).

3. **Given** una recomendación del FGA para incrementar un minero a 2700W,
   **When** el elevador correspondiente se encuentra dentro de la ventana de reposo de acometida (`is_facility_in_settle`) o reposo de incidente (`is_group_in_incident_quiet`),
   **Then** la compuerta correspondiente bloquea la acción, no se altera el preset en el minero, y la retención se registra con su causa determinista.

---

### User Story 2 — Trazabilidad y Auditoría Persistente de Decisiones FGA (Priority: P2)

Como responsable de mantenimiento de la infraestructura, necesito que cada recomendación, bloqueo o ejecución efectuada por el FGA quede registrada de forma durable e indexada en la base de datos local SQLite, para poder auditar el comportamiento del agente y correlacionarlo con eventos térmicos o eléctricos pasados.

**Por qué P2**: La autonomía sin auditabilidad introduce incertidumbre y dificulta la detección de anomalías operativas.

**Independent Test**: Ejecutar un ciclo donde el FGA propone un cambio de preset, verificar que se inserte un registro en la tabla `facility_agent_actions` de `EventStore` conteniendo timestamp, minero, preset origen, preset destino, estrategia, compuerta evaluada y resultado.

**Acceptance Scenarios**:

1. **Given** un ciclo donde el FGA evalúa un cambio de preset,
   **When** la acción es autorizada o bloqueada por una compuerta,
   **Then** se registra un evento estructurado en SQLite con los detalles de la decisión y la telemetría asociada.

2. **Given** un operador consultando el historial de intervenciones del FGA,
   **When** se solicita la consulta de eventos recientes,
   **Then** el sistema devuelve las últimas acciones registradas con indicación de éxito o causa de bloqueo.

---

### User Story 3 — Interacción y Control Operativo On-Demand vía Telegram (Priority: P2)

Como operador móvil, deseo poder disparar una evaluación manual del FGA mediante el comando `/agent run` desde Telegram y recibir una tarjeta concisa con el diagnóstico, las compuertas evaluadas y la acción ejecutada o rechazada.

**Por qué P2**: Permite al operador validar o forzar la optimización tras mantenimientos o cambios de temperatura ambiente sin esperar el próximo ciclo periódico del monitor.

**Independent Test**: Enviar `/agent run` en un entorno de pruebas y verificar que se ejecuta la evaluación completa, se responde con un mensaje formateado en $\le 32$ columnas y se informa la decisión exacta tomada.

**Acceptance Scenarios**:

1. **Given** el bot de Telegram activo en producción o QA,
   **When** el usuario envía el comando `/agent run`,
   **Then** el sistema ejecuta una evaluación sincrónica/asincrónica segura de `evaluate_asymmetric_allocation()`, somete el candidato al `ElevatorBudget` y responde con el resumen de la acción y el estado de los elevadores en $\le 32$ columnas.

2. **Given** el comando `/agent` invocado sin argumentos,
   **When** se presenta el dashboard ejecutivo,
   **Then** se incluye la indicación del comando `/agent run` y el estado de la última acción ejecutada.

---

### Edge Cases

- **Ausencia de telemetría de potencia o chips**: Si un minero no reporta temperatura de chips o potencia real (o potencia < 500W en fase de arranque), el FGA debe asignar la resistencia térmica nominal por defecto (`DEFAULT_THERMAL_RESISTANCE = 0.022`) y no proponer escalamientos agresivos.
- **Minero en fase de gracia de arranque (`is_warming_up = True`)**: El FGA no debe emitir candidatos de cambio de preset para máquinas que están en calentamiento o autotuning inicial.
- **Bloqueo de intervenciones en configuración (`presets_enabled = False`)**: Si la gobernanza autónoma de presets está desactivada por el operador, el FGA puede evaluar y registrar recomendaciones diagnósticas pero tiene terminantemente prohibido llamar a `safe_set_miner_preset`.
- **Fallo de comunicación con la API de VNish**: Si `safe_set_miner_preset` retorna error o timeout, el fallo debe registrarse en la auditoría sin interrumpir el ciclo del monitor ni afectar a otros mineros.
- **Saturación simultánea en múltiples mineros**: Si más de un minero requiere cambio de preset simultáneamente, el FGA debe priorizar una sola transición por ciclo para respetar la ventana de reposo de acometida (`DEFAULT_FACILITY_SETTLE_WINDOW_S = 180s`).

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El motor del FGA DEBE consumir `MinerGovernanceContext` (o su equivalente tipado) para obtener `current_power_w`, `chip_temp_c`, `inlet_temp_c`, `restart_required` y `is_warming_up` por cada minero.
- **FR-002**: El cálculo de resistencia térmica $R_{th}$ DEBE utilizar la potencia real medida (`current_power_w`) cuando `restart_required=True` y la potencia sea $\ge 500\text{ W}$, impidiendo el uso de objetivos desactualizados (Cierre de Fricción F-04).
- **FR-003**: El ciclo de gobernanza DEBE evaluar periódicamente las asignaciones del FGA contra el estado actual de los mineros para identificar si existe un `candidate_step`.
- **FR-004**: Todo `candidate_step` propuesto por el FGA DEBE ser validado a través de `evaluate_facility_transition_permission()` en `elevator_budget.py`, evaluando sin excepción los Gates 0 a 6 (Quiet Window, Settle Window, Hardware Ceiling, Solar Envelope, Thermal Headroom, Budget, Symmetry).
- **FR-005**: Si `evaluate_facility_transition_permission()` retorna `can_proceed=True` y las políticas de intervención lo autorizan, el sistema DEBE aplicar el nuevo preset mediante `safe_set_miner_preset()` con parámetros seguros de clamping.
- **FR-006**: Si una transición es autorizada y ejecutada con éxito, el sistema DEBE registrar la transición en `FacilityBudgetState` (`record_transition`) para iniciar la ventana de reposo de 180s en la acometida.
- **FR-007**: El sistema de almacenamiento (`EventStore`) DEBE disponer de una tabla dedicada `facility_agent_actions` para registrar cada intento de actuación del FGA, documentando timestamp, minero, preset anterior, preset propuesto, estrategia activa, compuerta evaluadora, resultado (`PERMITTED`, `BLOCKED`, `EXECUTED`, `FAILED`) y detalle explicativo.
- **FR-008**: El comando Telegram `/agent` DEBE soportar el subcomando `/agent run` para ejecutar una evaluación manual inmediata e informar el resultado al operador respetando el formato móvil ($\le 32$ columnas).
- **FR-009**: La ejecución del lazo FGA DEBE ser estrictamente no bloqueante respecto al ciclo principal de telemetría y adquisición de datos.

### Key Entities

- **FacilityAgentActionRecord**: Entidad que modela un evento de decisión/actuación del FGA persistido en SQLite. Atributos: `id`, `created_ts`, `miner_name`, `electrical_group`, `strategy`, `from_preset`, `to_preset`, `action_status` (`PROPOSED`, `BLOCKED`, `EXECUTED`, `FAILED`), `gate_name`, `reason`, `power_w`, `chip_temp_c`, `thermal_resistance`.
- **FGAActuatorBridge**: Componente desacoplado que orquesta la conexión entre `evaluate_asymmetric_allocation()`, `evaluate_facility_transition_permission()`, el despachador de firmware y el registro en `EventStore`.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de las decisiones de cambio de preset generadas por el FGA son evaluadas por los Gates 0 a 6 del `ElevatorBudget` antes de cualquier llamada a la API de hardware.
- **SC-002**: Ante condiciones de `restart_required=True`, el cálculo de $R_{th}$ en el FGA refleja la potencia real medida $P_{real}$ con 0% de desviación respecto a los datos del firmware.
- **SC-003**: Toda acción ejecutada o bloqueada del FGA queda persistida en la tabla `facility_agent_actions` en $\le 50\text{ ms}$ sin retener bloqueos de base de datos.
- **SC-004**: El comando Telegram `/agent run` responde al operador con la evaluación completa y la acción resultante en $\le 3.0\text{ segundos}$ en condiciones nominales.
- **SC-005**: La suite de pruebas automatizadas mantiene el 100% de aprobación (baseline $\ge 1466$ pruebas pasando, 0 fallos).
- **SC-006**: Las tarjetas y salidas de Telegram del FGA cumplen estrictamente con la restricción de diseño móvil de ancho $\le 32$ columnas.

---

## Assumptions

1. El módulo de hardware `safe_set_miner_preset` en `app/vnish/client.py` es la única vía autorizada para enviar modificaciones de preset a los mineros.
2. La base de datos SQLite opera en modo WAL con timeouts transaccionales configurados, permitiendo escrituras concurrentes sin colisiones con los workers de telemetría.
3. La estrategia por defecto del FGA sigue siendo `STRATEGY_BALANCED`, a menos que se configure explícitamente en `config.json` o mediante `/strategy`.
4. El nuevo lazo no altera las protecciones de P0 de hardware (Guardián Térmico a 84°C/87°C ni Failsafe al 100% de ventilación).
