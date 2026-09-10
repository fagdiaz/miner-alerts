# Feature Specification: Spec 051 - Fast Phase Drop vs Connectivity Discriminator

**Feature Directory**: `specs/051-phase-drop-discriminator`  
**Created**: 2026-09-10  
**Status**: Ready for Planning  
**Author**: Gemini 3.8 Flash High  
**RFC Reference**: `docs/speckit/RFC_TELEGRAM_MOBILE_UX_OPTIMIZATION.md` (Condiciones C1-C10)  
**Parent Specs**: `specs/040-dynamic-voltage-presets` (Elevator Grouping), `specs/022-adaptive-acquisition` (Parallel Acquisition), `specs/030-telegram-messaging-quality` (Telegram Priority Queue)

---

## 1. Executive Summary & Problem Statement

En una infraestructura minera ASIC, las fallas eléctricas en las líneas de alimentación (disparo de termomagnética de cabecera, apertura de diferencial, caída de una fase trifásica de red o salto de térmicas de elevadores) provocan una desenergización instantánea de los equipos conectados a ese circuito:

1. **Latencia Inaceptable del Monitoreo Convencional (30 a 90 segundos):**
   Actualmente, el monitor trata cualquier pérdida de respuesta de un minero como una falla individual de socket. Ante la caída repentina de un circuito (ej. 2 o 4 mineros apagados de golpe):
   - Cada worker agota su timeout TCP completo (5.0s por equipo).
   - Se requieren múltiples intentos o ticks consecutivos (`fails_before_alert = 3`, ciclo de 30s) para confirmar el estado `OFFLINE`.
   - La primera alerta de corte eléctrico en Telegram llega al técnico entre **45 y 90 segundos después** del incidente real, retrasando la intervención en tableros y aumentando el riesgo de desbalanceo de cargas o daño en transformadores.
2. **Confusión Diagnóstica (Corte Eléctrico vs. Caída de Switch/Fibra):**
   Una alerta genérica de "Minero OFFLINE" no distingue si se cayó el switch de red, si falló el router Wi-Fi o si realmente saltó la protección termomagnética de potencia. El operador no sabe si debe reiniciar el router o acudir inmediatamente al tablero eléctrico.
3. **Presencia de Telemetría Eléctrica de Grupo (Elevadores de Tensión):**
   La Spec 040 ya introdujo la asignación determinista de grupos eléctricos en `config.json` (`elevator_1`: S19JPRO-23 y 24; `elevator_2`: S19JPRO-25 y 26). Si ambos mineros de un mismo elevador dejan de responder en la misma ventana de milisegundos mientras el host sigue conectado, la probabilidad matemática de que sea un corte eléctrico en esa fase es $> 99.5\%$.

**Solución Propuesta (Fast Phase Drop vs Connectivity Discriminator):**
Un subsistema heurístico de clasificación ultra-rápida (< 3 segundos):
- **Autochequeo de Conectividad Local/WAN**: Verifica que el host monitor conserve conectividad de red activa (resolución local de gateway o polling exitoso de Telegram).
- **Detector de Caída al Unísono (Unison Drop)**: Identifica cuándo $\ge 2$ mineros de un mismo grupo eléctrico (o la totalidad de la flota) experimentan fallas de conexión TCP concurrentes en el mismo epoch de adquisición.
- **Supresión Rápida de Reintentos Lentos**: Corta de inmediato los reintentos redundantes para esa fase eléctrica.
- **Notificación Telegram Mobile-First de Prioridad Máxima (< 3s)**: Emite de inmediato una tarjeta crítica (`⚡ DISPARO DE CIRCUITO DETECTADO`) indicando el elevador o fase afectada y el estado de la fase gemela.

---

## 2. User Scenarios & Testing

### User Story 1 - Detección Instantánea de Disparo de Térmica por Elevador (Priority: P1)
Como operador de la granja minera,
quiero recibir una alerta inmediata en Telegram en menos de 3 segundos cuando salte la protección eléctrica de un elevador,
para acudir al tablero eléctrico de inmediato sabiendo con certeza qué circuito se desenergizó.

**Acceptance Scenarios**:
1. **Given** que el host monitor conserva conectividad activa, **When** los mineros de un mismo grupo eléctrico (ej. `elevator_1`: S19JPRO-23 y 24) caen simultáneamente en el mismo epoch, **Then** el sistema clasifica el evento de inmediato como `PHASE_DROP_GROUP` sin esperar timeouts sucesivos.
2. **Given** la clasificación de caída de fase, **When** se emite la alerta a Telegram, **Then** la notificación llega en $< 3.0$ segundos indicando claramente el elevador afectado y los mineros desconectados.
3. **Given** la tarjeta de Telegram, **When** el operador la visualiza, **Then** cumple estrictamente con el ancho Mobile-First ($\le 32$ columnas visibles).

