# Feature Specification: Spec 093 — Watchdog de Elevadores Eléctricos, Corrección de Rachas y Auto-Recuperación de Firmware Stock

**Feature Name**: Elevator Outage Watchdog, Detection Streak Hotfix & Autonomous Firmware Recovery  
**Feature Code**: `093-elevator-watchdog-and-firmware-autorecovery`  
**Tracking Issue / Incident**: Falla de Relé en Elevador 2, Caída Silenciosa de M25/M26 y Reversión a Firmware Stock en M26  
**Status**: RELEASE DE SOFTWARE VALIDADO — cierre Git autorizado el 2026-11-15
**Author**: Antigravity Assistant & Production Engineering  
**Baseline**: V6.0 Hookified Architecture (1530 tests PASS, NSSM Service RUNNING)  
**Target Outcome**:
1. Eliminación del bug de reseteo prematuro de rachas (`offline_streak` / `low_streak`) en `DetectionHook`, asegurando que cortes de energía o caídas de conectividad transicionen inequívocamente a `OFFLINE` tras `fails_before_alert` ticks.
2. Reconexión y cableado formal de `process_phase_drop_cycle` en el pipeline de hooks supervisores, emitiendo alertas críticas de Telegram inmediatas (`⚡ DISPARO DE CIRCUITO`) ante cortes de energía en elevadores.
3. Incorporación de un watchdog autónomo de firmware stock (`StockFirmwareRecoveryHandler`) que, ante la detección de `stock_firmware_fallback_detected`, intente un reinicio Bitmain seguro (`/cgi-bin/reboot.cgi`) y, en caso de persistir, reinstale limpiamente VNish 1.2.6 desde `C:\asicto\` y restaure el perfil dorado (`miner_profiles/{miner}.json`).

---

## 1. Problem Statement & Root Cause Forensic Summary

El 26 de octubre de 2026, la planta experimentó una falla física en un relé del Elevador 2 (`elevator_2`), cortando la alimentación de `S19JPRO-25` y `S19JPRO-26` durante 95 minutos continuos. El incidente expuso tres deficiencias críticas:

1. **Bug de Anulación Prematura de Rachas en `DetectionHook`**:
   - `DetectionHook.execute` (líneas 1087-1090 de `app/core/engine.py`) evaluaba `if new_state == STATE_OK: state.offline_streak = 0; state.low_streak = 0`.
   - Durante los ticks 1 y 2 de una desconexión, como `offline_streak < fails_before_alert` (umbral 3), `classify_state` devolvía el estado previo (`OK`).
   - Al ser `new_state == "OK"`, la racha `offline_streak` era reiniciada a 0 en cada tick, impidiendo matemáticamente que cualquier minero en `OK` alcanzara 3 fallos.
   - Como resultado, durante 95 minutos los mineros permanecieron clasificados como `OK` pese a no responder, y nunca se envió la alerta `🔴 MINERO OFFLINE`.

2. **Desconexión del Ciclo de Caída de Fase / Elevador (`process_phase_drop_cycle`)**:
   - En la refactorización modular a hooks de Spec 091, la función `process_phase_drop_cycle` (diseñada en Spec 051) quedó importada en `app/core/pipeline.py` pero huérfana de invocación en los hooks.
   - Cuando el 100% de los mineros de `elevator_2` cayeron, el sistema no disparó la alerta unificada `⚡ DISPARO DE CIRCUITO`.

3. **Reversión a Firmware Stock tras Apagón Brusco**:
   - Tras el corte eléctrico abrupto, el BeagleBone Black de `S19JPRO-26` booteó en su imagen de recuperación de fábrica Bitmain (`BMMiner 1.0.0`).
   - El monitor detectó `unlock_failed: stock_firmware_fallback_detected` pero no contaba con un actuador para enviar el reboot seguro a `/cgi-bin/reboot.cgi` ni para re-flashear automáticamente VNish 1.2.6 si el reinicio fallaba.

---

## 2. User Stories & Value Proposition

### User Story 1 — Detección Confiable de Mineros Offline
> **Como** operador del centro de minado,  
> **Quiero** que cuando un minero deje de responder por socket 4028 durante 3 ticks consecutivos, transicione inmediatamente a `OFFLINE` y me notifique por Telegram,  
> **Para** no operar a ciegas ante desconexiones de red o cortes individuales de energía.

### User Story 2 — Alerta Crítica Inmediata por Falla de Elevador Eléctrico
> **Como** supervisor de infraestructura eléctrica,  
> **Quiero** que el sistema detecte cuando todos los mineros de un mismo elevador (`elevator_1` o `elevator_2`) caen simultáneamente y envíe una alerta urgente `⚡ DISPARO DE CIRCUITO / CORTE EN ELEVADOR`,  
> **Para** acudir de inmediato al tablero eléctrico a verificar térmicas y relés pegados.

### User Story 3 — Auto-Recuperación de Firmware Stock de Bitmain
> **Como** ingeniero de operaciones,  
> **Quiero** que si un minero bootea en firmware stock tras un apagón, el supervisor intente un reboot de NAND vía HTTP Digest `/cgi-bin/reboot.cgi`, y si persiste, ejecute la instalación desatendida de VNish 1.2.6 desde `C:\asicto\` reinyectando las pools y presets correspondientes,  
> **Para** que la flota vuelva a hashear a potencia nominal sin requerir intervención manual.

---

## 3. Scope & Technical Specifications

### In Scope
1. **Hotfix de Rachas en `app/core/engine.py`**:
   - Modificar `DetectionHook.execute` para que `offline_streak` y `low_streak` solo se reseteen cuando el minero responda favorablemente (`responded=True` y rate por encima del umbral) o cuando transicione formalmente desde otro estado a `STATE_OK`.
2. **Reconexión de `process_phase_drop_cycle` en `app/core/pipeline.py`**:
   - Invocar `process_phase_drop_cycle` en `GovernanceHook` (o `DetectionHook`), alimentado con `tick_failed_miners` y `tick_responded_miners`, garantizando el bypass de histéresis y la alerta Telegram de elevador.
3. **Módulo de Auto-Recuperación de Firmware (`app/governance/firmware_recovery.py`)**:
   - Actuador con cooldown y límites de intentos para:
     a) Disparar reboot Bitmain a `http://{host}/cgi-bin/reboot.cgi`.
     b) Si persiste tras el reinicio, invocar `FirmwareFlasher.flash_bitmain_nand()` con `C:\asicto\asicto-s19jpro-bb-nand-v1.2.6-install.tar.gz`.
     c) Restaurar el perfil guardado en `data/miner_profiles/{miner}.json`.
     d) Notificar el progreso detallado a Telegram.
