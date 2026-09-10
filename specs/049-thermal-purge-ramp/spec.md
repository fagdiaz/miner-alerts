# Feature Specification: Spec 049 - Active Thermal Purge Ramp & Acoustic Contrast on Safe Shutdown

**Feature Directory**: `specs/049-thermal-purge-ramp`
**Created**: 2026-09-10
**Status**: Ready for Planning
**Author**: Gemini 3.8 Flash High
**RFC Reference**: `docs/speckit/RFC_TELEGRAM_MOBILE_UX_OPTIMIZATION.md` (Condiciones C1-C10)
**Parent Spec**: `specs/048-safe-fleet-shutdown` (Safe Fleet Shutdown & Multi-Select Maintenance Mode)

---

## 1. Executive Summary & Problem Statement

En la Spec 048 (*Safe Fleet Shutdown*), se implementó con éxito el protocolo de parada suave de minado (`POST /api/v1/mining/stop`), el selector táctil multiselección, el snooze de mantenimiento de 4 horas y un período de espera de 45 segundos para el enfriamiento de los disipadores.

Sin embargo, durante las pruebas de campo y la experiencia operativa se identificaron dos oportunidades críticas de optimización térmica y sensorial:

1. **Purga Térmica Pasiva vs. Activa:**
   En la Spec 048, al detener el minado (`0 W` de hash), los ventiladores continuaban girando al duty cycle que tenían previamente (ej. 75% o 80%). Si bien la máquina ya no generaba calor nuevo, la disipación del calor remanente atrapado en las aletas de aluminio de los disipadores era lenta.
   **Solución (Rampa de Purga Activa):** Al emitir la orden de parada, el orquestador debe forzar inmediatamente una rampa de ventilación al **100% de PWM** (o duty de purga configurado, >= 85%) durante los 45 segundos de la ventana de purga. Con la carga hash apagada (0 W), el flujo volumétrico máximo de aire barre de forma ultra-acelerada el calor latente, derrumbando la temperatura de los chips desde 65°C-80°C hasta menos de 35°C en apenas 45 segundos.

2. **Falta de Contraste Acústico y Confirmación Sensorial In Situ:**
   En un contenedor o galpón minero con múltiples máquinas y ruido ambiente elevado (>75 dBA), el operador en el tablero eléctrico depende exclusivamente de mirar la pantalla del celular para saber cuándo transcurrieron los 45 segundos.
   **Solución (Contraste Acústico Inmediato):** En el segundo 45 exacto, simultáneamente con el envío de la tarjeta de Telegram `✅ ÁREA ELÉCTRICA SEGURA`, el orquestador ordena a los ventiladores de los mineros detenidos caer de golpe al **piso de reposo** (`fan_min_duty: 40%` o modo reposo ~720-1.200 RPM). El paso instantáneo del rugido del 100% (~6.000 RPM) al susurro de reposo proporciona al técnico una **señal acústica física inconfundible**: el silencio repentino de los coolers confirma que los equipos están completamente fríos y que la maniobra en la llave termomagnética o seccionador es 100% segura.

3. **Reanudación Limpia (`/resume`):**
   Al ordenar la reanudación del minado con `/resume`, el orquestador restaura el modo de ventilación normal (control dinámico del Fan Governor o modo estándar de minado), impidiendo que los equipos inicien el autotuning con ventiladores bloqueados en el piso de reposo.

---

## 2. User Scenarios & Testing

### User Story 1 - Rampa de Purga Térmica Activa al 100% (Priority: P1)
Como operador que ordena una parada segura de 1 o más mineros,
quiero que los ventiladores de los equipos seleccionados aceleren inmediatamente al 100% apenas se corte la carga de hash (0 W),
para expulsar el calor remanente de los disipadores en el menor tiempo posible antes del corte eléctrico.

**Acceptance Scenarios**:
1. **Given** una parada segura confirmada (`sd_cfm`), **When** se detiene el minado (`POST /api/v1/mining/stop`), **Then** el orquestador despacha en paralelo `set_manual_fan_duty(miner, 100)` a todos los mineros detenidos con éxito.
2. **Given** la purga en marcha, **When** el bot envía la tarjeta `🛑 PARADA EN PROGRESO`, **Then** la tarjeta indica explícitamente `• Coolers: Rampa 100% (Purga)`.
3. **Given** un minero que falle la orden de purga por timeout transitorio, **Then** el fallo se registra en el EventStore sin abortar la ventana de seguridad de los restantes equipos.

### User Story 2 - Contraste Acústico al Segundo 45 y Aviso de Área Segura (Priority: P1)
Como técnico ubicado frente al tablero eléctrico en el galpón minero,
quiero escuchar cómo los ventiladores bajan bruscamente a reposo silencioso apenas se cumplen los 45 segundos de purga,
para tener confirmación física auditiva de que los disipadores están fríos y puedo bajar la llave térmica sin tocar el teléfono.

