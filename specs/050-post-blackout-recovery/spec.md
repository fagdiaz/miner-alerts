# Feature Specification: Spec 050 - Post-Blackout Recovery Guard

**Feature Directory**: `specs/050-post-blackout-recovery`  
**Created**: 2026-09-10  
**Status**: Ready for Planning  
**Author**: Gemini 3.8 Flash High  
**RFC Reference**: `docs/speckit/RFC_TELEGRAM_MOBILE_UX_OPTIMIZATION.md` (Condiciones C1-C10)  
**Parent Specs**: `specs/048-safe-fleet-shutdown` (Safe Fleet Shutdown), `specs/049-thermal-purge-ramp` (Active Thermal Purge Ramp), `specs/031-telegram-interactive-callbacks` (Interactive Buttons)

---

## 1. Executive Summary & Problem Statement

En una granja minera sujeta a cortes de energía eléctrica de la red pública, microcortes o disparos y rearmes de protecciones termomagnéticas, el retorno de tensión presenta un problema crítico de continuidad operativa:

1. **Estado "Stopped" Post-Reinicio:**
   Los mineros Antminer con firmware Vnish, al energizarse tras un corte imprevisto o apagado abrupto, pueden iniciar sus sistemas operativos Linux y levantar la API 4028 y el servidor HTTP, pero quedar con el proceso de minado detenido (`miner_state: "stopped"` o `hashrate: 0 TH/s`), especialmente si se encontraban pausados o si el perfil de arranque de la controladora no autoinicia el minado inmediatamente.
2. **Pérdida Silenciosa de Producción (Downtime):**
   Si el corte ocurre de madrugada o mientras el operador está fuera de línea, la granja permanece consumiendo energía base de coolers y fuentes sin generar hashrate durante horas, hasta que alguien consulte manualmente `/status` o ingrese a las interfaces web.
3. **Diferenciación Crítica de Mantenimiento Deliberado:**
   El sistema **no debe** intentar reanudar mineros que fueron apagados intencionalmente por el operador para mantenimiento eléctrico (Spec 048) o que se encuentren bajo un `/snooze` activo (Spec 033).
4. **Protección Térmica y Transitorios de Red:**
   Inmediatamente tras el retorno de tensión, la tensión eléctrica de la red suele presentar oscilaciones transitorias y los ventiladores deben estabilizarse. Se requiere una ventana de gracia antes de cualquier auto-reanudación para no sobrecargar la línea con un arranque simultáneo descontrolado.

**Solución Propuesta (Post-Blackout Recovery Guard):**
Un subsistema supervisor desacoplado dentro del monitor que:
- Detecta mineros accesibles que reportan `miner_state: "stopped"` o `0 TH/s` de forma sostenida (>= 2 ciclos de polling consecutivos) tras un reinicio de sistema (uptime corto o detección de retorno online).
- Verifica estrictamente que el minero **no** tenga activa una bandera de mantenimiento manual ni `/snooze`.
- Envía de inmediato una tarjeta ejecutiva interactiva a Telegram (`⚡ RECUPERACIÓN POST-CORTE`, Mobile-First <= 32 cols) con un botón táctil 1-tap `[ ▶️ Reanudar Flota ]` (o individual `[ ▶️ Reanudar ]`).
- Soporta un modo opcional de auto-reanudación (`auto_resume: true`) con ventana de gracia configurable (ej. 180s = 3 minutos post-estabilización) para volver a minar automáticamente si el operador no interviene.

---

## 2. User Scenarios & Testing

### User Story 1 - Detección Proactiva y Alerta Telegram con Botón 1-Tap (Priority: P1)
Como operador de la granja,
quiero recibir una alerta inmediata en Telegram cuando la luz vuelva y los mineros hayan encendido pero hayan quedado en estado detenido (`stopped`), con un botón táctil para reanudar toda la flota en un toque,
para no perder horas de producción sin necesidad de entrar a la IP de cada minero.

**Acceptance Scenarios**:
1. **Given** un minero que retorna online con `uptime < 10m` y `miner_state == "stopped"`, **When** la condición se confirma durante 2 ticks consecutivos, **Then** el monitor emite una notificación Telegram `⚡ RECUPERACIÓN POST-CORTE` detallando los mineros afectados.
2. **Given** la tarjeta de alerta post-corte, **When** se presenta al operador, **Then** incluye un botón táctil `[ ▶️ Reanudar Flota ]` (callback `cc:act:resume:all` o `pbr:resume:all`).
3. **Given** que el operador pulsa `[ ▶️ Reanudar Flota ]`, **When** se procesa la acción, **Then** se despacha `execute_parallel_resume` y se restaura el flujo activo de coolers y minado, notificando `▶️ MINADO REANUDADO`.

### User Story 2 - Respeto Estricto de Mantenimiento Deliberado y Snooze (Priority: P1)
Como técnico que apagó deliberadamente los mineros con `/shutdown` (Spec 048) para cambiar un cable o tablero,
quiero que el Guardián Post-Blackout NO emita falsas alarmas ni intente reanudar los equipos mientras dure el período de mantenimiento,
para evitar accidentes eléctricos y ruidos innecesarios en Telegram.

