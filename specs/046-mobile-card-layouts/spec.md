# Feature Specification: Spec 046 - Mobile-First Card Layout & UX Harmonization across Fleet Reports

**Feature Directory**: `specs/046-mobile-card-layouts`
**Created**: 2026-09-09
**Status**: Ready for Implementation
**Author**: Gemini 3.8 Flash High
**RFC Reference**: `docs/speckit/RFC_TELEGRAM_MOBILE_UX_OPTIMIZATION.md` (Condiciones C1-C10)

---

## 1. Executive Summary & Problem Statement

En smartphones (Telegram Mobile para iOS y Android), los mensajes de diagnóstico de flota de Miner Alerts (`/status`, `/fans`, `/efficiency`, `/presets`, `/elevadores`) se presentan actualmente como tablas horizontales de texto plano monoespaciado o filas de más de 70-90 caracteres de ancho.
Esto produce:
1. **Quebrado visual caótico**: Cada fila se corta arbitrariamente en 2 o 3 líneas desalineadas en pantallas estrechas (32 a 34 columnas visibles).
2. **Incomodidad operativa**: Para volver al menú o refrescar el diagnóstico tras esperar un ciclo de enfriamiento, el operador debe volver a tipear el comando `/fans` o `/status` manualmente en el teclado virtual.
3. **Falta de jerarquía visual**: Los datos críticos (temperatura máxima, RPM, Watts, Joules/TH) compiten visualmente con identificadores largos, hashes y tags secundarios.

**Spec 046** resuelve estos problemas rediseñando todas las salidas de diagnóstico de flota a **tarjetas verticales Mobile-First** con viñetas indentadas `•`, límites estrictos $\le 32$ caracteres visibles por línea de datos, semáforos Unicode armonizados y botoneras inline táctiles de 1-toque (`[ 🔄 Actualizar ] [ 📊 Gráfico ] [ 📱 Menú ]`), reutilizando el mecanismo probado en Spec 043 y Spec 045 sin tocar la lógica de adquisición, SQLite, FSM ni el loop de monitoreo.

---

## 2. User Scenarios & Testing

### User Story 1 - Diagnóstico Rápido de Flota en Móvil (`/status`) (Priority: P1)
Como operador de la granja minera que supervisa los equipos desde el teléfono celular en la calle o sala de control,
quiero que `/status` me muestre una tarjeta vertical limpia por minero con su hashrate, placas activas, temperatura, fans y consumo eléctrico,
para conocer el estado integral de la flota de un vistazo sin scroll horizontal ni líneas truncadas.

**Acceptance Scenarios**:
1. **Given** el bot activo y los 4 mineros en línea, **When** el usuario envía `/status`, **Then** recibe una tarjeta estructurada con título, separadores Unicode (`─`), un bloque vertical por minero ($\le 32$ caracteres visibles por línea) y un resumen de potencia total y hashrate combinado.
2. **Given** el mensaje de `/status`, **When** el usuario toca el botón inline `[ 🔄 Actualizar ]`, **Then** el mensaje se actualiza in-place con la telemetría más reciente sin generar un nuevo mensaje en el chat.
3. **Given** el mensaje de `/status`, **When** el usuario toca `[ 📱 Menú ]`, **Then** el mensaje se transforma in-place en el Command Center principal (`/menu`).

### User Story 2 - Evaluación Térmica y Salud de Ventiladores (`/fans`) (Priority: P1)
Como operador que necesita verificar el régimen térmico ante temperaturas elevadas,
quiero que `/fans` entregue una tarjeta vertical jerárquica con el estado de saturación, temperatura, margen térmico, RPM, PWM y modo de control (Fan Governor),
para identificar al instante mineros con disipación comprometida o filtros sucios.

**Acceptance Scenarios**:
1. **Given** mineros operando con Fan Governor, **When** el usuario ejecuta `/fans`, **Then** cada minero se muestra en una tarjeta vertical con viñetas `• Temp: XX.X°C (Margen: Y.Y°C)`, `• Fans: X,XXX RPM (YY% PWM)`, `• Modo: [HOLD_TARGET|RECOVERY_MAX|SILENT]`.
2. **Given** mineros en saturación térmica, **When** el reporte finaliza, **Then** incluye un bloque de atención con recomendaciones claras y botones inline de `[ 🔄 Actualizar ]` y `[ 📱 Menú ]`.

