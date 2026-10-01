# Feature Specification: Governance Dashboard (`/directivas`) & Snapshot Persistence

**Feature Branch**: `084-governance-dashboard`

**Created**: 2026-10-01

**Status**: Draft

**PROP**: PROP-020

---

## Contexto y Motivación

El sistema de gobernanza de **Miner Alerts** cuenta actualmente con **16 directivas activas distribuidas en 5 capas de prevalencia (P0 a P4)**:
1. **P0 (Inviolable)**: Thermal Guard (84°C step-down / 87°C pausa), Failsafe Fan (100% tras 3 fallos HTTP) y `ACTION_RECOVERY_MAX_COOLING` (100% PWM si potencia real < objetivo - 120W).
2. **P1 (Alta)**: Stock Firmware Fallback Block y Thermal Pause Interlock.
3. **P2 (Media-Alta)**: Soft Contingency Schedule (pico 5000W / valle 5400W), Solar Thermal Envelope (cap 2500W si 11:00-17:00 y T ≥ 82°C) y Thermal Headroom Gate (chip < 80°C para subir a 2700W).
4. **P3 (Media)**: Incident Quiet Window (300s post-incidente por grupo), Facility Settle Window (180s entre transiciones), Symmetric Balance Preference y FGA Asymmetric Optimizer (cohortes `COOL`/`STANDARD`/`HOT`).
5. **P4 (Baja)**: VNish Internal Daemon y Headroom Chilling (`boost_cooling` preventivo).

A pesar de que cada directiva opera de forma matemáticamente consistente y que la Spec 082 unificó los estados mediante [`MinerGovernanceContext`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/governance_context.py), **el operador no dispone de un panel unificado de observabilidad en tiempo real** para responder a preguntas críticas como:
- *¿Por qué un minero no sube a 2700W? ¿Está frenado por Gate 0 (Quiet), Gate 1 (Settle), Gate 3.1 (Headroom), o Solar Envelope?*
- *¿Qué acción está aplicando el Fan Governor en este instante y cuál es su tiempo de permanencia (`dwell_time`)?*
- *¿Se encuentra el minero en riesgo de quedar atrapado en un ciclo de enfriamiento forzado o deadlock de gobernanza?*

Durante el incidente del minero 24 (nudo F-01/F-02 documentado en la auditoría), el diagnóstico requirió la inspección manual de miles de líneas de logs. La **Spec 084 (PROP-020)** resuelve esta asimetría de información introduciendo:
1. **Dashboard móvil unificado en Telegram** (`/directivas`, con alias `/gov_status` y `/gov`) con ancho estricto $\le 32$ columnas, desglose por minero y vista resumida de flota.
2. **Persistencia periódica de `governance_snapshots`** en SQLite (EventStore), registrando cada ciclo el estado consolidado de directivas para auditoría forense histórica y base del futuro *Incident Autopsy Engine* (Spec 086).
3. **Watchdog Proactivo de Deadlocks**: Alerta temprana si un minero acumula más de 300 segundos continuos en `ACTION_RECOVERY_MAX_COOLING` sin converger hacia la potencia objetivo.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Diagnóstico Móvil Instantáneo de Directivas vía Telegram (Priority: P1)

Como operador de la planta, deseo ejecutar el comando `/directivas` (o `/directivas [minero]`) desde Telegram para visualizar en menos de 10 segundos el estado exacto de todas las directivas activas sobre la flota, identificando inmediatamente si alguna compuerta o directiva de protección está bloqueando la operación esperada.

**Por qué P1**: Es la interfaz de usuario directa que elimina la necesidad de conectarse por SSH o leer archivos de logs para entender el comportamiento de la gobernanza.

**Independent Test**: Invocar `/directivas` en Telegram (o simulación en tests unitarios) y verificar que responde con una tarjeta formateada $\le 32$ columnas que incluye el estado de Fan Governor, Elevator Budget (último Gate evaluado), Solar Thermal Envelope, Cohorte FGA y bandera `restart_required`.

**Acceptance Scenarios**:

1. **Given** una flota con 4 mineros operando normalmente a 2700W,
   **When** el operador ejecuta `/directivas`,
   **Then** el bot devuelve una tarjeta compacta de resumen de flota con semáforos por minero, potencia ejecutada/objetivo, estado del Fan Governor y compuerta de elevador activa.

