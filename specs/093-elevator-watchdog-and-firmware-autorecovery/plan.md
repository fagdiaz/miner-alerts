# Implementation Plan: Spec 093 — Watchdog de Elevadores Eléctricos, Corrección de Rachas y Auto-Recuperación de Firmware

**Feature**: `093-elevator-watchdog-and-firmware-autorecovery`  
**Dependencies**: Arquitectura V6.0 Hookified (`app/core/engine.py`, `app/core/pipeline.py`)  
**Risk Level**: Medio (Gobernanza y Detección de Estados)  
**Safety Gates**: `py_compile`, `pytest` $\ge 1530$ tests PASS, `speckit-qa`, `speckit-stabilize` 8/8 gates.

---

## 1. Technical Architecture & File Impact

### Módulos Modificados
1. `app/core/engine.py`:
   - Corregir el reseteo de `offline_streak` y `low_streak` en `DetectionHook.execute`.
   - Garantizar que la racha solo se limpie al transicionar de un estado anómalo a `STATE_OK` o cuando `responded` sea `True`.
2. `app/core/pipeline.py`:
   - Cablear la llamada a `process_phase_drop_cycle` en `GovernanceHook.execute` o `DetectionHook.execute`.
   - Pasar `tick_failed_miners` y `tick_responded_miners` procesados en `AcquisitionHook`.
   - Conectar el manejador de auto-recuperación de firmware cuando se detecte `stock_firmware_fallback_detected`.
3. `app/governance/firmware_recovery.py` (Nuevo):
   - Funciones `reboot_stock_bitmain(host, timeout_s=5.0) -> bool`.
   - `attempt_stock_firmware_recovery(host, miner_name, config, ...) -> Tuple[bool, str]`.
   - Control de estados transitorios (`_FIRMWARE_RECOVERY_ATTEMPTS`, cooldowns, candados para evitar dobles disparos).
4. `tests/test_spec093_elevator_and_firmware_recovery.py` (Nuevo):
   - Pruebas deterministas para:
     a) Racha offline incrementando hasta 3 y transicionando a `OFFLINE`.
     b) Disparo de alerta de elevador cuando todos los mineros de un grupo caen.
     c) Reintento de reboot Bitmain y fallback a `FirmwareFlasher`.

---

## 2. Step-by-Step Execution Sequence

1. **Paso 1: Corrección de Rachas en `app/core/engine.py`**:
   - Modificar las líneas 1087-1092 de `DetectionHook.execute`:
     ```python
     if new_state == STATE_OK:
         if prev_state != STATE_OK:
             state.low_streak = 0
             state.offline_streak = 0
         state.hashboard_since_ts = None
         state.auto_restart_count = 0
     ```
2. **Paso 2: Creación del Módulo de Auto-Recuperación `app/governance/firmware_recovery.py`**:
   - Implementar `reboot_stock_bitmain` con autenticación Digest.
   - Implementar `process_stock_firmware_fallback` que maneje el escalonamiento (intento 1: reboot, intento 2: flash + restore profile) con notificaciones a Telegram.
3. **Paso 3: Cableado en `app/core/pipeline.py`**:
   - Cablear `process_phase_drop_cycle` dentro de `GovernanceHook` usando los mineros fallidos y respondidos de la etapa de adquisición.
   - Integrar la invocación de `process_stock_firmware_fallback` cuando se reporte `stock_firmware_fallback_detected`.
4. **Paso 4: Pruebas y Validación**:
   - Crear suite de pruebas exhaustiva en `tests/test_spec093_elevator_and_firmware_recovery.py`.
   - Compilación con `py_compile`.
   - Ejecutar suite de regresión completa (`pytest`).
5. **Paso 5: Preflight QA y Estabilización**:
   - Ejecutar `speckit-qa` (`.agents/skills/speckit-qa/scripts/preflight.ps1`).
   - Reiniciar el servicio `MinerAlerts` en Windows y verificar telemetría en vivo.
   - Ejecutar `speckit-stabilize` (`preflight_stabilize.ps1`).
   - Actualizar documentación (`DEVELOPMENT_LOG.md`, `ROADMAP.md`, `prompt.txt`).


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


## Iteración M — Mensajería y evidencia, 2026-11-15

Riesgo HIGH por transporte. Render Status compara snooze con hora; digest agrega
restart_detected en clave nueva y conserva reboots_24h para compatibilidad.
Sender usa helper tipado común para envío directo/worker; tres intentos, errores
transitoriosConnectionError/Timeout/429/5xx, sin reintentar4xx permanentes. Heartbeat
actualizado antes/después y en esperas; cola y contrato15campos conservados, sin locks
durante red/sleep. Dedupe solo tras éxito confirmado; logs sin texto/token/chat_id.

DetectionHook es único propietario de una compuerta transitoria de notificaciones
por minero/tipo; no persistencia ni nuevas escrituras al estado de decisiones.
EventStore agrega lectura bajo su lock propio para éxito softrestart no consumido;
no mantener state_lock durante SQLite. Ventana120s evita heredar3600s de reboot.
No alterar decisiones de recuperación/reinicio ni config local.

Validar helper de transporte con red simulada, worker, Status, digestSQLite y replay
LOW/HASHBOARD del chat, límites, independencia, snooze y atribución de éxito/fallo.
QA preflight antes de implementar; suite completa antes de recarga y speckit-stabilize
de cierre con evidencia de la activación, antes de cualquier commit/push.
Backups y economía quedan como paquetes posteriores diseñados en plan secuencial,
sin otra spec activa ni implementación concurrente. Commit/push manuales.
