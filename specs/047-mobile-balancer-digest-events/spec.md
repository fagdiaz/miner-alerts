# Feature Specification: Spec 047 - Mobile-First Card Layout for Power Balancing, Daily Digest & Operational Intelligence

**Feature Directory**: `specs/047-mobile-balancer-digest-events`
**Created**: 2026-09-09
**Status**: Ready for Implementation
**Author**: Gemini 3.8 Flash High
**RFC Reference**: `docs/speckit/RFC_TELEGRAM_MOBILE_UX_OPTIMIZATION.md` (Condiciones C1-C10)

---

## 1. Executive Summary & Problem Statement

En smartphones (Telegram Mobile para iOS y Android), las salidas de diagnóstico y supervisión operativa correspondientes al balanceador de potencia, sensibilidad eléctrica de elevadores, resumen ejecutivo diario, estado de mantenimiento y consultas de incidentes históricos (`/balancer`, `/elevadores`, `/digest`, `/snoozed`, `/events`, `/event`, `/why`) aún mantienen formatos de consola de escritorio con líneas horizontales de 60 a 97 caracteres de longitud.

Esto genera:
1. **Quebrado visual y wrap caótico**: Líneas de telemetría como `• S19JPRO-23: 2500W | R: 0 (24h) / 0 (72h) | Uptime: 25h` o diagnósticos de elevador de más de 90 columnas se parten arbitrariamente en 3 renglones en la pantalla del celular (32-34 columnas visibles).
2. **Ausencia de botones táctiles de 1-toque**: Para refrescar el balanceador o el digest tras una intervención, el operador debe volver a tipear manualmente el comando en el teclado táctil del móvil.
3. **Inconsistencia estética con Specs 045 y 046**: Tras haber transformado `/help`, `/status`, `/fans`, `/efficiency` y `/presets` en fichas verticales limpias con viñetas `•`, los comandos restantes desentonan visualmente con la experiencia de usuario Mobile-First.

**Spec 047** completa la modernización Mobile-First del ecosistema de Telegram:
- Rediseña `/balancer`, `/elevadores`, `/digest`, `/snoozed`, `/events`, `/event` y `/why` a **tarjetas verticales Mobile-First** con viñetas indentadas `•` y ancho estricto $\le 32$ columnas visibles por línea.
- Conecta botoneras táctiles inline (`[ 🔄 Actualizar ] [ 📱 Menú ]`) para refresco in-place instantáneo (< 50ms) sin spam en `/balancer`, `/elevadores`, `/digest` y `/events`.
- Mantiene 100% de pureza funcional: cero dependencias de red, cero modificaciones a la FSM (`MinerState`), cálculos del balanceador ni lógica de auto-reboot.

---

## 2. User Scenarios & Testing

### User Story 1 - Balanceo Eléctrico y Elevadores en Celular (`/balancer`, `/elevadores`) (Priority: P1)
Como operador que gestiona la carga eléctrica de los elevadores de tensión desde el celular,
quiero que `/balancer` y `/elevadores` organicen la carga combinada (Watts), reinicios (24h/72h) y recomendaciones por elevador en tarjetas verticales $\le 32$ columnas,
para evaluar la estabilidad de la instalación eléctrica sin saturación visual.

**Acceptance Scenarios**:
1. **Given** mineros agrupados por elevador, **When** el usuario envía `/balancer`, **Then** recibe una tarjeta vertical estructurada con viñetas `•`, carga de grupo, acciones de balanceo y botón `[ 🔄 Actualizar ] [ 📱 Menú ]`.
2. **Given** el análisis de sensibilidad de elevadores, **When** el usuario ejecuta `/elevadores`, **Then** cada elevador se presenta en una tarjeta con semáforo, carga actual vs capacidad, historial de cascadas y recomendación ajustada en líneas $\le 32$ columnas.

### User Story 2 - Resumen Ejecutivo Diario y Mantenimiento (`/digest`, `/snoozed`) (Priority: P1)
Como operador que revisa el estado general del día o mineros silenciados,
quiero que `/digest` y `/snoozed` presenten las métricas clave (uptime, TH/s promedio, J/TH, eventos 24h, backups y cuentas regresivas de silencio) en formato vertical limpio,
para auditar la granja en 5 segundos desde la pantalla del móvil.