### User Story 2 - Discriminación Precisa de Caída de Red Local vs. Corte Eléctrico (Priority: P1)
Como técnico responsable,
quiero que el sistema distinga si se desconectó el cable de red del switch o si se cortó la energía de los mineros,
para no recibir alertas engañosas de corte de fase cuando en realidad falló el router o el switch Ethernet.

**Acceptance Scenarios**:
1. **Given** que todos los mineros dejan de responder pero el gateway local o Telegram tampoco responden (host aislado), **When** se evalúa la caída, **Then** el discriminador clasifica el evento como `NETWORK_ISOLATION` y suprime la alarma falsa de corte de fase.
2. **Given** que la red local del host está viva (gateway responde en $< 100$ms), **When** caen los mineros, **Then** se valida y confirma el corte eléctrico.

### User Story 3 - Coexistencia con Mantenimiento Programado y Apagado Seguro (Priority: P2)
Como operador que ejecutó un `/shutdown` deliberado (Spec 048),
quiero que el discriminador de corte de fase ignore la desenergización planificada de los equipos,
para no generar alertas ruidosas de "disparo de térmica" cuando la desconexión fue manual y controlada.

**Acceptance Scenarios**:
1. **Given** mineros con `is_shutdown_maintenance == True` o `/snooze` activo, **When** se cortan de la red al unísono, **Then** el discriminador suprime la alerta de corte de fase.

---

## 3. Functional Requirements

- **FR-001**: El sistema DEBE implementar un módulo desacoplado `app/governance/phase_drop_discriminator.py` con lógica pura de correlación temporal y clasificación de caídas.
- **FR-002**: El discriminador DEBE utilizar el mapeo de grupos eléctricos (`electrical_group` en `config.json` o metadatos de Spec 040) para agrupar mineros por fase/elevador.
- **FR-003**: El sistema DEBE validar la salud de la conectividad local del host (`verify_host_network_liveness()`) mediante ping/socket TCP no bloqueante ($\le 500$ms) al default gateway o endpoint de red antes de declarar corte de fase.
- **FR-004**: Si todos los mineros de un grupo eléctrico ($\ge 2$ equipos) o el 100% de la flota fallan simultáneamente en un lapso $\le 2.0$ segundos, el discriminador DEBE emitir un veredicto `PHASE_DROP_ELEVATOR` o `PHASE_DROP_FLEET`.
- **FR-005**: Al confirmarse el veredicto de corte de fase, el sistema DEBE suprimir la histeresis lenta habitual de 3 ticks y encolar inmediatamente la alerta Telegram con prioridad `HIGH` (Spec 030).
- **FR-006**: La tarjeta Telegram `render_phase_drop_alert` DEBE respetar el límite móvil estricto de 32 columnas visibles (`visible_line_width(line) <= 32`).
- **FR-007**: El sistema DEBE ignorar equipos que se encuentren bajo mantenimiento intencional (Spec 048 `is_shutdown_maintenance`) o silenciamiento activo (Spec 033).
- **FR-008**: Toda detección de caída de fase DEBE registrarse en `event_store` con acción `electrical_phase_drop` y detalle de equipos afectados.

---

## 4. Success Criteria

- **SC-001**: Tiempo de detección y notificación: alerta emitida a la cola de Telegram en $< 3.0$ segundos tras la pérdida simultánea de paquetes.
- **SC-002**: Precisión de clasificación: 0 falsos positivos de corte de fase ante caídas del cable de red del host monitor.
- **SC-003**: Respeto a operaciones manuales: 0 falsas alarmas durante apagados seguros deliberados (`/shutdown`).
- **SC-004**: Formato Mobile-First: 100% de las líneas de la tarjeta cumplen `visible_line_width <= 32`.
- **SC-005**: Suite de pruebas integral sin regresiones (100% tests PASS).

---

## 5. Scope Boundaries

- **IN SCOPE**:
  - Módulo puro `app/governance/phase_drop_discriminator.py`.
  - Rutina de verificación de enlace de red local del host.
  - Tarjetas ejecutivas Mobile-First en Telegram.
  - Integración en el ejecutor de adquisición adaptativa (`app/miner_monitor.py` / `app/core/acquisition.py`).
  - Pruebas unitarias y de integración completas.

- **OUT OF SCOPE**:
  - Sensores físicos de corriente amperométrica o pinzas toroidales (no disponibles).
  - Reconexión física motorizada de térmicas (maniobra estrictamente humana).
