# Feature Specification: Spec 052 - Scheduled Maintenance Windows & Soft Pre-Ramp

**Feature Directory**: `specs/052-maintenance-scheduler`  
**Created**: 2026-09-10  
**Status**: Ready for Planning  
**Author**: Gemini 3.8 Flash High  
**RFC Reference**: `docs/speckit/RFC_TELEGRAM_MOBILE_UX_OPTIMIZATION.md` (Condiciones C1-C10)  
**Parent Specs**: `specs/048-safe-fleet-shutdown` (Safe Fleet Shutdown), `specs/049-thermal-purge-ramp` (Active Thermal Purge Ramp), `specs/040-dynamic-voltage-presets` (Preset Ladder)

---

## 1. Executive Summary & Problem Statement

En una granja minera con potencia instalada superior a 10 kW, las maniobras de mantenimiento eléctrico (reapriete de bornes, cambio de térmicas, mantenimiento de transformadores o grupos electrógenos) son operaciones planificadas con anticipación:

1. **Dependencia de la Presencia Humana en Tiempo Real:**
   Actualmente, el protocolo de parada segura (Spec 048) es estrictamente on-demand. Si el técnico electricista llega a las 08:00 AM un sábado, el operador debe estar despierto frente a Telegram en ese minuto exacto para disparar la confirmación manual de 2 pasos (`/shutdown`).
2. **Impacto Inductivo de Corte Brusco a Plena Carga (11 kW $\to$ 0 kW):**
   Detener 4 mineros operando a máxima potencia (2700W por máquina = 10.8 kW totales) en un solo instante produce una desconexión abrupta de corriente alterna, generando oscilaciones transitorias de tensión en los elevadores y la red interna del galpón.
   **Solución (Pre-Rampa Suave de Potencia):** Durante los 10 a 15 minutos previos a la ventana programada, el orquestador debe desescalar progresivamente los presets de potencia (de 2700W a 2300W y luego a 2100W) mediante el ladder de presets (Spec 040), descargando suavemente el transformador y reduciendo la temperatura de los chips antes de la parada final.
3. **Purga Térmica y Contraste Acústico Automatizado:**
   Al llegar el minuto exacto programado, el sistema dispara automáticamente la secuencia validada de Spec 049: parada suave de hash (0W), rampa forzada de purga al 100% durante 45s y caída instantánea al piso de reposo acústico (40% PWM) con emisión de la tarjeta `✅ ÁREA ELÉCTRICA SEGURA` y activación de snooze por la duración programada.

**Solución Propuesta (Scheduled Maintenance Windows & Soft Pre-Ramp):**
- **Comandos Telegram y Programación Flexible**:
  * `/schedule_maintenance <in 30m | in 2h | YYYY-MM-DD HH:MM> [duración]` (ej. `/schedule_maintenance in 30m 2h` o `/schedule_maintenance 2026-09-12 08:00 3h`).
  * `/scheduled`: Consulta de ventanas programadas con botón táctil interactivo `[ ❌ Cancelar Ventana ]`.
- **Pre-Rampa Desescalonada (T-10m)**: Descenso progresivo de presets de potencia para aliviar la carga eléctrica.
- **Avisos Proactivos**: Notificaciones ejecutivas en Telegram a T-15m (pre-aviso), T-0 (parada y purga térmica) y T+fin (recordatorio de reanudación).

---

## 2. User Scenarios & Testing

### User Story 1 - Programación Diferida de Mantenimiento desde Telegram (Priority: P1)
Como operador de la granja,
quiero programar un mantenimiento eléctrico para dentro de unas horas o para un horario específico,
para que la flota se detenga de forma segura sin requerir mi intervención en ese momento exacto.

**Acceptance Scenarios**:
1. **Given** un operador en Telegram, **When** envía `/schedule_maintenance in 45m 2h`, **Then** el sistema confirma la programación mediante una tarjeta interactiva detallando hora de inicio, duración y fin previsto.
2. **Given** una ventana activa programada, **When** el operador consulta `/scheduled`, **Then** recibe una tarjeta Mobile-First con el tiempo restante y un botón `[ ❌ Cancelar ]`.
3. **Given** que el operador pulsa `[ ❌ Cancelar ]`, **When** se procesa la acción, **Then** la ventana se anula y la flota continúa en su régimen normal.