**Acceptance Scenarios**:
1. **Given** transcurridos los 45 segundos de purga activa, **When** expira el temporizador en el hilo daemon, **Then** el orquestador despacha en paralelo la orden de reposo (`set_manual_fan_duty(miner, 40)`) a los mineros detenidos.
2. **Given** el salto de 100% a reposo (40%), **When** los ventiladores deceleran bruscamente, **Then** el bot envía la tarjeta `✅ ÁREA ELÉCTRICA SEGURA` reflejando `• Coolers: Reposo (40%) | Silencio`.
3. **Given** el estado de reposo, **When** el técnico corta la térmica, **Then** los equipos se desenergizan sin arco eléctrico y con temperaturas de chip < 35°C.

### User Story 3 - Restauración de Ventilación al Reanudar (Priority: P1)
Como operador que vuelve a energizar la flota y envía `/resume`,
quiero que los mineros reactivados restablezcan automáticamente su perfil de ventilación normal o queden bajo el control del Fan Governor,
para que no continúen en modo reposo cuando las placas de hash comiencen a consumir energía.

**Acceptance Scenarios**:
1. **Given** mineros en reposo post-purga, **When** el operador ejecuta `/resume`, **Then** tras `safe_resume_mining()` se restaura la política de ventilación activa (restableciendo la gestión dinámica del Fan Governor o elevando duty preventivo al 100%).
2. **Given** la confirmación de reanudación, **When** se envía la tarjeta `▶️ MINADO REANUDADO`, **Then** la tarjeta refleja el restablecimiento de la supervisión térmica.

---

## 3. Functional Requirements

- **FR-001**: El orquestador de parada `app/governance/fleet_shutdown.py` DEBE incorporar una rutina paralela de despacho de duty de ventiladores (`execute_parallel_fan_duty(miners, duty, password)`).
- **FR-002**: Al confirmarse la parada de minado (`execute_parallel_shutdown`), para cada minero que haya detenido su hash con éxito, el sistema DEBE despachar de inmediato `duty=100%` en paralelo.
- **FR-003**: Durante los 45 segundos de purga, la tarjeta `render_shutdown_in_progress` DEBE cumplir con el ancho <= 32 columnas visibles y reflejar la rampa activa al 100%.
- **FR-004**: Al cumplirse los 45 segundos de purga, antes o simultáneamente con el envío de la tarjeta de área segura, el sistema DEBE despachar en paralelo la orden de reposo al piso mínimo (`duty=40%` o `fan_min_duty`).
- **FR-005**: La tarjeta `render_safe_area_card` DEBE reflejar el estado de reposo acústico (`• Coolers: Reposo (40%)`), cumpliendo con el límite móvil <= 32 columnas.
- **FR-006**: Al invocar `execute_parallel_resume`, el sistema DEBE asegurar que los ventiladores salgan del modo reposo, garantizando flujo de aire adecuado durante el arranque de placas.
- **FR-007**: Toda comunicación HTTP hacia los mineros durante la purga y el reposo DEBE tener un timeout estricto de <= 2.5 segundos por petición y ejecutarse en un hilo daemon desacoplado (`ShutdownPurgeNotify`), sin bloquear el bucle de eventos principal.
- **FR-008**: Los eventos de rampa de purga y caída a reposo DEBEN registrarse en el EventStore para trazabilidad operacional.

---

## 4. Success Criteria

- **SC-001**: Los ventiladores de todos los mineros detenidos aceleran al 100% en < 2 segundos tras la confirmación de la parada.
- **SC-002**: Los ventiladores de todos los mineros detenidos caen al piso de reposo (40% PWM) en el segundo 45 exacto, generando un contraste auditivo notorio in situ.
- **SC-003**: Enfriamiento acelerado verificado: la temperatura máxima de chip desciende por debajo de 35°C al término de la purga activa de 45 segundos.
- **SC-004**: Las tarjetas de Telegram mantienen un formato Mobile-First estricto (<= 32 columnas visibles) sin truncamiento ni rupturas de Markdown.
- **SC-005**: Cero regresiones en la suite de tests: 100% de las pruebas pasando (>= 723 tests PASS).

---

## 5. Scope Boundaries

- **IN SCOPE**:
  - Función de modulación concurrente `execute_parallel_fan_duty` en `app/governance/fleet_shutdown.py`.
  - Integración de rampa 100% y caída a 40% en el flujo de parada dentro de `app/miner_monitor.py`.
  - Actualización de las tarjetas móviles en `app/governance/fleet_shutdown.py` para documentar la purga y el reposo acústico.
  - Gestión de reanudación y desacople del piso de reposo en `/resume`.
  - Pruebas unitarias en `tests/test_fleet_shutdown.py` e integración en `tests/test_safe_fleet_shutdown_integration.py`.

- **OUT OF SCOPE**:
  - Modificación de hardware de los ventiladores ni instalación de relés físicos de corte.
  - Modificación de la máquina de estados FSM del monitor.
  - Cambios en el algoritmo del Preset Balancer.