4. **Pruebas Automatizadas**:
   - Pruebas unitarias de streaks en `tests/test_detection_hook_streaks.py`.
   - Pruebas de integración de alerta de elevador y auto-recuperación de firmware.

### Out of Scope
- Modificación del hardware de los elevadores físicos ni de relés.

---

## 4. Invariants & Safety Gates
1. **Invariante de Test Suite**: $\ge 1530$ tests PASS, 0 fallos, 0 regresiones.
2. **Invariante de No Bloqueo**: El flasheo o reinicio de firmware debe ejecutarse en hilos desacoplados (`threading.Thread`), sin bloquear el bucle de supervisión ni el poller de Telegram.
3. **Invariante de Cooldown de Elevador**: Las alertas de disparo de circuito deben respetar un cooldown mínimo de 300 segundos para evitar tormentas de mensajes.


## Contención P0 del incidente térmico — 2026-11-12

El operador autoriza resolver en esta sesión, incluyendo ajustes locales y reinicios controlados.
Logs muestran M24 a 87–88 C, downstep 2100 W rechazado HTTP 400 y ciclos pausa/reanudación.
La API de firmware confirma que 2100 no existe; escala inferior válida: 2300, 2150, 2000,
1850, 1800, 1740. Piso igual al techo impedía la reducción nativa.
Alcance del hotfix de estabilización de la spec activa: escalera compartida ya validada,
prioridad al preset observado, piso nativo libre, no confirmar estados/recuperación ante fallos
API y deduplicación térmica por minero/tipo durante 900 s. No nueva spec concurrente.
La primera alerta de pausa crítica usa un slot independiente y no queda silenciada por downsteps.
Los contadores de avisos viven en el estado del único loop de detección; se reinician al arrancar
el servicio para conservar la primera alerta tras startup. No nuevos hilos ni cambios de locks.
Pruebas contractuales actualizadas únicamente para permitir el piso térmico inferior.
Las pools ViaBTC están activas y aceptan shares. La causa eléctrica no está confirmada.

Contrato de recuperación verificado en vivo el 12 de noviembre: tras guardar el preset
reducido, usar reinicio del proceso de minado detenido para cargar los ajustes. Plain
resume/start podía retornar éxito dejando restart_required activo. El actuador conserva
la guarda QA y el gate de enfriamiento; no se reinicia el sistema operativo del ASIC.


## Reconciliación operativa 2026-11-14

Intención del operador: recuperar powerups cuando exista margen térmico y avisos útiles,
preservando seguridad de los elevadores y evitando spam. La configuración dinámica
posterior al hotfix del día12 es la intención vigente; no restaurar caps temporales viejos.

Hallazgos: servicio cargado desde12/11 17:12 con hash810b32c6, archivo modificado después.
Firmware conserva techos2300/2500/2150/2000 aunque config indica2700/2500/2700/2500.
M25/M26 a77 C ya consumen2148/1998 W: el preset configurado1800 no refleja el tier
activo del switcher. Balancer en dry-run; no habilitar un segundo controlador de potencia.
Alertas globales habilitadas, snoozes vencidos. Cambios nativos de potencia no tenían aviso.