2. **Given** un minero específico (ej: `S19JPRO-24`),
   **When** el operador ejecuta `/directivas S19JPRO-24` (o `/directivas 24`),
   **Then** el bot devuelve una tarjeta detallada con:
   - Fan Action y Duty actual (`HOLD_TARGET 92%`).
   - Margen térmico y temperatura de chips vs umbrales críticos.
   - Estado de compuertas del Elevator Budget (Gate 0 Quiet, Gate 1 Settle, Gate 3.1 Headroom, Gate 4 Contingency).
   - Cohorte FGA y resistencia térmica $R_{th}$.
   - Bandera `restart_required` (activa/inactiva y antigüedad).

3. **Given** un minero con transición bloqueada por compuerta térmica (`chip_temp_c >= 80.0°C`),
   **When** se inspecciona `/directivas`,
   **Then** la tarjeta resalta claramente el bloqueo: `GATE: HEADROOM (80.5°C >= 80.0°C)`.

---

### User Story 2 — Registro Histórico Persistente de Instantáneas de Gobernanza (Priority: P2)

Como ingeniero de confiabilidad, necesito que el monitor persista periódicamente una instantánea consolidada de gobernanza (`governance_snapshots`) en la base de datos SQLite para cada minero, de modo que podamos realizar auditorías temporales, análisis de correlación y alimentar herramientas forenses autónomas.

**Por qué P2**: Sin almacenamiento persistente, la observabilidad en vivo se pierde ante caídas o reinicios del proceso monitor y no permite trazar la evolución temporal de las compuertas.

**Independent Test**: Ejecutar un ciclo del monitor y consultar la tabla `governance_snapshots` en `EventStore`, comprobando que se inserten filas con timestamp, `miner_name`, `fan_action`, `fan_duty`, `target_power_w`, `current_power_w`, `chip_temp_c`, `fga_cohort`, `fga_r_th`, `elevator_gate_status` e `is_deadlocked`.

**Acceptance Scenarios**:

1. **Given** el monitor ejecutando ticks de adquisición y gobernanza,
   **When** concluye la evaluación del Fan Governor y Elevator Budget en cada tick,
   **Then** se inserta un registro en la tabla `governance_snapshots` de `EventStore` para cada minero evaluado.

2. **Given** la necesidad de auditar el comportamiento histórico de un minero,
   **When** se invoca el método `event_store.get_recent_governance_snapshots(miner_name, limit=50)`,
   **Then** se devuelven los registros más recientes ordenados en orden cronológico inverso (`created_ts DESC`).

3. **Given** la ejecución de la política de retención periódica (`cleanup_retention`),
   **When** los registros de `governance_snapshots` superan el período de retención configurado (por defecto 7 días),
   **Then** se depuran de forma segura sin bloquear las lecturas/escrituras concurrentes en WAL.

---

### User Story 3 — Detección y Alerta Temprana de Deadlocks de Enfriamiento (Priority: P2)

Como administrador del sistema, deseo recibir una notificación proactiva en Telegram si un minero queda atrapado en `ACTION_RECOVERY_MAX_COOLING` (100% ventiladores) durante más de 300 segundos continuos sin que su potencia converja al target, para intervenir antes de que se produzca desgaste innecesario de ventiladores o bloqueo de ascensos de potencia.

**Por qué P2**: Previene la recurrencia no detectada del nudo M24 (fricción F-02), donde los ventiladores permanecieron al 100% durante horas sin necesidad operativa.

**Independent Test**: Simular un minero con `action=ACTION_RECOVERY_MAX_COOLING` y `recovery_duration > 300.0s`, verificar que el monitor marque `is_deadlocked=1` en la instantánea y despache una alerta única hacia Telegram respetando un cooldown de 1800s.

**Acceptance Scenarios**:

1. **Given** un minero que ingresa en `ACTION_RECOVERY_MAX_COOLING` por discrepancia de potencia (`current_w < target_w - 120W`),
   **When** el tiempo acumulado en recuperación excede los 300 segundos continuos,
   **Then** el sistema registra `is_deadlocked = 1` en la instantánea de gobernanza y emite una alerta estructurada en Telegram con el diagnóstico del posible estancamiento y recomendaciones de acción (ej: verificar `restart_required` o conmutador de preset).

2. **Given** una alerta de deadlock ya enviada,
   **When** el minero continúa en la misma condición en los ticks subsiguientes dentro del período de cooldown (1800s),
   **Then** no se reenvía la alerta para evitar spam al operador, pero el estado `is_deadlocked` se mantiene registrado.

---

### Edge Cases

