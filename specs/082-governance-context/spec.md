# Feature Specification: MinerGovernanceContext — Contrato de Estado Centralizado

**Feature Branch**: `082-governance-context`

**Created**: 2026-10-01

**Status**: Draft

**PROP**: PROP-018

---

## Contexto y Motivación

El sistema de gobernanza de miner-alerts tiene 6 subsistemas semi-autónomos que
toman decisiones sobre los mineros: Fan Governor, Elevator Budget, Thermal Guard,
Facility Governance Agent (FGA), Auto-Restart Watchdog, y el nuevo Restart Required
Watchdog (Spec 081). Cada subsistema recibe su propio conjunto de parámetros dispersos,
lo que genera visibilidad parcial del estado global. La auditoría de 2026-10-01
documentó 8 fricciones, siendo la más crítica el "nudo M24": 3 subsistemas
correctos individualmente crearon un deadlock colectivo porque ninguno tenía
visibilidad completa del estado del otro.

Esta spec establece `MinerGovernanceContext`: un contrato de estado único, tipado
e inmutable que todos los subsistemas de gobernanza consumen como fuente de verdad.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — El sistema detecta y resuelve deadlocks de gobernanza autónomamente (Priority: P1)

El operador espera que la flota opere de forma autónoma sin intervención humana
ante situaciones de bloqueo entre subsistemas (como el nudo M24). Con el contrato
de estado centralizado, cada subsistema tiene visibilidad completa del estado
actual del minero y puede tomar decisiones correctas sin asumir sobre lo que
otro subsistema ya decidió.

**Por qué P1**: Elimina la clase de errores más costosa: los deadlocks silenciosos
que degradan la producción sin disparar alertas.

**Independent Test**: Inyectar un `MinerGovernanceContext` con `restart_required=True`
y `current_power_w=2498` en el Fan Governor y verificar que no activa
`ACTION_RECOVERY_MAX_COOLING` (ya resuelto empíricamente, ahora contractual).

**Acceptance Scenarios**:

1. **Given** un minero con `restart_required=True` y potencia real 2498W,
   **When** el Fan Governor evalúa la decisión,
   **Then** usa `current_power_w` como target efectivo (no el target configurado 2700W)
   y NO activa `ACTION_RECOVERY_MAX_COOLING`.

2. **Given** un `MinerGovernanceContext` con `thermal_pause_active=True`,
   **When** el Restart Required Watchdog evalúa si ejecutar un restart,
   **Then** devuelve `hold` sin ejecutar nada.

3. **Given** un `MinerGovernanceContext` con `fga_cohort="HOT"` y `chip_temp_c=83.0`,
   **When** el Elevator Budget evalúa una solicitud de ascenso a 2700W,
   **Then** la solicitud es bloqueada por el Thermal Headroom Gate.

---

### User Story 2 — Cada spec futura de gobernanza tiene un contrato claro de qué puede leer y mutar (Priority: P2)

Un modelo de IA o desarrollador que implementa una spec nueva de gobernanza
puede inspeccionar `MinerGovernanceContext` y saber exactamente qué campos
están disponibles y cuáles pertenecen a su dominio, sin necesidad de leer
miles de líneas de `miner_monitor.py`.

**Por qué P2**: Reduce el tiempo de implementación de specs futuras y elimina
el riesgo de que un subsistema acceda a estado que no le corresponde.

**Independent Test**: Los tests de contrato en `test_governance_context_contracts.py`
validan que cada subsistema solo accede a los campos de su dominio.

**Acceptance Scenarios**:

1. **Given** una instancia de `MinerGovernanceContext` construida desde `MinerState`,
   **When** el Fan Governor la consume,
   **Then** solo accede a los campos del dominio térmico/potencia (no a preset ni a FGA cohort).

2. **Given** una instancia de `MinerGovernanceContext`,
   **When** se intenta mutar cualquier campo,
   **Then** el dataclass es inmutable (frozen=True) y lanza `FrozenInstanceError`.

---

### User Story 3 — Integración transparente con el ciclo existente sin regresiones (Priority: P1)

El `MinerGovernanceContext` se construye en el ciclo principal de `miner_monitor.py`
y se pasa a los subsistemas. Los subsistemas existentes siguen funcionando exactamente
igual si no reciben el contexto (compatibilidad hacia atrás garantizada mediante
parámetros opcionales). La suite de 1440 tests pasa sin regresiones.

**Por qué P1**: Un cambio arquitectónico que rompe la suite o cambia comportamiento
en producción es inaceptable.

**Independent Test**: Ejecutar `pytest` después de la implementación y verificar
1440+ tests PASS. Ejecutar el ciclo de gobernanza en QA mode y confirmar que los
logs son idénticos a antes de la spec.

**Acceptance Scenarios**:

1. **Given** el ciclo de gobernanza en producción,
   **When** se construye `MinerGovernanceContext` desde `MinerState`,
   **Then** no hay excepciones, el ciclo completa en el tiempo normal (< 2.5s por minero).