Solución: recarga del servicio y alineación solo de límites VNish (no forzar preset activo
ni reiniciar ASIC). VNish decide con rise79/decrease84/check300, piso1740 y techosC3;
presupuesto nominal máximo5200W por elevador (por debajo de5400W en off-peak).
Aplicar M25 primero y observar antes de habilitar el techo M26. No cambiar pools.

Nuevo observador de potencia en DetectionHook: lee chain_power_w_total; requiere minero
respondiendo, tres cadenas, hashrate>=umbral y elapsed>=180. Estado transitorio por minero,
propiedad exclusiva del loop de detección; no nuevos threads, locks ni actuadores.
No persiste baseline al reiniciar: primera muestra silenciosa evita tormenta de startup.
Confirmación90s, resolución50W, cambio mínimo100W; cooldown900s conserva último cambio.
No interpreta 0W por pausa o falta de telemetría como cambio de perfil. Respeta snooze,
mantenimiento y QA. Usa la cola Telegram existente; no envía directamente desde otro hilo.


## Incidente compartido y techo empírico — 2026-11-14 noche

El operador solicita diagnóstico causal y máximo rendimiento sostenible. Continúa la
estabilización de la spec093 (watchdog de elevadores y firmware), sin otra spec concurrente.
Datos: logs21:48:47/21:48:51 registran chain#1 break enM25/M26. Mismos ticks de reinicio,
79C antes del fallo, potencia de ambos2300W estable, M23/M24 sin reinicio. No afirmar corte
AC, sobrecarga o cambio de potencia como causa confirmada. Falta medición de entrada.

Se agregan: correlación de reinicios inesperados por grupo en45s, cooldown900 independiente
por grupo, evento elevator_cascade_detected compatible con el analizador existente y aviso
neutral de evidencia (no declara circuito disparado). Estado acotado, propiedad del único
DetectionHook, sin nuevos threads/actuadores ni modificación de clasificación individual.
No se deriva intervención física de la correlación ni se usa estado persistido como trigger.

Recuperación firmware: last_active_boards=None no es evidencia de stock ni falla de placas;
helper puro evita comparación None<int. QA retorna antes de crear threads/actuar. La opción
stock_firmware_reflash_enabled=False se respeta antes de iniciar flasheo.

Política operativa: conservarM23hasta2700 yM24/M26hasta2500 si temperatura lo permite;
limitarM25a2500 por concentración de fallos a2700. Ambos del elevador2 quedan con máximo
5000W reportados. No sacrificar toda la flota ni fijar potencia baja permanentemente.
La selección es un compromiso de estabilidad, no prueba de óptimo económico global.
Comparaciones normalizadas por exposición son observacionales y pueden tener sesgos de
clima/selección/atribución de reinicios. No se estiman ganancias monetarias sin tarifa/pool.

Guardia térmica: para stepdown activo, potencia medida prevalece sobre el preset configurado.
Durante pausa se guarda el tier de reanudación medido en campoopcionalthermal_resume_preset;
validación de escalera/techo y defaults conservadores para estados legados. No nuevo trigger
persistido ni cambio de criterio de pausa/cooldown/QA. Se usa señal fresca de adquisición.


## Estabilización de mensajería del incidente — 2026-11-15

Una sola spec activa. Corregir hallazgos confirmados del chat: snooze vencido en Status;
digest separa reinicios detectados de acciones reboot; entrega con hasta tres intentos
por mensaje, timeouts acotados y espera Retry-After hasta30s (mayores no se adelantan).
Solo respuesta HTTP200 y ok=true confirma entrega. Fallo final explícito y sin dedupe
de éxito. Reintentos son al-menos-una-vez: respuesta perdida puede duplicar un aviso,
nunca ejecutar ni reenviar comandos del operador a los mineros. Sin nuevos threads.

Agrupar alternancia LOW/HASHBOARD por minero durante300s, conservando primera
alerta de cada severidad, OFFLINE inmediato según histéresis existente y recuperación.
No cambiar clasificación, streaks ni actuadores. Respetar snooze/mantenimiento.
Atribuir soft restart únicamente con evento de éxito reciente120s y todavía no asociado
a otra caída de uptime; no usar timestamp de intento como prueba de éxito. Sin escribir
estado vivo ni cambiar límites de potencia.


## Cierre de release de software autorizado — 2026-11-15

El operador autoriza expresamente commit y push del cierre 093 para continuar con094.
Gate de software8/8 PASS,1604 pruebas y75subpruebas PASS; versión activa desde15:13:46.
La observación D+1 y la causa física deM26 permanecen abiertas como seguimiento operativo,
sin afirmar reparación física. La próxima spec de respaldos no cambia controles de mineros.