**Acceptance Scenarios**:
1. **Given** mineros detenidos por `safe_fleet_shutdown` con `maintenance: true` o `/snooze` activo en `state.json`, **When** el monitor los detecta en `stopped`, **Then** el Guardián suprime la alerta y omite cualquier acción automática.
2. **Given** un minero que sale de mantenimiento mediante `/resume` o expiración de snooze, **When** posteriormente sufre un corte real y queda en `stopped`, **Then** el Guardián se reactiva normalmente.

### User Story 3 - Auto-Reanudación Autónoma Configurable con Ventana de Gracia (Priority: P2)
Como operador con granjas remotas desatendidas,
quiero poder configurar `auto_resume: true` con una ventana de gracia de 3 minutos tras el retorno de tensión,
para que la flota se reactive automáticamente aún si no tengo señal en el teléfono durante la madrugada.

**Acceptance Scenarios**:
1. **Given** `post_blackout_guard.auto_resume: true` y `grace_period_seconds: 180`, **When** los mineros permanecen en `stopped` durante 180s tras su descubrimiento online sin que el operador haya intervenido, **Then** el sistema ejecuta automáticamente la reanudación segura de la flota.
2. **Given** una auto-reanudación exitosa, **When** concluye la maniobra, **Then** se envía una tarjeta informativa a Telegram `✅ AUTO-RECUPERACIÓN EXITOSA` registrando la hora y los equipos restablecidos.
3. **Given** `auto_resume: false` (valor predeterminado seguro), **When** expira la ventana, **Then** el sistema NO ejecuta órdenes automáticas y solo mantiene la tarjeta interactiva a la espera del toque humano.

---

## 3. Functional Requirements

- **FR-001**: El sistema DEBE mantener un módulo desacoplado `app/governance/post_blackout_guard.py` con lógica pura de detección, evaluación de interlocks y generación de tarjetas móviles.
- **FR-002**: La detección DEBE identificar mineros cuyo `miner_state` reportado sea `"stopped"`, `"paused"` o similar, o que reporten `0 TH/s` con estado no transitorio (descartando `starting`, `benchmarking`, `init`).
- **FR-003**: El sistema DEBE requerir al menos 2 ciclos de polling consecutivos (o `consecutive_stopped_ticks >= 2`) antes de disparar la alerta, para prevenir falsos positivos durante la inicialización de sockets del firmware.
- **FR-004**: El sistema DEBE verificar los siguientes interlocks de seguridad antes de alertar o accionar:
  * Bandera de mantenimiento de Spec 048 (`is_in_maintenance(miner_id) == False`).
  * Silenciamiento temporal de Spec 033 (`is_snoozed(miner_id) == False`).
  * Guardia de arranque del monitor (`startup_safety_guard_active == False`).
  * Interlock térmico (`chip_temp < 85.0°C`).
- **FR-005**: La tarjeta de alerta `render_post_blackout_card` DEBE cumplir con el formato Mobile-First estricto: ancho máximo de 32 columnas visibles (`visible_line_width(line) <= 32`).
- **FR-006**: La tarjeta DEBE incluir botones interactivos Telegram Inline:
  * `[ ▶️ Reanudar Flota ]` si hay 2 o más mineros afectados.
  * `[ ▶️ Reanudar <ID> ]` si hay 1 minero individual afectado.
  * `[ 🔕 Silenciar 1h ]` para descartar la alerta si el operador desea dejarlos detenidos.
- **FR-007**: El sistema DEBE soportar configuración en `config.json` bajo la clave `post_blackout_guard`:
  ```json
  "post_blackout_guard": {
      "enabled": true,
      "auto_resume": false,
      "grace_period_seconds": 180,
      "confirm_ticks": 2
  }
  ```
- **FR-008**: Todas las acciones (detección, envío de alerta, auto-reanudación o reanudación manual) DEBEN registrarse en `event_store` con tipo de evento `post_blackout_recovery`.

---

## 4. Success Criteria

- **SC-001**: Detección determinista: el 100% de los mineros detenidos post-corte son detectados en <= 2 ciclos de monitoreo (<= 60s).
- **SC-002**: Cero falsos positivos: ningún minero en mantenimiento deliberado (Spec 048/033) ni en proceso normal de arranque (`starting`) dispara una alerta.
- **SC-003**: Tiempo de reacción interactivo: pulsar el botón `[ ▶️ Reanudar Flota ]` restablece los mineros y ventiladores en < 3.0 segundos concurrentes.
- **SC-004**: Formato Mobile-First: el 100% de las líneas de las tarjetas generadas cumplen `visible_line_width <= 32`.
- **SC-005**: Integridad de suite: 100% de las pruebas pasando sin regresiones (>= 727 tests PASS).

---

## 5. Scope Boundaries

- **IN SCOPE**:
  - Módulo puro `app/governance/post_blackout_guard.py`.
  - Integración en bucle de `app/miner_monitor.py` y manejo de callbacks Telegram.
  - Opciones de configuración en `app/config.example.json`.
  - Pruebas unitarias en `tests/test_post_blackout_guard.py` y de integración.
  
- **OUT OF SCOPE**:
  - Encendido físico remoto de fuentes ATX o llaves térmicas motorizadas (requiere hardware externo de PDU/contactor no disponible).
  - Alteración del código interno de los firmwares Vnish.