2. **Given** una llamada a `compute_governor_step()` sin el parámetro `ctx`,
   **Then** funciona exactamente igual que antes (compatibilidad hacia atrás).

3. **Given** una llamada a `compute_governor_step()` con `ctx=MinerGovernanceContext(...)`,
   **Then** el contexto supera los parámetros individuales cuando son inconsistentes.

---

### Edge Cases

- ¿Qué pasa si `MinerGovernanceContext` se construye con datos de telemetría parcial
  (por ejemplo, `chip_temp_c=None` porque el minero no respondió)?
  → Los campos opcionales son `Optional[float]` con `None` como valor seguro.
  Los subsistemas deben tratar `None` como "dato no disponible" y aplicar
  comportamiento conservador (equivalente al estado actual sin contexto).

- ¿Qué pasa si dos subsistemas tienen versiones distintas del contexto en el mismo ciclo?
  → El contexto se construye una sola vez por ciclo por minero en `miner_monitor.py`
  y se pasa por referencia inmutable. No puede haber divergencia dentro del mismo ciclo.

- ¿Qué pasa si se agrega un campo nuevo en `MinerGovernanceContext` y un subsistema
  antiguo no lo conoce?
  → Al ser un dataclass tipado con valores por defecto seguros, los subsistemas
  que no usan el campo nuevo no se ven afectados.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE proveer `MinerGovernanceContext` como dataclass
  inmutable (`frozen=True`) construible desde `MinerState` en O(1).

- **FR-002**: `MinerGovernanceContext` DEBE incluir los siguientes dominios de campos:
  - **Dominio Potencia**: `current_power_w`, `target_power_w`, `configured_preset`, `executed_preset`
  - **Dominio Térmico**: `chip_temp_c`, `inlet_temp_c`, `fga_thermal_resistance`, `fga_cohort`
  - **Dominio Estado Firmware**: `restart_required`, `restart_detected_ts`, `thermal_pause_active`
  - **Dominio Operativo**: `uptime_seconds`, `electrical_group`, `miner_name`, `is_warming_up`

- **FR-003**: El Fan Governor DEBE aceptar `ctx: Optional[MinerGovernanceContext] = None`
  en `compute_governor_step()`. Cuando `ctx` está presente, DEBE usarlo como fuente
  de verdad sobre `current_power_w` y `restart_required` en lugar de los parámetros
  individuales.

- **FR-004**: La trampa `ACTION_RECOVERY_MAX_COOLING` DEBE ser suprimida cuando
  `ctx.restart_required=True` y `ctx.current_power_w >= 500W`, usando
  `ctx.current_power_w` como target efectivo.

- **FR-005**: La función de construcción `MinerGovernanceContext.from_state(state, config)`
  DEBE ser una función pura sin efectos secundarios, sin I/O, ni mutación de estado.

- **FR-006**: Los tests de contrato DEBEN validar que cada subsistema solo accede a
  los campos de su dominio y que el objeto es inmutable.

- **FR-007**: La integración DEBE ser retrocompatible: las llamadas existentes a
  `compute_governor_step()` sin `ctx` deben seguir funcionando sin cambios.

### Key Entities

- **MinerGovernanceContext**: Snapshot inmutable del estado de un minero en un instante
  de ciclo, consumible por todos los subsistemas de gobernanza. Campos organizados
  por dominio (potencia, térmico, firmware, operativo). Construido desde `MinerState`.

- **GovernorDecision**: Resultado de `compute_governor_step()` — sin cambios en esta spec.
  El contexto es una entrada, no modifica la salida.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: La suite completa de tests pasa sin regresiones: ≥1440 tests PASS, 0 fallos.

- **SC-002**: `MinerGovernanceContext.from_state()` completa en < 1ms (construcción O(1)
  sin I/O). Verificable con `time.perf_counter()` en tests de rendimiento.

- **SC-003**: Con `restart_required=True` y `current_power_w=2498W` en el contexto,
  el Fan Governor NO activa `ACTION_RECOVERY_MAX_COOLING`. Verificable con test unitario
  determinista.

- **SC-004**: Todas las llamadas existentes al Fan Governor sin el parámetro `ctx`
  producen resultados idénticos a antes de la spec (verificado por paridad de tests).

- **SC-005**: El ciclo de gobernanza en producción no introduce latencia adicional
  medible (< 5ms por minero por ciclo para construir y pasar el contexto).

---

## Assumptions

- `MinerState` ya contiene todos los campos necesarios para construir `MinerGovernanceContext`.
  Si algún campo no existe aún en `MinerState`, se agrega en esta misma spec.

- El Elevator Budget y el FGA se integran con `MinerGovernanceContext` en specs futuras
  (083 y 085). Esta spec solo integra el Fan Governor como prueba de concepto y
  validación del contrato.

- El Thermal Guard no requiere integración inmediata ya que sus interlocks son
  independientes del ciclo de gobernanza de preset.

- La construcción del contexto ocurre en `miner_monitor.py` dentro del bucle por minero,
  antes de la llamada al Fan Governor.

- Los tests de contrato son tests unitarios puros (sin I/O, sin VNish, sin SQLite).