**Acceptance Scenarios**:
1. **Given** métricas acumuladas de 24 horas, **When** se solicita `/digest`, **Then** el reporte ejecutivo se formatea en viñetas verticales $\le 32$ columnas con botón inline de actualización.
2. **Given** mineros en mantenimiento temporal, **When** se ejecuta `/snoozed`, **Then** cada minero silenciado se detalla en una tarjeta compacta con tiempo restante y hora exacta de expiración.

### User Story 3 - Auditoría de Incidentes e Historial (`/events`, `/event`, `/why`) (Priority: P2)
Como operador que investiga un incidente o decisión de auto-reboot desde el móvil,
quiero que `/events`, `/event <id>` y `/why` formateen la evidencia cronológica y causas de reinicio en tarjetas verticales legibles,
para entender el origen de una anomalía sin lidiar con cadenas horizontales saturadas.

**Acceptance Scenarios**:
1. **Given** incidentes registrados en SQLite, **When** se ejecuta `/events`, **Then** la lista de incidentes se formatea con hora, equipo, etiqueta y atajo `/e<id>` en $\le 32$ columnas.
2. **Given** una decisión de auto-reboot evaluada, **When** se ejecuta `/why`, **Then** se detalla el minero, resultado, evidencia de hash, placas y voltajes en líneas verticales $\le 32$ columnas.

---

## 3. Functional Requirements

- **FR-001**: Todos los renderizadores (`build_balancer_table_text`, `build_miner_balancer_detail_text`, `build_elevator_sensitivity_text`, `format_daily_digest`, `build_snooze_status_text`, `render_event_list`, `render_event_detail`, `render_reboot_decision`) DEBEN garantizar líneas de datos $\le 32$ columnas visibles tras despojar etiquetas Markdown (Condición C1).
- **FR-002**: Las líneas largas de texto descriptivo (e.g. diagnósticos y recomendaciones) DEBEN fragmentarse mediante `wrap_mobile_lines()` respetando el límite $\le 32$ columnas.
- **FR-003**: `/balancer`, `/elevadores`, `/digest` y `/events` DEBEN adjuntar un inline keyboard con botones `[ 🔄 Actualizar ] [ 📱 Menú ]` (Condición C3).
- **FR-004**: Los callbacks `diag:ref:balancer`, `diag:ref:elev`, `diag:ref:digest`, `diag:ref:events` DEBEN despachar ACK inmediato (`answer_callback_query`) en $< 50$ ms y editar el mensaje in-place con `edit_message_text()`.
- **FR-005**: El tamaño total de cada reporte DEBE ser estrictamente $< 3,600$ caracteres (Condición C4).
- **FR-006**: La lógica de renderizado DEBE ser 100% pura y determinista, libre de bloqueos de red o mutación de estados de control (Condición C2 y C7).

---

## 4. Success Criteria

- **SC-001**: 100% de las líneas de datos de `/balancer`, `/elevadores`, `/digest`, `/snoozed`, `/events`, `/event` y `/why` validadas con $\le 32$ columnas visibles en suites de test automáticas.
- **SC-002**: Despacho in-place de callbacks de refresco funcionando sin excepciones `MessageNotModified` y con ACK $< 50$ ms.
- **SC-003**: 0 modificaciones a la FSM (`MinerState`), políticas de autorreinicio, gobernanza de hardware ni workers.
- **SC-004**: 100% de la suite de pruebas del repositorio pasando sin fallos ni regresiones ($\ge 675$ tests PASS).

---

## 5. Scope Boundaries

- **IN SCOPE**:
  - Rediseño de `build_balancer_table_text`, `build_miner_balancer_detail_text` y `build_elevator_sensitivity_text` en `app/governance/preset_balancer.py`.
  - Rediseño de `format_daily_digest` en `app/telegram/daily_digest.py`.
  - Rediseño de `build_snooze_status_text` en `app/telegram/snooze.py`.
  - Rediseño de `render_event_list`, `render_event_detail` y `render_reboot_decision` en `app/core/event_store.py`.
  - Expansión de `build_diagnostic_keyboard` y `parse_diagnostic_callback` en `app/telegram/fleet_cards.py`.
  - Conexión de callbacks en `_handle_diagnostic_callback` en `app/miner_monitor.py`.
  - Suites unitarias y de integración exhaustivas.

- **OUT OF SCOPE**:
  - Modificaciones a los algoritmos de balanceo (`evaluate_balancer_step`, `analyze_elevator_sensitivity`).
  - Cambios en el esquema de tablas SQLite de eventos.
  - Generación de gráficos PNG (permanece en Spec 032).
