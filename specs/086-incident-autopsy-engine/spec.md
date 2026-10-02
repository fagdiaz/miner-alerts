# Feature Specification: Spec 086 — Autopsia Autónoma de Incidentes y Supervisor Conversacional (PROP-016)

**Feature Branch**: `codex/022-adaptive-acquisition`  
**Feature Directory**: `specs/086-incident-autopsy-engine`  
**Created**: 2026-10-02  
**Status**: Draft  
**Input**: Motor Autónomo de Autopsia de Incidentes (Post-Mortem Analyzer), persistencia en SQLite (`incident_assessments`), tarjetas Mobile-First (<=32 cols) y Supervisor Conversacional Q&A en Telegram (PROP-016).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Autopsia Forense Automática ante Reinicio Inesperado (Priority: P1)

Como operador de la granja minera, cuando una máquina sufre un reinicio inesperado de su proceso de minado (`elapsed: 12507 -> 10s`), quiero que el sistema investigue automáticamente los logs del kernel y firmware en segundo plano para informarme de inmediato la causa raíz real (ej. cable de red defectuoso, sobrecalentamiento, rotura de cadena o falla eléctrica), para saber si debo intervenir físicamente sin tener que auditar logs manualmente.

**Why this priority**: Es el núcleo de PROP-016. Evita diagnósticos a ciegas en producción y previene que el operador pierda tiempo ingresando por SSH/Web a las máquinas para entender por qué cayó el hashrate.

**Independent Test**: Simular un reinicio inesperado en un minero con logs de `Link is Down`; el motor genera la autopsia, la persiste en SQLite y entrega una alerta en Telegram con causa "ENLACE FÍSICO" en $\le 32$ columnas.

**Acceptance Scenarios**:
1. **Given** un minero que sufre un reinicio clasificado como `unexpected`, **When** se detecta la caída de `elapsed`, **Then** se dispara un worker forense asíncrono con timeout duro de 2.5s que no bloquea el loop de monitoreo.
2. **Given** logs de kernel con múltiples eventos `libphy: Link is Down` y watchdog de VNish con `Low hashrate`, **When** el clasificador evalúa la evidencia, **Then** determina categoría `LINK_DROP`, confianza ALTA, y sugiere revisar el cable Ethernet RJ45.
3. **Given** la autopsia generada, **When** se emite la notificación, **Then** todas las líneas respetan $\le 32$ columnas de ancho móvil.

---

### User Story 2 - Inspección Forense On-Demand vía Telegram (Priority: P2)

Como operador, quiero poder consultar en cualquier momento el último análisis forense de cualquier minero enviando `/autopsia [minero]` (o aliases `/causa_raiz`, `/autopsy`), para revisar el historial del último incidente ocurrido sin esperar a que vuelva a fallar.

**Why this priority**: Brinda observabilidad histórica inmediata desde el teléfono.

**Independent Test**: Enviar `/autopsia 25` por Telegram; el bot consulta la última autopsia registrada en SQLite y devuelve la tarjeta ejecutiva formateada en $\le 32$ columnas.

**Acceptance Scenarios**:
1. **Given** incidentes previos persistidos en SQLite para el minero 25, **When** el operador envía `/autopsia 25`, **Then** recibe la tarjeta con hora, causa raíz, evidencia sintetizada y estado del silicio.
2. **Given** un minero que no tiene incidentes registrados en el periodo de retención, **When** se solicita su autopsia, **Then** el bot informa que el minero opera nominal sin incidentes recientes.

---

### User Story 3 - Supervisor Conversacional Q&A Determinístico Offline (Priority: P3)

Como operador, quiero poder enviar preguntas en lenguaje natural por Telegram (ej. *"¿Por qué reinició la 25?"*, *"¿Cómo está la red?"*, *"¿Hay máquinas calientes?"*), y recibir una respuesta fáctica instantánea en menos de 50 ms basada en los datos reales de la granja, sin costo de API y sin alucinaciones.

**Why this priority**: Transforma el bot en un asistente interactivo amigable para el operador de campo.

**Independent Test**: Enviar el mensaje *"¿por qué cayó la 24?"*; el despachador reconoce la intención, busca la última autopsia de la máquina 24 y responde concisamente en 3 líneas.

**Acceptance Scenarios**:
1. **Given** un mensaje de texto libre que coincide con patrones de causa de reinicio para un minero identificado, **When** el despachador procesa el texto, **Then** extrae la causa raíz de la última evaluación en SQLite y responde en $\le 32$ columnas.
2. **Given** una consulta de estado general o red, **When** no hay API externa configurada, **Then** el motor RAG determinístico responde con los hechos de los últimos 60 minutos.

