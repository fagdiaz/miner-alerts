# Feature Specification: Spec 048 - Safe Fleet Shutdown & Multi-Select Maintenance Mode

**Feature Directory**: `specs/048-safe-fleet-shutdown`
**Created**: 2026-09-09
**Status**: Ready for Implementation
**Author**: Gemini 3.8 Flash High
**RFC Reference**: `docs/speckit/RFC_TELEGRAM_MOBILE_UX_OPTIMIZATION.md` (Condiciones C1-C10)

---

## 1. Executive Summary & Problem Statement

En una granja de minería ASIC (Antminer S19j Pro con fuentes Bitmain APW12 y firmware Vnish), cada equipo consume entre 2.500 W y 2.700 W (~12,5 A a 220 V). Con una flota de 4 mineros (`23`, `24`, `25`, `26`), la instalación maneja una carga continua inductiva de **~10.800 W (~50 Amperes)**.

Cuando el operador necesita realizar intervenciones en la instalación eléctrica (mantenimiento de tableros, calibración de elevadores de tensión, reemplazo de térmicas o cableado), la práctica empírica de "desconectar directamente de la corriente o bajar la térmica" genera tres riesgos operacionales críticos:
1. **Arco Eléctrico y Transitorios Inductivos (*Kickback*):** Cortar 50 A en caliente produce un arco eléctrico que carboniza contactos de disyuntores y tomas, generando picos de sobretensión inductiva que viajan hacia los transistores de las fuentes conmutadas APW12.
2. **Golpe Térmico Inverso (*Thermal Heat Soak*):** Al cortar la alimentación abruptamente, los ventiladores se clavan en 0 RPM de inmediato. El calor masivo acumulado en el metal de los disipadores no se disipa al exterior y fluye hacia las placas de hash y las micro-soldaduras BGA de los chips ASIC, degradándolas por estrés térmico.
3. **Corrupción de Memoria NAND en Placa de Control:** El Linux embebido puede corromper particiones si se corta la energía mientras escribe logs o métricas.
4. **Falsas Alarmas y Tormentas de Reinicios:** Si los equipos se apagan sin previo aviso al monitor, Miner Alerts detecta caída a 0 TH/s y dispara alertas de pánico e intentos repetidos de auto-reboot.

**Spec 048** resuelve esto integralmente proveyendo un **Protocolo de Parada Segura Orquestado (*Graceful Shutdown*)** con **Selector Multiselección Táctil (*Checkboxes `⬜`/`☑️`*)** desde Telegram Mobile:
- Permite seleccionar individualmente de 1 a 4 mineros mediante casillas interactivas, apagar combinaciones arbitrarias (e.g. `23` y `25`) o la granja completa en un solo paso.
- Detiene el minado mediante la API Vnish (`POST /api/v1/mining/stop`), reduciendo la potencia de 2.700 W a 25 W por máquina en 1 segundo (caída del 99%).
- Ejecuta una **Purga Térmica Activa de 45 segundos** con ventiladores forzados hasta enfriar los disipadores (<45°C).
- Activa automáticamente un **Snooze de Mantenimiento de 4 horas** e interlocks para suspender alarmas y auto-reboots.
- Ofrece reanudación controlada (`/resume` individual o grupal) con auto-unsnooze.
- Armoniza `/help`, `/menu`, `/reboot`, `/snoozed`, `/status` y `/digest` para coherencia operacional absoluta.

---

## 2. User Scenarios & Testing

### User Story 1 - Selector Multiselección Táctil de Mineros (Priority: P1)
Como operador que administra la granja desde el celular,
quiero poder marcar con casillas interactivas `⬜`/`☑️` cualquier combinación de mineros (1, 2, 3 o los 4) y ordenar su parada segura en una sola confirmación unificada,
para no tener que repetir el procedimiento máquina por máquina.

**Acceptance Scenarios**:
1. **Given** el menú `/shutdown`, **When** el operador toca `[ ⬜ S19-23 ]` y `[ ⬜ S19-25 ]`, **Then** los botones cambian in-place a `[ ☑️ S19-23 ]` y `[ ☑️ S19-25 ]`, y el botón de acción se actualiza a `[ 🛑 APAGAR SELECCIONADOS (2) 🛑 ]`.
2. **Given** 2 mineros marcados, **When** el operador toca `[ 🛑 APAGAR SELECCIONADOS (2) 🛑 ]`, **Then** se presenta una única tarjeta de confirmación de 2 pasos con token efímero de 60s.
3. **Given** el botón `[ ✅ Marcar Todos ]`, **When** se presiona, **Then** todas las casillas se activan y el botón indica `[ ⚡ APAGAR TODOS (4) ⚡ ]`.
4. **Given** comandos de texto, **When** se escribe `/shutdown 23 25` o `/stop 23, 25`, **Then** se genera la misma confirmación unificada para ambos mineros.

### User Story 2 - Parada Suave y Purga Térmica Activa (Priority: P1)
Como operador que va a intervenir la red eléctrica,
quiero que la orden de parada corte primero la carga de potencia DC y mantenga los ventiladores encendidos durante 45 segundos,
para que los disipadores se enfríen por completo antes de que yo baje la llave térmica o desenchufe.