### User Story 2 - Pre-Rampa Suave de Desescalado Eléctrico (Priority: P1)
Como técnico responsable de la instalación eléctrica,
quiero que la flota reduzca gradualmente su potencia 10 minutos antes de la parada programada,
para no desenergizar 11 kW de golpe y proteger los transformadores y contactores de sobretensiones inductivas.

**Acceptance Scenarios**:
1. **Given** una ventana programada, **When** el reloj alcanza T-10 minutos, **Then** el sistema baja automáticamente los presets de potencia de todos los mineros a 2300W y luego a 2100W en T-5 minutos.
2. **Given** la pre-rampa en progreso, **When** el monitor despacha el desescalado, **Then** envía una notificación informativa `⏳ PRE-RAMPA ELÉCTRICA EN MARCHA`.

### User Story 3 - Ejecución de Parada, Purga y Auto-Snooze a T-0 (Priority: P1)
Como electricista en el galpón,
quiero que a la hora programada exacta los mineros apaguen el hash, purguen los disipadores 45s a 100% y caigan a reposo acústico,
para poder bajar la llave térmica con total seguridad.

**Acceptance Scenarios**:
1. **Given** que el reloj alcanza la hora fijada (T-0), **When** el planificador se dispara, **Then** ejecuta `execute_parallel_shutdown`, fuerza rampa al 100% por 45s y luego baja al 40% PWM.
2. **Given** la purga completada, **When** caen los ventiladores a reposo, **Then** emite la tarjeta `✅ ÁREA ELÉCTRICA SEGURA` y aplica un `/snooze` equivalente a la duración configurada.

---

## 3. Functional Requirements

- **FR-001**: El sistema DEBE implementar un módulo puro desacoplado `app/governance/maintenance_scheduler.py` encargado del almacenamiento en memoria y validación de ventanas programadas.
- **FR-002**: El planificador DEBE soportar sintaxis relativa (`in 30m`, `in 2h`) y absoluta (`YYYY-MM-DD HH:MM`) en hora local de Argentina (UTC-3).
- **FR-003**: El comando `/schedule_maintenance` DEBE validar que la hora de inicio sea futura ($\ge 5$ minutos desde el momento actual) y que la duración esté comprendida entre 15 minutos y 24 horas.
- **FR-004**: A T-10 minutos de la hora programada, el sistema DEBE iniciar la pre-rampa suave reduciendo presets mediante `apply_soft_ramp_down()`.
- **FR-005**: A T-0, el sistema DEBE disparar de forma concurrente el protocolo de parada y purga térmica validado en Spec 048 y Spec 049.
- **FR-006**: El sistema DEBE persistir la ventana programada en `state.json` bajo la clave `scheduled_maintenance` para sobrevivir a reinicios del servicio.
- **FR-007**: El comando `/scheduled` DEBE renderizar una tarjeta Mobile-First estrictamente $\le 32$ columnas visibles (`visible_line_width(line) <= 32`).
- **FR-008**: Todas las transiciones de la ventana (programación, pre-rampa, ejecución, cancelación y fin) DEBEN registrarse en `event_store` con acción `scheduled_maintenance`.

---

## 4. Success Criteria

- **SC-001**: Precisión temporal: la pre-rampa inicia a $T - 10\text{m} \pm 15\text{s}$ y la parada se ejecuta a $T - 0 \pm 5\text{s}$.
- **SC-002**: Descarga eléctrica escalonada verificada: potencia total de la flota desciende al menos un 20% antes de la parada completa (0W).
- **SC-003**: Persistencia ante reinicios: una ventana programada se recupera y ejecuta con exactitud si el monitor se reinicia antes de la hora fijada.
- **SC-004**: Formato Mobile-First: 100% de las líneas de las tarjetas de mantenimiento cumplen `visible_line_width <= 32`.
- **SC-005**: Cero regresiones en la suite global de tests (100% PASS).

---

## 5. Scope Boundaries

- **IN SCOPE**:
  - Módulo `app/governance/maintenance_scheduler.py`.
  - Parser de fechas y tiempos relativos/absolutos.
  - Lógica de pre-rampa suave de presets.
  - Integración en bucle periódico del monitor (`app/miner_monitor.py`) y handlers de Telegram (`/schedule_maintenance`, `/scheduled`, callback `sch:cancel`).
  - Pruebas unitarias e integración completas.

- **OUT OF SCOPE**:
  - Manipulación mecánica física de seccionadores o térmicas.
  - Sincronización con calendarios externos vía CalDAV o Google Calendar.