---

### Edge Cases

- **Timeout de Conexión a Logs**: Si la máquina no responde en 2.5s, la recolección aborta de forma limpia y la autopsia se genera en base a la telemetría previa disponible en `EventStore` indicando `EVIDENCIA_PARCIAL`.
- **Ráfaga de Reinicios Múltiples**: Si varios mineros reinician simultáneamente (ej. tras un corte eléctrico), cada autopsia se procesa en pool de hilos acotado sin saturar la CPU ni disparar spam masivo en Telegram (agrupamiento o cooldown).
- **Logs Cíclicos Vacíos**: Si el buffer de logs de la máquina se limpió por un reboot de hardware total, el clasificador declara `REINICIO_POR_HARDWARE_O_CORTE` evaluando la caída abrupta de voltaje o pérdida de sesión.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE implementar un motor forense `IncidentAutopsyEngine` que se ejecute de forma asíncrona ante cualquier reinicio `unexpected`.
- **FR-002**: La recolección de evidencia desde el minero DEBE ser estrictamente de sólo lectura (`read-only`) con timeout máximo no configurable superior a 3.0s (default 2.5s).
- **FR-003**: El clasificador forense DEBE categorizar determinísticamente las causas raíz en:
  - `LINK_DROP`: Caídas de enlace Ethernet / interfaz de red.
  - `CHAIN_BREAK`: Rotura de cadena de chips / error de silicio.
  - `THERMAL_SHUTDOWN`: Sobretemperatura de chips ($\ge 85^\circ$C).
  - `PSU_FAULT`: Falla de fuente de poder o chequeo de voltaje.
  - `AUTOTUNE_STALL`: Congelamiento de autotuning o fallo de PLL.
  - `POWER_LOSS`: Corte total de alimentación / caída de elevador.
  - `UNRESOLVED`: Evidencia insuficiente para diagnóstico concluyente.
- **FR-004**: Los resultados de la autopsia DEBEN persistirse de forma estructurada en la tabla `incident_assessments` de SQLite (`EventStore`).
- **FR-005**: Las tarjetas de autopsia y alertas DEBEN construirse bajo el estándar Mobile-First respetando un ancho estricto de $\le 32$ columnas por línea.
- **FR-006**: El sistema DEBE exponer el comando `/autopsia [minero]` con aliases `/autopsy`, `/causa_raiz`, `/investigar` en el router de comandos de Telegram.
- **FR-007**: El sistema DEBE implementar un enrutador de lenguaje natural determinístico (offline, zero-cost) en Telegram capaz de responder intenciones de autopsia y estado de red.

---

### Key Entities

- **AutopsyEvidence**: Conjunto inmutable de hechos recopilados (eventos de kernel, logs de VNish, telemetría de potencia/chips previa a la caída, estado de enlace de red).
- **AutopsyReport**: Evaluación final que contiene el nombre del minero, timestamp, categoría de causa raíz, nivel de certeza (ALTA, MEDIA, BAJA), lista de evidencias clave y sugerencia técnica de remediación.
- **IncidentAssessmentRecord**: Fila persistida en la tabla `incident_assessments` en SQLite (`data/miner_alerts.db`) para auditoría y consultas históricas.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Tiempo de generación de la autopsia $\le 3.5$ segundos desde la detección del reinicio.
- **SC-002**: Cero impacto en el bucle principal de adquisición (bloqueo medido del tick principal = 0 ms).
- **SC-003**: 100% de las tarjetas y mensajes de autopsia cumplen con la restricción de ancho $\le 32$ columnas por línea.
- **SC-004**: Precisión diagnóstica determinística del 100% ante los patrones de prueba sintéticos (`Link is Down`, `Overheating`, `Chain break`).
- **SC-005**: La suite de pruebas de regresión global se mantiene con 0 fallos y suma al menos 8 tests automáticos nuevos ($\ge 1506$ tests totales).

---

## Assumptions

- Las máquinas en producción corren firmware VNish con endpoints WebSocket de logs `/api/v1/logs-ws/{tab}` activos.
- El esquema SQLite existente cuenta con la tabla `incident_assessments` (schema 7 de `EventStore`).
- Si no hay conectividad externa a internet, el motor RAG determinístico atiende el 100% de las consultas de autopsia de forma local sin requerir servicios de LLM.