**Acceptance Scenarios**:
1. **Given** una parada confirmada, **When** se despacha la orden a los mineros seleccionados, **Then** se ejecuta `POST /api/v1/mining/stop` en paralelo, cayendo la potencia a <25 W por equipo.
2. **Given** la carga hash en 0 W, **When** transcurre la purga térmica de 45 segundos, **Then** los ventiladores se mantienen evacuando calor residual hasta alcanzar temperatura segura.
3. **Given** finalizada la purga, **When** el área es segura, **Then** el bot envía la notificación: `✅ ÁREA ELÉCTRICA SEGURA: Ya podés cortar la corriente`.

### User Story 3 - Mantenimiento Silencioso y Reanudación (*Resume*) (Priority: P1)
Como operador realizando trabajos eléctricos,
quiero que Miner Alerts no me envíe alertas de fallo ni intente reiniciar las máquinas mientras están en mantenimiento, y que pueda reanudarlas fácilmente con `/resume`,
para garantizar tranquilidad operativa durante la intervención.

**Acceptance Scenarios**:
1. **Given** equipos en parada segura, **When** el monitor evalúa su estado, **Then** un Snooze de Mantenimiento de 4 horas bloquea alertas de `OFFLINE`/`LOW` y anula decisiones de `auto_reboot`.
2. **Given** un intento accidental de ejecutar `/reboot` sobre un minero detenido, **Then** el comando advierte: `⚠️ Minero en Parada de Mantenimiento. Usá /resume para volver a minar`.
3. **Given** restablecida la corriente, **When** el operador envía `/resume 23 25` o toca `[ ▶️ Reanudar ]`, **Then** se ejecuta `POST /api/v1/mining/resume`, se cancela automáticamente el snooze y se restablece la supervisión normal.

---

## 3. Functional Requirements

- **FR-001**: Las tarjetas del selector, confirmación y reportes de parada DEBEN estructurarse con ancho estricto $\le 32$ columnas visibles por línea (RFC C1).
- **FR-002**: La interacción con las casillas del selector DEBE gestionarse mediante callbacks `cc:act:sd_tog:<id>:<bitmask>` con ACK inmediato ($< 50$ ms) y edición in-place del teclado (RFC C3).
- **FR-003**: El cliente Vnish DEBE implementar `stop_mining()` y `resume_mining()` mediante `POST /api/v1/mining/stop` y `POST /api/v1/mining/resume` con autenticación Bearer token transaccional (unlock/lock).
- **FR-004**: La parada de múltiples mineros DEBE ejecutarse de forma paralela y no bloqueante mediante un pool de hilos acotado o concurrencia asíncrona.
- **FR-005**: El orquestador de parada DEBE gestionar la purga térmica activa manteniendo ventiladores encendidos durante 45 segundos antes de emitir la confirmación de área segura.
- **FR-006**: Toda orden de parada DEBE requerir confirmación explícita mediante un token criptográfico efímero de 60 segundos gestionado en `CallbackTokenRegistry` (`action="shutdown"`).
- **FR-007**: La confirmación de parada DEBE aplicar un Snooze de Mantenimiento de 4 horas en `snooze_until_ts` con etiqueta explícita `Mantenimiento Eléctrico`, el cual DEBE ser revocado automáticamente al reanudar con `/resume`.
- **FR-008**: Los subsistemas de [Fan Governor](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/fan_governor.py) y [Preset Balancer](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/preset_balancer.py) DEBEN omitir de forma segura cualquier equipo con `miner_state == "stopped"`.

---

## 4. Success Criteria

- **SC-001**: Selector multiselección táctil funcional permitiendo cualquier combinación de 1 a 4 mineros con actualización instantánea de botones en pantalla.
- **SC-002**: Confirmación unificada en 2 pasos deteniendo los equipos seleccionados en simultáneo y ejecutando la purga térmica de 45s.
- **SC-003**: Cero falsas alarmas ni reboots espurios durante el período de mantenimiento eléctrico gracias al auto-snooze de 4 horas.
- **SC-004**: Reanudación limpia mediante `/resume` o botón táctil, reactivando el minado y removiendo el snooze de mantenimiento.
- **SC-005**: 100% de la suite de pruebas del repositorio pasando sin regresiones ($\ge 695$ tests PASS).

---

## 5. Scope Boundaries

- **IN SCOPE**:
  - Métodos `stop_mining()` y `resume_mining()` en `app/vnish/client.py`.
  - Módulo desacoplado `app/governance/fleet_shutdown.py` para orquestación y purga térmica.
  - Vistas táctiles en `app/telegram/command_center.py` (selector con checkboxes y diálogo de confirmación).
  - Callbacks `cc:act:sd_tog`, `cc:act:sd_req`, `cc:act:sd_cfm`, `cc:act:sd_ccl`, `cc:act:resume` en `app/miner_monitor.py`.
  - Comandos de texto `/shutdown`, `/stop`, `/resume` con soporte para argumentos múltiples (`/shutdown 23 25`).
  - Armonización de `/help` ([`help_center.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/telegram/help_center.py)), `/menu`, `/reboot`, `/snoozed`, `/status` y `/digest`.
  - Pruebas unitarias y de integración completas.

- **OUT OF SCOPE**:
  - Corte electromecánico de 220 V (físicamente inexistente en el hardware ASIC sin PDU inteligente de red).
  - Alteración de los umbrales de alerta térmica estándar de la máquina de estados.\n