### User Story 3 - Eficiencia Energética y Perfiles Operativos (`/efficiency`, `/presets`) (Priority: P2)
Como operador responsable del consumo eléctrico y balance de carga,
quiero que `/efficiency` y `/presets` organicen el consumo (W), rendimiento (TH/s), J/TH y perfiles autotuning de manera legible en pantallas angostas,
para tomar decisiones sobre presets sin fatiga visual.

**Acceptance Scenarios**:
1. **Given** mediciones de potencia y hashrate, **When** se ejecuta `/efficiency`, **Then** se presentan tarjetas verticales con semáforo, J/TH, TH/s y Watts, seguido del promedio de flota y carga total en kW.
2. **Given** perfiles Vnish activos, **When** se ejecuta `/presets`, **Then** se reporta frecuencia (MHz), tensión (V), perfil inferido y estado de autotuning por minero sin desbordar el ancho de pantalla.

---

## 3. Functional Requirements

- **FR-001**: Todos los renderizadores de reportes de flota (`/status`, `/fans`, `/efficiency`, `/presets`, `/elevadores`) DEBEN formatear sus líneas de datos con un ancho visible máximo $\le 32$ columnas comprobado tras eliminar tags Markdown (Condición C1).
- **FR-002**: Se PROHÍBE el uso de bloques de código monoespaciados extensos (```) o tablas horizontales que fuercen el scroll horizontal en clientes móviles.
- **FR-003**: Cada reporte de diagnóstico DEBE adjuntar una botonera inline con acciones táctiles:
  - `/status`: `[ 🔄 Actualizar ]`, `[ 📊 Gráfico ]`, `[ 📱 Menú ]`.
  - `/fans`: `[ 🔄 Actualizar ]`, `[ 📱 Menú ]`.
  - `/efficiency`: `[ 🔄 Actualizar ]`, `[ 📱 Menú ]`.
  - `/presets`: `[ 🔄 Actualizar ]`, `[ 📱 Menú ]`.
- **FR-004**: Las acciones de actualización `[ 🔄 Actualizar ]` DEBEN responder con `answerCallbackQuery` inmediato (< 50ms) y editar el mensaje *in-place* vía `edit_message_text()` sin generar spam de mensajes nuevos.
- **FR-005**: Si el cliente no soporta inline keyboards o la entrega se realiza vía fallback directo (`queue=None`), el texto plano DEBE ser 100% legible y autónomo.
- **FR-006**: La lógica de renderizado DEBE residir en funciones puras desacopladas (en sus respectivos módulos de gobernanza o en `app/telegram/`) sin dependencias de I/O de red ni toma de locks en el hilo de renderizado.
- **FR-007**: El tamaño total de cada reporte DEBE ser estrictamente $< 3,600$ caracteres para garantizar que nunca sea particionado por `split_telegram_message()`, evitando la rotura de bloques Markdown (Condición C4).

---

## 4. Success Criteria

- **SC-001**: 100% de las líneas de datos de `/status`, `/fans`, `/efficiency`, `/presets` y `/elevadores` validadas determinísticamente con ancho visible $\le 32$ caracteres en suites de test automáticas.
- **SC-002**: Navegación táctil completa verificada: refresco in-place y retorno al Command Center (`cc:nav:main`) funcionando sin excepciones `MessageNotModified`.
- **SC-003**: 0 modificaciones a la máquina de estados FSM (`MinerState`), auto-reboot, Hashcore CLI ni concurrencia de adquisición (Condición C7).
- **SC-004**: 100% de la suite de pruebas del repositorio pasando sin fallos ni regresiones (objetivo $\ge 660$ tests PASS).

---

## 5. Scope Boundaries

- **IN SCOPE**:
  - Encapsulación y rediseño de `render_fleet_status_card()` para `/status`.
  - Rediseño de `build_fans_table_text()` en `app/governance/fan_health.py`.
  - Rediseño de `build_efficiency_table_text()` en `app/governance/energy_efficiency.py`.
  - Rediseño de `build_presets_table_text()` en `app/vnish/presets.py`.
  - Conexión de callbacks de refresco (`diag:ref:status`, `diag:ref:fans`, etc.) en `miner_monitor.py`.
  - Pruebas unitarias de ancho, formato y callbacks.

- **OUT OF SCOPE**:
  - Modificaciones a los algoritmos de gobernanza (Fan Governor, Balancer).
  - Cambios en el esquema de base de datos SQLite o recolección de telemetría.
  - Alertas automáticas episódicas o de estado (mantienen sus plantillas vigentes).