- **Minero en arranque / calentamiento (`is_warming_up=True`)**: Las compuertas de elevadores y fan governor pueden mostrar estados transitorios; la tarjeta de directivas debe marcar claramente el indicador `[WARMING UP]` y suprimir alertas de deadlock.
- **Falta de telemetría de chips o potencia**: Si el minero no respondió en el tick actual, el snapshot debe registrar `fan_action = 'UNKNOWN'`, compuerta `NO_TELEMETRY` y valores nulos/por defecto seguros.
- **Comando `/directivas` con minero inexistente**: Si el operador solicita `/directivas M99`, el bot debe responder amablemente con la lista de mineros válidos en $\le 32$ columnas.
- **Formato estricto para Telegram**: Las tarjetas no deben exceder 32 caracteres por línea bajo ningún concepto, garantizando visualización sin saltos de línea antiestéticos en clientes móviles Android/iOS.
- **Tolerancia a fallos de persistencia**: Un error de escritura en SQLite no debe interrumpir el ciclo de gobernanza del monitor ni impedir la respuesta de comandos en Telegram.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE implementar el comando de Telegram `/directivas` y sus alias `/gov_status` y `/gov`.
- **FR-002**: El comando `/directivas` sin argumentos DEBE devolver una tarjeta ejecutiva de la flota consolidando el estado de gobernanza de cada minero en ancho $\le 32$ columnas.
- **FR-003**: El comando `/directivas <minero>` DEBE devolver una tarjeta detallada con el estado de las 5 capas de directivas para el minero especificado en ancho $\le 32$ columnas.
- **FR-004**: `EventStore` DEBE crear de forma aditiva la tabla `governance_snapshots` con índices temporales y por minero, soportando migraciones automáticas sin pérdida de datos.
- **FR-005**: `EventStore` DEBE proveer métodos `record_governance_snapshot(...)` y `get_recent_governance_snapshots(miner_name, limit)` con manejo seguro de concurrencia y conexiones WAL.
- **FR-006**: El ciclo del monitor DEBE evaluar y registrar periódicamente en cada tick una instantánea de gobernanza por cada minero activo.
- **FR-007**: El monitor DEBE detectar condiciones de estancamiento (`is_deadlocked`): `action == ACTION_RECOVERY_MAX_COOLING` acumulado por $> 300$ segundos sin resolución, y registrar dicha bandera en la instantánea.
- **FR-008**: El monitor DEBE despachar una alerta proactiva a Telegram ante la detección de un deadlock, sujeta a un cooldown mínimo de 1800 segundos por minero para evitar repetición excesiva.

---

### Key Entities

- **`GovernanceSnapshot`**: Entidad de datos que encapsula el estado instantáneo de todas las directivas que actúan sobre un minero en un timestamp dado (`miner_name`, `fan_action`, `fan_duty`, `target_power_w`, `current_power_w`, `chip_temp_c`, `fga_cohort`, `fga_r_th`, `elevator_group`, `elevator_gate_status`, `solar_envelope_active`, `contingency_mode`, `restart_required`, `is_deadlocked`, `details_json`).
- **`DirectiveStatusCard`**: Objeto visual formateador que transforma un `MinerGovernanceContext` o un `GovernanceSnapshot` en bloques de texto Markdown monoespaciados $\le 32$ columnas aptos para Telegram.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El operador puede diagnosticar en menos de 10 segundos la directiva y compuerta exacta que rige a cualquier minero invocando `/directivas` desde su móvil.
- **SC-002**: El 100% de las tarjetas generadas por `/directivas` y `/directivas <minero>` cumplen la restricción de ancho móvil $\le 32$ caracteres por línea.
- **SC-003**: Persistencia completa de instantáneas en SQLite con sobrecarga de tiempo de CPU inferior a 5 milisegundos por ciclo en el tick del monitor.
- **SC-004**: Cero regresiones en la suite de pruebas del proyecto (1477 tests existentes PASS + nuevos tests de gobernanza y comandos).

---

## Assumptions

- Las 16 directivas identificadas en `docs/audit/DIRECTIVES_HARMONIZATION_AUDIT.md` continúan siendo la referencia de gobernanza del sistema.
- El contrato `MinerGovernanceContext` establecido en la Spec 082 es la fuente canónica de telemetría y estado para la generación de la tarjeta y la instantánea.
- El almacenamiento en SQLite bajo WAL soporta escrituras concurrentes sin bloquear las consultas de telemetría ni los comandos de Telegram.
- La alerta proactiva de deadlock utiliza el canal configurado de alertas de Telegram de Miner Alerts.
