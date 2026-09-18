# Historial de Desarrollo y Cambios - Miner Alerts

Este archivo registra las specs y cambios completados que tienen respaldo en el codigo, la documentacion o evidencia operativa vigente, en orden cronologico inverso.
La entrada mas reciente debe agregarse inmediatamente debajo de este bloque.

## [2026-09-18] - Auditoría QA y Spec 077: Gobernanza Escalonada de Elevadores, Bajada Compartida y Soft-Contingencia Horaria (PROP-012)

* **Objetivo**:
  1. Ejecutar auditoría integral de QA y corrección de bugs en lógica de soak tick de contingencia (`adaptive_contingency.py`), normalización de reseteos en Telegram y eliminación de imports duplicados.
  2. Implementar `PROP-012` / `Spec 077` para modelar y gobernar las restricciones físicas de la infraestructura eléctrica: acometida compartida desde la calle entre ambos elevadores y mitigación de transitorios inductivos ($L \frac{di}{dt}$) y calentamiento por Joule ($I^2 R$).
  3. Establecer la cola de transición escalonada para toda la instalación (*Facility-Wide Staggered Queue*): exactamente 1 minero ejecuta cambios de preset por ciclo con una ventana de reposo obligatoria de 180 segundos (*Facility Settle Window*).
  4. Implementar presupuesto dinámico por transformador elevador ($\le 5000\text{W}$ en horario pico, $\le 5400\text{W}$ en horario valle) y hacer valer la preferencia de equilibrio simétrico (priorizar parejas 2x 2500W antes de intentar combinaciones asimétricas 2700W + 2300W).
  5. Implementar Soft-Contingencia Horaria quirúrgica: en días hábiles (Lunes a Viernes), desescalada paulatina (1 a la vez espaciada por 180s) hacia 2500W durante el pico matutino (08:30-10:30 hs) y nocturno (19:30-22:30 hs). Fuera de los picos (19 horas en días de semana y 100% de fines de semana), se autoriza la exploración escalonada de máxima potencia hacia 2700W (hasta 5400W/elevador y 10.8 kW en acometida).
  6. Preservar la co-gobernanza con VNish: fijar la macro-envolvente en el monitor con clampeo estricto de `top_preset` para evitar que el daemon térmico interno desbalancee los elevadores en ambiente frío, permitiendo que VNish administre la sintonización fina de chips.
* **Auditoría QA y Hallazgos Subsanados**:
  - *Falla de recuperación de minero robusto en `adaptive_contingency.py`*: `soak_tick` sólo verificaba al canario, dejando al compañero robusto degradado indefinidamente. Reparado incorporando evaluación y rampa ascendente del compañero.
  - *Sobreescritura espuria por fallback 2700W en canario*: `canary_initial_preset or DEFAULT_MAX_CEILING` forzaba a mineros canarios no degradados a subir a 2700W. Corregido para considerar al canario degradado sólo si `canary_initial_preset` fue efectivamente fijado.
  - *Condición de `is_full_restore`*: Redefinida para exigir que ambos mineros del elevador alcancen sus respectivos presets iniciales antes de desactivar la contingencia.
  - *Fallback seguro en amortiguador de arranque*: `inrush_dampener_restored_preset` ahora recurre al preset actual (`curr_p`) antes de caer al techo global.
  - *Reseteo de contingencia en Telegram*: `/contingencia reset` ahora abarca a todos los grupos de `DEFAULT_CANARY_MAP` incluso en arranques en frío donde el diccionario de estados esté vacío.
* **Componentes Implementados / Modificados**:
  - `app/governance/elevator_budget.py`: Módulo funcional puro con `FacilityBudgetState`, cálculo de potencia de grupo, `evaluate_soft_contingency_schedule()`, `can_step_up_within_budget()`, `evaluate_symmetric_balance_preference()`, y compuerta de 4 niveles `evaluate_facility_transition_permission()`.
  - `app/governance/preset_balancer.py`: Extensión de `evaluate_balancer_step()` con soporte de `facility_state`, acciones `ACTION_HOLD_FACILITY_SETTLE`, `ACTION_HOLD_BUDGET_LIMIT`, `ACTION_HOLD_ASYMMETRY_PREFERENCE` y `ACTION_HOLD_SCHEDULE_CEILING`.
  - `app/miner_monitor.py`: Persistencia de `facility_budget` en `state.json`, secuenciación de actuador único en `execute_balancer_cycle()` bajo ejecutor acotado con timeout de flota, y orquestador de Soft-Contingencia en el bucle principal.
  - `tests/test_elevator_budget.py`: 21 tests unitarios exhaustivos para estados de reposo, límites de calendario y cálculo de presupuestos.
  - `tests/test_adaptive_contingency.py`: Tests añadidos para recuperación escalonada de minero robusto y desescaladas secuenciales.
  - `tests/test_preset_balancer.py`: Tests unitarios para interbloqueos de ventana de reposo de bajada compartida, techo de horario pico y preferencia simétrica.
* **Resultados & Verificación**:
  - Suite de regresión global: **1288/1288 tests PASS**, 75 subtests PASS en 43.28s (0 fallos, 0 errores, 0 regresiones).
  - Compilación limpia con `py_compile` en todos los módulos modificados.
  - Estado del Minero 25: 378/378 chips sanos y hasheando de forma estable en 2300W (87.5 TH/s, 59-81°C).
  - Servicio Windows `MinerAlerts` actualizado y certificado.

## [2026-09-18] - Auditoría QA y Spec 076: Reinstalación Autónoma de Firmware VNish en NAND y Calibración de Escalera de Hardware S19j Pro (PROP-011)

* **Objetivo**:
  1. Ejecutar auditoría integral de QA y corrección de bugs/fallas de buenas prácticas en el sistema de monitoreo.
  2. Implementar `PROP-011` / `Spec 076` para permitir la reinstalación autónoma y remota de firmware VNish 1.2.6 en NAND eMMC (BeagleBone Black) sobre mineros que hayan caído al firmware de fábrica de Bitmain tras apagones o corrupción de memoria.
  3. Calibrar la escalera autoritativa de hardware de Antminer S19j Pro eliminando peldaños teóricos (`2100W`, `2800W`) que provocaban rechazos `HTTP 400 Bad Request`, incorporando el peldaño `1800W`, y remediando el bloqueo que atrapaba al Minero 23 a 1800W.
  4. Implementar aprovisionamiento automático post-booteo (`miner_provisioner.py`) inyectando pools de Binance, preset de potencia y restaurando la matriz guardada de 378 chips afinados desde perfiles dorados.
  5. Desplegar comando interactivo de Telegram `/flash_vnish <miner>` con confirmación en dos pasos, protección contra ejecuciones concurrentes y reporte en tiempo real de fases a un worker daemon desacoplado.
* **Auditoría QA y Hallazgos Subsanados**:
  - *Vulnerabilidad de coincidencia parcial en `find_preset_index`*: Arreglado en `app/governance/preset_balancer.py` reemplazando `in` sobre strings por extracción numérica de watts vía regex y correspondencia exacta con `nominal_power_w`.
  - *Calibración de escalera S19j Pro (9 peldaños)*: `1740W, 1800W, 1850W, 2000W, 2150W, 2300W, 2500W, 2700W, 2970W`. `DEFAULT_MIN_PRESET_FLOOR` elevado a `2150W`.
  - *Cableado de Headroom Chilling (Spec 075)*: Conectado `decision.boost_cooling_requested` en `preset_balancer.py` a `st.boost_cooling_active` en `miner_monitor.py` y `boost_cooling=True` en `compute_governor_step`.
  - *Calibración térmica de emergencia*: `fan_governor_emergency_temp_c` configurado en `83.0°C` por defecto en `miner_monitor.py`.
  - *Desbloqueo de top preset en rampa*: Soporte de `top_preset` explícito en `safe_set_miner_preset` y rampa de 2700W en `miner_monitor.py` pasando `clamp_top_preset=False, top_preset="2700"`.
  - *Resolución de nombres en Telegram*: Corregidas llamadas a `display_name(miner)` que pasaban diccionarios en lugar de strings en `flash.py` y `miner_monitor.py`.
* **Componentes Implementados / Modificados**:
  - `app/network/firmware_flasher.py`: Módulo autónomo de flasheo con detección de Bitmain stock en puerto 80 (`is_stock_bitmain`) y carga multipart HTTP Digest `/cgi-bin/upgrade.cgi` (`flash_bitmain_nand`) con streaming seguro y tolerancia a desconexión por reboot.
  - `app/governance/miner_provisioner.py`: Inyección automática de credenciales de pool (Binance), preset nominal (2300W / 2700W) y matriz de 378 chips afinados desde `data/miner_profiles/{miner_name}.json`.
  - `app/telegram/commands/flash.py`: Comando `/flash_vnish` con verificación en 2 pasos (botones inline `flash_cfm`/`flash_ccl` o `CONFIRM`), guardas de concurrencia y pipeline en worker daemon desacoplado.
  - `app/telegram/callbacks.py` y `app/miner_monitor.py`: Manejadores para callbacks `flash_cfm` y `flash_ccl`, integración de worker daemon y alias `generate = create_token` en `CallbackTokenRegistry`.
  - `app/telegram/router.py`: Registro de `FlashVnishCommand` y sus alias (`flash`, `flashear`, `instalar_firmware`).
  - `tests/test_firmware_flasher.py`: 9 tests unitarios para sondeo y carga de firmware Bitmain.
  - `tests/test_miner_provisioner.py`: 5 tests unitarios para autenticación, inyección de pools, presets y matrices de afinación.
  - `tests/test_telegram_flash_command.py`: 12 tests para ayuda, validación, confirmación inline, y simulación integral de pipeline.
  - `tests/test_telegram_callbacks.py`: Pruebas de parsing y longitudes límite para `flash_cfm` y `flash_ccl`.
* **Resultados & Verificación**:
  - Suite de regresión global: **1262/1262 tests PASS** en 41.69s (0 fallos, 0 errores, 0 regresiones).
  - Compilación limpia con `py_compile` en todos los módulos de producción.
  - Telemetría en vivo: Minero 23 normalizado y estable en 2300W (78-81 TH/s). Minero 24 en 88-90 TH/s con VNish 1.2.6 y 378 chips afinados. Flota completa al 100% de salud.
  - Servicio Windows `MinerAlerts` reiniciado y certificado en producción.

## [2026-09-18] - Implementación Spec 075: Recuperación Suave de Hasheo, Headroom Chilling y Diagnóstico Raíz Minero 24 (PROP-010)

* **Objetivo**:
  1. Diagnosticar la causa raíz de la falla del Minero 24 (`192.168.100.24`) tras el apagón de las 11:52 hs e incorporarla como defensa en el motor supervisor.
  2. Implementar `PROP-010` / `Spec 075` para proteger las fuentes Bitmain APW12 contra auto-bloqueo (*Latch-Off*) ante transitorios inductivos y reinicios de software violentos a plena potencia.
  3. Resolver la trampa de suboptimización térmica (*Sub-Optimal Fan Trap*) acoplando el Preset Balancer con el Fan Governor mediante el protocolo de **Headroom Chilling** (forzado temporal de ventilación al 100% ante bloqueo térmico en 2500W para desbloquear 2700W con +6 TH/s de ganancia).
  4. Implementar desescalada preventiva (*Soft-Landing Clamp* a 1800W) antes de emitir órdenes de reinicio de minado (`safe_restart_mining`) y ventana pasiva de normalización (*Settle Window* de 120s).
  5. Calibrar el umbral de emergencia del Fan Governor a 83.0°C.
  6. Blindar el sistema contra bucles infinitos de reinicio ante fallas físicas de sensores I2C o caídas al firmware de fábrica de Bitmain (NAND).
* **Diagnóstico Raíz Minero 24**:
  - Al retornar la energía tras el corte de las 11:52 hs, el Minero 24 no detectó la tarjeta MicroSD con VNish en su placa de control BeagleBone Black (TI AM335x) y cayó al firmware de fábrica Bitmain 2021 (`BMMiner 1.0.0` / HTTP Digest realm `"antMiner Configuration"`).
  - El firmware base cargado (`BHB42601`) no coincide con las placas instaladas (`BHB42621`), generando en el Kernel Log: `Sweep error string = J255:4. Fixture data load failed, exit. ERROR_SOC_INIT: basic init failed! stop_mining: basic init failed! ****power off hashboard****`.
  - El monitor detectó 0 TH/s y despachó 3 auto-reboots inútiles hasta el bloqueo por ventana (`blocked_by=window`).
  - Mitigación implementada: Detección automática en `unlock_miner()` de `stock_firmware_fallback_detected` e inhibición absoluta de reinicios en caliente (`INTERLOCK_STOCK_FIRMWARE`, `ACTION_INHIBIT_HARDWARE_FAULT`) junto con alerta diagnóstica en Telegram.
* **Componentes Modificados / Creados**:
  - `app/governance/safe_recovery.py`: Módulo funcional puro con `SafeRecoveryState`, `RecoveryDecision`, `evaluate_safe_recovery`, `evaluate_headroom_chilling`, ventana de 120s, pre-clamp a 1800W, soak de 180s y compuertas de inhibición para fallas de hardware/firmware.
  - `app/governance/fan_governor.py`: Integración de `boost_cooling` (Headroom Chilling, Regla 6b) y calibración de `emergency_temp_c` a 83.0°C.
  - `app/governance/preset_balancer.py`: Extensión de `StabilityMetrics` con `fan_pwm_percent`, `BalancerDecision` con `boost_cooling_requested` y evaluación proactiva de Headroom Chilling en Regla 3.
  - `app/miner_monitor.py`: Integración de Soft-Landing pre-clamp en `_async_execute_mining_restart`, ventana de settle de 120s, restauración de rampa tras 180s en OK, inhibición defensiva ante `stock_firmware_fallback_detected`, y persistencia en `MinerState`.
  - `app/core/reboot_safety.py`: Adición de `INTERLOCK_HARDWARE_FAULT` e `INTERLOCK_STOCK_FIRMWARE` a las compuertas de interlock de auto-reboot.
  - `app/core/state_manager.py`: Actualización de serialización de `MinerState` preservando paridad exacta en `state.json`.
  - `app/vnish/client.py`: Detección de header HTTP Digest/lighttpd para identificar `stock_firmware_fallback_detected`.
  - `app/config.example.json`: Inclusión de `safe_recovery_settle_window_seconds: 120.0`, `safe_recovery_pre_clamp_preset: "1800"`, `safe_recovery_ramp_up_soak_seconds: 180.0`, y `fan_governor_emergency_temp_c: 83.0`.
    - `tools/backup_miner_profiles.py`: Utilidad de respaldo y restauración de perfiles dorados de sintonización (/api/v1/settings con matrices de chips y pools) para restauraciones instantáneas ante reflasheos de NAND.
  - `tests/test_safe_recovery.py`: 7 tests unitarios nuevos cubriendo toda la máquina de estados y fallas de hardware.
  - `tests/test_fan_governor.py`: 21 tests (3 nuevos para Headroom Chilling).
  - `tests/test_preset_balancer.py`: 20 tests (3 nuevos para Headroom Chilling).
  - `tests/test_reboot_safety.py`: 17 tests (2 nuevos para interlocks de stock firmware y fallas físicas).
* **Resultados & Verificación**:
  - Suite completa de regresión: **1236/1236 tests PASS** en 39.5s (0 fallos, 0 errores, 0 regresiones).
  - Auditoría exhaustiva de concurrencia y subprocesos completada: jerarquía de cerrojos L1/L2 invariante (`state_lock` para memoria, `_SAVE_STATE_LOCK` para disco atómico), cero I/O de red bajo cerrojos, prevención de carreras en hilos `AutoRestart_{name}` mediante `last_auto_restart_ts` atómico, y blindaje de todas las mutaciones de estado de recuperación suave bajo `with state_lock:`.
  - Verificación en vivo y recuperación completa de Minero 24: Tras reinstalación limpia en NAND eMMC con Hashcore Toolkit (`asicto-s19jpro-bb-nand-v1.2.6-install.tar.gz`), se inyectaron pools de Binance Pool vía API. El minero salió de `failure`, completó su auto-tuning con 378/378 chips afinados, y alcanzó 81.5 TH/s en estado OK consolidado.
  - Respaldo de perfiles dorados de la flota completa ejecutado exitosamente en `data/miner_profiles/` (S19JPRO-23, S19JPRO-24 con 378 chips afinados, S19JPRO-25 con 293 chips afinados y S19JPRO-26 con 162 chips afinados).
  - Servicio Windows `MinerAlerts` reiniciado y certificado en producción. Flota 100% en estado OK.

## [2026-09-17] - Hotfix Operativo & Diagnóstico Eléctrico: Resolución de Bugs en Telegram/Hashcore y Análisis de Caída Minero 25

* **Objetivo**:
  1. Evaluar la hipótesis de corte térmico/eléctrico en el minero 25 (>2700W / disparo de llave termomagnética).
  2. Resolver bug crítico en Hashcore CLI: `TypeError: subprocess.run() got multiple values for keyword argument 'creationflags'` que impedía la ejecución de reinicios remotos por Telegram.
  3. Resolver bug en comando Telegram `/reboot_no_ok`: solo contemplaba `STATE_LOW`, omitiendo mineros `OFFLINE` y `HASHBOARD` (devolviendo "No hay mineros en estado NO-OK").
  4. Resolver bug de latencia y timeouts en botones inline de Telegram: variable `_TELEGRAM_QUEUE` no propagada al namespace del módulo causaba degradación síncrona en el poller thread y expiración de callbacks (`query is too old`).
  5. Validar con 1221 pruebas unitarias y desplegar en producción reiniciando el servicio Windows `MinerAlerts`.
* **Componentes Modificados**:
  - `app/miner_monitor.py`:
    - Sanitización de `kwargs` en `_execute_subprocess_no_window` para evitar colisión de `creationflags=_NO_WINDOW_CREATION_FLAGS`.
    - Corrección de `is_miner_no_ok(state)` para evaluar `state.state != STATE_OK` (abarcando `OFFLINE`, `HASHBOARD`, `UNKNOWN`).
    - Propagación explícita `_self_module._TELEGRAM_QUEUE = _TELEGRAM_QUEUE` en el arranque del servicio.
  - `tests/test_reboot_safety.py`: Adición de `test_is_miner_no_ok_classifications` cubriendo todos los estados.
* **Resultados & Verificación**:
  - Suite de pruebas unitarias: **1221/1221 tests PASS** en 34.19s (0 fallos, 0 errores).
  - Servicio `MinerAlerts`: Reiniciado exitosamente (PID 19204), adquisición adaptativa en curso y cola asíncrona de Telegram restablecida.
  - Diagnóstico Minero 25: Evidencia en telemetría descarta que estuviera consumiendo >2700W (operaba a 2298W estables). A las 19:10:05 revivió y hasheó a 42.7 TH/s en 3 cadenas antes de caer a las 19:11:10 (ausente de ARP/ping). Hipótesis física confirmada: apertura de protección térmica/disyuntor local o latch-off de APW12 ante el pico de arranque.

## [2026-09-17] - Implementación en Laboratorio & Validación Spec 074: Amortiguador de Inrush Pareado de Elevador (PROP-009)

* **Objetivo**:
  1. Diseñar e implementar el mecanismo de contingencia pareada y amortiguación de inrush inductivo (`PROP-009`, Spec 074) para eliminar las cascadas de reinicios en pares eléctricos (`elevator_1`: 23 & 24, `elevator_2`: 25 & 26).
  2. Resolver **H1 (Fallo de coincidencia de nombres)**: Reemplazar comparaciones estrictas de cadenas `m.get("name") == target` por coincidencia canónica normalizada `normalize_miner_name(...)`, sincronizando además `balancer_preset` en los estados en memoria.
  3. Resolver **H2 (Conflicto con demonio térmico Vnish)**: Habilitar `clamp_top_preset=True` en `set_miner_preset` y `safe_set_miner_preset` de `app/vnish/client.py`, fijando tanto `preset` como `preset_switcher.top_preset` para evitar que Vnish sobreescriba la contingencia en clima frío.
  4. Resolver **H3 (Transitorios inductivos por inrush $L \cdot di/dt$)**: Implementar desescalada preventiva transitoria del compañero robusto (-1 peldaño por 300s) durante el arranque del minero canario, con auto-restauración en `soak_tick` tras superar la ventana crítica de arranque.
  5. Resolver **H4 (Sobreenfriamiento en arranque)**: Incorporar `is_warming_up` y cota mínima `current_power_w >= 500.0` en `fan_governor.py` para suprimir `ACTION_RECOVERY_MAX_COOLING` durante los primeros 240s post-reinicio, preservando la temperatura óptima de silicio y previniendo falsos abortos de autotuning.
  6. Preservar 100% la compatibilidad retroactiva de serialización en `GroupContingencyState`.
* **Componentes Modificados / Creados**:
  - `docs/proposals/PROP-009-contingency-stabilization-hypotheses.md`: Dossier técnico y deducción física de inductancia mutua.
  - `tools/audit_contingency_night.py`: Herramienta de auditoría de incidentes nocturnos sobre SQLite.
  - `specs/074-paired-elevator-contingency/`: Directorio formal de especificación (`spec.md`, `plan.md`, `tasks.md`, `evidence.md`).
  - `app/governance/adaptive_contingency.py`: Soporte de amortiguación pareada en `GroupContingencyState`, `ContingencyDecision` y `evaluate_canary_contingency`.
  - `app/vnish/client.py`: Soporte para `clamp_top_preset=True` en la API REST.
  - `app/governance/fan_governor.py`: Inclusión de `is_warming_up` y filtro de potencia mínima.
  - `app/miner_monitor.py`: Normalización de nombres, sincronización de `balancer_preset` y manejo seguro de actuadores en `unexpected_restart` y `soak_tick`.
  - `tests/test_paired_elevator_contingency.py`: Suite dedicada de 15 pruebas unitarias cubriendo H1-H4 y serialización.
  - `tests/test_vnish_client.py`: Actualización de assertions para soporte de `clamp_top_preset`.
* **Resultados & Verificación**:
  - Auditoría de Concurrencia y Subprocesos (Claude Sonnet 4.6 Thinking): **APROBADO**.
  - Blindaje Preventivo: Mutaciones de `states[sk].balancer_preset` y lecturas de `_grp_presets` aseguradas bajo `state_lock` sin bloquear llamadas REST externas; serialización de `_ELEVATOR_CONTINGENCY_STATES` protegida con copia atómica vía `list(cont_states.items())`.
  - Suite dedicada Spec 074: **15/15 tests PASS** en 0.002s.
  - Suite de regresión integral del proyecto: **1219/1219 tests PASS** en 33.10s (0 fallos, 0 errores, 0 regresiones).
  - Servicio de producción `MinerAlerts`: En ejecución continua (`RUNNING`), 4/4 mineros operando nominalmente (~401 TH/s).
  - Estado: Certificado para despliegue cuando el operador lo disponga.

## [2026-09-16] - Saneamiento y Reorganización Estructural de la Documentación en `/docs`

* **Objetivo**:
  1. Reorganizar de forma integral y profesional la estructura del directorio `docs/`, resolviendo la saturación de archivos sueltos en `docs/speckit/` y la falta de un portal maestro de entrada.
  2. Crear `docs/README.md` como índice y mapa de navegación central para operadores, desarrolladores y arquitectos.
  3. Crear el subdirectorio formal `docs/speckit/rfcs/` con su respectivo `README.md`, agrupando `RFC_TEMPLATE.md`, `RFC_TELEGRAM_INTERACTIVE_CONTROL.md` y `RFC_TELEGRAM_MOBILE_UX_OPTIMIZATION.md`.
  4. Crear el subdirectorio `docs/speckit/archive/plans/` y archivar los planes de acción cerrados y certificados (`ACTION_PLAN_POST_V5_EVOLUTION.md`, `ACTION_PLAN_REPO_CLEANUP_AND_ROADMAP.md`, `ACTION_PLAN_V5_1_HORIZON.md` y `ACTION_PLAN_V5_MODULARIZATION.md`), despejando la raíz de `docs/speckit/` para contener exclusivamente los 7 documentos canónicos vivos.
  5. Actualizar `docs/speckit/README.md` alineándolo a la versión V5.1.0 y las 73 especificaciones completadas (1204 tests PASS).
  6. Actualizar `docs/speckit/archive/README.md` incorporando la tabla de planes archivados.
  7. Sincronizar todos los enlaces cruzados en `docs/speckit/ROADMAP.md`, `docs/speckit/SPEC_PROGRAM.md`, `docs/proposals/SYSTEM_IMPROVEMENT_PROPOSALS.md` y el `README.md` raíz.
* **Componentes Modificados / Creados**:
  - `docs/README.md`: Creado portal de documentación maestro.
  - `docs/speckit/rfcs/`: Creado directorio con `README.md` y 3 RFCs reubicados vía `git mv`.
  - `docs/speckit/archive/plans/`: Creado directorio con 4 planes de acción históricos archivados vía `git mv`.
  - `docs/speckit/README.md`: Actualizado a V5.1.0 (73 specs, 1204 tests PASS).
  - `docs/speckit/archive/README.md`: Actualizado con el catálogo de planes históricos.
  - `docs/speckit/ROADMAP.md`: Enlaces a planes de acción actualizados a `archive/plans/`.
  - `docs/speckit/SPEC_PROGRAM.md`: Enlace de horizonte V5.1 actualizado.
  - `docs/proposals/SYSTEM_IMPROVEMENT_PROPOSALS.md`: Enlace de horizonte V5.1 y estados PROP actualizados.
  - `README.md`: Enlaces del bloque de documentación actualizados.
* **Resultados & Verificación**:
  - Estructura validada: raíz de `docs/speckit/` reducida a exactamente 7 documentos canónicos vivos y 2 subdirectorios organizados (`rfcs/`, `archive/`).
  - Suite completa del proyecto: **1204/1204 tests PASS** en 41.37s (0 fallos, 0 errores, 0 regresiones).
  - Integridad de release: `tools/release_audit.py --check-only` PASS (8/8 disposiciones terminales verificadas).
  - Servicio Windows `MinerAlerts`: `Running` ininterrumpido.

## [2026-09-16] - Implementación & Certificación Spec 069: Telemetría Profunda por Cadena & Diagnóstico Predictivo Chain Break (PROP-008)

* **Objetivo**:
  1. Diseñar e implementar el motor predictivo de salud por cadena en `app/governance/chain_health.py` (`PredictiveChainEngine` y `PredictiveChainRisk`) para anticipar paradas abruptas por `chain_break` en firmwares Vnish tras degradaciones continuas de bus I2C o silicio (incidente S19JPRO-24 Cadena 2).
  2. Optimizar consultas de series temporales en SQLite WAL agregando el índice compuesto `ix_chain_telemetry_miner_chain_time` sobre `(miner_key, chain_id, observed_ts DESC)` en `app/core/event_store.py`, garantizando tiempos de ejecución $< 15\text{ ms}$ (promedio medido: $< 1\text{ ms}$).
  3. Implementar helper tolerante a bloqueos `fetch_chain_samples_window(miner_key, chain_id, since_ts)` con reintentos exponenciales ante `SQLITE_BUSY_SNAPSHOT` y conversión universal de filas vía `_cursor_rows_to_dicts`.
  4. Implementar Regla 1 (QA-069-01): Fallo persistente de sensor I2C en ventana deslizante de 12h requiriendo significancia estadística mínima ($N \ge 24$ muestras) y $\ge 90\%$ de fallos concentrados en una ubicación física idéntica (`faulty_sensor_locs`), suprimiendo falsas alarmas durante arranques o fluctuaciones transitorias.
  5. Implementar Regla 2: Detección de déficit de hashrate localizado ($\ge 10\%$ sostenido por $\ge 3\text{h}$) con validación cruzada de placas adyacentes nominales ($\le 2\%$) para aislar degradación física de chips.
  6. Implementar Regla 3 (QA-069-02): Discriminador de grupo eléctrico (`correlate_electrical_group`) que clasifica perturbaciones colectivas (`POWER_DISTURBANCE`) cuando $\ge 2$ mineros del mismo circuito eléctrico (`elevator_1` vs `elevator_2`) caen simultáneamente ($\le 60\text{s}$), inhibiendo falsos reportes de daño de silicio individual con fallback seguro ante configuraciones sin grupo y soporte de claves compuestas.
  7. Formatear tarjetas móviles compactas en Telegram ($\le 32$ columnas) mediante `build_predictive_chain_risk_card()`, soportando explícitamente Cadena 0 (Board 0).
  8. Integrar ciclo de evaluación periódica horaria en `app/miner_monitor.py` desacoplado en hilo daemon (`name="PredictiveChainBreakScheduled"`), con deduplicación estricta por cadena mediante enfriamiento de 24 horas (`state.chain_warnings_ts`) y preservación intacta de invariantes de supervisión de `main()`.
  9. Auditoría QA especialista & quick wins: corrección de `NameError` en hilo de evaluación en `main()`, resolución de claves compuestas de estado, aislamiento de cooldowns por elevador, mitigación de fallos de cursor SQLite y blindaje con `_safe_float`.
  10. Incorporar 23 nuevas pruebas unitarias y de rendimiento en `tests/test_chain_predictive_rules.py` (20 tests) y `tests/test_chain_query_performance.py` (3 tests), elevando la suite global del proyecto a **1204 tests PASS**.
* **Componentes Modificados / Creados**:
  - `app/core/event_store.py`: Índice compuesto `ix_chain_telemetry_miner_chain_time`, `_cursor_rows_to_dicts` y helper `fetch_chain_samples_window()`.
  - `app/core/__init__.py`: Exportación de `fetch_chain_samples_window`.
  - `app/governance/chain_health.py`: `PredictiveChainEngine`, `PredictiveChainRisk`, constantes de tipo y severidad, helper `extract_faulty_sensor_locs`, `_safe_float`, correlador de grupos eléctricos y formateador de tarjeta Telegram.
  - `app/governance/__init__.py`: Exportación de clases, dataclasses y formateadores predictivos.
  - `app/core/state_manager.py`: Serialización y deserialización de `chain_warnings_ts`.
  - `app/miner_monitor.py`: Campo `chain_warnings_ts` en `@dataclass MinerState`, deserialización en `load_state()`, worker `_async_evaluate_predictive_chain_break()` y programación horaria en `main()`.
  - `app/config.example.json`: Parámetros `predictive_chain_break_enabled`, `chain_sensor_error_persistence_hours`, `chain_sensor_error_min_samples`, `chain_sensor_error_sample_pct`, `chain_deficit_threshold_pct`, `chain_deficit_duration_hours`, `chain_warning_cooldown_hours`.
  - `tests/test_chain_predictive_rules.py`: 20 pruebas unitarias exhaustivas para reglas I2C, déficit, supresión eléctrica, deduplicación y QA de robustez.
  - `tests/test_chain_query_performance.py`: 3 pruebas de benchmark de latencia (<15ms) y verificación de `EXPLAIN QUERY PLAN` sobre 10.000 registros.
  - `tests/test_state_serialization_parity.py`: Verificación de paridad de serialización para `chain_warnings_ts`.
  - `specs/069-chain-telemetry-break-prediction/tasks.md` & `evidence.md`: Tareas completadas y certificación registrada.
* **Resultados & Verificación**:
  - Pruebas unitarias de reglas predictivas: 20/20 tests PASS en 0.56s.
  - Pruebas de rendimiento SQLite: 3/3 tests PASS en 0.72s.
  - Paridad de serialización de estado: 3/3 tests PASS en 0.53s.
  - Suite completa del proyecto: **1204/1204 tests PASS** en 36.4s (0 fallos, 0 errores, 0 regresiones).
  - Servicio Windows `MinerAlerts`: `Running` ininterrumpido.

## [2026-09-16] - Auditoría Especialista de QA & Saneamiento de Resiliencia (Specs 068, 070, 071, 072, 073)

* **Objetivo**:
  1. Ejecutar auditoría exhaustiva con rol de especialista sobre las especificaciones recientemente implementadas (068, 070, 071, 072, 073) analizando manejo de handles de kernel, estados de error en named pipes de Windows NT, prevención de falsas alarmas de deadlock, contención de excepciones en watchdog y ergonomía de herramientas CLI.
  2. Subsanar bug crítico de Windows Named Pipes en `app/ipc/watchdog_pipe.py`: cuando un cliente se desconecta anticipadamente provocando `ERROR_NO_DATA (232)` en `ConnectNamedPipe()`, invocar explícitamente `DisconnectNamedPipe(h_pipe)` para resetear el handle del kernel y prevenir que el servidor quede atrapado en un bucle infinito rechazando futuros clientes.
  3. Incorporar salvaguarda de uptime en `tools/monitor_watchdog.py`: exigir que el uptime del monitor supere el umbral de deadlock (`uptime_s >= max_deadlock_tick_age_s`) antes de evaluar congelamiento, evitando falsos reinicios durante arranques recientes o lecturas de heartbeats anteriores.
  4. Blindar el sondeo IPC en `tools/monitor_watchdog.py:main()` mediante bloque `try/except` que capture cualquier excepción inesperada y asegure la degradación suave hacia la evaluación por latido (`RF-04: Degradación Suave`).
  5. Mejorar ergonomía de CLI en `tools/audit_config.py` admitiendo el alias `--config` / `-c` para el parámetro `--target`.
  6. Fortalecer el analizador de comandos IPC sanitizando bytes nulos y delimitadores `\r\n`.
  7. Incorporar 5 nuevas pruebas unitarias exhaustivas en `tests/test_watchdog_ipc.py` y `tests/test_audit_config.py`, elevando la suite global a 1181 tests PASS.
* **Componentes Modificados**:
  - `app/ipc/watchdog_pipe.py`: Reset de handle con `DisconnectNamedPipe` ante fallo de conexión, parsing robusto con `math.isfinite()` y sanitización de comandos.
  - `tools/monitor_watchdog.py`: Salvaguarda de uptime contra falsos deadlocks y blindaje defensivo con logging en `main()`.
  - `tools/audit_config.py`: Alias `--config` / `-c` para `--target`.
  - `tests/test_watchdog_ipc.py`: 4 nuevos tests de auditoría (recuperación ante `ERROR_NO_DATA`, uptime guard, comandos multilinea, contención de fallos). Total 20 tests.
  - `tests/test_audit_config.py`: 1 nuevo test para `--config`. Total 13 tests.
* **Resultados & Verificación**:
  - Pruebas unitarias de IPC: 20/20 tests PASS en 0.89s.
  - Pruebas unitarias de auditoría de config: 13/13 tests PASS en 0.05s.
  - Suite completa del proyecto: **1181/1181 tests PASS** en 34.3s (0 fallos, 0 errores, 0 regresiones).
  - Servicio Windows `MinerAlerts`: `Running` ininterrumpido.

## [2026-09-16] - Implementación Spec 068: Canal IPC Alta Frecuencia Monitor ↔ Watchdog vía Named Pipes (PROP-007)

* **Objetivo**:
  1. Diseñar e implementar el módulo de comunicación inter-proceso de alta frecuencia `app/ipc/watchdog_pipe.py` con `WatchdogIPCServer` y `WatchdogIPCClient`, soportando Named Pipes nativos en Windows NT con descriptor de seguridad permisivo SDDL `D:(A;;GRGW;;;WD)` y fallback automático a loopback socket TCP `127.0.0.1:4029` con `SO_REUSEADDR`.
  2. Implementar helper de diagnóstico forense de hilos `dump_thread_frames()` capturando los tracebacks de todos los hilos activos vía `sys._current_frames()` enriquecido con nombres de hilos y flags daemon.
  3. Integrar `WatchdogIPCServer` en `app/miner_monitor.py:main()` de forma aditiva y desacoplada en un hilo daemon dedicado (`name="WatchdogIPCServer"`), suministrando `(tick_sequence, process_start_ts, last_tick_duration)` sin retener locks y con parada limpia en $<200\text{ ms}$ vía wake-up connect.
  4. Actualizar `tools/monitor_watchdog.py` incorporando sondeo de alta frecuencia (<15s) con máquina de estados de 3 intentos ante fallos, detección determinista de deadlock del bucle principal (`tick_sequence` congelado tras 60s), captura forense y recuperación automática mediante `Restart-Service -Name MinerAlerts -Force` o `Start-Service`.
  5. Documentar configuración en `app/config.example.json` y certificar la suite global sin regresiones.
* **Componentes Modificados / Creados**:
  - `app/ipc/__init__.py` & `app/ipc/watchdog_pipe.py`: Servidor y cliente IPC, protocolo `PING`/`PONG`/`DUMP`, gestión de seguridad SDDL y sockets.
  - `app/miner_monitor.py`: Instanciación y parada aditiva de `WatchdogIPCServer` y tracking de `_last_tick_duration`.
  - `tools/monitor_watchdog.py`: Integración de `probe_ipc_and_recover`, `restart_service`, `start_service` y flags `--ipc`/`--no-ipc`.
  - `app/config.example.json`: Incorporación de bloque `watchdog_ipc_*`.
  - `tests/test_watchdog_ipc.py`: 16 pruebas unitarias integrales de transporte pipe/socket, timeouts, parada limpia, deadlocks y recuperación de servicio.
  - `specs/068-watchdog-ipc-pipe/tasks.md` & `evidence.md`: Marcado completo de T001-T011 y reporte de evidencia técnica.
* **Resultados & Verificación**:
  - Suite unitaria Spec 068: 16/16 tests PASS en 0.83s.
  - Suite de regresión liveness: 28/28 tests PASS en 0.09s.
  - Suite completa del proyecto: **1176/1176 tests PASS** en 34.4s (0 fallos, 0 errores, 0 regresiones).
  - Servicio Windows `MinerAlerts`: `Running` ininterrumpido.

## [2026-09-16] - Implementación Spec 070 (Fases C y D): Extracción de Hooks y Desacoplamiento Total de `inspect.getsource(main)` (ST-05)

* **Objetivo**:
  1. Extraer los bloques procedurales de clasificación de estado y de evaluación de auto-reboot desde `main()` hacia `DetectionHook` (Stage 30) y `ActuatorHook` (Stage 50) en `app/core/engine.py`.
  2. Registrar formalmente `DetectionHook` y `ActuatorHook` en `_supervisory_engine` en `app/miner_monitor.py` y delegar la clasificación de estado del ciclo a `DetectionHook.classify_state()`.
  3. Desacoplar completamente los 4 archivos de tests legados (`test_auto_reboot_signal_gate.py`, `test_hashboard_auto_reboot.py`, `test_reboot_safety.py`, `test_vnish_hashboard_detection.py`) sustituyendo las aserciones frágiles de texto sobre `inspect.getsource(main)` por evaluaciones funcionales directas de `DetectionHook` y `ActuatorHook`.
  4. Actualizar `test_startup_grace_period.py` para verificar la invocación de `DetectionHook.classify_state` en `main()`.
  5. Certificar 1160 tests globales PASS sin regresiones y servicio Windows `MinerAlerts` en estado `Running`.
* **Componentes Modificados**:
  - `app/core/engine.py`: Incorporación de `DetectionHook` y `ActuatorHook` con interfaces tipadas, preservando contratos e invariantes operativas.
  - `app/miner_monitor.py`: Registro de hooks en `_supervisory_engine` y delegación limpia de `classify_state`.
  - `tests/test_auto_reboot_signal_gate.py`: Modernización funcional de 4 tests eliminando `inspect.getsource(main)`.
  - `tests/test_hashboard_auto_reboot.py`: Modernización funcional de 14 tests eliminando `inspect.getsource(main)`.
  - `tests/test_reboot_safety.py`: Modernización funcional de 13 tests eliminando `inspect.getsource(main)`.
  - `tests/test_vnish_hashboard_detection.py`: Modernización funcional de 6 tests eliminando `inspect.getsource(main)`.
  - `tests/test_startup_grace_period.py`: Actualización de aserción contractual de `main`.
  - `tests/test_supervisory_hooks.py`: Verificación de ejecución secuencial en pipeline.
  - `specs/070-core-modularization-decoupling/tasks.md` & `evidence.md`: Marcado completo de T001-T016 y reporte de evidencia.
* **Resultados & Verificación**:
  - Suite completa de regresión: **1160/1160 tests PASS** en 34.3s (0 fallos, 0 errores, 0 regresiones).
  - Servicio Windows `MinerAlerts`: `Running` ininterrumpido.
  - Cero dependencias residuales de introspección de código fuente sobre `main()`.

## [2026-09-16] - Implementación Spec 070 (Fases A y B): Arnés de Comportamiento Determinista & Certificación de Paridad Dual (ST-05)

* **Objetivo**:
  1. Construir un arnés de comportamiento supervisorio de caja negra (`tests/test_supervisory_core_behavioral.py`) reproduciendo funcionalmente las 37 reglas e invariantes evaluadas históricamente mediante `inspect.getsource(main)`.
  2. Certificar la coexistencia y paridad dual de los 37 tests legados junto a los 37 tests de comportamiento funcional sin modificar una sola línea de código en producción (`app/miner_monitor.py` intacto, RI-02).
  3. Incrementar la suite global de 1119 a 1156 tests PASS (0 fallos, 0 errores, 0 regresiones) con el servicio de producción `MinerAlerts` en estado `Running`.
* **Componentes Modificados / Creados**:
  - `tests/test_supervisory_core_behavioral.py`: Arnés `SupervisoryBehavioralHarness` y 37 pruebas deterministas (8 compuertas de señal, 8 auto-reboot por hashboard, 13 interlocks y cooldowns, 8 precedencia de placas vs hashrate).
  - `specs/070-core-modularization-decoupling/tasks.md`: Fases A y B marcadas como completadas (T001-T007).
  - `specs/070-core-modularization-decoupling/evidence.md`: Evidencia de certificación y tiempos de ejecución.
* **Resultados & Verificación**:
  - Suite de comportamiento: 37/37 tests PASS en 0.002s.
  - Suite completa de regresión con paridad dual: **1156/1156 tests PASS** en 32.3s.
  - Servicio Windows `MinerAlerts`: `Running` ininterrumpido.

## [2026-09-16] - Implementación Spec 073: Reutilización de Clientes en Tools & Alineación de Configuración (P3)

* **Objetivo**:
  1. Refactorizar herramientas de soporte (`tools/miner_diagnostics.py` y `tools/debug_4028.py`) para reutilizar centralizadamente el cliente de red `app.network.cgminer_client.query_cgminer`, eliminando llamadas procedurales directas y `sys.exit()` incondicionales al importar módulos.
  2. Implementar validador estructural de configuración (`tools/audit_config.py`) con detección de claves faltantes requeridas/opcionales, verificación de tipos (con relajación de compatibilidad numérica `int`/`float` y `chat_id`), detección de marcadores de posición (`PONER_TOKEN`, etc.), reporte de claves desconocidas y validación de entidades de hardware (`miners`).
  3. Consolidar fixtures redundantes de tests de UX compacta en `tests/fixtures_compact_ux.py` e importar desde `test_compact_format.py` y `test_compact_ux.py`.
  4. Garantizar compatibilidad estricta con Windows NT, ejecución segura y suite de regresión 100% verde.
* **Componentes Modificados / Creados**:
  - `tools/debug_4028.py`: Modularización en funciones `debug_miner()` y `main()` protegidas por bloque `if __name__ == "__main__":` y delegación a `query_cgminer`.
  - `tools/miner_diagnostics.py`: Reutilización centralizada de `query_cgminer`.
  - `tools/audit_config.py`: Herramienta CLI y programática de auditoría de esquemas JSON con modos estándar y `--strict`.
  - `tests/test_miner_diagnostics_client.py`: Suite exhaustiva de pruebas unitarias para `miner_diagnostics` y `debug_4028` (éxito, fallo, excepciones de socket, argumentos de CLI y retorno de códigos).
  - `tests/test_audit_config.py`: 12 pruebas unitarias de validación cruzada y casos borde de configuración.
  - `tests/fixtures_compact_ux.py`: Consolidación de `make_test_coordinator` y `observe_test_episode`.
  - `tests/test_compact_format.py` & `tests/test_compact_ux.py`: Reutilización de fixtures consolidados.
  - `specs/073-tools-client-reuse-and-config-alignment/evidence.md`: Evidencia de certificación y ejecución.
* **Resultados & Verificación**:
  - Pruebas unitarias de Spec 073: 20 tests PASS en 0.007s (`test_miner_diagnostics_client.py` y `test_audit_config.py`).
  - Suite completa de regresión: **1119 tests PASS** en 32.2s (0 fallos, 0 errores, 0 regresiones).
  - Servicio Windows `MinerAlerts`: `Running` ininterrumpido.

## [2026-09-16] - Implementación Spec 072: Unificación de Serialización de Estado & Desacoplamiento de Shims Redundantes (P2)

* **Objetivo**: 
  1. Unificar la serialización de `MinerState` centralizándola en `StateManager.serialize_miner_state(state)` / `serialize_miner_state(state)` en `app/core/state_manager.py`, eliminando la duplicación del payload de ~45 campos en `_build_state_payload()` en `app/miner_monitor.py`.
  2. Migrar los comandos de Telegram (`diagnostics.py`, `fans.py`, `reboot.py`, `maintenance.py`) para reutilizar `find_assessment_by_target` y `format_miner_key` de `app/telegram/command_center.py`, eliminando formateos manuales dispersos y previniendo `KeyError`.
  3. Centralizar el generador recursivo `_dicts()` en `app/core/mining_quality.py` e importarlo limpiamente en `app/vnish/telemetry.py`.
  4. Preservar intactos los 37 contratos de tests `inspect.getsource(main)`.
* **Componentes Modificados / Creados**:
  - `app/core/state_manager.py`: Exposición del método estático `StateManager.serialize_miner_state` y alias de módulo `serialize_miner_state`.
  - `app/miner_monitor.py`: Delegación de `_build_state_payload()` en `serialize_miner_state()`.
  - `app/telegram/commands/diagnostics.py`: Reutilización de `format_miner_key`.
  - `app/telegram/commands/reboot.py`: Reutilización de `format_miner_key`.
  - `app/telegram/commands/fans.py`: Reutilización de `format_miner_key` en 4 puntos de sondeo.
  - `tests/test_state_serialization_parity.py`: Suite exhaustiva de paridad determinista de campos y serializabilidad JSON de `MinerState`.
  - `tests/test_find_assessment_by_target.py`: 8 pruebas unitarias de resolución por ID corto, nombre completo, IP y formateo seguro de claves.
* **Resultados & Verificación**:
  - Pruebas unitarias de Spec 072: 11 tests PASS (3 en `test_state_serialization_parity.py`, 8 en `test_find_assessment_by_target.py`).
  - Suite completa de regresión: **1113 tests PASS** en 33.5s (0 fallos, 0 errores, 0 regresiones).
  - Servicio Windows `MinerAlerts`: `Running` ininterrumpido.

## [2026-09-16] - Auditoría QA Exhaustiva & Mitigaciones de Diseño en Especificaciones Pendientes (Specs 068 a 073)

* **Objetivo**: Auditoría técnica de calidad y control de riesgos sobre las especificaciones pendientes de implementación (Specs 068, 069, 070, 072 y 073), asegurando que todos los planes, especificaciones y listas de tareas incorporen salvaguardas de seguridad, concurrencia, permisos en Windows NT y significancia estadística antes de iniciar cualquier fase de código.
* **Hallazgos y Mejoras Incorporadas en Artefactos de Diseño**:
  - **Spec 068 (Canal IPC Monitor ↔ Watchdog - PROP-007)**:
    * Inclusión de descriptor de seguridad explícito (`SECURITY_DESCRIPTOR` con SDDL `D:(A;;GRGW;;;WD)`) vía `advapi32` para eliminar el fallo `ERROR_ACCESS_DENIED (5)` entre el servicio `LocalSystem` y usuarios interactivos o tareas programadas locales.
    * Incorporación de conexión efímera de desbloqueo ("wake-up connect") en `server.stop()` para liberar llamadas síncronas de `ConnectNamedPipe` y garantizar parada limpia en $<200\text{ ms}$ sin demorar el shutdown del servicio.
    * Incorporación de `SO_REUSEADDR` en el socket loopback fallback para evitar colisiones de puerto.
  - **Spec 069 (Telemetría Profunda por Cadena & Diagnóstico Predictivo - PROP-008)**:
    * Incorporación de condición de significancia estadística mínima ($N \ge 24$ muestras recolectadas en la ventana de 12h) antes de calcular la persistencia $\ge 90\%$ de fallos I2C, erradicando falsos positivos en arranques o tras caídas de red.
    * Creación segura de índice compuesto `ix_chain_telemetry_miner_chain_time` protegida con timeout y reintentos ante bloqueos de base de datos.
    * Fallback seguro en correlación causal eléctrica si los mineros no tienen especificado grupo o elevador en configuración.
  - **Spec 070 (Modularización del Core Fase B - ST-05)**:
    * Desacoplamiento estratégico: La Fase 1 (construcción del arnés de comportamiento determinista de 37 invariantes) se habilita como prerrequisito de seguridad no destructivo previo a modificaciones en `miner_monitor.py:main()`.
    * Extensión de paridad dual reflejando la línea base actual de 1110 tests (meta: 1147 tests PASS).
  - **Spec 072 (Unificación de Serialización de Estado - P2)**:
    * Definición formal de paridad cruzada byte-a-byte y consolidación de helpers de resolución y formateo seguro de claves de estado (`format_miner_key`) en `app/telegram/command_center.py` para prevenir importaciones circulares y errores `KeyError` en mineros sin clave `host`.
  - **Spec 073 (Reutilización de Clientes en Tools & Auditoría de Config - P3)**:
    * Distinción estricta en el validador entre claves críticas requeridas (`telegram`, `miners`, `poll_seconds`) y claves opcionales con valores predeterminados seguros en runtime.
    * Flexibilidad de compatibilidad de tipos para valores numéricos (`int` y `float`) y credenciales de Telegram (`chat_id` como `str` o `int`).
* **Estado de la Suite & Producción**:
  - Suite de regresión certificada: **1110 tests PASS** en 34.1s (0 fallos, 0 regresiones).
  - Servicio de Windows `MinerAlerts` activo y en ejecución continua (`Running`).
  - Implementación de especificaciones en pausa, listas para ejecución aprobada.

## [2026-09-16] - Implementación Spec 071: Consolidación de Pool SQLite Resiliente & Barrera Defensiva de Hilos Daemon (P0/P1)

* **Objetivo**: 
  1. Corregir vulnerabilidad P0: hilo daemon `RestoreLock_{name}` en `app/miner_monitor.py:3226` ejecutando `safe_set_miner_preset` sin captura de excepciones, y auditar todos los demás hilos daemon agregando barreras `try ... except` completas y nombres descriptivos (`ShutdownPurgeNotify`, `TelegramSender`, `TelegramPolling`).
  2. Corregir deuda técnica P1: consolidar llamadas directas ad-hoc `sqlite3.connect(f"file:...mode=ro")` repartidas en 7 módulos hacia la función centralizada tolerante `open_readonly_connection` y `execute_readonly_with_retry` con backoff exponencial, eliminando bloqueos intermitentes de base de datos durante checkpoints WAL.
* **Componentes Modificados / Creados**:
  - `app/miner_monitor.py`:
    * Función interna `_async_restore_tripwire_preset` con barrera de excepción completa y logging estructurado `[TRIPWIRE_INTERLOCK_RESTORE_OK/FAIL/ERR]`.
    * Envolvimiento de `_purge_and_notify` (`ShutdownPurgeNotify`) en barrera `try ... except Exception as _th_exc: log(f"[SHUTDOWN_PURGE_ERR] ...")`.
    * Asignación explícita de nombres descriptivos a hilos de mensajería: `TelegramSender` y `TelegramPolling`.
  - `app/core/event_store.py`:
    * Exposición de `open_readonly_connection(db_path, timeout=3.0)` con resolución tolerante de rutas relativas con fallback a `repo_root`, `mode=ro`, `PRAGMA query_only = ON` y `PRAGMA synchronous = NORMAL`.
    * `create_readonly_connection` reforzada con `PRAGMA synchronous = NORMAL`.
  - `app/core/__init__.py`:
    * Exportación pública de `open_readonly_connection`.
  - Consumidores SQLite Migrados:
    * `app/governance/energy_efficiency.py`: migrado a `open_readonly_connection` y `execute_readonly_with_retry`.
    * `app/governance/fan_health.py`: migrado a `open_readonly_connection` y `execute_readonly_with_retry`.
    * `app/governance/preset_balancer.py`: migradas consultas de telemetría histórica y sensibilidad de cascada a `open_readonly_connection` y `execute_readonly_with_retry`.
    * `app/telegram/charts.py`: `_connect_ro` conectado a `create_readonly_connection`.
    * `app/telegram/daily_digest.py`: migrado a `open_readonly_connection` y `execute_readonly_with_retry` en todas las consultas del resumen diario.
    * `app/vnish/presets.py`: migrado a `open_readonly_connection` y `execute_readonly_with_retry`.
  - Suites de Pruebas Agregadas:
    * `tests/test_sqlite_readonly_consolidation.py`: valida pragmas, reintentos de consulta bajo contención y tolerancia a archivos inexistentes en todos los módulos consumidores.
    * `tests/test_tripwire_thread_hardening.py`: valida contención de excepciones y logs defensivos ante fallas de red o excepciones runtime en hilos daemon.
* **Validación & Cobertura**:
  - Sintaxis: `py_compile` en los 9 módulos modificado PASS.
  - Regresión total: **1079 tests PASS** en 32.7s (+7 tests sobre la línea base de 1072, 0 fallas, 0 regresiones).
  - Servicio de Windows: `MinerAlerts` se mantuvo en estado `Running`.

## [2026-09-16] - Auditoría Arquitectónica Exhaustiva & Enriquecimiento del Horizonte V5.1 (Specs 068 a 070)

* **Objetivo**: Auditoría técnica y blindaje arquitectónico integral de las especificaciones pendientes (Spec 068, Spec 069 y Spec 070) sin escritura de código prematuro, resolviendo riesgos de concurrencia Windows, límites de latencia SQLite WAL y desacoplamiento de tests de inspección textual.
* **Análisis y Mejoras Arquitectónicas Plasmadas**:
  - **Spec 068 (Canal IPC Monitor ↔ Watchdog en Windows - PROP-007)**:
    * Evaluación comparativa de transporte: Named Pipes nativos de Windows (`\\.\pipe\MinerAlertsWatchdog`) vía `ctypes.windll.kernel32` (para cero dependencias de paquetes binarios en el venv) con arquitectura dual de fallback a Socket TCP Loopback (`127.0.0.1:4029`).
    * Protocolo Ping-Pong (`PING <nonce>` $\rightarrow$ `PONG <nonce> <seq> <uptime>`) con timeout de $100\text{ ms}$.
    * Diferenciador de bloqueo de loop principal: Si el IPC responde pero `tick_sequence` permanece congelado por $> 60\text{ s}$, se diagnostica cuelgue de `state_lock` o bloqueo socket en el hilo principal.
    * Protocolo de volcado forense automático: Captura de trazas de todos los hilos (`sys._current_frames()`) en `logs/deadlock_forensics_<timestamp>.log` antes de ordenar `Restart-Service -Name MinerAlerts -Force`.
  - **Spec 069 (Telemetría Profunda por Cadena & Predictive Chain Break - PROP-008)**:
    * Definición de índice compuesto en SQLite WAL: `CREATE INDEX IF NOT EXISTS ix_chain_telemetry_miner_chain_time ON chain_telemetry_samples(miner_key, chain_id, observed_ts DESC)` para consultas agregadas en $< 8\text{ ms}$ vía `execute_readonly_with_retry`.
    * Regla de persistencia de error I2C: Detección en ventana de 12 horas con $\ge 90\%$ de muestras en fallo (`sensors_error_count > 0` en misma ubicación de silicio), emitiendo alerta preventiva deduplicada en Telegram para evitar paradas catastróficas por `chain_break` (caso Minero 24 Cadena 2).
    * Aislamiento causal eléctrico: Correlación cruzada entre elevadores (`elevator_1` vs `elevator_2`) para clasificar caídas múltiples simultáneas como `POWER_DISTURBANCE` y suprimir falsos diagnósticos de fallo físico en chips.
  - **Spec 070 (Modularización Core Fase B - Desacoplamiento de `inspect.getsource(main)` - ST-05)**:
    * Análisis de las 4 suites de tests acopladas textualmente (37 tests de invariantes).
    * Estrategia de migración de riesgo cero: Construcción previa de `tests/test_supervisory_core_behavioral.py` reproduciendo los 37 escenarios de interlocks, compuertas de reinicio y estados de falla sobre `CoreSupervisoryEngine` con mocks de caja negra.
    * Fase de paridad dual: Coexistencia de 37 tests originales + 37 tests de comportamiento ($\ge 1109$ tests globales PASS) antes de refactorizar el bucle procedural de `main()` hacia hooks independientes.
* **Documentación Sincronizada**:
  - `docs/speckit/ACTION_PLAN_V5_1_HORIZON.md`: Especificaciones y mitigaciones de riesgo profundizadas.
  - `docs/speckit/ROADMAP.md`: Iniciativas 19 a 22 actualizadas y reflejadas en el progreso del programa.
  - `prompt.txt`: Actualizado con la línea base de 1072 tests PASS y el plan auditado.

## [2026-09-16] - Implementación Spec 067: Gateway Heartbeat & Supresión de Tormentas de Red Local (PROP-005) + Auditoría QA Completa

* **Objetivo**: 
  1. Auditoría de seguridad integral de specs 061-066 conforme al ACTION_PLAN_V5_1_HORIZON.md.
  2. Implementar `GatewayHeartbeatWorker` (Spec 067/PROP-005): hilo daemon ultraliviano de sondeo TCP al router local para detectar microcortes de switch y suprimir tormentas de falsas alarmas de desconexión masiva en la flota ASIC.
* **Auditoría QA Ejecutada** (pre-implementación):
  - Verificado: 37 invariantes constitucionales (inspect.getsource) PASS sin alteración.
  - Verificado: timeouts ≤ 5.0s en Api4028Transport, VnishClient, HashcoreClient.
  - Verificado: `CREATE_NO_WINDOW` en hashcore_client.py y monitor_watchdog.py.
  - Verificado: `context.governance` y `context.last_daily_digest_date` sincronizados antes de `execute_tick()`.
  - **Fix aplicado**: `_async_execute_mining_restart` — envolvimiento total en `try...except Exception` (hilo daemon podía morir silenciosamente ante excepción inesperada).
* **Componentes Modificados / Creados**:
  - `app/network/gateway_heartbeat.py`: `GatewayHeartbeatWorker` (zero dependencias externas, socket connect con timeout 50ms, fallback de puerto DNS/53, control atómico GIL-safe, cierre explícito de sockets en `finally`, barrera total de excepciones en `_run()`).
  - `app/network/__init__.py`: Re-exportado `GatewayHeartbeatWorker`.
  - `app/miner_monitor.py`: 
    * Instanciación condicional de `_gateway_heartbeat` antes del `while True:` con degradación suave.
    * Guard `_network_storm_active` antes del despacho de `EPISODE_ALERT` — filtra episodios de `STATE_OFFLINE` durante parpadeos de switch (ventana configurable, default 15s).
    * `_gateway_heartbeat.stop()` en el `finally` del loop principal.
    * Fix: barrera de excepción en `_async_execute_mining_restart`.
  - `app/config.example.json`: Añadidas 6 claves para Spec 067 (`gateway_heartbeat_enabled: false` por defecto, opt-in).
  - `tests/test_gateway_heartbeat.py`: Suite completa de **27 pruebas** unitarias (7 clases): inicialización, `is_recently_lost`, `gateway_loss_elapsed_s`, socket close safety, fallback de puerto, ciclo de vida start/stop con mocks.
* **Verificación y Evidencia**:
  - Suite unitaria Spec 067: **27 / 27 PASS** en 0.76s.
  - Suite de invariantes (37 tests): **37 PASS** en 0.066s.
  - Suite de regresión completa: **1072 / 1072 tests PASS** en 38.91s (0 fallos, 0 errores, 0 regresiones).
  - Servicio Windows `MinerAlerts`: **Running** tras `Restart-Service`, sin errores en logs de inicio.
  - Commits: `67f0c9b` (fix audit + scaffold) y `b8cdf92` (feat spec-067).

## [2026-09-16] - Estabilización Operativa: Auto-Restart Warmup Guard & Adaptación Dinámica de Gobernador Térmico en Contingencia

* **Objetivo**:
  1. Corregir el reinicio por software prematuro (`Auto-Restart` Nivel 1) tras reinicios físicos o caídas de tensión (`unexpected restart`), evitando interrumpir el autotuning/calibración de frecuencias de los mineros.
  2. Adaptar la regulación de ventiladores en `FanGovernor` cuando la contingencia eléctrica reduce el consumo (ej. preset a 2100W o 2300W), derivando la potencia objetivo del preset activo real en lugar del máximo teórico estático (2700W) para evitar el bloqueo espurio en 100% PWM (`RECOVERY_MAX_COOLING`).
* **Componentes Modificados**:
  - `app/miner_monitor.py`:
    * En `evaluate_auto_restart_candidate`: agregados parámetros `elapsed: Optional[int] = None`, `min_elapsed_seconds: int = 180`, `startup_grace_active: bool = False`. Bloqueo defensivo con `"miner_warming_up"` si `elapsed < min_elapsed_seconds` y bloqueo si el proceso anfitrión se encuentra en gracia de arranque.
    * En `execute_governor_cycle`: derivación de `target_pwr` a partir de `state.balancer_preset`, `state.hw_error_locked_preset` o `state.vnish_discovered_preset` (prioridad sobre `target_power_w` fijo de 2700W). Permite que ante contingencia (2300W/2100W) el gobernador regule de inmediato hacia la temperatura consigna de 82.0°C modulando PWM (`STEP_DOWN` desde 100% hacia 85%-67%). Al salir de contingencia, el optimizador eleva la potencia hacia 2700W/2800W manteniendo siempre la consigna térmica de 82.0°C.
    * En `_async_execute_mining_restart`: envolvimiento completo en `try ... except Exception as _exc:` con logging estructurado para blindar el hilo daemon ante fallos de red.
  - `app/config.example.json`: Añadido `"auto_restart_min_elapsed_seconds": 180`.
  - `tests/test_two_tier_recovery.py`: Añadidas 2 pruebas unitarias de guardia de calentamiento e inhibición por gracia de arranque.
  - `tests/test_fan_governor_concurrency.py`: Añadida prueba `test_contingency_reduced_preset_adapts_fans_to_regulate_temp`.
* **Verificación y Evidencia**:
  - Registro de producción en `logs/out.log`: S19JPRO-25 operando a 2299W con preset de contingencia 2300W modula ventiladores en ciclo cerrado descendente: 100% -> 95% -> 90% -> 85% (`STEP_DOWN`), eliminando el bloqueo en 100% PWM.
  - Suite de regresión: **1065 / 1065 tests PASS** en 35.0s.

## [2026-09-15] - Implementación Spec 066: Cold-Boot Fleet Grace Period Post-Arranque (PROP-001)

* **Objetivo**: Implementar un período de gracia y calentamiento post-arranque (`WARMING_UP`) para la flota de mineros ASIC, eliminando las falsas alarmas de `STARTUP`, `OFFLINE` y `LOW` que ocurren durante el booteo de NAND y la calibración por autotuning de frecuencias/voltajes de los equipos tras cortes de energía o reinicios de servicio.
* **Componentes Modificados / Creados**:
  - `app/config.example.json`: Añadidos parámetros `"startup_fleet_grace_period_seconds": 180` y `"startup_fleet_grace_threshold_ths": 50.0`.
  - `app/miner_monitor.py`:
    * Lectura y validación de `startup_fleet_grace_period_seconds` y `startup_fleet_grace_threshold_ths`.
    * Control de estado `startup_grace_active` y timeout tras expiración de la ventana de calentamiento.
    * Supresión de streaks de falla (`offline_streak = 0`, `low_streak = 0`) y reseteo de temporizadores de falla sostenida (`low_since_ts = None`, `hashboard_since_ts = None`) durante la fase `WARMING_UP`.
    * Supresión de despacho de alertas de episodios irregulares (`EPISODE_ALERT`) a Telegram durante la gracia.
    * Implementación de helpers puros: `is_fleet_warmup_complete(miners, states, threshold_ths, expected_boards)` y `format_fleet_restored_line(name, rate, temp)`.
    * Consolidación temprana con tarjeta unificada `🟢 FLOTA RESTABLECIDA` al superar el umbral en toda la flota, o consolidación por timeout `STARTUP [FIN PERÍODO DE GRACIA]` con reconocimiento de episodios iniciales (`acknowledge_active_initials()`).
    * Sincronización continua de `monitor_ctx.governance = _GLOBAL_INTERVENTION_GOV` en cada tick e inyección en `extra_tick_data` para resolver stale governance.
    * Preservación estricta de todos los contratos de inspección literal de código (`inspect.getsource(main)`).
  - `app/core/engine.py`: `GovernanceInterlockHook` lee preferentemente de `tick_data.get("governance")` o `context.governance`.
  - `tests/test_startup_grace_period.py`: Nueva suite con 15 pruebas unitarias exhaustivas cubriendo formateo, predicados, supresión de streaks, disparo de consolidación temprana/timeout y contratos de inspección.
  - `tests/test_supervisory_hooks.py`: Añadida prueba de sincronización y lectura de governance en `GovernanceInterlockHook`.
* **Verificación y Evidencia**:
  - `preflight.ps1 -RunBuilds` → **PASS** (ExitCode: 0, py_compile limpio, git-diff-check limpio).
  - Suite de invariantes (37 tests) → **37 PASS** en 0.071s.
  - Suite enfocada (66 tests) → **66 PASS** en 0.166s.
  - Suite completa de regresión → **1062 / 1062 tests PASS** en 34.4s (0 fallos, 0 errores, 0 regresiones).
  - Preservación 100% de contratos `inspect.getsource(main)`.

## [2026-09-15] - QA Audit & Estabilización Post-Implementación Specs 061 a 065

* **Objetivo**: Auditoría exhaustiva de calidad (QA) y robustez operativa sobre las implementaciones Specs 061 a 065 (SQLite WAL, HW Error Tripwire, Gobernador Estacional, Gráficos Multi-Miner y Pipeline Declarativo de Hooks), resolución de defectos sutiles de ordenamiento y contención, y certificación de la suite global de 1043 pruebas unitarias.
* **Defectos Detectados y Corregidos**:
  - **BUG-01 (Inversión de Orden de Etapas en `CoreSupervisoryEngine.execute_tick`)**:
    * En `app/core/engine.py`, la separación entre `other_hooks` y `persistence_hooks` provocaba que los hooks de etapa `POST_TICK` (etapa 70) se ejecutaran antes de los hooks de `PERSISTENCE` (etapa 60).
    * Se unificó el bucle de despacho en orden estricto de `HookStage` con contención defensiva individual por hook (`try ... except Exception:`), garantizando que `PERSISTENCE` se ejecute siempre antes de `POST_TICK` y que ambas etapas se ejecuten de manera incondicional incluso ante fallos en etapas precedentes.
    * Actualizada la aserción en `tests/test_supervisory_hooks.py` reflejando el orden canónico: `["pre", "detect", "gov", "persist", "post"]`.
  - **BUG-02 (Ausencia de Barrera de Excepciones en Hilo Asíncrono de Restauración de Preset)**:
    * En `app/miner_monitor.py:5442` (`_async_restore_locked_preset`), un fallo de red o socket inesperado durante `safe_set_miner_preset` podía generar trazas sin capturar en el hilo daemon.
    * Se envolvió el cuerpo del hilo en un bloque defensivo `try ... except Exception as _th_exc:` con registro estructurado en logs (`[TRIPWIRE_INTERLOCK_ERR]`).
  - **BUG-03 (Propagación de `tick_sequence` a `CoreSupervisoryEngine`)**:
    * `execute_tick()` no aceptaba el número de secuencia de tick desde el bucle principal de `miner_monitor.py`, manteniendo el contador en 0.
    * Se agregó el parámetro `tick_sequence: Optional[int] = None` y se propagó el `tick_sequence` actual desde el bucle de supervisión en `miner_monitor.py`.
  - **BUG-04 (Protección contra `SQLITE_BUSY_SNAPSHOT` en Consultas de Gráficos Telegram)**:
    * En `app/telegram/charts.py:fetch_miner_chart_data()`, las consultas directas sobre SQLite durante checkpoints `TRUNCATE` concurrentes podían recibir excepciones de bloqueo.
    * Se integró la función `execute_readonly_with_retry` de `app.core.event_store`, absorbiendo transitorios de checkpoint con reintentos y retroceso exponencial automático.
  - **BUG-05 (Doble Escritura Innecesaria de `state.json` por Tick)**:
    * El bucle principal de `miner_monitor.py` ya ejecuta `_flush_state_payload(state_path, _payload)` durante el tick; posteriormente, `PersistenceHook.execute()` volvía a invocar `context.state_manager.save()`, generando una segunda escritura y fsync redundante por cada ciclo de supervisión.
    * Se añadió `extra_tick_data: Optional[Dict[str, Any]] = None` a `CoreSupervisoryEngine.execute_tick()`, inyectando `_state_persisted=True` desde el loop principal para activar el skip guard canónico de `PersistenceHook` (`persistence_skipped: reason='already_persisted_by_main_loop'`).
  - **BUG-06 (Prevención de Sobrescritura de `last_daily_digest_date` con Valor Stale)**:
    * `PersistenceHook` leía `last_daily_digest_date` de `context.last_daily_digest_date` (fijado en `None` en el arranque) en lugar del valor actualizado dinámicamente en tiempo de ejecución.
    * Se sincronizó `monitor_ctx.last_daily_digest_date = _LAST_DAILY_DIGEST_DATE` en `miner_monitor.py` y se inyectó en `extra_tick_data`, agregando pruebas unitarias de priorización en `tests/test_supervisory_hooks.py`.
  - **QA-01 (Saneamiento Integral de Espacios en Blanco y Saltos de Línea)**:
    * Se purgaron espacios finales en `app/miner_monitor.py`, `app/core/event_store.py`, `app/governance/preset_balancer.py`, etc., logrando que `git diff --check` y el script de preflight `preflight.ps1 -RunBuilds` pasen con salida 0 (PASS).
* **Verificación y Evidencia**:
  - `preflight.ps1 -RunBuilds` → **PASS** (ExitCode: 0, py_compile limpio, git-diff-check limpio).
  - Suite completa: `unittest discover -s tests` → **1046 / 1046 tests PASS** en 35.0s (0 fallos, 0 errores, 0 regresiones).
  - Verificación de contratos `inspect.getsource(main)` y literales críticos: 100% preservados.
  - Servicio Windows `MinerAlerts` validado y reiniciado con las actualizaciones.

## [2026-09-15] - Implementación Spec 065: Pipeline Declarativo de Hooks en CoreSupervisoryEngine (ST-04)

* **Objetivo**: Evolucionar `CoreSupervisoryEngine` hacia un pipeline declarativo de hooks estructurado por etapas (`HookStage`), con contención defensiva de fallos por hook, modelo de tiempo monotónico garantizado y preservación del 100% de los contratos de tests de introspección de `main()`.
* **Componentes Modificados / Creados**:
  - `app/core/engine.py`:
    * Implementado `HookStage` (enum `IntEnum` con 7 etapas ordenadas: `PRE_TICK=10`, `ACQUISITION=20`, `DETECTION=30`, `GOVERNANCE=40`, `ACTUATOR=50`, `PERSISTENCE=60`, `POST_TICK=70`).
    * Implementada clase base `SupervisoryHook` con interfaz `execute(context, tick_sequence, now_ts, tick_data) -> Optional[Dict]`.
    * Implementado dataclass `HookResult` (hook_name, stage, ok, duration_seconds, data, error).
    * Extendido `CoreSupervisoryEngine` con `register_hook(hook)` (ordenamiento determinista por `HookStage`) y `execute_tick(states, last_update_id_ref, now_ts) -> TickResult` con contención defensiva por hook y garantía de ejecución de etapa `PERSISTENCE` incluso si todas las etapas previas fallan.
    * Implementados hooks canónicos: `PersistenceHook` (etapa `PERSISTENCE`, delega en `StateManager.save()` fuera de locks), `GovernanceInterlockHook` (etapa `GOVERNANCE`, evalúa expiración de temporizadores) y `TimingGuardHook` (etapa `PRE_TICK`, registra `_timing_guard_start` en `tick_data` y emite warning si el intervalo supera umbral configurable).
  - `app/miner_monitor.py`:
    * Instanciación aditiva de `CoreSupervisoryEngine` con los 3 hooks canónicos antes del `while True:`, con `_poll_interval_seconds` como referencia inmutable del intervalo de configuración.
    * Reemplazado `time.sleep(poll_seconds)` por el modelo monotónico: `poll_seconds = max(0.0, _poll_interval_seconds - (time.monotonic() - tick_start)); time.sleep(poll_seconds)`, garantizando que `poll_seconds` es el intervalo mínimo entre `tick_start`s sin deriva acumulativa.
    * Sin modificación de ningún literal verificado por los tests de `inspect.getsource(main)`.
  - `tests/test_supervisory_hooks.py` (nuevo):
    * 47 tests nuevos en 13 clases cubriendo: orden de etapas, contrato de clase base, registro y ordenamiento, `execute_tick` con `tick_data` flow, contención defensiva de errores, garantía de `PERSISTENCE`, modelo monotónico de timing, hooks canónicos (`TimingGuardHook`, `GovernanceInterlockHook`, `PersistenceHook`), pipeline E2E y validación de integración aditiva en `miner_monitor.py`.
* **Verificación y Evidencia**:
  - `py_compile app/core/engine.py app/core/context.py app/miner_monitor.py` → SYNTAX OK.
  - `pytest tests/test_supervisory_hooks.py` → **47 passed**.
  - `pytest tests/` → **1043 passed** (996 originales + 47 nuevos), 0 regresiones.
  - `test_monitor_liveness::test_monitor_publishes_heartbeat_after_state_persistence` → PASSED (literal `time.sleep(poll_seconds)` preservado).
  - Servicio Windows `MinerAlerts` activo e ininterrumpido durante toda la implementación.
* **Invariantes Cumplidas**:
  - `len(tests_pass) >= 996` → ✅ 1043 tests PASS.
  - Contratos `inspect.getsource(main)` y `time.sleep(poll_seconds)` literales intactos.
  - Etapa `PERSISTENCE` siempre se ejecuta (3 tests de garantía dedicados).
  - Modelo monotónico aplicado: sleep = max(0, interval - elapsed).
  - Zero peticiones HTTP extras a mineros.

## [2026-09-15] - Implementación Spec 064: Telemetría Visual y Gráficos Comparativos Multi-Miner en Telegram (UX-01)

* **Objetivo**: Desarrollar visualización gráfica multi-miner agrupada por elevador eléctrico y flota, selector interactivo de horizonte temporal (1h, 6h, 24h, 7d) con actualización in-place sin spam mediante `editMessageMedia`, y blindaje estricto de memoria en `matplotlib` para entornos desatendidos de Windows.
* **Componentes Modificados / Creados**:
  - `app/telegram/charts.py`:
    * Implementado `fetch_group_chart_data(db_path, group_name, configured_miners, hours, now_ts)` para consultar muestras de telemetría de todos los mineros de un elevador eléctrico.
    * Implementado `render_group_chart_png(group_data, hours)` con diseño dual en memoria (subplot superior: Hashrate individual con colores consistentes y línea de umbral; subplot inferior: Temperatura individual de chip con la misma paleta por minero).
    * Implementado `build_chart_range_keyboard(target, current_hours)` generando teclado inline interactivo `[ 1h ] [ 6h ] [ 24h ] [ 7d ]` con marcador visual de rango activo (`• 1h •`).
    * Blindaje mandatorio de memoria con `try ... finally: plt.close(fig)` en todos los paths de renderizado.
  - `app/telegram/callbacks.py`:
    * Soporte para gramática de acción `chart_range:<target>:<hours>` en `parse_callback_data()` y `build_callback_data()`, garantizando payload acotado <= 64 bytes.
  - `app/telegram/commands/diagnostics.py`:
    * Extendido `ChartCommand` para resolver objetivos de grupo eléctrico (ej. `elevator_1`, `elevator_2`) y adjuntar automáticamente el teclado inline de rangos temporales en `/chart <objetivo> [horas]`.
    * Soporte de horizontes temporales de hasta 168h (7 días).
  - `app/miner_monitor.py`:
    * Extendido `send_telegram_photo()` con parámetro opcional `reply_markup`.
    * Implementado `edit_telegram_photo(bot_token, chat_id, message_id, photo_bytes, caption, reply_markup)` utilizando la API `editMessageMedia` de Telegram con multipart/form-data y `attach://file_0`.
    * Integrado manejador de callbacks `chart_range` en `_handle_callback_query()`, actualizando imágenes in-place y respondiendo con toasts informativos sin polución de chat.
  - `app/telegram/__init__.py`:
    * Re-exportación de `build_chart_range_keyboard`, `fetch_group_chart_data` y `render_group_chart_png`.
  - `app/telegram/help_center.py`:
    * Actualizada la definición del comando `/chart` documentando el soporte para grupos y selector interactivo.
  - `tests/test_multi_miner_charts.py`:
    * Suite dedicada de 11 pruebas unitarias y de integración cubriendo consultas de grupo, teclado inline, `editMessageMedia`, dispatch de callbacks y prueba de estabilidad de memoria (100 renders consecutivos con verificación de cero fugas en `plt.get_fignums()`).
* **Verificación y Evidencia**:
  - Compilación limpia con `py_compile` en todos los módulos.
  - 11 pruebas dedicadas en `tests/test_multi_miner_charts.py` PASS en 17.7s.
  - 996 pruebas globales en `tests/` PASS en 33.7s (0 fallos, 0 regresiones).
  - Servicio Windows `MinerAlerts` verificado en estado `Running`.
  - Certificado en `specs/064-multi-miner-charts/evidence.md`.

## [2026-09-15] - Implementación Spec 063: Gobernador Térmico con Conciencia Estacional (Ambient-Aware Thermal PID) (GOV-02)

* **Objetivo**: Implementar la adaptación estacional en el gobernador térmico de lazo cerrado mediante inferencia de temperatura ambiente a partir de los sensores de entrada ya sondeados en la telemetría Vnish (`stats_response`), ajustando dinámicamente objetivos y pisos térmicos según la temporada climática (invierno/estándar/verano) sin sobrecarga de red HTTP y preservando 3 guardarraíles inviolables de hardware.
* **Componentes Modificados / Creados**:
  - `app/vnish/telemetry.py`:
    * Añadido `inlet_temp_c: Optional[float] = None` a dataclass `VnishTelemetry` y a `as_dict()`.
    * Extracción regex de sensores de entrada (`_INLET_TEMP_RE`) para claves como `temp_in`, `temp_pcb_in`, `temp_inlet` con filtro de validez $[-10.0, 60.0]^\circ\text{C}$ en `normalize_vnish_stats()`.
  - `app/governance/fan_governor.py`:
    * Extensión de `GovernorConfig` con parámetros estacionales (`seasonal_enabled`, `winter_ambient_threshold_c = 18.0`, `summer_ambient_threshold_c = 28.0`, `winter_target_temp_c = 76.0`, `winter_min_duty_percent = 45`, `summer_target_temp_c = 80.0`, `summer_min_duty_percent = 65`, `summer_step_up_percent = 5`).
    * Implementación de la dataclass `SeasonalGovernorParams` y de la función pura `resolve_seasonal_parameters(ambient_temp_c, config)`.
    * Garantía matemática de los 3 guardarraíles inviolables: techo máx target 82.0°C, piso mín 30% PWM y Thermal Guard/Emergency Spike siempre a 100% PWM.
    * Integración de `ambient_temp_c` y `seasonal_mode` en `compute_governor_step()`, adaptando target, deadband, min_duty y step-up estacionalmente con clamping defensivo ante Silent Mode.
  - `app/governance/__init__.py`:
    * Re-exportación de `SeasonalGovernorParams`, `resolve_seasonal_parameters`, `SEASONAL_MODE_WINTER`, `SEASONAL_MODE_STANDARD`, `SEASONAL_MODE_SUMMER` en `__all__`.
  - `app/miner_monitor.py`:
    * Extensión de `MinerState` con `inlet_temp_c` y asignación en el ciclo de muestreo.
    * Persistencia no volátil en `load_state` y `_build_state_payload`.
    * Agregación de $T_{\text{amb}}$ por grupo eléctrico y a nivel flota en `execute_governor_cycle()`, resolviendo `ambient_temp_c` para cada minero.
    * Inclusión de `season={dec.seasonal_mode}` en el registro estructurado de `execute_governor_cycle()`.
  - `app/core/state_manager.py`:
    * Serialización atómica de `inlet_temp_c` en `_serialise_miner_state`.
  - `app/config.example.json`:
    * Documentadas las claves de configuración estacionales con valores seguros por defecto.
  - `tests/test_fan_governor_seasonal.py`:
    * Suite dedicada de 26 pruebas unitarias y de integración cubriendo transiciones de modos, guardarraíles inviolables, interacción con Silent Mode, fallbacks y agregación grupal.
* **Verificación y Evidencia**:
  - Compilación limpia con `py_compile` en todos los módulos modificados.
  - 26 tests en `tests/test_fan_governor_seasonal.py` PASS en 0.001s.
  - 82 tests en suites combinadas de fan governor y telemetría PASS.
  - 985 tests globales PASS en 15.214s (0 regresiones, 0 fallos).
  - Servicio Windows `MinerAlerts` en estado `Running`.
  - Certificado en `specs/063-ambient-thermal-pid/evidence.md`.

## [2026-09-15] - Formalización Spec 063: Gobernador Térmico con Conciencia Estacional (Ambient-Aware Thermal PID) (GOV-02)

* **Objetivo**: Formalizar la especificación técnica (`spec.md`, `plan.md`, `tasks.md`) para la Spec 063 incorporando las correcciones de auditoría de Claude Sonnet 4.6 (inferencia de $T_{\text{amb}}$ mediante promediado de `inlet_temp_c` ya disponible en `stats_response` sin peticiones HTTP extras, curvas estacionales de invierno/verano y 3 guardarraíles inviolables: techo máx target 82°C, piso mín 30% PWM y Thermal Guard de 85°C siempre forzando 100% PWM).
* **Artefactos Creados**:
  - `specs/063-ambient-thermal-pid/spec.md`: Historias de usuario, requerimientos funcionales, guardarraíles inviolables y casos de borde.
  - `specs/063-ambient-thermal-pid/plan.md`: Plan de implementación en 3 fases (Fase A: Extracción de telemetría de entrada, Fase B: Dominio puro y guardarraíles invariantes, Fase C: Integración en monitor y suite de tests).
  - `specs/063-ambient-thermal-pid/tasks.md`: 7 tareas estructuradas.
* **Seguimiento**:
  - Actualizado `.specify/feature.json` a `specs/063-ambient-thermal-pid`.
  - Actualizado `AGENTS.md` con plan activo `specs/063-ambient-thermal-pid/plan.md`.
  - Actualizado `docs/speckit/ROADMAP.md` registrando la Iniciativa 15 (Spec 063) como "En Progreso".

## [2026-09-15] - Implementación Spec 062: HW Error Tripwire & Rollback Automático de Overclock (GOV-01)

* **Objetivo**: Implementar el mecanismo de protección física de silicio ante degradación o overclock excesivo mediante un tripwire que monitorea el incremento y la tasa porcentual de Hardware Errors en ventanas de 10 minutos consultando `EventStore`, aplicando desescalada automática de potencia y un candado de seguridad de 48 horas persistido en `state.json` con interlock anti-cascada post-reboot.
* **Componentes Modificados / Creados**:
  - `app/governance/preset_balancer.py`:
    * Definición de `ACTION_STEP_DOWN_HW_ERRORS = "STEP_DOWN_HW_ERRORS"`.
    * Extensión de `StabilityMetrics` con `hw_errors_delta_10m`, `hw_error_rate_pct`, `hw_error_lock_until_ts`, `hw_error_locked_preset`.
    * Extensión de `BalancerConfig` con umbrales `hw_error_rate_threshold_pct = 0.5`, `hw_error_delta_threshold = 200`, `hw_error_lock_hours = 48.0`.
    * Regla de disparo en `evaluate_balancer_step()` con compuerta AND (`hw_error_rate_pct >= 0.5%` Y `hw_errors_delta_10m >= 200`).
    * Forzado defensivo ante violación de candado post-reboot (paso 0.2) e inhibición estricta de step-up (`ACTION_STEP_UP_OPTIMIZE`) mientras el candado esté activo.
    * Tarjeta Mobile-First `render_hw_error_tripwire_card()` con ancho `<= 32` columnas.
    * Extracción no volátil en `extract_miner_stability_metrics()` comparando muestra $T$ contra muestra $T - 10\text{m}$ en `telemetry_samples` de SQLite.
  - `app/governance/__init__.py`:
    * Re-exportación de `ACTION_STEP_DOWN_HW_ERRORS` y `render_hw_error_tripwire_card` en `__all__`.
  - `app/miner_monitor.py`:
    * Extensión de `MinerState` con `hw_error_lock_until_ts` y `hw_error_locked_preset`.
    * Persistencia no volátil en `load_state` y `_build_state_payload`.
    * Integración en `execute_balancer_cycle()` activando el candado de 48 horas y despachando alertas a Telegram vía `render_hw_error_tripwire_card()`.
    * Interlock anti-cascada post-reboot en `refresh_vnish_overclock_settings` y en la detección de reinicio de minero (`reboot_reason`) restaurando el preset defensivo en background sin bloquear `state_lock`.
    * Preservación intacta del auto-reboot por `STATE_LOW` o `STATE_HASHBOARD`.
  - `app/core/state_manager.py`:
    * Serialización atómica de `hw_error_lock_until_ts` y `hw_error_locked_preset` en `_serialise_miner_state`.
  - `app/config.example.json`:
    * Documentadas las opciones `preset_balancer_hw_error_rate_threshold_pct`, `preset_balancer_hw_error_delta_threshold`, `preset_balancer_hw_error_lock_hours`.
  - `tests/test_hw_error_tripwire.py`:
    * Suite exhaustiva de 13 pruebas unitarias e integración con 100% de éxito.
* **Validación**:
  - `py_compile`: 100% OK en todos los módulos modificados.
  - Tests Spec 062: 13/13 PASS en 0.143s.
  - Suite completa del proyecto: 959/959 PASS en 15.671s (cero fallos, cero regresiones).
  - Servicio Windows `MinerAlerts`: Estado `Running` verificado.

## [2026-09-15] - Formalización Spec 062: HW Error Tripwire & Rollback Automático de Overclock (GOV-01)

* **Objetivo**: Formalizar la especificación técnica (`spec.md`, `plan.md`, `tasks.md`) para la Spec 062 incorporando las correcciones de auditoría de Claude Sonnet 4.6 (métrica no volátil desde `EventStore`, umbral combinado de tasa y delta absoluto, candado de 48 horas persistido en `state.json` e interlock anti-cascada adversarial post-reboot).
* **Artefactos Creados**:
  - `specs/062-hw-error-tripwire/spec.md`: Historias de usuario, requerimientos funcionales y escenarios defensivos.
  - `specs/062-hw-error-tripwire/plan.md`: Plan de implementación en 3 fases (Fase A: Dominio puro y regla de tripwire, Fase B: Persistencia de candado y extracción SQLite, Fase C: Anti-cascada en monitor y suite de tests).
  - `specs/062-hw-error-tripwire/tasks.md`: 7 tareas ejecutables estructuradas.
* **Seguimiento**:
  - Actualizado `.specify/feature.json` a `specs/062-hw-error-tripwire`.
  - Actualizado `AGENTS.md` con plan activo `specs/062-hw-error-tripwire/plan.md`.
  - Actualizado `docs/speckit/ROADMAP.md` registrando la Iniciativa 14 (Spec 062) como "En Progreso".

## [2026-09-15] - Implementación Spec 061: Resiliencia SQLite WAL Mode & Integrity Check (ST-03)

* **Objetivo**: Implementar de punta a punta la Spec 061 blindando `EventStore` contra corrupciones de disco tras apagones intempestivos, previniendo saturación de espacio en Windows NTFS y habilitando lectura externa concurrente sin bloqueos de snapshot.
* **Componentes Modificados**:
  - `app/core/event_store.py`:
    * Hilo daemon asíncrono `_integrity_check_worker` con `PRAGMA quick_check;` en conexión de solo lectura aislada (0 ms de impacto en el arranque del monitor y Startup Guard).
    * Auto-cuarentena atómica a `miner_alerts_corrupt_<epoch>.db` (`.db`, `.db-wal`, `.db-shm`) y recreación limpia de esquema v7 con emisión de alertas críticas.
    * Techo blando de almacenamiento: `PRAGMA max_page_count = 262144;` (~1 GB) en `_initialize()`.
    * Método público `EventStore.checkpoint_wal(mode: str = "PASSIVE") -> Tuple[int, int, int]` soportando `PASSIVE`, `FULL`, `RESTART` y `TRUNCATE`.
    * Cierre defensivo de handles de conexión ante excepciones de inicialización y soporte de context manager `__enter__` / `__exit__`.
    * Helpers públicos `create_readonly_connection(db_path, timeout=3.0)` y `execute_readonly_with_retry` con retroceso exponencial (100ms, 200ms, 400ms) ante `SQLITE_BUSY_SNAPSHOT`.
  - `app/core/__init__.py`: Re-exportación de `create_readonly_connection` y `execute_readonly_with_retry` en `__all__`.
  - `app/miner_monitor.py`:
    * Conexión de checkpoint horario `PASSIVE` y checkpoint diario `TRUNCATE` en horario valle (03:00 - 05:00 UTC) dentro del bucle de supervisión principal.
  - `tests/test_event_store_wal_resilience.py`:
    * Suite dedicada de 11 tests cubriendo quick-check asíncrono, detección de corrupción de cabecera y páginas internas, modos de checkpointing, creación de conexión de solo lectura, reintentos BUSY_SNAPSHOT y concurrencia multi-lector bajo escrituras continuas y truncamiento en caliente.
* **Validación**:
  - `py_compile`: 100% OK en todos los módulos modificados.
  - Tests de resiliencia WAL: 11/11 PASS en 0.900s.
  - Suite completa del proyecto: 946/946 PASS en 15.427s (0 fallos, 0 errores, 0 regresiones sobre 935 base).
  - Servicio Windows `MinerAlerts`: `Running` continuo verificado.

## [2026-09-15] - Formalización Spec 061: Resiliencia SQLite WAL Mode & Integrity Check (ST-03)

* **Objetivo**: Diagramar y generar los artefactos formales de especificación (`spec.md`, `plan.md`, `tasks.md`) para la Spec 061 incorporando las 3 correcciones críticas auditadas por Claude Sonnet 4.6 (quick_check asíncrono, checkpointing TRUNCATE diario fuera de pico en Windows NTFS y pool multi-lector defensivo ante `SQLITE_BUSY_SNAPSHOT`).
* **Artefactos Creados**:
  - `specs/061-sqlite-wal-integrity/spec.md`: Requerimientos funcionales, historias de usuario, casos de borde y contratos de interfaz.
  - `specs/061-sqlite-wal-integrity/plan.md`: Plan de implementación en 3 fases (Fase A: Integridad Asíncrona & Límite de Espacio, Fase B: Checkpointing en Windows NTFS, Fase C: Pool de Lectura y Suite de Tests).
  - `specs/061-sqlite-wal-integrity/tasks.md`: 7 tareas ejecutables estructuradas con dependencias binarias.
* **Seguimiento**:
  - Actualizado `.specify/feature.json` a `specs/061-sqlite-wal-integrity`.
  - Actualizado `AGENTS.md` con el plan activo y gate de observación.
  - Actualizado `docs/speckit/ROADMAP.md` registrando la Iniciativa 13 (Spec 061) como "En Planificación".

## [2026-09-15] - Auditoría Técnica ACTION_PLAN_POST_V5: Specs 061–065 (Claude Sonnet 4.6 Thinking)

* **Objetivo**: Auditar el plan de las iniciativas Specs 061 a 065 del horizonte post-V5.0, identificar riesgos arquitectónicos no previstos y refinar el diseño de cada spec antes de que Gemini genere las especificaciones formales.

* **Correcciones aplicadas a `docs/speckit/ACTION_PLAN_POST_V5_EVOLUTION.md`**:

  **Spec 061 (SQLite WAL & Integrity)**:
  - `PRAGMA quick_check` movido de `_initialize()` sincrónico a hilo daemon asíncrono — evita retraso de 100-500ms en startup de Telegram.
  - Agregado `PRAGMA wal_checkpoint(TRUNCATE)` en ciclo de mantenimiento diario (03:00-05:00): el PASSIVE no trunca el WAL en Windows con lectores externos activos.
  - Pool de lectura: documentado manejo de `SQLITE_BUSY_SNAPSHOT` (código 5) con backoff 100ms/200ms/400ms y máx 3 reintentos.

  **Spec 062 (HW Error Tripwire)**:
  - Threshold corregido: `≥50 errors en 10m` es demasiado sensible para S19j Pro (~90 TH/s). Umbral correcto: `hw_error_rate_pct > 0.5% AND hw_errors_delta_10m >= 200`.
  - Delta de HW errors debe calcularse desde el EventStore (sample T vs T-10m), no en memoria — se pierde en reboot.
  - Introducido interlock anti-cascada: `hw_error_locked_preset` debe persistir en `state.json` y restaurarse post-reboot L1/L2 (impide que el firmware restaure 2700W y reactive el silicio estresado).

  **Spec 063 (Thermal PID Estacional)**:
  - `temp_in` ya disponible en `stats_response` existente del ciclo de 30s (campo `temp_pcb_in` / `temp_in` en Vnish `/api/v1/summary`). Cero requests HTTP adicionales.
  - Guardarraíl 85°C explicitado como invariante de diseño: el modo estacional NUNCA puede elevar el objetivo más allá de 82°C, ni reducir el piso global por debajo del 30% definido en `GovernorConfig.min_fan_duty_percent`.

  **Spec 064 (Gráficos Multi-Miner)**:
  - `editMessageMedia` requiere multipart/form-data `attach://file_0` — no es un POST JSON estándar. Documentado en el spec.
  - Requisito obligatorio de backend `Agg` + `plt.close(fig)` explícito post-render. Sin esto, matplotlib acumula figuras hasta OOM en Windows.
  - Nuevo test de leak: 100 renders consecutivos con verificación de RSS < +5%.

  **Spec 065 (Hooks Declarativos)**:
  - Estrategia de migración corregida: hooks como decoradores en Fase A (código permanece en `main()`, tests siguen pasando), migración Fase A→B conservadora con paridad de tests documentada antes de mover cada bloque.
  - Riesgo de timing identificado: `poll_seconds` debe ser tiempo mínimo entre `tick_start` (no sleep puro). Modelo monotónico ya en `engine.py` — verificar preservación en Fase B.
  - Orden de extracción recomendado: PersistenceHook → GovernanceInterlockHook → ActuatorHook → AcquisitionHook/IncidentDetectionHook.

* **Código modificado**: Sólo documentación — `docs/speckit/ACTION_PLAN_POST_V5_EVOLUTION.md` (plan auditado y corregido in-place).
* **Tests**: Sin cambios de código. 935/935 PASS vigente.
* **Servicio Windows**: `MinerAlerts` Running (no se tocó).

## [2026-09-15] - Spec 060 Phase B: Integración de StateManager y MonitorContext en Daemon Principal (Milestone V5.0)

* **Objetivo**: Conectar los nuevos subsistemas de arquitectura limpia `StateManager` y `MonitorContext` de `app/core/` en el punto de entrada de ejecución `main()` en `app/miner_monitor.py` de forma aditiva y segura, certificando 100% de los contratos de inspección estática (`inspect.getsource(main)`) y alcanzando el hito de modularización V5.0.

* **Componentes y Cambios Implementados**:
  - `app/miner_monitor.py`:
    - Instanciación de `StateManager` vinculando `state_path`, `state_lock`, `_SAVE_STATE_LOCK` y accessor a variables globales con serialización retrocompatible con `state.json`.
    - Instanciación de `MonitorContext` mediante `build_monitor_context` agrupando todas las variables mutables y configuraciones (`config`, `state_lock`, `valid_miners`, `state_manager`, `event_store`, `hashcore_cfg`, gobernanza y contingencia).
    - Preservación estricta de las sentencias literales requeridas por las suites de inspección estática (`tests/test_auto_reboot_signal_gate.py`, `tests/test_reboot_safety.py`, `tests/test_vnish_hashboard_detection.py`, `tests/test_monitor_incidents.py`).
  - `tests/test_core_daemon.py`:
    - Creada suite con 7 pruebas unitarias completas validando:
      - `test_state_manager_save_and_restore`: persistencia y recarga atómica L1->L2.
      - `test_state_manager_lock_hierarchy`: comprobación de jerarquía anti-deadlock L1 (`state_lock`) -> L2 (`_SAVE_STATE_LOCK`).
      - `test_monitor_context_immutability_and_di`: inyección de dependencias y validación de tipos en `MonitorContext`.
      - `test_monitor_context_factory_missing_field`: validación defensiva en la factoría `build_monitor_context`.
      - `test_engine_hooks_execution_flow`: flujo secuencial de hooks (`before_tick`, `after_tick`) y orquestación con `TickResult`.
      - `test_engine_shutdown_flag`: parada segura determinista mediante `threading.Event`.
      - `test_engine_pure_helpers`: comprobación de `log_tick_header`, `check_governance_expiry` y `should_skip_actuators`.

* **Verificación y Pruebas**:
  - **935/935 tests PASS** en 12.766s (+7 tests unitarios nuevos, cero fallos, cero regresiones).
  - Verificación de sintaxis: `py_compile` en todos los módulos de `app/core/` y `app/miner_monitor.py` limpia (código de salida 0).
  - Servicio Windows `MinerAlerts` en estado `Running` (StartType Automatic).
  - Milestone V5.0 de Modularización completado.

## [2026-09-15] - Spec 060 Phase A: Core Daemon Architecture — StateManager, MonitorContext, CoreSupervisoryEngine

* **Objetivo**: Implementar los tres módulos de la Fase 3 del `ACTION_PLAN_V5_MODULARIZATION.md`: `state_manager.py`, `context.py` y `engine.py` dentro de `app/core/`, constituyendo la infraestructura de arquitectura limpia para V5.0.

* **Módulos creados**:
  - `app/core/state_manager.py` — `StateManager`: gestor atómico de persistencia con jerarquía de locks L1→L2 correctamente implementada. `_build_state_payload()` corre bajo `state_lock`, el flush (`os.fsync` + `os.replace`) corre bajo `_flush_lock` únicamente. Implementa `save()`, `build_payload()`, `flush_payload()`, `get_state()`, `update_state()`. Helper `_serialise_miner_state()` espeja el campo a campo el payload legacy de `_build_state_payload` en `miner_monitor.py` para retrocompatibilidad perfecta de `state.json`.
  - `app/core/context.py` — `MonitorContext`: contenedor de inyección de dependencias tipado (`@dataclass`). Consolida `config`, `state_manager`, `state_lock`, `miners`, `bot_token`, `chat_id`, `telegram_queue`, `event_store`, `hashcore_cfg`, `governance`, `elevator_contingency`, `scheduled_window`, `qa_mode` y flags QA. Reemplaza progresivamente las variables globales mutables (`_GLOBAL_INTERVENTION_GOV`, `_ELEVATOR_CONTINGENCY_STATES`, `_ACTIVE_SCHEDULED_WINDOW`, `_QA_MODE`). Factory `build_monitor_context()` con validación de campos requeridos.
  - `app/core/engine.py` — `CoreSupervisoryEngine`: orquestador del ciclo de 30s con arquitectura de hooks registrables por tick. Modelo de threading: `run()` en hilo principal, hooks ejecutados secuencialmente, `shutdown()` via `threading.Event`. Helpers puros: `log_tick_header()`, `check_governance_expiry()`, `should_skip_actuators()`. Compatible con los contratos de `inspect.getsource(main)` — **no remueve lógica de `main()`**, solo agrega infraestructura.

* **Compatibilidad y contratos de tests preservados**:
  - `main()` permanece intacta en `app/miner_monitor.py` con todos los patrones que `test_auto_reboot_signal_gate.py`, `test_reboot_safety.py`, `test_vnish_hashboard_detection.py` y `test_monitor_incidents.py` verifican via `inspect.getsource()`.
  - Los 3 módulos nuevos NO importan de `miner_monitor.py` — cero riesgo de importación circular.
  - `app/core/__init__.py` actualizado con 6 nuevos símbolos en `__all__`.

* **Validación**:
  - `py_compile app\core\state_manager.py app\core\context.py app\core\engine.py app\miner_monitor.py` → **SYNTAX OK**.
  - Suite completa: **928/928 tests PASS en 12.77s** (0 regresiones).
  - Servicio Windows `MinerAlerts` → **Running** (Automatic).

## [2026-09-15] - Implementación Spec 059: Protocolos de Red y Clientes de Hardware (MT-02)

* **Objetivo**: Extraer la comunicación de socket crudo TCP 4028 (CGMiner/Telnet JSON), el actuador de hardware Hashcore Toolkit CLI y formalizar el cliente REST orientado a objetos para Vnish fuera de `app/miner_monitor.py` hacia `app/network/`, reduciendo el monolito a 6,856 líneas y blindando el sistema contra sockets bloqueantes o fallos en subprocess.
* **Componentes y Cambios Implementados**:
  - `app/network/cgminer_client.py`:
    - Creada clase `CGMinerClient` para interactuar de forma tipada con el puerto 4028.
    - Implementadas funciones `query_cgminer`, `read_summary`, `read_stats_snapshot`, `read_stats_active_boards`, `read_pools`, `read_version` con soporte para inyección de `query_fn`.
    - Implementadas funciones puras de conteo y parsing: `count_active_boards` (soporta formato moderno `chain_acn` y claves escalares legadas `chain{i}_asicnum`), `extract_temps` y `fw_hint`.
    - Eliminación automática de bytes nulos (`\x00`), timeouts estrictos por socket y decodificación UTF-8 tolerante.
  - `app/network/hashcore_client.py`:
    - Creada clase `HashcoreClient` y funciones `run_hashcore_cli`, `run_hashcore_discovery`, `get_hashcore_cli_path`.
    - Enforced `CREATE_NO_WINDOW = 0x08000000` para ejecución silenciosa en servicios de Windows.
    - Cumplimiento riguroso de guardarraíles QA (`qa_mode`, `qa_allow_actions`) para prevenir reinicios accidentales.
  - `app/network/vnish_client.py`:
    - Creada clase `VnishClient` orientada a objetos con gestión de contexto (`__enter__` / `__exit__`), reutilización de sesión HTTP, timeouts acotados de 2.5s y métodos tipados (`set_fan_duty`, `restart_mining`, `get_status`, `get_overclock_settings`, `set_preset`).
    - Re-exportadas las funciones base de `app/vnish/client.py`.
  - `app/network/__init__.py`:
    - Exportación centralizada de todos los clientes y funciones de red.
  - `app/miner_monitor.py`:
    - Sustituidas ~300 líneas de sockets y subprocesos por fachadas hacia `app.network` (`read_summary`, `read_stats_snapshot`, `_count_active_boards`, `run_hashcore_cli`, etc.).
    - Preservados contratos de inspección y capacidad de intercepción para mocks de tests (`patch("app.miner_monitor._read_command")`, `patch("app.miner_monitor.subprocess.run")`).
  - `tests/test_network_clients.py`:
    - Creada suite con 18 tests unitarios exhaustivos cubriendo parsing de summary/stats, timeouts de red, manejo de QA en Hashcore y ciclo de vida de `VnishClient`.
* **Verificación y Pruebas**:
  - **928/928 tests PASS** en 13.166s (+18 tests nuevos, cero fallos, cero regresiones).
  - Servicio Windows `MinerAlerts` activo y en ejecución (`Running`).

## [2026-09-15] - Implementación Spec 058: Modularización del Telegram Command Center & Dispatcher (MT-01)

* **Objetivo**: Extraer más de 2,600 líneas de código procedural de despacho de comandos de Telegram fuera de `app/miner_monitor.py` hacia subsistemas desacoplados, implementando autenticación estricta por `chat_id`, resolución robusta de alias en inglés y español, aislamiento de errores y política estricta de No-Silencio.
* **Componentes y Cambios Implementados**:
  - `app/telegram/context.py`:
    - Creada clase `TelegramRequestContext` para encapsular contexto de ejecución (`bot_token`, `chat_id`, `config`, `miners`, `states`, `state_lock`, `event_store`, `hashcore_cfg`, `token_registry`, `pending_reboots`, `pending_lock`).
    - Métodos helper para persistencia segura de estado (`persist_state_safely`) respetando la jerarquía anti-deadlock L1 (`state_lock`) -> L2 (`_SAVE_STATE_LOCK`), y envío uniforme de mensajes (`send_message`, asegurando `is_command=True`).
  - `app/telegram/commands/base.py`:
    - Creada clase abstracta `BaseCommandHandler` con resolución de alias, coincidencia normalizada y verificación estricta de autorización por `chat_id`.
  - `app/telegram/router.py`:
    - Creados `TelegramCommandRouter` (registro y despacho de comandos con boundary de excepción para evitar caída del hilo) y `TelegramCallbackRouter` (ruteo centralizado de consultas callback con validación de identidad).
    - Fábrica `create_default_command_router()` que registra la totalidad de comandos operativos de la flota.
  - `app/telegram/commands/`:
    - `status.py`: Comandos `/status`, `/estado`, `/resumen`, `/metrics` e `/info`.
    - `fans.py`: Comandos `/fans`, `/silent`, `/silencio`, `/governor`, `/gov`.
    - `interventions.py`: Comandos `/interventions`, `/contingency`, `/balancer`, `/elevadores`.
    - `reboot.py`: Comandos `/reboot`, `/reiniciar`, `/reboot_no_ok`, `/confirm`, `/c<code>`.
    - `diagnostics.py`: Comandos `/diagnose`, `/firmware`, `/quality`, `/health`, `/chart`, `/events`, `/event`, `/why`, `/chains`, `/efficiency`, `/presets`, `/selftest`.
    - `maintenance.py`: Comandos `/snooze`, `/unsnooze`, `/snoozed`, `/shutdown`, `/resume`, `/schedule_maintenance`, `/scheduled`.
    - `help.py`: Comandos `/help`, `/ayuda`, `/menu`, `/start`, `/panel`, `/digest`.
  - `app/telegram/poller.py`:
    - Desacoplamiento de polling HTTP `getUpdates` con backoff exponencial y procesamiento modular.
  - `app/miner_monitor.py`:
    - Reducción masiva de **9,724 líneas a 7,055 líneas (-2,669 LOC)** en el monolito.
    - Delegación limpia de la recepción de comandos hacia `_command_router.dispatch(...)`.
    - Preservados contratos inspect (`build_miner_diagnosis_text`, `build_firmware_events_text`, `build_mining_quality_text`, `build_stability_health_text`, `is_command=True`).
  - `tests/test_telegram_dispatcher.py`:
    - Creada suite con 8 pruebas unitarias cubriendo registro, alias en español, verificación de autorización, tolerancia a fallos y política No-Silencio.
  - `tests/test_telegram_messaging.py`:
    - Actualizado test de cableado para validar tanto la persistencia de `is_command=True` en `TelegramRequestContext` como en los módulos desacoplados.
* **Verificación y Pruebas**:
  - **910/910 tests PASS** en 13.5s (cero fallos, cero regresiones).
  - Servicio Windows `MinerAlerts` activo y en ejecución (`Running`).

## [2026-09-15] - Implementación Quick Win QW-04: Extracción de `_build_state_payload()` y Desacoplamiento de I/O

* **Objetivo**: Resolver la retención innecesaria de `state_lock` durante el I/O a disco (`os.fsync()`, escritura a `.tmp`, copia a `.bak` y `os.replace`), desacoplando la serialización en memoria del volcado físico a disco en Windows NTFS según la auditoría de Sonnet.
* **Componentes y Cambios Implementados**:
  - `app/miner_monitor.py`:
    - Creada función pura `_build_state_payload(states, last_update_id, last_daily_digest_date)` que captura el snapshot completo de `states`, `scheduled_maintenance`, `intervention_governance` y `elevator_contingency` bajo `state_lock` en memoria (<0.1ms).
    - Creada función `_flush_state_payload(state_path, payload)` que gestiona el I/O físico a disco protegido exclusivamente por `_SAVE_STATE_LOCK`, sin retener `state_lock`.
    - Preservada `save_state()` como wrapper hacia atrás para llamadas externas.
    - Refactorizados todos los call sites críticos en `miner_monitor.py` (L3546 y L3566 en silent mode, L3800 en reboot manual, L3814, L3827 y L3848 en intervenciones, L4492 en confirmación de reboot, L4535 en snooze, L4806, L4813 y L4820 en comandos `/interventions`, L9434 en guarda térmica y L9602 en bucle principal) aplicando el patrón:
      ```python
      with state_lock:
          # mutaciones de estado en memoria
          _payload = _build_state_payload(states, current_last_update_id)
      _flush_state_payload(state_path, _payload)
      ```
  - `tests/test_monitor_liveness.py`:
    - Actualizada la aserción de orden de persistencia `test_monitor_publishes_heartbeat_after_state_persistence` para admitir `_flush_state_payload` manteniendo total compatibilidad.
* **Verificación y Pruebas**:
  - **902/902 tests PASS** en 14.2s (cero errores, cero regresiones).
  - Verificación sintáctica con `py_compile` limpia.
  - Servicio Windows `MinerAlerts` activo y corriendo.

## [2026-09-15] - Auditoría de Concurrencia Arquitectónica y Validación del Plan V5.0 (Claude Sonnet 4.6 Thinking)

* **Objetivo**: Auditar en profundidad la seguridad multi-hilo de `_SAVE_STATE_LOCK` / `state_lock`, la inmutabilidad de `InterventionGovernance`, la pureza determinista de `evaluate_canary_contingency`, y validar la secuencia de modularización del `ACTION_PLAN_V5_MODULARIZATION.md`.

* **HALLAZGO-01: Dirección de Lock Consistente — Deadlock Descartado**
  - **Auditoría**: Examinados los 6 call sites de `save_state` (líneas 3803, 3817, 4476, 4520, 4788/4795, 9578). En todos ellos el patrón es `with state_lock:` → `save_state()` → `with _SAVE_STATE_LOCK:`. Esta **dirección L1→L2 es uniforme** en todo el código.
  - **Condición de Deadlock**: Requeriría que `save_state` intentara re-adquirir `state_lock` (inversión de dirección). Verificado: `save_state` (L2635-2741) **NUNCA adquiere `state_lock`**. El deadlock está formalmente descartado bajo el patrón actual.
  - **Estado**: ✅ SEGURO. Nulo riesgo de deadlock con el código actual.

* **HALLAZGO-02: Latencia de Alertas por `os.fsync()` dentro de `state_lock` — Riesgo Latente**
  - **Diagnóstico**: El call site del bucle principal (L9577-9578) retiene `state_lock` durante todo el `save_state()`, incluyendo `json.dumps`, escritura a `.tmp` y `os.fsync()`. En Windows NTFS el `fsync()` puede tardar 10-200ms. Durante ese tiempo, el hilo de Telegram queda bloqueado si intenta leer `states`.
  - **Impacto actual**: Bajo — el loop es de 30s y los comandos de Telegram no son time-critical en ese orden de magnitud. No hay pérdida de alertas.
  - **Impacto en Spec 060**: Si `state_manager.py` adopta el mismo patrón, el `MonitorContext` con eventos asincrónicos podría amplificar la latencia. **Corrección recomendada para Spec 060**: construir el payload del estado **fuera** de `state_lock` (snapshot inmutable del dict), luego liberar `state_lock` y hacer el I/O bajo `_SAVE_STATE_LOCK` solamente.
  - **Quick Win Propuesto (sin cambiar lógica)**: Extraer `_build_state_payload(states, gov, ...)` → liberar `state_lock` → invocar `save_state` con el payload ya construido. Cero cambios en lógica de negocio.
  - **Estado**: ⚠️ ACEPTABLE en producción actual. DEBE corregirse en Spec 060 antes de `state_manager.py`.

* **HALLAZGO-03: `InterventionGovernance` — Thread-Safety Confirmada**
  - `@dataclass(frozen=True)` + copy-on-write en `apply_governance_toggle()` garantiza que ningún hilo puede mutar una instancia vista por otro hilo.
  - Asignación de `_GLOBAL_INTERVENTION_GOV = apply_governance_toggle(...)` es atómica bajo CPython GIL.
  - Race condition teórica: hilo de monitoreo puede leer una instancia con 1 ciclo de retraso (30s). Aceptable por diseño.
  - **Estado**: ✅ CORRECTO. Thread-safe por diseño inmutable.

* **HALLAZGO-04: `evaluate_canary_contingency` — Pureza Confirmada**
  - Función pura sin I/O, sin mutación de estado global. `ContingencyDecision` es `frozen=True`.
  - Corrección de filtro `electrical_group` (L8258/9532) verificada como aplicada.
  - **Estado**: ✅ CORRECTO. Determinista y thread-safe.

* **VALIDACIÓN: Secuencia de Modularización ACTION_PLAN_V5**
  - **Fase 0 → Spec 058 → Spec 059 → Spec 060**: Secuencia validada como óptima.
  - **Ajuste Recomendado**: `state_manager.py` debe iniciarse como Quick Win paralelo en Fase 0/058, no esperar a Spec 060. El refactor de `_build_state_payload()` fuera del lock es la semilla natural de `state_manager.py`.
  - **Riesgo mayor**: El comentario en `ACTION_PLAN_V5` que dice "L2 NUNCA debe intentar adquirir L1" debe actualizarse para reflejar que la dirección real documentada y aplicada es **L1→L2 (state_lock primero, luego _SAVE_STATE_LOCK)**, que es la jerarquía correcta.

* **Archivos auditados**: `app/miner_monitor.py` (L2632-2741, L3793-3820, L4465-4530, L4775-4800, L9565-9578), `app/governance/intervention_policy.py` (L1-227), `app/governance/adaptive_contingency.py` (L1-80, L140-220), `docs/speckit/ACTION_PLAN_V5_MODULARIZATION.md`.
* **Tests**: Sin cambios de código — sin necesidad de re-validar suite. 902/902 PASS sigue vigente.
* **Correcciones de código**: Ninguna aplicada (el código es correcto). Refinamiento documentado en `ACTION_PLAN_V5_MODULARIZATION.md`.

## [2026-09-15] - Auditoría Integral de Arquitectura, QA y Correcciones Críticas en Producción

* **Objetivo**: Conducir una auditoría exhaustiva post-implementación de Spec 057, buscando bugs y condiciones de carrera en los cambios recientes (Specs 054-057), evaluando la deuda técnica del monolito `app/miner_monitor.py` (9,693 LOC), analizando la concurrencia multi-hilo en Windows y generando un plan de modularización de Quick Wins a Refactors.
* **Hallazgos Críticos Identificados y Corregidos en Caliente**:
  1. **BUG-01 (Clave de Grupo de Contingencia)**: Corregida discrepancia en `miner_monitor.py:8258` y `9532` donde se consultaba `_m.get("group")` en lugar de `(_m.get("electrical_group") or _m.get("group"))`. Ahora `_grp_presets` se puebla correctamente para comparar la carga agregada de los elevadores.
  2. **BUG-02 (Tipado de Fan Governor)**: Corregido retorno de `execute_governor_cycle` que retornaba implícitamente `None` en salidas tempranas mientras que al final retornaba una lista de eventos, violando consistencia de tipos. Anotado a `list` y retornos tempranos devuelven `[]`.
  3. **BUG-03 / RACE-01 (Concurrencia en Windows `save_state`)**: Detectada y resuelta colisión de escritura de disco en Windows entre el hilo de monitoreo principal y el worker de Telegram al invocar concurrentemente `save_state()`. Se implementó el mutex dedicado `_SAVE_STATE_LOCK = threading.Lock()` protegiendo el volcado temporal, la rotación `.bak` y `os.replace`.
* **Auditoría de Arquitectura y Concurrencia**:
  - **Monolito**: Desglosadas las responsabilidades de `app/miner_monitor.py`. Se identificaron ~3,000 líneas en `telegram_polling_worker` y ~900 líneas en el protocolo Telnet 4028 que pueden extraerse limpiamente sin romper producción.
  - **SQLite / EventStore**: Confirmada configuración óptima con WAL mode, synchronous NORMAL, busy timeout 5s y locks de instancia para transacciones.
  - **Límites de Fallo**: Sockets 4028 y HTTP REST Vnish con timeouts estrictos (5.0s y 2.5s) que nunca propagan excepciones al bucle principal.
* **Hoja de Ruta de Refactorización**:
  - Generado el informe formal de auditoría `AUDIT_REPORT_PROJECT_WIDE.md`.
  - Definidos Quick Wins (extracción de menús a `command_center.py`, rotación de logs), Mejoras a Medio Plazo (Specs 058-059: `app/telegram/commands/` y `app/network/cgminer_client.py`) y Refactor Estratégico (Spec 060: desacoplamiento Core Daemon vs Telegram Gateway con Dependency Injection).
* **Verificación y Pruebas**:
  - **902/902 tests PASS** en 13.9s.
  - Servicio Windows `MinerAlerts` reiniciado y verificado en ejecución activa (telemetría 100% nominal).

## [2026-09-15] - Spec 057: Intervention Governance & Adaptive Elevator Contingency (Completado)

* **Objetivo**: Implementar una gobernanza integral de intervenciones con modo global "Vnish Libre" accesible táctilmente desde Telegram Command Center (`/menu`), selectores granulares de actuadores (Reinicios L1/L2, Fan Governor, Balancer y Contingencia) con temporizadores de expiración segura (30m, 1h, 2h, 4h, indef), complementado con un plan de contingencia eléctrica asimétrica por elevador que mitiga las caídas de tensión matutinas actuando sobre el minero canario/sensible sin castigar al minero robusto y explorando los límites reales del sistema de potencia.
* **Diagnóstico Operativo y Evidencia Forense**:
  - Evidencia forense del 2026-09-14: 11 reinicios no solicitados entre las 05:27 y las 11:34 en los mineros 23, 24 y 25 (con alerta de cascada en Elevador 1 a las 10:14) causados por caídas externas de tensión de red e incompatibilidad transitoria con los autotransformadores elevadores. La telemetría previa fue 100% nominal (101.4 TH/s, 0 errores HW, 81°C).
  - En días con tensión de red estable (como hoy 2026-09-15), la flota opera sin perturbaciones. No procede un estrangulamiento ciego diario por horario.
  - La mitigación es asimétrica y relativa al estado actual: reducir únicamente el minero canario (Miner 24 en Elevador 1, Miner 25 en Elevador 2) en 1 escalón de potencia (ej. de 2700W a 2500W, o de 2500W a 2300W), dejando al minero compañero intacto.
  - La gobernanza de intervenciones garantiza que la telemetría, el guardado en SQLite, el watchdog y las alertas sigan operando al 100% mientras las mutaciones quedan bloqueadas.
* **Componentes y Cambios Implementados**:
  - `app/governance/intervention_policy.py`:
    - Dataclass inmutable `InterventionGovernance` con atributos para control maestro (`master_enabled`), reinicios (`reboots_enabled`), gobernador de ventiladores (`governor_enabled`), contingencia (`contingency_enabled`), preset balancer (`presets_enabled`), y temporizador de expiración monótono (`expires_at_ts`).
    - Función pura `should_allow_intervention(action_type, gov, now_ts)` con restauración automática por expiración de temporizador.
    - Función pura `apply_governance_toggle(gov, target, now_ts, duration_seconds)`.
    - Helper `format_governance_summary` para badges `🟢 ON`, `🟡 PARCIAL`, `🔴 LIBRE`.
  - `app/governance/adaptive_contingency.py`:
    - Mapeo declarativo de mineros canarios por grupo (`elevator_1` -> S19JPRO-24, `elevator_2` -> S19JPRO-25).
    - Funciones puras `find_previous_preset_tier` y `find_next_preset_tier` basadas en la escalera Vnish relativa al estado actual (piso 2100W, techo 2700W).
    - Motor de decisión determinista `evaluate_canary_contingency` con acciones `STEP_DOWN_CANARY`, `STEP_DOWN_LIMIT`, `STEP_DOWN_PARTNER`, `HOLD_CONTINGENCY`, `STEP_UP_SOAK`, `RESTORE_NOMINAL`.
    - Regla de Step-Up Soak: tras 2 horas (7200s) continuas sin reinicios en el grupo, rampa suave hacia el preset nominal.
  - `app/telegram/command_center.py`:
    - Incorporada 5ª fila en el menú principal `/menu`: `[ 🛡️ Intervenciones: 🟢 ON / 🔴 LIBRE ]`.
    - Submenú interactivo `render_interventions_menu` con botón maestro Vnish Libre, toggles individuales y temporizadores táctiles (30m, 1h, 2h, 4h, Indef).
    - Parser extendido para callbacks `cc:nav:interventions` y `cc:act:int_*`.
  - `app/miner_monitor.py`:
    - Interlocking de actuadores mutantes: Soft Auto-Restart L1 (`evaluate_auto_restart_candidate`), Hard Auto-Reboot L2 (`STATE_LOW` y `STATE_HASHBOARD`), Fan Governor (`execute_governor_cycle`), Preset Balancer (`execute_balancer_cycle`).
    - Despacho de callbacks táctiles en `_handle_command_center_callback` (`int_all`, `int_tog`, `int_tim`).
    - Comandos de texto rápidos en Telegram: `/interventions <status|on|off|30m|1h|2h|4h>` y `/contingency <status|reset>`.
    - Detección de expiración en bucle principal con reactivación automática de todas las intervenciones y alerta proactiva a Telegram.
    - Canalización de incidentes: ante reinicio inesperado en elevadores, evalúa contingencia asimétrica y aplica preset al minero objetivo.
    - Ciclo periódico de Step-Up Soak en bucle principal tras 2 horas de estabilidad.
    - Persistencia atómica de `intervention_governance` y `elevator_contingency` en `state.json`.
  - `tests/test_intervention_governance.py`:
    - 13 pruebas unitarias e integraciones de guardián de gobernanza, ruteo de layout y persistencia.
  - `tests/test_adaptive_contingency.py`:
    - 8 pruebas unitarias deterministas cubriendo casos canario, prueba en los límites, compañero robusto y step-up soak.
* **Verificación y Pruebas**:
  - **902/902 tests PASS** en 13.9s (+21 tests nuevos añadidos, cero regresiones).
  - Validación sintáctica completa con `py_compile` en todos los módulos modificados.

## [2026-09-13] - Spec 056: Two-Tier Mining Recovery (Auto-Restart vs Auto-Reboot) (Completado)

* **Objetivo**: Implementar una estrategia de recuperación escalonada de dos niveles que discrimine de forma segura y automática entre un **Auto-Reinicio de Minado por Software (Nivel 1)** y un **Auto-Reboot Completo de Hardware (Nivel 2)** cuando un minero detiene su hasheo (0.0 TH/s), pierde temporalmente sus placas (0/3 placas) o entra en estado detenido (`stopped`), previniendo caídas prolongadas sin desgastar innecesariamente la controladora ni reiniciar el sistema operativo Linux de la máquina.
* **Diagnóstico Forense de Causa Raíz**:
  - En incidentes como el del Minero 23 (`2026-09-13 09:35:06`), tras un error de cadena (`chain_break`), el firmware Vnish detuvo el proceso de minado `bmminer` pasando a `miner_state="stopped"` con 0/3 placas y 0.0 TH/s.
  - La única herramienta automática disponible hasta ahora era el hard reboot vía Hashcore CLI (`POST /api/v1/system/reboot` o script bat), el cual tarda entre 3 y 4 minutos, corta la energía de los chips, reinicia el sistema operativo Linux y causa oscilaciones en la red.
  - La API REST autenticada de Vnish expone `GET /api/v1/status` (que retorna `restart_required` y `reboot_required`) y `POST /api/v1/mining/restart`, permitiendo reiniciar exclusivamente el motor de minado de software en 15 a 20 segundos manteniendo el sistema operativo y la conectividad intactos.
* **Componentes y Cambios Implementados**:
  - `app/vnish/client.py`:
    - Implementadas `restart_mining` (con fallback de endpoints `/api/v1/mining/restart` y `/api/v1/mining/start`) y `safe_restart_mining` con desbloqueo y bloqueo transaccional.
    - Implementada `parse_miner_status_flags` para extraer limpiamente `miner_state`, `restart_required` y `reboot_required` de `/api/v1/status`.
  - `app/vnish/__init__.py`:
    - Exportadas las nuevas funciones en el paquete.
  - `app/miner_monitor.py`:
    - Incorporados campos `last_auto_restart_ts: Optional[float] = None` y `auto_restart_count: int = 0` en `@dataclass MinerState`, con serialización completa en `save_state` y `load_state`.
    - Nuevas claves de configuración: `auto_restart_mining_enabled` (default `True`), `auto_restart_cooldown_seconds` (default `300s`), `auto_restart_max_retries_before_reboot` (default `2`).
    - Implementada la función pura `evaluate_auto_restart_candidate(...)` con filtros para estados transitorios (`starting`, `init`, etc.), reboots de hardware requeridos, cooldown de software y límite de reintentos.
    - Creado worker asíncrono `_async_execute_mining_restart` para despachar el reinicio de software en background sin bloquear el ciclo de adquisición.
    - Canalización en el loop del monitor: si el minero se encuentra degradado y califica para Nivel 1, despacha el soft restart. Si los reintentos de Nivel 1 se agotan (`auto_restart_count >= 2`), cede limpiamente el control a la política de Nivel 2 (Spec 055 / Spec 008) tras transcurrir la ventana sostenida.
    - Notificaciones operativas de Telegram para Nivel 1: `[AUTO-RESTART] {name} hasheo detenido -> reinicio rápido de minado enviado (Nivel 1)`.
    - Reseteo automático de `auto_restart_count` ante recuperación a `STATE_OK` o tras la ejecución de un hard reboot manual/automático.
  - `app/config.example.json`:
    - Documentadas las claves de configuración de dos niveles y sus overrides para QA.
  - `tests/test_two_tier_recovery.py`:
    - 27 pruebas unitarias cubriendo endpoints REST, flags de firmware, lógica de decisión de Nivel 1, persistencia de estado y ciclo de vida de escalación a Nivel 2.
* **Verificación y Pruebas**:
  - **881/881 tests PASS** en 14.0s (27 tests nuevos añadidos, cero regresiones).
  - Validación sintáctica completa con `py_compile`.

* **Objetivo**: Proveer autorecuperación automática y segura ante pérdidas totales o severas de placas hash (`STATE_HASHBOARD`, 0/3 placas activas, 0.0 TH/s) tras caídas de cadena (`chain_break`) o desincronización de firmware, evitando que los mineros queden atrapados en bucles de inactividad de más de 7 horas sin reinicio.
* **Diagnóstico Forense de Causa Raíz**:
  - Durante el incidente del Minero 23 (`2026-09-13 00:38:17`), un `chain_break` en cadena 1 provocó que el firmware reiniciara y dejara 0 de 3 placas activas.
  - El monitor clasificó el estado como `STATE_HASHBOARD`. Sin embargo, la lógica histórica de auto-reboot (`Spec 008`) estaba restringida exclusivamente a `STATE_LOW`. En `STATE_HASHBOARD`, el monitor reseteaba `low_since_ts = None`, clasificando erróneamente al minero como `blocked_by=not_low`, impidiendo la evaluación del reinicio durante más de 7 horas continuas hasta la intervención humana.
* **Componentes y Cambios Implementados**:
  - `app/miner_monitor.py`:
    - Incorporado campo `hashboard_since_ts: Optional[float] = None` en `@dataclass MinerState`, con persistencia en `save_state` y reinicio seguro en `load_state`.
    - Claves de configuración agregadas con fallbacks seguros: `auto_reboot_hashboard_enabled` (default `True`), `auto_reboot_hashboard_sustained_seconds` (default `600s`), `auto_reboot_hashboard_partial_enabled` (default `False`).
    - Extendida la función pura `auto_reboot_signal_allows_evaluation` para soportar `STATE_HASHBOARD` (0/3 placas con temporizador activo) manteniendo compatibilidad 100% con `STATE_LOW`.
    - Creado helper `reset_sustained_hashboard_if_ineligible` para resetear el reloj ante recuperación o señales inválidas.
    - Canalización completa y dedicada de interlocks en el bucle principal de monitorización:
      1. Startup Guard (600s).
      2. Ventana sostenida (600s).
      3. Interlocks constitucionales (Thermal Guard 85°C, Fleet Incident Guard $\ge 2$ mineros, Firmware Transition Guard que resetea el reloj si hay cadenas en reinicio).
      4. Cooldown (1800s).
      5. Límite de ventana (3 reboots / 24h) y modo degradado.
      6. Ejecución controlada vía Hashcore CLI (`run_hashcore_cli`) y reseteo simultáneo de temporizadores `low_since_ts` y `hashboard_since_ts`.
    - Notificación Telegram especializada para recuperación de hashboard:
      `AUTO-REBOOT: {name} falla de placas (0/3) sostenida por 10 min -> reboot enviado\nDiagnostico: /why`.
    - Registro en `reboot_decisions` del `EventStore` con `trigger="hashboard_failure"` y `low_elapsed_seconds=600.0`.
  - `tests/test_hashboard_auto_reboot.py`:
    - 14 tests unitarios y de canalización cubriendo compatibilidad de señales, gates parciales vs totales, temporización monótona, preservación de los 6 interlocks y serialización de estado.
* **Verificación y Pruebas**:
  - **854/854 tests PASS** en 14.5s (14 nuevos tests añadidos, cero regresiones).
  - Cero violaciones de invariantes en `test_auto_reboot_signal_gate.py`, `test_reboot_safety.py` y `test_vnish_hashboard_detection.py`.

## [2026-09-12] - Release v4.1.2: Gradient-Adaptive Fan Step-Down & Fast Cool-Zone Dwell Optimization (Completado)

* **Objetivo**: Acelerar la convergencia térmica independiente de cada minero hacia el objetivo constitucional de 82.0°C cuando operan a máxima potencia (ej. 2700W) pero en temperaturas frías (ej. 72°C-76°C con ventiladores excesivos al 84%+), eliminando la lentitud del paso fijo (-2% cada 90s/120s) sin generar overshoot térmico al acercarse a la banda muerta.
* **Diagnóstico de Causa Raíz**:
  - El algoritmo de desescalado térmico en `app/governance/fan_governor.py` aplicaba un decremento plano y uniforme de `-2%` PWM sin importar la magnitud del margen térmico disponible (incluso estando 10°C por debajo del objetivo).
  - Adicionalmente, en `app/miner_monitor.py`, la acción `ACTION_HOLD_DWELL` incrementaba el contador `state.governor_holds`, lo que hacía que tras 3 ciclos de espera se activara prematuramente el dwell adaptativo penalizador de `120s`, ralentizando el desescalado a ~1% por minuto y demorando más de 20-25 minutos en estabilizarse.
* **Componentes y Cambios Implementados**:
  - `app/governance/fan_governor.py`:
    - **Régimen de Frío Profundo** ($T \le 76.0^\circ\text{C}$, $\Delta \ge 5.0^\circ\text{C}$): Paso ágil de **-5%** PWM por ciclo y dwell dinámico reducido a **60s** (cuando no está reteniendo banda muerta), reduciendo el tiempo de convergencia de 25 minutos a 4-5 minutos.
    - **Régimen de Frío Moderado** ($76.0^\circ\text{C} < T \le 78.5^\circ\text{C}$, $\Delta \ge 2.5^\circ\text{C}$): Paso intermedio de **-3%** PWM por ciclo con dwell estándar de **90s**.
    - **Zona de Aproximación Fina** ($78.5^\circ\text{C} < T < 81.0^\circ\text{C}$): Paso suave de aterrizaje de **-2%** PWM con dwell de **90s** para garantizar estabilidad absoluta y cero overshoot térmico al ingresar a la banda muerta $[81.0, 82.5]^\circ\text{C}$.
  - `app/miner_monitor.py`:
    - Corregida la actualización de `state.governor_holds`: ahora solo se incrementa ante `ACTION_HOLD_TARGET` (cuando el minero está efectivamente reteniendo la banda muerta objetivo), previniendo que `ACTION_HOLD_DWELL` infle el contador durante la fase de desescalado.
  - `tests/test_fan_governor.py`:
    - Incorporados 3 nuevos tests unitarios deterministas: `test_step_down_gradient_deep_cold`, `test_step_down_gradient_moderate_cold` y `test_step_down_gradient_fine_landing`.
  - `tests/test_fan_governor_concurrency.py`:
    - Actualizado test concurrente multi-minero (`test_individual_miner_reasoning_different_targets_and_temperatures`) para reflejar la reducción ágil de -5% en el Minero 26 en zona de frío profundo.
* **Verificación y Pruebas**:
  - **840/840 tests PASS** en 14.6s (3 nuevos tests añadidos, cero regresiones).
  - Validación de análisis térmico 100% independiente por minero certificada.

## [2026-09-12] - Release v4.1.1: Monitor Uptime Persistence Hardening & Sensor Diagnostic Accuracy Hotfix (Completado)

* **Objetivo**: Corregir la actualización de `state.last_elapsed` en el ciclo principal de monitoreo para evitar falsos incidentes recurrentes de reinicio, eliminar falsos positivos de errores I2C en cadenas inactivas/apagadas, y purgar eventos residuales en SQLite tras el arranque en producción.
* **Componentes y Cambios Implementados**:
  - `app/miner_monitor.py`: Incorporada la asignación `state.last_elapsed = elapsed` en cada ciclo cuando el minero responde, asegurando que `reboot_reason` solo se active una vez tras una caída de uptime y evitando el re-disparo recurrente cada 30 segundos.
  - `app/vnish/chains.py`: Refinada la métrica `sensors_error_count` en `from_api_dict` para no clasificar sensores en estado `"init"` o inactivos como errores de hardware cuando la cadena no está en producción (`mining`/`ok`).
  - `app/governance/chain_health.py`: Filtrado de sensores defectuosos en `assess_single_chain` para ignorar sensores no inicializados en cadenas en estado de falla o detenidas, y dinamización del diagnóstico en `build_chain_alert_card` (`Cadena fuera de servicio` vs `Falla de bus/sensor en placa` según el estado real).
  - `tests/test_state_resilience.py`: Añadido test determinista `test_state_last_elapsed_updates_preventing_loop` validando que `reboot_reason` no se re-dispare en el tick subsiguiente.
  - `tests/test_chain_health.py`: Añadido test `test_uninitialized_sensors_on_failure_chain_no_false_i2c_error` validando cero falsos positivos de I2C en placas inactivas.
  - Base de datos (`data/miner_alerts.db`): Purga de 108 registros espurios de `restart_detected` y 60 de `elevator_cascade_restart` generados por la falta de actualización del uptime.
* **Verificación y Pruebas**:
  - **837/837 tests PASS** en 14.5s (2 nuevos tests añadidos, cero regresiones).
  - Minero 25 recuperado y reanudado en minería activa (76+ TH/s en auto-tuning con 12/12 sensores midiendo normalmente).

## [2026-09-12] - Spec 054: Deep Hashboard Telemetry & Predictive Chain Break Diagnostics (Completado)

* **Objetivo**: Implementar la adquisición desacoplada, persistencia histórica en SQLite v7, diagnóstico predictivo de silicio e interfaz interactiva Mobile-First para la telemetría granular de hashboards expuesta por Vnish en `/api/v1/chains`, permitiendo detectar fallas en el bus I2C y sensores térmicos (p. ej. falla de sensor loc 28 en Minero 24) antes de que deriven en cortes de cadena físicos (`chain_break`) y reinicios abruptos de hardware.
* **Componentes y Cambios Implementados**:
  - **Fase 1 (Modelo de Datos y SQLite v7)**:
    - `app/vnish/chains.py`: Modelos `ChainSensor` y `ChainTelemetry` con cálculo de déficit de hashrate, temperaturas máximas por chip/placa, estado de salud y parseo de arrays `sensors` y `chips`.
    - `app/core/event_store.py`: Incremento a `SCHEMA_VERSION = 7` con tabla `chain_telemetry_samples` e índices optimizados (`ix_chain_telemetry_miner_time`, `ix_chain_telemetry_chain_error`, `ix_chain_telemetry_time`). Métodos de inserción por lotes y consulta en ventana.
  - **Fase 2 (Colector Asíncrono de Cadenas Vnish)**:
    - `app/vnish/chain_collector.py`: Funciones no bloqueantes `fetch_miner_chains` y `fetch_fleet_chains` con timeout estricto de 2.5s y ejecución en `ThreadPoolExecutor`.
    - `app/miner_monitor.py`: Hilo daemon programado `ChainTelemetryScheduled` cada 900s (15 min) y disparadores reactivos ante eventos de reinicio o transición hacia estados `HASHBOARD` o `LOW`.
  - **Fase 3 (Motor de Diagnóstico Predictivo y Aislamiento de Fallas)**:
    - `app/governance/chain_health.py`: Clasificación de salud por placa (`CHAIN_OK`, `CHAIN_SENSOR_ERROR`, `CHAIN_DEFICIT`, `CHAIN_FAULT`). Filtro de racha (mínimo 2 capturas) y cooldown (7200s) para alertas preventivas tempranas en Telegram.
    - `app/governance/preset_balancer.py` y `app/core/event_store.py`: Enriquecimiento automático de `record_elevator_restart_circumstance` y `operational_events` con la placa física culpable (`culprit_chain`) y su visualización en el detalle del incidente (`• Causa física: Cadena X`).
  - **Fase 4 (UX Telegram y Comando Interactivo `/chains`)**:
    - `app/telegram/command_center.py` y `app/telegram/fleet_cards.py`: Tarjetas Mobile-First con ancho visible `<= 32` columnas (`build_chains_card_text` y `build_chains_fleet_summary_text`), teclado interactivo de 1-tap `build_chains_keyboard` con navegación directa entre mineros, refresco en sitio y retorno al menú principal.
    - `app/miner_monitor.py`: Despacho del comando `/chains [minero]` y alias `/chain`, `/placas`, junto con manejo de callbacks `diag:chains:<id>` y `diag:ref:chains`.
    - `app/telegram/help_center.py`: Registro del comando `/chains` dentro de la categoría `diag`.
  - **Fase 5 (Herramienta Analítica de Historial)**:
    - `tools/analyze_chain_breaks.py`: CLI desacoplada para análisis forense y minería de datos históricos en SQLite. Calcula métricas de degradación de silicio, correlaciones con reinicios históricos y ofrece salida en tabla formateada y `--json`.
* **Verificación y Pruebas**:
  - `tests/test_chain_collector.py`, `tests/test_chain_health.py`, `tests/test_analyze_chain_breaks.py`, `tests/test_event_store.py`, `tests/test_fleet_cards.py`.
  - **835/835 tests PASS** al 100% en 13.63s (33 nuevos tests añadidos, cero regresiones).
  - Verificación exitosa en producción real contra `data/miner_alerts.db`: la herramienta analítica confirmó el 100% de errores de sensor I2C en la Cadena 2 del Minero 24 (loc 28) y salud óptima en los demás equipos.

## [2026-09-12] - Release v4.0.3: Fan Governor Minimum Floor 30% Hotfix & Spec 054 Predictive Diagnostics Planning (Completado)

* **Objetivo**: Corregir el piso mínimo de ventilación en el gobernador de ventiladores (`fan_governor.py`), que mantenía anclado al Minero 26 en 75% PWM cuando operaba a 79.0°C (por debajo del objetivo térmico de 82.0°C), permitir la modulación continua independiente de coolers hasta el piso físico del 30% PWM por equipo, y formalizar la especificación técnica completa (Spec 054) para la ingesta y análisis predictivo de fallas de hashboard (`chain_break`) basada en telemetría profunda de `/api/v1/chains`.
* **Diagnóstico de Causa Raíz (Minero 26 a 79°C anclado al 75% PWM)**:
  - En `app/governance/fan_governor.py`, la regla de desescalado térmico (R4) calcula `new_duty = max(config.min_fan_duty_percent, curr_duty - step)`.
  - El valor por defecto de `min_fan_duty_percent` en `GovernorConfig` estaba configurado en `75%`.
  - Cuando el Minero 26 registró 79.0°C (frío respecto a la banda muerta de 81.0°C–82.5°C), el gobernador intentó reducir ventilación (`75% - 2% = 73%`), pero la función `max(75, 73)` forzó nuevamente 75%, concluyendo `requires_write = False` y reteniendo el ciclo.
* **Fix Implementado en Gobernador y Monitor**:
  - `app/governance/fan_governor.py`: Se modificó el valor por defecto de `GovernorConfig.min_fan_duty_percent` de 75 a 30 (abarcando todo el rango físico permitido de modulación continua).
  - `app/miner_monitor.py`: Se actualizaron los fallbacks de configuración en línea 2548 y 5433 de 75 a 30.
  - `app/config.json` y `app/config.example.json`: Se actualizó `"fan_governor_min_duty_pct": 30`.
  - `tests/test_fan_governor.py`: Se adaptó `test_minimum_duty_floor` al nuevo piso del 30% y se añadió `test_minimum_duty_floor_custom` para verificar pisos configurables superiores (75%).
  - Todos los interlocks de seguridad (`EMERGENCY_SPIKE` a 83.5°C hacia 100% PWM y `STEP_UP` por encima de 82.5°C) permanecen 100% intactos.
* **Verificación Operativa en Vivo**:
  - Se reinició el servicio Windows `MinerAlerts` (`Restart-Service -Name MinerAlerts`).
  - En el primer tick de producción, el monitor registró:
    `[2026-09-12 20:42:32] [GOV] miner=S19JPRO-26 action=STEP_DOWN duty=73% target=73% holds=0 fails=0 pwr=2699/2700W`
  - Minero 26 redujo de inmediato sus ventiladores de 75% a 73% PWM buscando los 82.0°C, mientras que los otros mineros de la flota mantuvieron su autonomía absoluta (Minero 23 a 81%, Minero 24 a 88%, Minero 25 a 88%).
* **Planificación de Spec 054 (Predictive Chain Diagnostics)**:
  - Se redactó la especificación formal `specs/054-chain-break-predictive-diagnostics/spec.md`, el plan de arquitectura `plan.md` y el desglose de tareas `tasks.md` (T001 a T018 en 6 fases).
  - Se incorporó la propuesta formal `PROP-008` en `docs/proposals/SYSTEM_IMPROVEMENT_PROPOSALS.md`.
  - Se sincronizaron la hoja de ruta `docs/speckit/ROADMAP.md`, `SPEC_PROGRAM.md` y `DELIVERY_PLAN.md`.
* **Pruebas y Estado**:
  - **802/802 tests PASS** al 100% en 13.68s.
  - Servicio Windows en ejecución en vivo sin errores.

## [2026-09-12] - Fan Health False Positive Fix & Incident 940 Chain Break Diagnostic Discovery (Completado)

* **Objetivo**: Corregir el falso positivo de alarma mecánica de ventilador (`[VENTILADOR] 24 Falla mecánica de ventilador detectada`) emitido durante secuencias de reinicio/arranque del firmware Vnish, auditar otros evaluadores de salud preventiva y realizar una investigación técnica profunda sobre la causa raíz del `chain_break` en el minero 24 registrado a las 16:28:11, definiendo la estrategia de acumulación de datos para análisis predictivo.
* **Diagnóstico de Incidente en Producción (Evento 940 - 16:28 a 16:35)**:
  - **Reinicio del Minero 24**: A las `16:28:11`, Vnish registró en el minero 24: `S19JPRO-24 (miner) - chain/chain_break: Corte de cadena detectado` y `restart/miner_stopped: Proceso de minado detenido`. Su uptime cayó de 114.917s (~32h) a 1s.
  - **Aislamiento Respecto al Elevador 1**: El Minero 23 (peer en el mismo elevador 1) operó sin interrupciones, sosteniendo 2.698W continuos, 100 TH/s y 12.875 mV estables. El monitor registró `is_elevator_cascade: false` y carga total de 2.698W, descartando fluctuaciones globales en el elevador 1.
  - **Causa del Falso Positivo de Cooler (16:31:07)**: Durante el arranque del driver de minado (`firmware_initializing`), la API 4028 devolvió temporalmente `fan_rpm_max: None`. `assess_miner_cooling` en `app/governance/fan_health.py` evaluaba `has_missing_signal = "fan_signal_missing" in diagnostic_flags` sin comprobar si la máquina estaba realmente minando (`rate_ths > 0.0`), disparando inmediatamente una alerta crítica de falla mecánica de cooler y riesgo de sobrecalentamiento, a pesar de que los chips estaban fríos a 47°C y 30 segundos después los ventiladores giraban a 6.000 RPM al 100% PWM.
* **Fix Implementado en `app/governance/fan_health.py`**:
  - En `assess_miner_cooling`: se añadió verificación explícita de minado activo `is_hashing = rate_ths is not None and rate_ths > 0.0`. Si `not is_hashing`, la falta de señal de tacómetro o bajas RPM se clasifica como `STATUS_UNKNOWN` ("Equipo en arranque o sin carga de minado; telemetría no concluyente"), suprimiendo por completo la generación de alertas `STATUS_FAN_DEFECT` durante arranques, autotuning o paradas controladas.
  - Se confirmó que los demás evaluadores preventivos (`energy_efficiency.py` y `presets.py`) ya se encontraban blindados contra 0 TH/s.
* **Hallazgo Clave de Hardware en Minero 24 (Sonda `/api/v1/chains`)**:
  - Se realizó una sonda en caliente sobre las APIs REST de los 4 mineros.
  - Los mineros 23, 25 y 26 reportaron el 100% de sus sensores térmicos en estado `measure` en todas las cadenas (`[measure, measure, measure, measure]`).
  - **Exclusivamente el Minero 24 en la Cadena 2 (Board 2)** presenta un sensor en estado de error: `{'state': 'error', 'board': 39, 'chip': 54, 'loc': 28}`.
  - En el modelo Antminer S19j Pro, la posición 28 corresponde al sensor de temperatura I2C del chip 28 de la Hashboard 2. Las fallas intermitentes en la línea I2C de este sensor o soldaduras frías en ese sector de la placa provocan cuelgues en el bus de comunicación con la controladora PIC, siendo el disparador físico directo del `chain_break`.
* **Pruebas y Certificación**:
  - Se agregó `test_assess_miner_cooling_startup_no_false_fan_defect` en `tests/test_fan_health.py`.
  - **801/801 tests PASS** en 14.33s (0 errores, 0 fallos).
  - Servicio Windows `MinerAlerts` reiniciado y operativo en producción bajo PID 20460 / 25004.

## [2026-09-12] - Silent Mode / Modo Visitas: 30%–50% PWM Duty Range, 82°C Thermal Regulation & Elevator Autonomy (Completado)

* **Objetivo**: Modificar el Modo Silencio / Visitas (Spec 044) para acotar la modulación de ventilación al rango estricto de **30% a 50% PWM** (anteriormente 40%–70%), manteniendo la máxima potencia de minado posible mientras se sostiene la temperatura objetivo en **82.0°C**, y garantizando la autonomía operativa independiente por cada elevador y minero (p. ej. un minero estabilizado en 82°C con 50% de coolers y otro en 82°C con 30% de coolers con idéntico hashrate según su flujo térmico local).
* **Diagnóstico y Corrección de Limitadores Ocultos**:
  - **Inversión de Rangos en `execute_governor_cycle`**: Se corrigió `miner_gov_cfg.min_fan_duty_percent = max(_sm_min, miner_gov_cfg.min_fan_duty_percent)`. Debido a que el piso normal por defecto era 75%, el cálculo forzaba `min=75%` contra un `max=50%` acústico, impidiendo físicamente que los ventiladores modularan por debajo de 75%. Se fijó `min_fan_duty_percent = min(_sm_min, _sm_max)` (30%) y `max_fan_duty_percent = max(_sm_min, _sm_max)` (50%).
  - **Pinzamiento Hardware en Cliente Vnish**: En `app/vnish/client.py`, la función `set_manual_fan_duty` imponía un clamp estricto `clamped_duty = max(40, ...)`. Se actualizó a `max(30, ...)` permitiendo que las órdenes entre 30% y 39% PWM alcancen el hardware físico.
  - **Prioridad Térmica y Bucle de Recuperación en Silencio**: En `execute_governor_cycle`, `target_power_w` forzaba `ACTION_RECOVERY_MAX_COOLING` si la potencia estaba bajo el objetivo nominal, anclando los coolers al techo máximo (50%) e impidiendo la bajada a 30%. Se neutralizó `gov_target_pwr = None` durante modo silencio, permitiendo que el lazo cerrado regule exclusivamente por la banda muerta de temperatura (81.0°C – 82.5°C).
  - **Clamp Rápido Fuera de Rango**: En `app/governance/fan_governor.py`, se implementó detección reactiva de exceso sobre techo (`curr_duty > max_fan_duty_percent` -> `ACTION_STEP_DOWN` inmediato a techo sin esperar dwell) y piso (`curr_duty < min_fan_duty_percent` -> `ACTION_STEP_UP` inmediato a piso).
* **Configuración y UI**:
  - `app/config.json` y `app/config.example.json`: `silent_mode_min_duty_pct: 30`, `silent_mode_target_max_duty: 50`.
  - `app/miner_monitor.py`: Actualizados catálogos, comando `/silent` y vistas de Command Center a 30%–50% PWM.
  - `app/telegram/command_center.py` y `help_center.py`: Actualizados textos de ayuda y tarjetas interactivas de Telegram a 30%–50% PWM.
* **Pruebas y Verificación**:
  - Suite de pruebas ampliada a **800 tests PASS al 100%** (0 fallos, 0 errores) en 13.58s.
  - Se añadieron tests dedicados en `tests/test_silent_mode.py` (`TestSilentModeIndependentElevators`) validando independencia simultánea de mineros en elevador 1 y 2 a 82°C con 50% y 30% PWM respectivamente.
  - Servicio Windows `MinerAlerts` reiniciado y operativo en producción supervisando la flota sin incidencias.

## [2026-09-10] - Release v4.0.1: Post-Blackout Persistence Hardening & Concurrency Scope Hotfix (Completado)

* **Objetivo**: Diagnosticar, corregir y certificar la resiliencia operativa tras un corte de suministro eléctrico real (blackout), eliminando un `UnboundLocalError` en `main()` que causaba el bloqueo del servicio en estado `PAUSED` por el acelerador de reinicios de NSSM, blindando la persistencia de `state.json` mediante sincronización física `os.fsync()` contra corrupción de bloques nulos (`\x00`) en apagones abruptos, aislando las pruebas de callbacks de Telegram para no mutar el estado de producción, e incorporando una suite automatizada de resiliencia y verificación estática AST que eleva la cobertura a 797 tests PASS al 100%.
* **Diagnóstico de Incidente en Producción**:
  - Tras el restablecimiento eléctrico a las 21:41, el monitor emitió la notificación inicial de `STARTUP` pero crasheó en el primer tick por acceso no inicializado a `_ACTIVE_SCHEDULED_WINDOW` dentro de `main()`.
  - El bucle rápido de caídas provocó que NSSM pausara el servicio (`sc queryex MinerAlerts` -> `7 PAUSED`), impidiendo que el bot procesara comandos (`Status`) y disparando la alerta del watchdog externo (`tools/monitor_watchdog.py`) por estancamiento de heartbeat (`MONITOR SIN PROGRESO: service_stopped, tick_stale, telegram_poller_stale`).
  - Adicionalmente, el corte repentino dejó `app/state.json` con 9.075 bytes nulos (`\x00`) al no haberse forzado el volcado de la memoria intermedia del sistema operativo a almacenamiento físico.
* **Cumplimiento de Condiciones Técnicas Obligatorias**:
  - **C1 (Declaración Global y Cerrojo Reentrante en `main`)**: Declaración explícita de `global _ACTIVE_SCHEDULED_WINDOW` en `main()` y captura/actualización bajo `with state_lock:` eliminando el `UnboundLocalError` y previniendo colisiones con comandos concurrentes de Telegram.
  - **C2 (Persistencia Inmune a Apagones con `fsync` y Respaldo `.bak`)**: En `save_state()`, escritura con `f.flush()` y `os.fsync(f.fileno())` antes de `os.replace()`, junto a la creación automática de `state.json.bak`.
  - **C3 (Recuperación Automática de Estado Corrupto)**: En `load_state()`, detección de archivos vacíos o con secuencias de bytes nulos (`\x00`), recuperando automáticamente desde `state.json.bak` sin abortar ni corromper memoria.
  - **C4 (Aislamiento Total de Tests Unitarios)**: Refactorización de `test_telegram_callbacks.py` y `test_telegram_charts.py` para operar sobre `tempfile.TemporaryDirectory()`, evitando que la ejecución de pruebas sobreescriba el archivo de producción `app/state.json`.
  - **C5 (Suite de Resiliencia y Verificación AST)**: Creación de `tests/test_state_resilience.py` con 5 pruebas unitarias que validan la creación de `.bak`, recuperación ante corrupción por apagón y una auditoría AST sobre el 100% de funciones de `miner_monitor.py` asegurando cero variables de módulo no declaradas como globales.
* **Módulos y Cambios**:
  - `app/miner_monitor.py`:
    * Declaración `global _ACTIVE_SCHEDULED_WINDOW` en `main()`.
    * Envoltura con `state_lock` en lectura y actualización de ventanas programadas.
    * Persistencia segura con `os.fsync()` y respaldo `.bak` en `save_state()`.
    * Deserialización tolerante con fallback automático a `.bak` en `load_state()`.
  - `tests/test_telegram_callbacks.py` & `tests/test_telegram_charts.py`:
    * Uso de directorios temporales aislados en `setUp`/`tearDown`.
  - `tests/test_state_resilience.py`:
    * Nueva suite de 5 pruebas de resiliencia y verificación estática AST.
* **Resultados y Pruebas**:
  - Sintaxis: `py_compile` 100% PASS en monitor y suites de prueba.
  - Servicio de Producción: Restablecido y supervisando activamente en estado `4 RUNNING` (PID 6424).
  - Watchdog de Producción: `healthy=true`, notificación automática `MONITOR RECUPERADO` emitida en Telegram.
  - Flota ASIC: 4/4 mineros en estado `OK` reportando telemetría normal y fan governor regulando a 75°C.
  - Suite global completa: **797/797 tests PASS** en 13.02s (0 fallos, 0 errores, 0 regresiones).

## [2026-09-10] - Spec 053: V4 Core Governance Concurrency Hardening & Release Stabilization (Completado)

* **Objetivo**: Auditar, reforzar y certificar la estabilidad multihilo, la sincronización de estado compartido y la seguridad reentrante de cerrojos (`state_lock = threading.RLock()`) tras la incorporación de las 14 especificaciones del ciclo de Gobernanza Avanzada (Specs 039 a 052), garantizando la inmunidad contra colisiones en `save_state()`, verificando que el 100% de las tarjetas de Telegram del sistema cumplan estrictamente con el estándar Mobile-First (`visible_line_width <= 32`), y certificando el Release Candidate V4 (`v4.0.0`) con 792/792 tests PASS sin regresiones.
* **Cumplimiento de Condiciones Técnicas Obligatorias RFC**:
  - **C1 (Refuerzo de Cerrojos y Reentrancia Segura)**: Migración de `state_lock` a `threading.RLock()` en `miner_monitor.py`, eliminando riesgos de bloqueos recursivos o deadlocks cuando callbacks o funciones auxiliares invocan utilidades de persistencia.
  - **C2 (Aislamiento Atómico en `save_state`)**: Captura de referencias locales atómicas para `_ACTIVE_SCHEDULED_WINDOW` y clonación de listas mutables (`auto_reboot_timestamps`), evitando excepciones de mutación concurrente (`RuntimeError: dictionary changed size during iteration`) durante la serialización a disco.
  - **C3 (Certificación Master Mobile-First <= 32 Columnas)**: Verificación automatizada exhaustiva sobre el 100% de las líneas emitidas por todas las tarjetas móviles del sistema (estado, métricas, fans, presets, balancer, elevadores, digest, eventos, apagado de flota, purga, post-blackout, corte de fase y planificador de mantenimiento).
  - **C4 (Suite de Estrés y Concurrencia V4)**: Simulación de alta contención multihilo con 8 hilos concurrentes combinando mutaciones masivas de estado, serializaciones simultáneas a disco, evaluaciones temporales de ventanas y clasificación de fallas sin bloqueos ni excepciones.
  - **C5 (Certificación Global del Release V4)**: Ejecución de la suite completa de 792 pruebas unitarias y de integración en 13.398s con 100% de aprobación y cero regresiones.
* **Módulos y Cambios**:
  - `app/miner_monitor.py`:
    * Migración de `state_lock` a `threading.RLock()`.
    * Blindaje atómico en `save_state()` con copias desacopladas de estructuras de datos mutables.
  - `tests/test_mobile_compliance.py`:
    * Suite maestra de certificación visual con 7 casos de prueba verificando `visible_line_width(line) <= 32` en el 100% de las tarjetas móviles del sistema.
  - `tests/test_v4_concurrency.py`:
    * Suite de estrés multihilo con 4 casos de prueba validando contención en `save_state`, reentrancia de cerrojos, evaluaciones concurrentes de fase y ventanas de mantenimiento.
* **Resultados y Pruebas**:
  - Sintaxis: `py_compile` 100% PASS en todo el proyecto.
  - Suite de cumplimiento móvil: 7/7 tests PASS (0.004s).
  - Suite de concurrencia V4: 4/4 tests PASS (1.512s).
  - Suite global completa: **792/792 tests PASS** en 13.398s (0 fallos, 0 errores, 0 regresiones).

## [2026-09-10] - Spec 052: Scheduled Electrical Maintenance Windows & Soft Pre-Ramp (Completado)

* **Objetivo**: Planificar y ejecutar ventanas de mantenimiento eléctrico programadas (cortes de servicio eléctrico, limpieza de filtros, obras en tablero) permitiendo a los operadores definir horarios de parada anticipados, ejecutando una desescalada progresiva de carga (Soft Pre-Ramp a 2300W en T-10m y 2100W en T-5m) para minimizar el choque térmico y picos de sobretensión inductiva al desenergizar, apagando ordenadamente la flota en T-0 con purga activa de 45s a 100% de coolers, reposo a 40% PWM, auto-snooze por la duración de la ventana y confirmación Mobile-First interactiva.
* **Cumplimiento de Condiciones Técnicas Obligatorias RFC**:
  - **C1 (Mobile-First <= 32 Columnas)**: El 100% de las tarjetas (`render_schedule_confirmation_card`, `render_scheduled_status_card`, `render_pre_ramp_card`, `render_schedule_cancelled_card`) cumplen estrictamente con `visible_line_width(line) <= 32`.
  - **C2 (Parser Temporal Flexible y Robusto)**: Soporte intuitivo para sintaxis relativa (`in 30m`, `in 2h`, `+1h`) y absoluta (`14:30`, `YYYY-MM-DD HH:MM`) anclada a la hora local de Argentina (UTC-3), validando que la ventana esté al menos 5 minutos en el futuro y no exceda 30 días, con duración entre 15m y 24h.
  - **C3 (Pre-Rampa Escalonada de Carga)**: Transición automática sin intervención humana: a $T-10\text{m}$ aplica preset de 2300W (`PRE_RAMP_TIER_1`), y a $T-5\text{m}$ reduce a 2100W (`PRE_RAMP_TIER_2`) notificando a Telegram la desescalada preventiva.
  - **C4 (Secuencia Segura en T-0)**: Parada ordenada mediante `execute_parallel_shutdown`, disparo de rampa de purga activa al 100% de ventiladores durante 45s (Spec 049), caída suave al piso acústico de reposo (40% PWM) y activación de bandera `is_shutdown_maintenance = True` con silenciamiento de alarmas (`snooze_until_ts`) hasta el fin de la ventana programada.
  - **C5 (Cancelación en Caliente y Reconstitución de Estado)**: Botón interactivo 1-tap `[ ❌ Cancelar Ventana ]` en Telegram para anulación inmediata, con persistencia atómica en `state.json` que sobrevive a reinicios del servicio sin desfasar ni duplicar acciones.
  - **C6 (Trazabilidad en EventStore)**: Registro de auditoría `scheduled_shutdown_t0`, `scheduled_preramp` y `schedule_cancelled`.
* **Módulos y Cambios**:
  - `app/governance/maintenance_scheduler.py`:
    * Implementación del módulo de gobernanza con `ScheduledStage`, `ScheduledWindow`, `parse_duration_seconds`, `parse_schedule_expression`, `evaluate_window_stage`, `process_maintenance_scheduler_cycle` y generadores de tarjetas móviles `render_schedule_confirmation_card`, `render_scheduled_status_card`, `render_pre_ramp_card` y `render_schedule_cancelled_card`.
  - `app/governance/__init__.py`:
    * Exportación canónica de todas las estructuras y funciones del planificador de mantenimiento.
  - `app/miner_monitor.py`:
    * Whitelist de comandos ampliada: `/schedule_maintenance`, `/schedule`, `/programar`, `/scheduled`, `/programado`.
    * Serialización en `save_state` y reconstitución en `load_state` del estado `scheduled_maintenance`.
    * Handler de comandos Telegram para programar ventanas y consultar el estado actual con teclado interactivo inline.
    * Handler de callbacks `sch:cancel:<window_id>` para anulación en un clic.
    * Hook de ciclo de vida en bucle principal `process_maintenance_scheduler_cycle` evaluando transiciones temporales de forma periódica.
  - `tests/test_maintenance_scheduler.py`:
    * 11 pruebas unitarias cubriendo parsing de expresiones relativas y absolutas, validaciones de rango, cálculo de etapas, serialización/deserialización y ancho móvil estricto de $\le 32$ columnas.
  - `tests/test_maintenance_scheduler_integration.py`:
    * 3 pruebas de integración simulando la línea de tiempo completa ($T-10\text{m} \to T-5\text{m} \to T-0$), persistencia y recuperación ante reinicio, y anulación en caliente vía callback.
* **Resultados y Pruebas**:
  - Sintaxis: `py_compile` 100% PASS en `maintenance_scheduler.py`, `__init__.py`, `miner_monitor.py` y suites de prueba.
  - Suite completa: **781/781 tests PASS** en 10.934s (0 fallos, 0 errores, 0 regresiones).

## [2026-09-10] - Spec 051: Fast Phase Drop vs Connectivity Discriminator (Completado)

* **Objetivo**: Proveer clasificación heurística ultra-rápida (< 3 segundos) de caídas simultáneas de mineros para discriminar disparos de protecciones termomagnéticas por elevador o cortes generales de línea respecto a pérdidas de conectividad Ethernet local del host monitor (switch/router), suprimiendo la histeresis lenta habitual de 3 ticks (30 a 90s) y emitiendo inmediatamente una tarjeta ejecutiva Mobile-First en Telegram.
* **Cumplimiento de Condiciones Técnicas Obligatorias RFC**:
  - **C1 (Mobile-First <= 32 Columnas)**: El 100% de las tarjetas generadas (`render_phase_drop_alert` para corte de elevador, corte general y aislamiento de host) cumplen estrictamente con `visible_line_width(line) <= 32`.
  - **C2 (Alerta Instantánea < 3s & Supresión de Histeresis)**: Ante la caída unísona de $\ge 2$ mineros del mismo elevador o de la flota completa, el monitor no espera los 3 ticks habituales de `fails_before_alert`, marcando inmediatamente `OFFLINE` y encolando la tarjeta con prioridad `HIGH` (msg_type="ERROR").
  - **C3 (Autochequeo de Host y Cero Falsos Positivos)**: Verificación no bloqueante ($\le 500$ms) de la salud de red del host antes de declarar corte eléctrico. Si el host pierde acceso al gateway/red externa (`NETWORK_ISOLATION`), se suprime la falsa alarma eléctrica.
  - **C4 (Exclusión de Mantenimiento Intencional)**: Equipos bajo mantenimiento deliberado (Spec 048 `is_shutdown_maintenance`) o silenciamiento activo (Spec 033 `snooze_until_ts`) se excluyen del cálculo de caídas unísonas.
  - **C5 (Deduplicación & Cooldown Antispam)**: Cooldown configurable de 300s para evitar reenvío periódico de la tarjeta mientras la térmica continúe desenergizada, y deduplicación en el lote de notificaciones de episodios para evitar alertas redundantes.
  - **C6 (Trazabilidad en EventStore)**: Registro de eventos `electrical_phase_drop` con severidad `critical` y metadatos completos de grupos y mineros afectados.
* **Módulos y Cambios**:
  - `app/governance/phase_drop_discriminator.py`:
    * Implementación del módulo puro con `PhaseDropVerdict`, `PhaseDropAssessment`, `PhaseDropConfig`, `check_host_gateway_reachability`, `evaluate_phase_drop`, `parse_phase_drop_config`, `process_phase_drop_cycle` y `render_phase_drop_alert`.
  - `app/governance/__init__.py`:
    * Exportación canónica de todas las clases y funciones del discriminador de fase.
  - `app/miner_monitor.py`:
    * Inicialización de rastreador de caídas de fase y configuración.
    * Recolección por tick de fallos concurrentes y mineros en mantenimiento.
    * Hook de ciclo `process_phase_drop_cycle` ejecutado tras la adquisición, bypass de histeresis y filtrado de episodios redundantes en `episode_batch`.
  - `app/config.example.json`:
    * Documentación del bloque `phase_drop_discriminator` (`enabled`, `gateway_host`, `gateway_port`, `gateway_timeout_seconds`, `cooldown_seconds`).
  - `tests/test_phase_drop_discriminator.py`:
    * 12 pruebas unitarias cubriendo veredictos (`NORMAL`, `PHASE_DROP_ELEVATOR`, `PHASE_DROP_FLEET`, `NETWORK_ISOLATION`, `INDIVIDUAL_FAILURES`), chequeo de red, exclusión de mantenimiento y límite de 32 columnas.
  - `tests/test_phase_drop_integration.py`:
    * 6 pruebas de integración verificando bypass inmediato de histeresis, despacho Telegram, persistencia en EventStore, cooldown antispam, recuperación de circuito y deduplicación de episodios.
* **Resultados y Pruebas**:
  - Sintaxis: `py_compile` 100% OK en monitor, gobernanza y suites de tests.
  - Suite completa: **767/767 tests PASS** en 10.894s (0 fallos, 0 errores, 0 regresiones).

## [2026-09-10] - Spec 050: Guardián de Recuperación Post-Blackout (Completado)

* **Objetivo**: Detectar de forma proactiva mineros ASIC que, tras el retorno de tensión de un corte de energía o microcorte, inician con el sistema operativo activo pero con el minado detenido (`miner_state: "stopped"` o 0 TH/s persistente), ofreciendo una notificación interactiva en Telegram con botón táctil 1-tap `[ ▶️ Reanudar Flota ]` y auto-reanudación autónoma opcional con ventana de gracia.
* **Cumplimiento de Condiciones Técnicas Obligatorias RFC**:
  - **C1 (Mobile-First <= 32 Columnas)**: El 100% de las tarjetas (`render_post_blackout_alert`, `render_recovery_action_card`) cumplen `visible_line_width(line) <= 32`.
  - **C2 (No-Bloqueo del Monitor)**: La evaluación periódica opera en memoria O(1); la reanudación se ejecuta concurrentemente en paralelo vía `ThreadPoolExecutor`.
  - **C3 (Respeto a Mantenimiento y Snooze)**: Interlocks estrictos que suprimen alertas y auto-reanudaciones si los equipos se encuentran en mantenimiento intencional (Spec 048 `is_shutdown_maintenance`) o bajo silenciamiento activo (Spec 033 `snooze_until_ts`).
  - **C4 (Histeresis Antirruido)**: Requiere $\ge 2$ ciclos de sondeo consecutivos confirmados antes de disparar la alerta, descartando arranques transitorios (`starting`, `benchmarking`).
  - **C5 (Seguridad Térmica y Restauración de Coolers)**: La reanudación (`pbr:resume:*` o auto-resume) incluye la reactivación preventiva de los ventiladores al 100% de PWM para impedir calentamiento inicial con coolers en reposo.
  - **C6 (Trazabilidad en EventStore)**: Registro de eventos `post_blackout_alert`, `post_blackout_resume_manual` y `post_blackout_resume_auto`.
* **Módulos y Cambios**:
  - `app/governance/post_blackout_guard.py`:
    * Implementación del módulo puro con `PostBlackoutTarget`, `PostBlackoutTracker`, `evaluate_miner_post_blackout`, `render_post_blackout_alert`, `render_recovery_action_card`, `execute_post_blackout_cycle` y `process_post_blackout_callback`.
  - `app/governance/__init__.py`:
    * Exportación canónica de todas las clases y funciones del guardián.
  - `app/miner_monitor.py`:
    * Hook de ciclo periódico `execute_post_blackout_cycle` enlazado tras el balanceador de presets.
    * Enrutamiento de callbacks `pbr:*` en el dispatcher de Telegram llamando a `process_post_blackout_callback`.
  - `app/config.example.json`:
    * Documentación del bloque de configuración `post_blackout_guard` (`enabled`, `confirm_ticks`, `auto_resume`, `grace_period_seconds`, `max_chip_temp_c`).
  - `tests/test_post_blackout_guard.py`:
    * 18 pruebas unitarias cubriendo lógica pura, interlocks, formato móvil $\le 32$ cols, tracker y ciclo.
  - `tests/test_post_blackout_integration.py`:
    * 4 pruebas de integración extremo a extremo con mocks de Telegram y hardware.
* **Resultados y Pruebas**:
  - Sintaxis: `py_compile` 100% OK en monitor, gobernanza y tests.
  - Suite completa: **749/749 tests PASS** en 10.809s (0 fallos, 0 errores, 0 regresiones).

## [2026-09-10] - Spec 049: Rampa de Purga Térmica Activa y Contraste Acústico en Parada Segura (Completado)

* **Objetivo**: Optimizar el protocolo de apagado seguro de la granja (Spec 048) incorporando una rampa forzada de purga térmica al 100% de PWM durante los 45 segundos de enfriamiento (con potencia hash en 0W) y una caída instantánea al piso de reposo acústico (40% PWM / ~2.400 RPM, descendiendo a ~720 RPM en reposo sin carga) en el segundo 45 exacto, simultáneamente con la notificación Telegram `✅ ÁREA ELÉCTRICA SEGURA`.
* **Cumplimiento de Condiciones Técnicas Obligatorias RFC**:
  - **C1 (Mobile-First <= 32 Columnas)**: El 100% de las tarjetas móviles (`render_shutdown_in_progress`, `render_safe_area_card`) cumplen `visible_line_width(line) <= 32`.
  - **C2 (Pureza y No-Bloqueo del Monitor)**: La modulación de coolers se ejecuta mediante `ThreadPoolExecutor` desacoplado y en hilos daemon (`ShutdownPurgeNotify`) sin frenar el bucle principal de sondeo ni el polling de Telegram.
  - **C3 (Rampa Térmica Activa 100%)**: Aceleración inmediata de coolers a 100% en todos los mineros detenidos con éxito, maximizando el caudal de aire para barrer el calor latente de chips y disipadores de 65-80°C a <35°C.
  - **C4 (Contraste Acústico al Segundo 45)**: Desaceleración brusca de 6.000 RPM a piso de reposo (40% PWM), generando una señal física audible inconfundible para el operador ubicado frente al tablero eléctrico.
  - **C5 (Seguridad en Reanudación)**: `/resume` restaura automáticamente la ventilación activa preventiva antes del arranque de placas, impidiendo calentamiento inicial con coolers en reposo.
  - **C6 (Trazabilidad en EventStore)**: Registro de eventos `purge_fan_ramp` y `purge_idle_drop` con timestamp y estado en SQLite.
* **Módulos y Cambios**:
  - `app/governance/fleet_shutdown.py`:
    * Constantes `DEFAULT_PURGE_FAN_DUTY = 100` y `DEFAULT_IDLE_FAN_DUTY = 40`.
    * Función `execute_parallel_fan_duty(miners, duty_percent, password, timeout=2.5, fan_fn=None)`.
    * Tarjeta `render_shutdown_in_progress` actualizada: `• Purga: Rampa 100% activa` y `⏳ Barriendo calor (45s)`.
    * Tarjeta `render_safe_area_card` actualizada: `• Coolers: Reposo (40% PWM)` y `• Disipadores: Fríos (<35°C)`.
  - `app/governance/__init__.py`:
    * Exportación de `execute_parallel_fan_duty`, `DEFAULT_PURGE_FAN_DUTY` y `DEFAULT_IDLE_FAN_DUTY`.
  - `app/miner_monitor.py`:
    * `sd_cfm`: despacho de rampa al 100% en paralelo a los mineros detenidos con registro en `event_store`.
    * Hilo `ShutdownPurgeNotify`: tras 45s de sueño, despacho de caída a reposo al 40% en paralelo y envío de `render_safe_area_card`.
    * `resume`: reactivación de ventilación activa en mineros reanudados.
  - `tests/test_fleet_shutdown.py`:
    * Pruebas unitarias para `execute_parallel_fan_duty` (éxito, fallos parciales, lista vacía) y validación de ancho móvil $\le 32$ columnas.
  - `tests/test_safe_fleet_shutdown_integration.py`:
    * 2 nuevas pruebas de integración: `test_thermal_purge_ramp_and_acoustic_drop_integration` y `test_resume_restores_active_fan_duty`.
* **Resultados y Pruebas**:
  - Sintaxis: `py_compile` 100% OK en monitor, governance y tests.
  - Suite completa: **727/727 tests PASS** en 10.556s (0 fallos, 0 errores, 0 regresiones).

## [2026-09-10] - Fix: Telemetría en Vivo y Hashrate Total en Tarjeta /status (Estabilización)

* **Problema Resuelto**: El comando `/status` de Telegram no mostraba el hashrate individual de los mineros (`Hash: XX.X TH/s`), ni la potencia/eficiencia (`Pwr: XXXW (XX.X J/T)`), ni el hashrate total de la flota (`⚡ Total: 0.0 TH/s`). La tarjeta mostraba únicamente `Estado: OK` y `Temp: N/A | Fans: N/A` a pesar de que los equipos minaban a potencia nominal.
* **Causa Raíz**:
  - En la implementación de `render_fleet_status_card()` (Spec 046), el renderizador esperaba atributos `last_rate_ths`, `last_active_boards`, `last_max_chip_temp`, `last_fan_duty_percent`, `last_power_w` y `last_efficiency_j_th` en los objetos `MinerState`.
  - La clase `@dataclass MinerState` en `app/miner_monitor.py` no declaraba dichos campos y el bucle principal de monitoreo solo alimentaba variables del Fan Governor (`governor_last_power_w`, `governor_last_temp_c`), omitiendo persistir `rate_ths` y telemetría de placas en el estado del minero bajo `state_lock`.
  - Tampoco se serializaban ni deserializaban estos campos en `save_state()` ni `load_state()`.
* **Solución Implementada**:
  - `app/miner_monitor.py`:
    * Agregados los campos de telemetría a `@dataclass MinerState` con valores por defecto.
    * Bucle principal de monitoreo: bajo `state_lock`, se alimenta en cada tick `state.last_rate_ths`, `state.last_active_boards`, `state.last_expected_boards`, `state.last_max_chip_temp`, `state.last_fan_duty_percent`, `state.last_power_w` y `state.last_efficiency_j_th` calculada.
    * `save_state()` y `load_state()`: Serialización y deserialización atómica de los campos de telemetría en `state.json`.
    * Corrección de referencia a diccionario de estados en snapshot de métricas.
    * Corrección de bug crítico `_match_miner` en comandos individuales `/fans [miner]`, `/efficiency [miner]` y `/presets [miner]`: se reemplazó la función no declarada por `resolve_miner(target_arg, miners)` y acceso a propiedades canónicas `host/ip`.
  - `app/telegram/fleet_cards.py`:
    * Fallback resiliente a telemetría del Fan Governor (`governor_last_temp_c`, `governor_duty`, `governor_last_power_w`) y cálculo dinámico de eficiencia si no estaban inicializados.
  - `tests/test_fleet_cards.py`:
    * 2 nuevos tests unitarios: `test_status_card_with_real_miner_state_and_persistence` y `test_status_card_fallback_to_governor_telemetry`.
* **Resultados y Pruebas**:
  - Sintaxis: `py_compile app/miner_monitor.py app/telegram/fleet_cards.py` 100% OK.
  - Suite global completa: **723/723 tests PASS** en 10.824s (0 fallos, 0 errores).

## [2026-09-09] - Spec 048: Safe Fleet Shutdown & Multi-Select Maintenance Mode (Completado)

* **Objetivo**: Implementar un sistema de parada segura (*Apagado Seguro*) y modo de mantenimiento eléctrico desde Telegram, permitiendo desenergizar de forma selectiva (de 1 a 4 mineros o la granja completa) antes de realizar maniobras en la red eléctrica o tableros sin cortar la corriente en caliente ni generar arcos eléctricos o estrés térmico en componentes. Incluye selector táctil interactivo multiselección con casillas (`⬜`/`☑️`), confirmación en 2 pasos mediante token efímero de 60s, purga térmica activa (45s de ventiladores forzados para enfriar chips antes de habilitar el corte AC), auto-snooze de 4 horas para suprimir alarmas/reboots y reanudación limpia con auto-unsnooze.
* **Cumplimiento de Condiciones Técnicas Obligatorias RFC**:
  - **C1 (Límite Estricto Mobile-First <= 32 Columnas)**: El 100% de las tarjetas de confirmación, selector, en progreso, área eléctrica segura y reanudación cumplen `visible_line_width(line) <= 32`.
  - **C2 (Parada y Reanudación Segura de Hardware Vnish)**: Métodos `stop_mining()` (`POST /api/v1/mining/stop`) y `resume_mining()` (`POST /api/v1/mining/resume`) con transacciones HTTP y timeouts acotados.
  - **C3 (Purga Térmica Activa de 45 Segundos)**: Ventilación forzada de 45s tras el corte de carga hash (0W) para eliminar calor remanente antes del corte eléctrico, finalizando con la alerta "ÁREA ELÉCTRICA SEGURA".
  - **C4 (Selector Táctil Multiselección Determinista)**: Matriz de casillas con máscara compacta (`0000` $\leftrightarrow$ `1010`) en callbacks `<= 21` bytes (`cc:act:sd_tog:<id>:<mask >`), permitiendo marcar cualquier combinación en una sola pantalla sin chat spam.
  - **C5 (Confirmación en 2 Pasos con Token Criptográfico Efímero de 60s)**: Generación y consumo atómico en `CallbackTokenRegistry` para impedir ejecuciones accidentales.
  - **C6 (Auto-Snooze de Mantenimiento de 4 Horas)**: Supresión total de falsas alarmas `OFFLINE`/`LOW` y bloqueo estricto de autorreinicios durante la ventana de trabajo; auto-unsnooze automático en `/resume`.
  - **C7 (Interlocks de Protección & Armonización de Comandos)**: `/reboot` manual y auto-reboot bloquean reinicios sobre mineros detenidos; Fan Governor y Preset Balancer omiten mineros en parada; `/snoozed` y `/status` reflejan el estado con insignia `⏸️ DETENIDO (Mantenimiento)`; registro de `/shutdown` y `/resume` en el catálogo de `/help`.
* **Módulos y Cambios**:
  - `app/vnish/client.py` y `app/vnish/__init__.py`:
    * Implementación de `stop_mining()`, `resume_mining()`, `safe_stop_mining()` y `safe_resume_mining()`.
  - `app/governance/fleet_shutdown.py`:
    * Nuevo orquestador de parada con helpers de máscara de bits (`make_empty_bitmask`, `make_full_bitmask`, `toggle_selection_bitmask`, `resolve_selected_miners`).
    * Despachadores paralelos con `ThreadPoolExecutor` (`execute_parallel_shutdown`, `execute_parallel_resume`).
    * Renderizadores de tarjetas móviles (`render_shutdown_in_progress`, `render_safe_area_card`, `render_resume_success_card`, `render_shutdown_error_card`).
  - `app/governance/__init__.py`:
    * Exportación de todos los tipos y funciones de `fleet_shutdown`.
  - `app/telegram/command_center.py`:
    * Constantes `CC_NAV_SHUTDOWN`, `CC_NAV_RESUME`.
    * Parser de callbacks para `sd_tog`, `sd_req`, `sd_cfm`, `sd_ccl`, `sd_all`, `sd_clr`, `resume`.
    * Renderizadores `render_shutdown_menu()`, `render_shutdown_confirmation()`, `render_resume_menu()`.
    * Incorporación del botón táctil `[ 🛑 Parada Segura ]` en el dashboard principal.
  - `app/miner_monitor.py`:
    * Inclusión de `is_shutdown_maintenance: bool` y `shutdown_maintenance_ts: float` en `MinerState`, `load_state()` y `save_state()`.
    * Routing de callbacks de parada, confirmación, purga asíncrona en hilo daemon y reanudación.
    * Comandos de texto `/shutdown [args]`, `/stop`, `/apagar`, `/resume [args]`, `/reanudar`.
    * Guardas de seguridad en `/reboot` (single y bulk), `fan_governor` y `preset_balancer`.
  - `app/telegram/fleet_cards.py`:
    * Insignia `⏸️` para mineros en parada en `_miner_state_badge()`.
    * Líneas `Estado: ⏸️ DETENIDO` y `Modo: ⏸️ Parada Segura` en `render_fleet_status_card()`.
  - `app/telegram/snooze.py`:
    * Etiqueta `[⏸️ DETENIDO]` en `build_snooze_status_text()` para `/snoozed`.
  - `app/telegram/help_center.py`:
    * Registro canónico de `/shutdown` y `/resume` bajo la categoría `ctrl`.
  - Tests:
    * `tests/test_fleet_shutdown.py` (17 tests).
    * `tests/test_command_center.py` (22 tests).
    * `tests/test_safe_fleet_shutdown_integration.py` (13 tests).
* **Resultados y Pruebas**:
  - Compilación sintáctica: 100% OK (`miner_monitor.py`, `fleet_shutdown.py`, `command_center.py`, `fleet_cards.py`, `snooze.py`, `help_center.py`).
  - Suite global completa: **721/721 tests PASS** en 11.124s (0 fallos, 0 errores, +34 tests netos sobre baseline).
  - Servicio Windows `MinerAlerts` reiniciado y verificado operativo bajo PID `32436`.
  - **Prueba Operativa de Campo y Maniobra Eléctrica en Vivo**:
    * Ejecución real de `/shutdown` en los 4 mineros (`192.168.100.23` a `26`): Parada en paralelo en <1.2s, hashboards a 0W (0.0 TH/s), disipadores fríos (<45°C), ventiladores en piso mínimo de reposo de servidor (~720 RPM).
    * Entrega de tarjeta Telegram `✅ ÁREA ELÉCTRICA SEGURA` tras 45s de purga.
    * Apertura física de llave térmica en tablero general; Auto-Snooze de Mantenimiento de 4 horas retuvo alarmas y suprimió reboots.
    * Reanudación en caliente tras retorno de energía: `safe_resume_mining` en paralelo en 4/4 mineros, autotuning completado, retorno a presets nominales (2500W, 2700W, 2300W, 2300W), hashrates en 80-87 TH/s, chips en 46-56°C y notificación `▶️ MINADO REANUDADO` entregada.

## [2026-09-09] - Spec 047: Mobile-First Card Layout for Balancer, Digest & Operational Events (Completado)

* **Objetivo**: Completar la armonización Mobile-First de la interfaz de Telegram para los módulos de diagnóstico, gobernanza y soporte operativo restantes: Balanceador de presets y elevadores (`/balancer`, `/elevadores`), Reporte diario ejecutivo (`/digest`, `/summary`), Silencios de mantenimiento (`/snoozed`) e Historial de incidentes operacionales (`/events`, `/event <id>`, `/why`), garantizando renderizado determinista `<= 32` columnas visibles por línea, teclado inline de refresco en 1 toque (`[ 🔄 Actualizar ] [ 📱 Menú ]`), edición in-place sin spam y apego a las directivas RFC C1-C10.
* **Cumplimiento de Condiciones Técnicas Obligatorias RFC**:
  - **C1 (Límite Estricto Mobile-First <= 32 Columnas)**: El 100% de las líneas de texto generadas por todos los renderizadores modificados verifican de forma pura e incondicional `visible_line_width(line) <= 32` (verificado con suite unitaria dedicada). Todo texto extenso de diagnósticos, recomendaciones, motivos o evidencias se pagina con `wrap_mobile_lines`.
  - **C2 (Pureza de Renderizado)**: Renderizadores desacoplados de I/O, sockets o locks compartidos.
  - **C3 (Callbacks Aislados <= 64 Bytes & ACK < 50ms)**: Soporte completo para `diag:ref:balancer`, `diag:ref:elev`, `diag:ref:digest`, `diag:ref:events` en `parse_diagnostic_callback()` con ACK inmediato en `_handle_diagnostic_callback()`.
  - **C4 (Sin Paginación Rota)**: Reportes estructurados < 2,000 caracteres, muy inferiores al umbral de fragmentación de 3,600 caracteres.
  - **C5 (Sanitización Markdown)**: Uso de delimitadores móviles limpios (`•`, `─` * 28) y protección ante Markdown sin romper etiquetas.
  - **C6 (Fallback Equivalente de Entrega)**: Mensajes 100% legibles y completos tanto con inline markups como en clientes estándar.
  - **C7 (Límites Constitucionales y Seguridad)**: Cero cambios en la máquina de estados (`MinerState`), algoritmos matemáticos del balanceador, límites de temperatura ni loop de monitoreo.
* **Módulos y Cambios**:
  - `app/governance/preset_balancer.py`:
    * Refactorización de `build_balancer_table_text()` a tarjetas verticales agrupadas por elevador con viñetas `•`, carga agregada y wrapping de motivos.
    * Refactorización de `build_miner_balancer_detail_text()` a tarjeta diagnóstica vertical por minero.
    * Refactorización de `build_elevator_sensitivity_text()` a tarjetas de sensibilidad eléctrica verticalizadas con wrapping de recomendaciones.
  - `app/telegram/daily_digest.py`:
    * Refactorización de `format_daily_digest()` a bloques verticales alineados con resumen de flota, hashrate, eficiencia, shares y backup.
  - `app/telegram/snooze.py`:
    * Refactorización de `build_snooze_status_text()` a fichas por minero silenciado con cálculo de tiempo restante en `<= 32` columnas.
  - `app/core/event_store.py`:
    * Refactorización de `render_event_list()` a listado vertical compacto con identificador click-safe `/e<id>`.
    * Refactorización de `render_event_detail()` a ficha de incidente con wrapping de resumen y eventos relacionados.
    * Refactorización de `render_reboot_decision()` con bloques verticales para decisiones de auto-reboot, interlocks térmicos, de flota y transiciones de firmware.
  - `app/telegram/fleet_cards.py`:
    * Incorporación de constantes `DIAG_REF_BALANCER`, `DIAG_REF_ELEV`, `DIAG_REF_DIGEST`, `DIAG_REF_EVENTS`.
    * Ampliación de `SUPPORTED_REPORT_TYPES` y soporte en `build_diagnostic_keyboard()`.
  - `app/miner_monitor.py`:
    * Integración de `_handle_diagnostic_callback()` para los nuevos reportes diagnósticos (`balancer`, `elev`, `digest`, `events`) con pase de `event_store`.
    * Inclusión de `reply_markup` con botonera interactiva en los dispatchers de `/balancer`, `/elevadores`, `/digest` y `/events`.
  - `tests/test_mobile_diagnostics.py`: Suite dedicada de 8 pruebas unitarias validando límite estricto `<= 32` columnas en todas las funciones y casos edge.
  - `tests/test_telegram_callbacks.py`: 4 nuevas pruebas de integración cubriendo el despacho y edición in-place de los nuevos callbacks.
* **Resultados y Pruebas**:
  - Compilación sintáctica: 100% OK (`miner_monitor.py`, `preset_balancer.py`, `daily_digest.py`, `snooze.py`, `event_store.py`).
  - Suite global completa: **687/687 tests PASS** en 11.281s (0 fallos, 0 errores, +12 tests netos sobre baseline).
  - Auditoría de liberación: **PASS** (`tools/release_audit.py --check-only`), digest `7ba53dcea43ada9ae59d1593a08de897750aba8f9d8ccea17e8fe2c4fefa441d`, 63 payload files, 8/8 terminal dispositions verificadas.

## [2026-09-09] - Spec 046: Mobile-First Card Layout & UX Harmonization across Fleet Reports (Completado)

* **Objetivo**: Estandarizar la presentación de reportes diagnósticos y de flota para dispositivos móviles en Telegram, rediseñando los comandos `/status`, `/fans`, `/efficiency` y `/presets` a un formato de tarjeta vertical con viñetas (`•`), ancho estricto `<= 32` columnas visibles por línea, teclado inline de refresco en 1 toque (`[ 🔄 Actualizar ] [ 📱 Menú ]`), edición in-place sin spam y protección contra overflow o fragmentación rota de mensajes (RFC C1-C10).
* **Cumplimiento de Condiciones Técnicas Obligatorias RFC**:
  - **C1 (Límite Estricto Mobile-First <= 32 Columnas)**: Todas las tarjetas y líneas de datos de `/status`, `/fans`, `/efficiency` y `/presets` verifican `<= 32` caracteres visibles limpios (validado tras filtrar tags Markdown mediante `strip_markdown()`). Los listados de advertencias y alertas por minero se formatean en viñetas verticales para impedir rupturas de línea antiestéticas en pantallas pequeñas.
  - **C2 (Pureza de Renderizado)**: Renderizadores desacoplados y deterministas (`render_fleet_status_card`, `build_fans_table_text`, `build_efficiency_table_text`, `build_presets_table_text`) libres de dependencias de red, sockets, SQLite o locks compartidos.
  - **C3 (Callbacks Aislados <= 64 Bytes & ACK < 50ms)**: Parser `parse_diagnostic_callback` con validación estricta `<= 64` bytes UTF-8 (`diag:ref:status`, `diag:ref:fans`, `diag:ref:eff`, `diag:ref:presets`). Despacho inmediato de `answer_callback_query` antes de procesar o editar el mensaje para despejar el spinner táctil en Telegram.
  - **C4 (Sin Paginación Rota)**: Reportes estructurados con longitud total inferior a 1,500 caracteres, muy por debajo de la ventana de seguridad de Telegram (3,600 caracteres).
  - **C5 (Sanitización Markdown)**: Uso de `escape_markdown()` para proteger nombres de mineros, estados y métricas operativas.
  - **C6 (Fallback Equivalente de Entrega)**: Preservación completa de información diagnóstica tanto con botones interactivos como en clientes que no soportan inline markups.
  - **C7 (Límites Constitucionales y Seguridad)**: Cero alteraciones en la máquina de estados (`MinerState`), políticas de autorreinicio, gobernanza de temperatura (`execute_governor_cycle`), CLI de Hashcore ni loop de monitoreo.
* **Módulos y Cambios**:
  - `app/telegram/fleet_cards.py`: Nuevo módulo dedicado con `render_fleet_status_card()`, constructores de teclados `build_diagnostic_keyboard()`, parser `parse_diagnostic_callback()` y constantes `DIAG_PREFIX = "diag:"`.
  - `app/governance/fan_health.py`: Refactorización de `build_fans_table_text()` reemplazando la tabla tabular de 86 columnas por bloques verticales limpios con viñetas `•`, modo de ventilador explícito (`• Modo: [MANUAL]`), semáforos Unicode y recomendaciones térmicas.
  - `app/governance/energy_efficiency.py`: Refactorización de `build_efficiency_table_text()` a tarjetas verticales por minero con viñetas `•`, consumo en W/kW, ratio J/TH y resumen global de flota.
  - `app/vnish/presets.py`: Refactorización de `build_presets_table_text()` a tarjetas verticales por minero con perfil inferido, frecuencia MHz, tensión mV y advertencias en viñetas.
  - `app/miner_monitor.py`:
    * Conexión del router `_handle_diagnostic_callback()` en `_handle_callback_query()` con ACK temprano e in-place update mediante `edit_message_text(..., parse_mode="Markdown")`.
    * Sustitución del texto crudo de snapshot en `/status` por `render_fleet_status_card()` con teclado interactivo de refresco y retorno.
    * Incorporación de botoneras inline `build_diagnostic_keyboard()` en `/fans`, `/efficiency` y `/presets`.
  - `app/telegram/__init__.py`: Exportación canónica de `fleet_cards`.
  - `tests/test_fleet_cards.py`: 9 pruebas unitarias exhaustivas validando ancho `<= 32` columnas, longitud total, tolerancia a datos ausentes/nulos y formato de callbacks.
  - `tests/test_telegram_callbacks.py`: 6 nuevas pruebas de integración en `TestDiagnosticCallbacksIntegration` cubriendo `diag:ref:status`, `diag:ref:fans`, `diag:ref:eff`, `diag:ref:presets`, rechazo a no autorizados y rechazo de payloads corruptos.
* **Resultados y Pruebas**:
  - Compilación sintáctica: 100% OK (`miner_monitor.py` y `miner_diagnostics.py`).
  - Suite completa del repositorio: **675/675 tests PASS** en 10.69s (0 fallos, 0 errores, +15 tests netos sobre baseline).
  - Auditoría de liberación: **PASS** (`tools/release_audit.py --check-only`), digest `57cc9185739a9685bb4d5f013298233dcf074aa00bea03c1441492a6710706ea`, 63 payload files.



* **Objetivo**: Diseñar, implementar e integrar el Centro de Ayuda Mobile-First para Telegram, incorporando navegación interactiva por categorías temáticas en 1-2 toques, tarjetas verticales acotadas a `<= 32` columnas visibles, registro canónico exhaustivo de comandos del dispatcher (incluyendo `/menu` y `/silent` con sus aliases), protocolo de callbacks `help:` acotado a 64 bytes UTF-8 y fallback de entrega segura de markups según las condiciones C1-C10 del RFC `RFC_TELEGRAM_MOBILE_UX_OPTIMIZATION.md`.
* **Cumplimiento de Condiciones Técnicas Obligatorias RFC**:
  - **C1 (Contrato Mobile-First)**: Todas las tarjetas y vistas (`render_help_home`, `render_help_category`, `render_help_command_detail`) garantizan líneas de datos `<= 32` caracteres visibles, verificadas tras despojar etiquetas Markdown con `strip_markdown`.
  - **C2 (Registro Canónico Único)**: Centralización en `HELP_COMMANDS` y `HELP_CATEGORIES` dentro de `app/telegram/help_center.py` cubriendo los 28 comandos reales del sistema e incorporando `/menu` (aliases `start`, `panel`) y `/silent` (aliases `silencio`, `modo_silencio`).
  - **C3 (Callbacks Aislados <= 64 Bytes & ACK Temprano)**: Parser `parse_help_callback` con gramática cerrada (`help:nav:home`, `help:cat:<id>`, `help:cmd:<name>`) y validación estricta de longitud UTF-8 `<= 64` bytes. `_handle_help_callback()` despacha `answer_callback_query` inmediato (<50ms) antes de generar la vista o editar el mensaje.
  - **C4 (Paginación sin Particionado Roto)**: Vistas interactivas completas < 1,500 caracteres, muy por debajo del límite de 3,600 caracteres, evitando el paso por `split_telegram_message()` para proteger tags Markdown.
  - **C5 (Sanitización Markdown)**: Funciones `escape_markdown` y `strip_markdown` para blindaje ante caracteres hostiles (`*`, `_`, `` ` ``, `[`).
  - **C6 (Fallback Equivalente de Entrega)**: `_send_telegram_direct()` y `send_telegram()` preservan `reply_markup` en el último fragmento cuando la cola no está disponible (`_TELEGRAM_QUEUE is None`) o ante bypass de cola.
  - **C7 (Límites de Seguridad)**: Cero modificaciones a la máquina de estados, bucle de monitoreo, auto-reboot o workers concurrentes.
* **Módulos y Cambios**:
  - `app/telegram/help_center.py`: Módulo puro determinista con catálogo de 28 comandos, 5 categorías operativas (`mon`, `thm`, `pwr`, `ctrl`, `diag`), renderizadores visuales (`render_help_home`, `render_help_category`, `render_help_command_detail`), utilidades de ajuste móvil (`wrap_mobile_lines`) y fallbacks legacy (`render_legacy_help_index`, `render_legacy_help_detail`).
  - `app/telegram/command_center.py`: Cableado de botón `[ 📖 Centro de Ayuda ]` (`help:nav:home`) en fila 4 de `render_main_dashboard()`, habilitando navegación bidireccional Command Center <-> Help Center.
  - `app/miner_monitor.py`:
    * Handler `_handle_help_callback()` con ACK temprano e in-place update mediante `edit_message_text(..., parse_mode="Markdown")`.
    * Router de callbacks en `_handle_callback_query()` enrutando `help:` con RBAC estricto.
    * Dispatcher `/help` conectando a `render_help_home()` y `render_help_command_detail()`.
    * Enriquecimiento de `/info <cmd>` para desplegar detalle táctil interactivo en lugar de buscar minero inexistente.
    * Registro de `/menu` y `/silent` en `_COMMANDS` y `CMD_WHITELIST`.
    * Preservación de `reply_markup` en `_send_telegram_direct()`.
  - `app/telegram/__init__.py`: Exportación canónica de constantes, modelos y funciones del Help Center.
  - `specs/045-telegram-mobile-help-center/`: Especificación completa con `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/help-center-api.md`, `quickstart.md`, `tasks.md`, `checklists/requirements.md` y `evidence.md`.
* **Resultados y Pruebas**:
  - Compilación sintáctica: 100% OK (`py_compile`).
  - Tests unitarios y de integración:
    * 29 tests en `tests/test_help_center.py` (0.006s).
    * 5 tests de integración de callbacks en `tests/test_telegram_callbacks.py`.
    * 1 test de fallback de `reply_markup` en `tests/test_telegram_messaging.py`.
    * 18 tests en `tests/test_command_center.py`.
  - Suite completa del repositorio: **660/660 tests PASS** en 10.56s (0 fallos, 0 regresiones).
  - Release audit: **PASS** (`tools/release_audit.py --check-only`), digest `4c1d77311f67049c1ece885108210e2e8626e7bd05833d5360ec0bb06bf41851`, 62 payload files.


## [2026-09-08] - Spec 044: Modo Silencio Inteligente con Temporizador Persistente y Thermal Guard

* **Objetivo**: Implementar el "Modo Silencio / Visitas" para limitar acústicamente los ventiladores al 40%–70% PWM manteniendo la operación segura bajo 82°C, con temporizadores persistentes configurables (30m, 1h, 2h, 4h, 6h, indefinido), reversión automática al régimen normal, control táctil desde el Command Center (`/menu`) y anulación de emergencia atómica por Guardián Térmico (`EMERGENCY_SPIKE` / `FAILSAFE_FAULT`).
* **Cumplimiento de Condiciones Constitucionales P0 (Auditoría Claude Sonnet 4.6)**:
  - **C1 (Concurrencia No Bloqueante)**: El hilo de Telegram Polling solo actualiza `MinerState` en memoria y persiste con `save_state()` bajo `state_lock`. Las órdenes físicas de ventilación se despachan de forma asíncrona y gradual a través del ciclo del Fan Governor, garantizando respuesta táctil inmediata (<500ms) sin bloqueos de red.
  - **C2 (Aislamiento FSM y Reconciliación en Arranque)**: Nuevos campos dedicados en `MinerState` (`silent_mode_active`, `silent_mode_revert_ts`, `silent_mode_prev_duty`, `silent_mode_prev_preset`, `silent_mode_target_max_duty`) completamente aislados de `snooze_until_ts`. En `first_tick` tras reinicio de Windows/NSSM, se purgan silencios vencidos durante el downtime y se notifica a Telegram.
  - **C3 (Coexistencia con Fan Governor)**: Inyección dinámica de `max_fan_duty_percent` en `execute_governor_cycle` cuando el modo silencio está activo, permitiendo que el gobernador trabaje acotado en la ventana acústica permitida sin competir con ella.
  - **C4 (Guardián Térmico y Desactivación Atómica)**: Ante `EMERGENCY_SPIKE` (83.5°C) o `FAILSAFE_FAULT`, se anula atómicamente el modo silencio bajo `state_lock`, se persiste de inmediato a disco con `save_state()`, se fuerzan los ventiladores al 100% PWM y se despacha alerta prioritaria a Telegram.
* **Módulos y Cambios**:
  - `app/config.example.json`: Añadidos parámetros `silent_mode_target_max_duty: 70` y `silent_mode_min_duty_pct: 40`.
  - `app/miner_monitor.py`:
    * `MinerState`: Campos dedicados de estado y soporte en serialización/deserialización `load_state`/`save_state`.
    * Startup / `first_tick`: Reconciliación y purga de silencios expirados con notificación Telegram.
    * Loop principal: Chequeo de vencimiento de temporizadores por tick y notificación de reversión.
    * Integración Fan Governor: Inyección de límites dinámicos y captura de anulaciones por Thermal Guard.
    * Telegram Commands & Callbacks: Comando `/silent [30m|1h|2h|4h|6h|indef|off]` y botones interactivos en Command Center (`cc:nav:silent`, `cc:act:silent:*`).
  - `app/telegram/command_center.py`: Función `render_silent_mode_view` con selector táctil de duraciones, botón dinámico `[ 🔇 Modo Silencio ]` / `[ 🔊 Desactivar Silencio ]` en dashboard principal.
  - `app/telegram/__init__.py`: Exportaciones canónicas de `CC_NAV_SILENT` y `render_silent_mode_view`.
* **Resultados y Certificación**:
  - Compilación sintáctica: 100% OK (`py_compile`).
  - Tests unitarios: 17 nuevos tests creados en `tests/test_silent_mode.py` y 2 tests en `tests/test_command_center.py` (total 34 tests específicos).
  - Suite completa: **621/621 tests PASS** en 10.95s (0 fallos, 0 regresiones).
  - Release audit: **PASS** (`tools/release_audit.py --check-only`), digest `7d59e841532e752d9281dd0e491a60cb2f8d7b0dcc8feebe903e4b655320ad1f`, 61 payload files.

## [2026-09-08] - Spec 043: Telegram Interactive Command Center & Rich UI

* **Objetivo**: Implementar el centro de comando táctil `/menu` con teclados inline interactivos (`InlineKeyboardMarkup`), navegación in-place de submenús (`editMessageText`), semáforos, barras de estado y botones contextuales de acción rápida para incidentes y alertas con confirmación en dos toques.
* **Módulos y Cambios**:
  - `app/telegram/command_center.py`: Módulo puro para renderizado del Command Center, barras de progreso Unicode `[██████░░]`, submenús de Métricas, Reinicios, Presets y Alertas.
  - `app/telegram/__init__.py`: Exportaciones canónicas de builders y constantes del Command Center.
  - `app/miner_monitor.py`:
    * Implementación de `edit_message_text()` con captura de excepciones y supresión de `Message is not modified`.
    * Despacho inmediato de `answerCallbackQuery` (< 500ms) para retroalimentación táctil instantánea.
    * Handler `_handle_command_center_callback` conectado al router de callbacks con prefijo `cc:`.
    * Enrutamiento de comandos `/menu`, `/start`, `/panel` para desplegar el dashboard táctil.
    * Control de seguridad RBAC (`from_id == chat_id`) rechazando usuarios no autorizados con modal de advertencia.
* **Resultados y Certificación**:
  - Compilación sintáctica: 100% OK (`py_compile app\telegram\command_center.py app\miner_monitor.py`).
  - Tests unitarios: 15 nuevos tests creados en `tests/test_command_center.py` pasando en 0.005s.
  - Suite de tests completa: **602/602 tests PASS** en 10.99s (0 fallos, 0 regresiones).
  - Release audit: **PASS** (`tools/release_audit.py --check-only`), digest `b25b7807ec7e1dd2e0265c1c1925ea96ffa8742c43fad9172f257469912da781`, 61 payload files.
  - Servicio en producción ininterrumpido.

## [2026-09-08] - Auditoría Arquitectónica Formal del RFC: Telegram Interactive Command Center

* **Objetivo**: Auditar `docs/speckit/RFC_TELEGRAM_INTERACTIVE_CONTROL.md` (propuesta de Centro de Control Táctil, Modo Silencio con Temporizador y Safety Thermal Guard) antes de iniciar su implementación como Specs 043-044.
* **Auditor**: Claude Sonnet 4.6 (Thinking). Baseline auditado: V3.0.0 post-Spec 042 (587/587 tests PASS).
* **Código inspeccionado**: `app/miner_monitor.py`, `app/telegram/callbacks.py`, `app/telegram/snooze.py`, `app/governance/fan_governor.py`, `app/vnish/client.py`.
* **Veredicto**: RFC APROBADO con 4 condiciones obligatorias de implementación (C1-C4):
  - **C1 (Concurrencia)**: Callbacks de botones que disparan escrituras a VNish deben usar `ThreadPoolExecutor + shutdown(wait=False)` desacoplado del hilo de polling, reutilizando el patrón de `execute_governor_cycle`. El hilo de polling solo: parsea, autentica, responde `answerCallbackQuery`, encola acción.
  - **C2 (Persistencia de Temporizador)**: `MinerState` debe tener campos `silent_mode_active`, `silent_mode_revert_ts`, `silent_mode_prev_duty`, `silent_mode_prev_freq_mhz` separados del snooze existente. Verificación explícita en primer tick ante reinicio del servicio NSSM.
  - **C3 (Race Condition Governor vs. Modo Silencio)**: `GovernorConfig` debe recibir `min/max_fan_duty_percent` dinámicos del estado del Modo Silencio de cada minero, para que Governor y Modo Silencio cooperen en lugar de competir sobre el mismo actuador PWM.
  - **C4 (Thermal Guard)**: `EMERGENCY_SPIKE` y `FAILSAFE_FAULT` del Governor deben desactivar `silent_mode_active = False` bajo `state_lock`, persistiendo estado consistente ante reinicios. Notificación Telegram inmediata de anulación.
* **Hallazgos adicionales**:
  - Snooze existente (inhibición de alertas) y Modo Silencio (limitación física de hardware) son FSM distintas que no deben mezclarse.
  - Persistir `prev_duty` y `prev_freq_mhz` además del nombre del perfil VNish como fallback de restauración.
  - Verificar disponibilidad real del endpoint `/api/v1/profile` en Vnish 1.2.7-1.2.9 antes de diseñar Spec 044.
  - Numeración corregida: nuevas specs serán 043 (Inline Keyboards) y 044 (Modo Silencio + Thermal Guard).
* **Artefacto**: `docs/speckit/RFC_TELEGRAM_INTERACTIVE_CONTROL.md` §6 completado con auditoría formal.
* **Próximo paso**: Gemini 3.8 Flash High crea specs/043 y specs/044 usando el RFC auditado como contrato de diseño.

## [2026-09-08] - Spec 042: Purga Limpia de Shims y Modernización de Tests en `app/`

* **Objetivo**: Completar el ordenamiento arquitectónico integral de `app/` alcanzando la máxima pulcritud posible: eliminación definitiva de los 22 archivos shims/fachadas planos sueltos en la raíz de `app/` tras la modernización directa de toda la suite de tests en `tests/` para importar exclusivamente de los 4 subpaquetes de dominio (`app.core`, `app.vnish`, `app.governance`, `app.telegram`), dejando en `app/` únicamente el orquestador raíz `miner_monitor.py` y el inicializador de paquete `__init__.py` junto con los archivos locales de runtime.
* **Acciones Ejecutadas por Fases**:
  1. **Fase 2 - Dominio Telegram**:
     - Modernización de imports y fixtures en `test_telegram_callbacks.py`, `test_telegram_charts.py`, `test_telegram_messaging.py`, `test_telegram_snooze.py`, `test_daily_digest.py`, `test_controlled_telegram_simulation.py`, `test_v3_concurrency.py`.
     - Purga vía `git rm` de 5 shims: `app/daily_digest.py`, `app/telegram_callbacks.py`, `app/telegram_charts.py`, `app/telegram_messages.py`, `app/telegram_snooze.py`.
  2. **Fase 3 - Dominio Vnish**:
     - Modernización de imports y 12 targets de `@patch` en `test_vnish_client.py`, `test_vnish_presets.py`, `test_vnish_logs.py`, `test_vnish_telemetry.py`, `test_reboot_decision_audit.py`.
     - Purga vía `git rm` de 4 shims: `app/vnish_client.py`, `app/vnish_logs.py`, `app/vnish_presets.py`, `app/vnish_telemetry.py`.
  3. **Fase 4 - Dominio Governance**:
     - Modernización de imports en `test_fan_governor.py`, `test_fan_governor_concurrency.py`, `test_preset_balancer.py`, `test_preset_balancer_integration.py`, `test_fan_health.py`, `test_energy_efficiency.py`.
     - Adición formal de export `fetch_latest_cooling_assessments` a `app/governance/__init__.py`.
     - Purga vía `git rm` de 4 shims: `app/fan_governor.py`, `app/preset_balancer.py`, `app/fan_health.py`, `app/energy_efficiency.py`.
  4. **Fase 5 - Dominio Core**:
     - Modernización de imports y module inspections en `test_acquisition.py`, `test_acquisition_baseline.py`, `test_t009_t011_invariants.py`, `test_t012_shadow_and_rollback.py`, `test_alert_episodes.py`, `test_compact_format.py`, `test_compact_ux.py`, `test_notification_stability.py`, `test_event_store.py`, `test_incident_report.py`, `test_operations_dashboard.py`, `test_mining_quality.py`, `test_stability_profile.py`, `test_monitor_liveness.py`, `test_metrics_exporter.py`, `test_metrics_snapshot.py`, `test_reboot_safety.py`, `test_restart_intelligence.py`, `test_evidence_fusion.py`, `test_evidence_fusion_fixtures.py`, `test_t014_diagnose_adapter.py`, `test_t017_deterministic_validation.py`, `test_t018_performance_and_growth.py`.
     - Purga vía `git rm` de 9 shims: `app/acquisition.py`, `app/alert_episodes.py`, `app/event_store.py`, `app/evidence_fusion.py`, `app/liveness.py`, `app/metrics_snapshot.py`, `app/mining_quality.py`, `app/reboot_safety.py`, `app/restart_intelligence.py`, `app/stability_profile.py`.
  5. **Fase 6 - Limpieza Profunda de Imports Internos y Certificación**:
     - Eliminación de imports de respaldo innecesarios en `app/miner_monitor.py` y `app/telegram/daily_digest.py`.
     - Verificación de cero módulos planos sueltos en `app/` (únicamente `miner_monitor.py` e `__init__.py`).
* **Resultados y Certificación**:
  - Compilación sintáctica: 100% OK (`py_compile app\miner_monitor.py`).
  - Suite de tests completa: **587/587 tests PASS** en 10.68s.
  - Release audit: **PASS** (`tools/release_audit.py --check-only`), digest `b11a92084d2f558327290d98c05b7fa691e512ddc7f33d36e7f0e120459249fd`, reducción de runtime payload de 83 a 60 archivos limpios.
  - Producción: Servicio Windows `MinerAlerts` ininterrumpido y 100% estable.

---

## [2026-09-08] - Spec 041: Arquitectura Modular y Reorganización de Dominios en `app/`

* **Objetivo**: Reorganizar los 22 archivos Python planos de `app/` en 4 subpaquetes de dominio desacoplados (`app/core/`, `app/vnish/`, `app/governance/`, `app/telegram/`), manteniendo `app/miner_monitor.py` como orquestador raíz y garantizando 100% de retrocompatibilidad y cero regresiones mediante fachadas con module aliasing (`sys.modules[__name__] = _impl`).
* **Migración por Dominios Realizada**:
  1. **Dominio Telegram (`app/telegram/`)**:
     - Subpaquete `app/telegram/` con `callbacks.py`, `charts.py`, `messages.py`, `snooze.py` y `daily_digest.py`.
     - Shims retrocompatibles en `app/` con re-exportaciones canónicas.
  2. **Dominio Vnish Firmware (`app/vnish/`)**:
     - Subpaquete `app/vnish/` con `client.py`, `presets.py`, `logs.py` y `telemetry.py`.
     - Shims en `app/` con module aliasing para soporte de monkey-patching en tests.
  3. **Dominio Gobernanza y Salud Térmica (`app/governance/`)**:
     - Subpaquete `app/governance/` con `fan_governor.py`, `preset_balancer.py`, `fan_health.py` y `energy_efficiency.py`.
     - Shims en `app/` con preservación de interfaces para herramientas operativas.
  4. **Dominio Core (`app/core/`)**:
     - Inicialización formal del paquete raíz `app/__init__.py`.
     - Subpaquete `app/core/` con 10 módulos: `acquisition.py`, `event_store.py`, `alert_episodes.py`, `evidence_fusion.py`, `liveness.py`, `metrics_snapshot.py`, `mining_quality.py`, `reboot_safety.py`, `restart_intelligence.py` y `stability_profile.py`.
     - Shims en `app/` con module aliasing.
  5. **Modernización Canónica de Imports**:
     - Actualización de importaciones directas en `app/miner_monitor.py` y herramientas satélite (`tools/acquisition_baseline.py`, `tools/metrics_exporter.py`, `tools/metrics_sync.py`, `tools/monitor_watchdog.py`, `tools/operations_dashboard.py`, `tools/vnish_log_collector.py`) apuntando a los nuevos dominios con fallback defensivo a los shims.
* **Resultados y Certificación**:
  - Compilación sintáctica: 100% OK (`py_compile` en todos los módulos y herramientas).
  - Suite de Tests: **587/587 tests PASS** en 11.26s sin una sola regresión ni advertencia.
  - Auditoría de Release: PASS (`tools/release_audit.py --check-only`), 83 archivos de payload computados bajo SHA-256 `1d54510535bf6d089af3e84b75835da07b66643388e6d0ea4a2658372672f290`.
  - Servicio Windows `MinerAlerts` en producción: 100% operativo sin caída de servicio.

---

## [2026-09-08] - Auditoría y Reorganización Documental de Speckit (Archivo de Estrategias y Modernización del Índice)

* **Objetivo**: Limpiar y desfragmentar la estructura de archivos markdown en `docs/speckit/`, separando nítidamente la documentación operativa viva y de referencia activa de aquellas propuestas y estrategias históricas cerradas o concluidas, preservando la trazabilidad completa del proyecto sin saturar el contexto de los operadores y modelos.
* **Acciones y Reorganización Realizada**:
  1. **Creación del Directorio de Archivo (`docs/speckit/archive/`)**:
     - Traslado mediante `git mv` (preservando historial de git) de los siguientes documentos históricos cerrados:
       * `HASHCORE_TOOLKIT_STRATEGY.md` -> `docs/speckit/archive/HASHCORE_TOOLKIT_STRATEGY.md` (Inventario de capacidades Hashcore - Spec 026; concluido y congelado).
       * `INTERFACE_STRATEGY.md` -> `docs/speckit/archive/INTERFACE_STRATEGY.md` (Evaluación de interfaz web FastAPI - Spec 027; decisión formal `no_build`).
       * `V3_EXPANSION_PLAN.md` -> `docs/speckit/archive/V3_EXPANSION_PLAN.md` (Plan inicial Telegram Max y V3 - Specs 031 a 038; 100% implementado y certificado en producción).
     - Creación de [`docs/speckit/archive/README.md`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/speckit/archive/README.md) explicando el motivo de archivo, contexto de origen, estado terminal y referencia a la implementación viva correspondiente.
  2. **Modernización del Índice Maestro (`docs/speckit/README.md`)**:
     - Reescritura del índice principal para mapear claramente:
       * **Documentación Operativa Viva**: `ROADMAP.md` (backlog/entregas), `RUNBOOK.md` (manual operativo/comandos), `SPEC_PROGRAM.md` (marco programático y DoD), `DELIVERY_PLAN.md` (calendario y soak), `MINER_DIAGNOSTICS.md` (diagnósticos) y `TECHNOLOGY_STRATEGY.md` (arquitectura y decisiones técnicas).
       * **Sección de Archivo**: Referencia clara al contenido histórico en `archive/`.
       * **Estado del Sistema**: Actualizado a Release V3.0.0 Certificado y V3.1 (Gobernador térmico/potencia y autodescubrimiento Vnish en producción, 40/40 specs completadas).
       * **La Joya del Proyecto**: Referencia destacada a `docs/audit/DEVELOPMENT_LOG.md`.
  3. **Alineación de Enlaces Raíz (`README.md`)**:
     - Actualización de los enlaces del bloque de documentación en el `README.md` principal para reflejar la estructura reorganizada y evitar referencias rotas.
* **Certificación**:
  - Estructura validada: 0 archivos rotos, links relativos y markdown links normalizados.
  - Suite de tests íntegra: 587/587 tests PASS.

---

## [2026-09-08] - Autodescubrimiento Dinámico de Presets Vnish y Diagnóstico de Sensibilidad de Elevadores de Tensión

* **Objetivo**: Implementar la adaptación dinámica automática del sistema ante decisiones del usuario en Vnish (e.g. cambios manuales en `top_preset` o autoswitch como el incremento de los mineros 25 y 26 a 2700W) sin requerir modificaciones estáticas manuales en `config.json`, e incorporar el registro, correlación y diagnóstico integral de la sensibilidad eléctrica de los elevadores de tensión ante reinicios y caídas de carga.
* **Componentes Implementados**:
  1. **Autodescubrimiento Dinámico de Presets Vnish (`app/vnish_client.py`, `app/miner_monitor.py`)**:
     - Implementación de `get_overclock_settings` y `safe_get_overclock_settings` en `app/vnish_client.py`: consulta `/api/v1/settings` bajo sesión autenticada con token Bearer, extrayendo `preset`, `top_preset`, `rise_temp`, `decrease_temp` y `switcher_enabled`, e infiriendo el `target_power_w` objetivo directamente del techo activo fijado por el usuario.
     - En `MinerState`: nuevos campos persistentes `vnish_discovered_target_power_w`, `vnish_discovered_preset`, `vnish_discovered_top_preset`, `vnish_discovered_switcher_enabled` y `vnish_discovered_ts`, con soporte en `load_state` y `save_state`.
     - En `execute_governor_cycle()`: `target_power_w` prioriza el valor autodescubierto en vivo desde Vnish (`state.vnish_discovered_target_power_w`), adaptando inmediatamente las metas térmicas y de enfriamiento (`RECOVERY_MAX_COOLING`) en cuanto el usuario altera la configuración web de Vnish.
     - Ciclo periódico de sincronización concurrente no bloqueante (`refresh_vnish_overclock_settings`) cada 300s y al arranque del servicio.
     - Normalización de presets en escalera (`find_preset_index` stripping `'W'`) para compatibilidad bidireccional entre `"2700"` (Vnish REST) y `"2700W"` (ladder).
  2. **Registro y Diagnóstico de Sensibilidad de Elevadores (`app/preset_balancer.py`, `app/miner_monitor.py`)**:
     - Enriquecimiento de `StabilityMetrics` con `current_power_w` y `current_temp_c`.
     - `record_elevator_restart_circumstance()`: Ante cada reinicio detectado (`restart_detected`), captura de forma determinista la circunstancia previa del elevador: carga total combinada (Watts), potencia y temperatura pre-reinicio del equipo, estado de los mineros pares del grupo, y detección de caídas en cascada (`is_elevator_cascade`) si otro minero del mismo elevador reinició dentro de la ventana de 30 minutos (`group_cascade_window_s`).
     - Almacenamiento estructurado en `operational_events` (`details_json`) e inserción del evento especializado `elevator_cascade_restart` ante caídas correlacionadas.
     - Motor de diagnóstico `analyze_elevator_sensitivity()` y generador de tarjeta de estado `build_elevator_sensitivity_text()`. Clasifica cada elevador en `ESTABLE`, `SENSIBILIDAD_MODERADA` o `ALTA_SENSIBILIDAD` con recomendaciones de carga máxima sugerida.
     - Comandos de Telegram: soporte de `/elevadores` (alias `/elevators`, `/sensibilidad`, `/elev`) y visualización de carga por elevador en la cabecera de grupo en `/balancer`.
  3. **Configuración de Producción**:
     - `app/config.json`: S19JPRO-25 y S19JPRO-26 actualizados a `target_power_w: 2700.0`.
* **Certificación**:
  - 587/587 tests PASS en 10.93s.
  - Servicio `MinerAlerts` reiniciado con éxito bajo PID 71304; logs verifican autodescubrimiento en vivo (`[VNISH_SYNC]`) y metas de 2700W para la flota completa.

---

## [2026-09-08] - Desacople de Telemetría de Gobernador y Fallback en Memoria para Balanceador de Presets

* **Objetivo**: Auditar y robustecer la resiliencia operativa: desacoplar la ingesta de telemetría del Fan Governor respecto de las alertas preventivas de cooling, evitar que mineros offline operen sobre telemetría fantasma, y agregar fallback de estado en memoria en el Balanceador de Presets para inferir potencias y márgenes térmicos reales aun cuando la base SQLite no haya grabado muestras recientes.
* **Mejoras Implementadas**:
  - **Desacople de Ingesta de Telemetría (`app/miner_monitor.py:5901`)**:
    * La alimentación de `state.governor_last_temp_c` y `state.governor_last_power_w` se movió fuera del bloque condicional de `cooling_alert_enabled`, garantizando que el gobernador reciba telemetría en tiempo real independientemente de cómo esté configurado el subsistema de alertas de enfriamiento.
    * Ante desconexión o falla de respuesta del minero (`not responded`), se limpian los valores a `None`, garantizando que el gobernador devuelva `ACTION_UNKNOWN` con `requires_write=False` y nunca intente ajustar ventiladores sobre datos obsoletos o en mineros inalcanzables.
  - **Fallback en Memoria para Métricas de Estabilidad (`app/preset_balancer.py:386`)**:
    * En `extract_miner_stability_metrics()`, si la tabla `telemetry_samples` de SQLite no contiene filas recientes para un minero, se recurre automáticamente a los valores en memoria de `states` (`st.governor_last_power_w`, `st.governor_last_temp_c` y `st.last_elapsed`).
    * Erradica la inferencia errónea del preset por defecto ("1600W") en mineros que operan en 2500W o 2700W.
* **Certificación**:
  - 581/581 tests PASS en 8.77s.
  - Sintaxis limpia (`py_compile`) y servicio reiniciado en producción.

---

## [2026-09-08] - Calibración Térmica de Fan Governor a 82.0°C para Prevención de Autoswitch Vnish

* **Objetivo**: Reducir el target térmico del gobernador de 83.0°C a 82.0°C para maximizar la estabilidad operativa y evitar que fluctuaciones térmicas normales se acerquen al umbral de corte/desescalado de Vnish (`decrease_temp: 84.0°C`).
* **Ajustes Operativos (`app/config.json`, `app/config.example.json`, `app/miner_monitor.py`)**:
  - `fan_governor_target_temp_c`: 82.0°C (objetivo central de trabajo saludable).
  - `fan_governor_deadband_low_c`: 81.0°C (modula ventiladores -2% si T < 81.0°C).
  - `fan_governor_deadband_high_c`: 82.5°C (incrementa ventiladores +3% si T > 82.5°C).
  - `fan_governor_emergency_temp_c`: 83.5°C (salto de emergencia a 100% PWM si T >= 83.5°C, manteniendo 0.5°C de margen estricto antes de los 84.0°C de Vnish).
* **Certificación**:
  - 581/581 tests PASS en 8.92s.
  - Servicio reiniciado en producción bajo PID nuevo y verificada la ejecución en vivo.

---

## [2026-09-08] - Corrección de Razonamiento Individual por Minero y Preservación de Configuración en `valid_miners`

* **Objetivo**: Garantizar el razonamiento 100% individual y personalizado por minero en el Fan Governor: resolver la causa raíz por la cual mineros operando en su techo configurado (S19JPRO-25 y 26 en 2500W con temperatura sana de 76°C) recibían orden de 100% de coolers (`RECOVERY_MAX_COOLING`) en lugar de modular hacia abajo (`STEP_DOWN`), permitiendo que cada equipo module sus ventiladores de forma estrictamente desacoplada de los demás.
* **Causa Raíz Identificada**:
  - En la inicialización del monitor (`miner_monitor.py:5596`), la lista `valid_miners` se instanciaba con un diccionario mínimo `{name, host, port}`, descartando inadvertidamente los campos `target_power_w`, `electrical_group` y cualquier otro atributo individual del minero.
  - Al no recibir `target_power_w` (devolvía `None`), el gobernador recurría al fallback global `fan_governor_target_power_w = 2700.0W`.
  - Como resultado, S19JPRO-25 y 26 (consumiendo 2498–2499W) eran evaluados contra 2700W en vez de contra sus 2500W reales, interpretándose falsamente como equipos con déficit de potencia (2499W < 2700 - 120W), disparando coolers al 100% incondicional.
* **Corrección y Mejoras Implementadas**:
  - **Preservación Total en `valid_miners`**: `valid_miners.append(dict(miner))` preserva íntegramente `target_power_w`, `electrical_group`, `max_preset` y posibles overrides por equipo.
  - **Configuración Dinámica por Minero (`miner_gov_cfg`)**: Permite que cada minero sobreescriba individualmente umbrales térmicos (`target_temp_c`, deadbands, piso de PWM, etc.) si se define en su entrada de configuración.
  - **Claridad Observacional en Logs y Telegram**:
    * Log del ciclo: `pwr=2499/2500W` o `pwr=2499/2700W` refleja de inmediato la potencia actual respecto a la meta individual.
    * Comando `/gov`: Muestra la relación `T=76.0°C 2499/2500W PWM=98% [STEP_DOWN]`, evidenciando el razonamiento individual.
  - **Certificación de Pruebas**:
    * Nuevo test de integración: `test_individual_miner_reasoning_different_targets_and_temperatures` en `tests/test_fan_governor_concurrency.py`.
    * 581/581 tests PASS en 9.04s.

---

## [2026-09-08] - Integración de Recuperación de Autoswitch Vnish en Fan Governor y Formato REST API

* **Objetivo**: Resolver el desacople entre el autoswitch nativo de Vnish y la modulación del Fan Governor: evitar que un minero quede estancado en potencias subóptimas (ej. 2300W en vez de 2500W/2700W) por modulación descendente de ventiladores a 83°C. Forzar 100% de enfriamiento hasta que el equipo alcance su potencia objetivo, permitiendo que el chip baje a $\le 79^\circ\text{C}$ y el firmware Vnish suba el preset al máximo permitido.
* **Resultados y Evidencia**:
  - **Mecanismo de Recuperación de Autoswitch (`app/fan_governor.py`, `app/miner_monitor.py`)**:
    * Regla `ACTION_RECOVERY_MAX_COOLING`: Si `current_power_w < (target_power_w - margin_w)` (margen 120W), el gobernador fuerza 100% de PWM de forma incondicional, deshabilitando el step-down mientras el minero esté por debajo de su techo de autoswitch.
    * Con 100% de ventilación, los chips se enfrían por debajo del umbral `rise_temp` (79.0°C de Vnish), habilitando el ascenso automático de preset de Vnish tras el `check_time` (300s).
    * Únicamente cuando el equipo alcanza su potencia objetivo (2700W en 23/24, 2500W en 25/26) y la temperatura es $\le 82.0^\circ\text{C}$, el gobernador modula los ventiladores hacia abajo para estabilizar la temperatura en 83.0°C.
    * Telemetría de potencia (`chain_power_w_total`) persistida en `MinerState` (`governor_last_power_w`) y reflejada en el comando `/gov` de Telegram (`T=82.5°C 2698W PWM=96%`).
  - **Normalización de Formato REST API Vnish (`app/vnish_client.py`)**:
    * La API REST de Vnish rechaza `"2700W"` con HTTP 400 (`ProfileName invalid: '2700W'`). Se normalizó en `set_miner_preset()` para limpiar sufijos `"W"`, enviando `"2700"`.
  - **Configuración Operativa (`app/config.json`, `app/config.example.json`)**:
    * `miners`: S19JPRO-23 y 24 configurados con `target_power_w: 2700.0`; S19JPRO-25 y 26 configurados con `target_power_w: 2500.0`.
    * `preset_balancer_dry_run: true`: El balanceador corre en modo diagnóstico / monitoreo de cascada eléctrica sin forzar presets que compitan con el autoswitch de Vnish.
    * `fan_governor_enabled: true`, `fan_governor_dry_run: false`: Gobernador activo en producción.
  - **Suite de Pruebas**:
    * Nuevos tests unitarios y de integración: `test_recovery_max_cooling_when_below_target_power`, `test_recovery_max_cooling_already_at_100`, `test_normal_modulation_when_at_target_power`, `test_execute_governor_cycle_recovers_to_100_when_below_target_power`.
    * 580/580 tests PASS en 8.86s (0 fallos, 0 errores, 0 regresiones).
    * `py_compile` limpio en todo el proyecto.

---

## [2026-09-08] - Activación Plena por Defecto de Gobernador Térmico y Balanceador de Presets en Producción

* **Objetivo**: Configurar como activas por defecto (`enabled: true`, `dry_run: false`) las nuevas aplicaciones de control y gobernanza de hardware (Spec 039 Fan Governor y Spec 040 Preset Balancer), manteniendo intacta la capacidad de desconexión y reconexión manual interactiva en caliente vía Telegram (`/gov on`/`/gov off`, `/balancer on`/`/balancer off`). Normalizar y sincronizar toda la documentación del proyecto, reiniciar el servicio en modo activo y certificar la estabilidad absoluta del sistema.
* **Resultados y Evidencia**:
  - **Activación por Defecto en Configuración (`app/config.json` y `app/config.example.json`)**:
    * `fan_governor_enabled: true` y `fan_governor_dry_run: false`: Gobernador térmico de lazo cerrado activo al arrancar el servicio. Modula coolers al target de 83.0°C en base a la telemetría periódica. Desactivable en cualquier momento con `/gov off` (fallback automático a 100% PWM).
    * `preset_balancer_enabled: true` y `preset_balancer_dry_run: false`: Balanceador de presets activo al arrancar el servicio. Desescala preventivamente por reinicios en 24h, caídas en cascada del mismo elevador o temperatura límite $\ge 84.0^\circ\text{C}$. Desactivable en cualquier momento con `/balancer off`.
  - **Normalización de Documentación**:
    * `specs/039-vnish-fan-governor/evidence.md`: Actualizado con la activación en producción, target 83°C y umbrales definitivos.
    * `specs/040-dynamic-voltage-presets/evidence.md`: Actualizado con los 14 tests unitarios deterministas (incluyendo sobrecarga térmica) y activación en producción.
    * `docs/speckit/ROADMAP.md`: Specs 039 y 040 marcadas formalmente como *COMPLETADAS Y ACTIVAS EN PRODUCCIÓN*.
    * `docs/speckit/DELIVERY_PLAN.md`: Hitos de cierre registrados para Specs 039 y 040.
    * `docs/speckit/SPEC_PROGRAM.md`: Estado del programa actualizado a 40 especificaciones cerradas (V1 a V3.1) y 576 tests automáticos.
  - **Certificación de Pruebas**:
    * 576/576 tests PASS en 8.52s (0 fallos, 0 errores, 0 regresiones).
    * Validación de sintaxis limpia en todo el árbol de código.

---

## [2026-09-08] - Calibración Operativa Térmica 83°C–84°C, Step-Down por Temperatura y Mitigación de Spam en Telegram

* **Objetivo**: Alinear la estrategia física de operación solicitada por el operador: punto de trabajo sano a 83.0°C, límite máximo estable de 84.0°C con desescalado secuencial de potencia (2700W -> 2500W -> 2300W) si los ventiladores al 100% no son suficientes para contener la temperatura, modulación descendente de ventiladores cuando exista margen térmico, y erradicación definitiva de falsas alertas de saturación y ruido de autotune en Telegram.
* **Resultados y Evidencia**:
  - **Desescalado Térmico en Balanceador de Presets (`app/preset_balancer.py`)**:
    * Implementada regla prioritaria `ACTION_STEP_DOWN_THERMAL`: ante margen térmico crítico $\le 1.0^\circ\text{C}$ (temperatura $\ge 84.0^\circ\text{C}$ frente al corte por hardware de 85.0°C), el balanceador desescala de inmediato el preset de potencia (`2700W -> 2500W -> 2300W`) para proteger el hardware antes de que ocurra un trip de emergencia.
    * Test unitario agregado: `test_step_down_on_thermal_overload` en `tests/test_preset_balancer.py` (14/14 tests PASS).
  - **Calibración de Gobernador Térmico (Spec 039)**:
    * `fan_governor_target_temp_c`: 83.0°C (punto objetivo de máxima eficiencia y salud física).
    * `fan_governor_deadband_low_c`: 82.0°C. Si temp < 82.0°C, reduce el duty de ventiladores (-2%) para evitar desgaste y ruido innecesarios.
    * `fan_governor_deadband_high_c`: 83.5°C. Si temp > 83.5°C, incrementa el duty de ventiladores (+3%).
    * `fan_governor_emergency_temp_c`: 84.0°C. Dispara ventiladores al 100% PWM de inmediato.
  - **Mitigación de Spam y Falsas Alarmas en Telegram (`app/fan_health.py`, `app/miner_monitor.py`)**:
    * El umbral hardcoded de 82.0°C para `STATUS_CRITICAL_HEAT` se refactorizó a `critical_temp_c: float = 84.5` (configurable vía `cooling_critical_temp_c`). Esto evita que mineros operando sanamente a 81°C–83.5°C sean catalogados falsamente como calor crítico.
    * `cooling_saturate_temp_c` elevado de 78.0°C a 84.0°C con `cooling_saturate_pwm_pct`: 98.0%, `cooling_saturate_streak`: 5 ticks y `cooling_cooldown_seconds`: 7200s (2 horas). Erradica los avisos espurios de saturación a 81.0°C reportados por el usuario.
    * `preset_alert_enabled: false`: Silencia las notificaciones informativas de autotune de Vnish por fluctuaciones normales de 25–35 MHz. El estado de frecuencia permanece totalmente accesible bajo demanda vía `/presets` y `/digest`.
  - **Suite de Pruebas y Certificación**:
    * 576/576 tests PASS en 8.66s.
    * `py_compile` limpio en `app/miner_monitor.py`, `app/fan_health.py` y `app/preset_balancer.py`.

---

## [2026-09-08] - Implementación y Cierre de Spec 040 (Dynamic Power & Preset Balancer: Fases 1 a 5 Completadas)

* **Objetivo**: Desarrollar e integrar el Balanceador Dinámico de Presets y Potencia para Elevadores de Tensión Sensibles (Spec 040), respondiendo a la necesidad operativa de calibrar el hashrate versus frecuencia de caídas/reinicios, proteger fases eléctricas y evitar apagados en cascada en la granja.
* **Resultados y Evidencia**:
  - **Fase 1 (Extensión de Cliente REST Vnish Presets - `app/vnish_client.py`)**:
    * Métodos transaccionales implementados: `get_available_presets()` (consulta en `GET /api/v1/presets`), `set_miner_preset()` (modulación de overclock en `POST /api/v1/settings`) y `safe_set_miner_preset()` con garantía de cierre de sesión (`lock_miner`) en bloque `finally`.
    * Tests unitarios con mocks HTTP en `tests/test_vnish_client.py` (15/15 tests PASS).
  - **Fase 2 (Motor Matemático Puro de Balanceo Costo/Beneficio - `app/preset_balancer.py`)**:
    * Modelos de datos: `PresetTier`, `StabilityMetrics`, `BalancerConfig`, `BalancerDecision`.
    * Escalera estándar de presets Vnish para S19j Pro: 1600W a 2800W.
    * Función objetivo $H_{\text{eff}}$ demostrando matemáticamente que operar a 93 TH/s (2500W) sin reinicios genera más hashrate neto acumulado que operar forzado a 98 TH/s (2700W) con reinicios frecuentes (93.00 TH/s vs 89.96 TH/s netos).
    * Regla de desescalado rápido individual ante $\ge 2$ reinicios en 24h.
    * Regla de protección de elevador sensible: desescalado en cascada si dos mineros del mismo elevador se reinician en menos de 30 minutos.
    * Hysteresis conservadora: exige 72 horas continuas de estabilidad total y margen térmico $\ge 4.0^\circ\text{C}$ antes de considerar subir 1 preset.
    * Función `extract_miner_stability_metrics()` leyendo SQLite con URI `?mode=ro` en < 20ms.
    * Formateadores de Telegram: `build_balancer_table_text()` (agrupado por elevador) y `build_miner_balancer_detail_text()`.
  - **Fase 3 (Suite de Pruebas Unitarias Deterministas - `tests/test_preset_balancer.py`)**:
    * 13 tests unitarios deterministas cubriendo cálculo de $H_{\text{eff}}$, desescalado por reinicios, freno en preset mínimo (1600W), desescalado grupal en cascada, escalado tras soak de 72h, bloqueo térmico, inferencia por potencia, tablas Telegram y consulta contra base real (13/13 tests PASS en 0.002s).
  - **Fase 4 (Integración en Monitor, Persistencia y Comandos Telegram - `app/miner_monitor.py`)**:
    * Soporte para `electrical_group` en cada minero en `config.json` y `config.example.json`.
    * Campos en `MinerState` (`balancer_preset`, `balancer_last_change_ts`, `balancer_last_action`, `balancer_last_reason`) persistidos atómicamente en `state.json`.
    * Ciclo de balanceo `execute_balancer_cycle()` integrado de forma no-bloqueante con `ThreadPoolExecutor` (timeout global de flota de 5.0s) y ejecución periódica (`preset_balancer_interval_seconds: 1800`).
    * Configuración ultra-segura por defecto: `preset_balancer_enabled: false` y `preset_balancer_dry_run: true`.
    * Comandos Telegram interactivos: `/balancer` (tabla ejecutiva agrupada por elevador), `/balancer on`, `/balancer off`, `/balancer setmax <miner> <preset>`, `/balancer run` y detalle individual por minero.
  - **Fase 5 (Validación, Tests de Concurrencia y Certificación Global)**:
    * `tests/test_preset_balancer_integration.py`: 9 tests de integración y concurrencia verificando simulación en dry-run, escritura activa mockeada, timeout de flota, cerrojos multihilo bajo `state_lock` y comandos de ayuda.
    * Certificación de Suite Global: **575/575 tests PASS** en 10.08s (0 fallos, 0 errores, 0 regresiones).
    * `py_compile` limpio en `app/miner_monitor.py`.
  - **Modelo**: Gemini 3.8 Flash High (100% autónomo).

---

## [2026-09-08] - Implementación y Cierre de Spec 039 (Vnish Thermal & Acoustic Fan Governor — Fases 1 a 5 Completadas)

* **Objetivo**: Desarrollar e integrar el Gobernador Térmico y Acústico de Ventiladores Vnish (Spec 039), incorporando detección de modo en `/fans`, cliente REST seguro (`app/vnish_client.py`), algoritmo determinista de lazo cerrado (`app/fan_governor.py`), integración multihilo protegida en el monitor (`app/miner_monitor.py`), comandos interactivos Telegram (`/gov`, `/gov on`, `/gov off`, `/gov set`) y suite de estrés de concurrencia.
* **Resultados y Evidencia**:
  - **Fase 1 (Visibilidad de Modo de Enfriamiento)**:
    * `app/vnish_telemetry.py`: Extendido para extraer `fan_mode` (`manual`, `auto`, `immers`) tanto desde el payload `STATS` de API 4028 como desde el payload REST `/api/v1/summary`.
    * `app/fan_health.py`: `CoolingAssessment` extendido con `fan_mode`. `build_fans_table_text()` ahora renderiza indicadores explícitos `(100% [MANUAL])` y `build_miner_fan_detail_text()` expone `• Modo Control: MANUAL`.
    * `app/miner_monitor.py`: Almacena `state.last_fan_mode` y lo transfiere al evaluador de salud de enfriamiento.
  - **Fase 2 (Cliente Vnish REST Seguro - `app/vnish_client.py`)**:
    * Funciones transaccionales seguras: `unlock_miner`, `lock_miner`, `get_cooling_settings`, `set_manual_fan_duty` y wrapper de alto nivel `safe_set_fan_duty` con bloque `try ... finally: lock_miner` garantizado.
    * Enmascaramiento de secretos (`mask_secret`) previniendo exposición de passwords o Bearer tokens en logs.
    * Clamping de hardware: duty limitado rígidamente entre [40%, 100%].
    * Timeouts cortos de 2.5s por solicitud HTTP (cumplimiento R2).
  - **Fase 3 (Algoritmo Determinista del Gobernador - `app/fan_governor.py`)**:
    * Motor matemático puro `compute_governor_step()` sin efectos colaterales ni I/O.
    * R1 (Anti-Hunting): Dwell time adaptativo (90s base, 120s si `consecutive_holds >= 3`) y banda muerta $[81.0, 82.5]^\circ\text{C}$.
    * R3 (Fail-Safe Explícito a 100%): Salto forzado a 100% ante $\ge 3$ fallos consecutivos de comunicación o error de hardware.
    * R4 (Piso de Seguridad Infranqueable): Límite mínimo elevado a 75% PWM.
    * Regla de emergencia térmica inmediata ante $T_{max} \ge 83.0^\circ\text{C}$ con salto inmediato a 100% omitiendo la ventana de asentamiento.
  - **Fase 4 (Integración en Monitor y Comandos Telegram)**:
    * `app/miner_monitor.py`:
      - Campos en `MinerState` (`governor_duty`, `governor_holds`, `governor_last_change_ts`, `governor_failures`, `governor_last_action`, `governor_last_temp_c`) con persistencia en `load_state`/`save_state` bajo `state_lock`.
      - Función `execute_governor_cycle()` ejecutada al final de cada ciclo tras la telemetría, despachando escrituras de hardware en paralelo mediante `ThreadPoolExecutor(max_workers=min(4, len(writers)))` con timeout de flota de 5.0s y `shutdown(wait=False)` (R2).
      - Comandos interactivos Telegram: `/gov` (alias `/governor`), `/gov on`, `/gov off` (con fallback de seguridad forzado a 100% PWM, R3) y `/gov set <temp>` (validación de rango [75.0°C, 83.0°C]).
      - Feature flags defensivos por defecto: `fan_governor_enabled: false` y `fan_governor_dry_run: true`.
    * `app/config.example.json`: Esquema completo documentado con credenciales redactadas (`CHANGE_ME`).
  - **Fase 5 (Tests de Concurrencia y Certificación Global)**:
    * `tests/test_fan_governor_concurrency.py`: 12 tests deterministas de concurrencia cubriendo fleet timeout (minero lento de 10s no bloquea el ciclo más de 2s), aislamiento de excepciones, dry-run, concurrencia bajo `state_lock`, fallback a 100% en `/gov off`, emergency spike, dwell adaptativo y piso de 75% PWM.
    * `app/telegram_charts.py`: Envuelto el renderizado de figuras Matplotlib en bloques `try ... finally: plt.close(fig)` para prevenir fugas de memoria OpenBLAS y descriptores GDI en Windows.
    * Suite global de regresión: **549/549 tests PASS** en 8.29s (0 fallos, 0 errores, 0 regresiones).
  - **Colaboración Multi-Modelo**: Gemini 3.8 Flash High (Fases 1, 2, 3, auditoría cruzada de integración y bugfix en `governor_last_temp_c`) + Claude Sonnet 4.6 Thinking (Auditoría arquitectónica pre-implementación R1-R4, esqueleto de Fases 4 y 5).

---

## [2026-09-07] - Implementación y Cierre de Spec 038 (V3 Core Concurrency, Multi-Threading Race Conditions & Release Stabilization)

* **Objetivo**: Ejecutar la auditoría profunda de concurrencia multihilo, sincronización de cerrojos `state_lock`, prevención de bloqueos mutuos (*deadlocks*), higiene estricta de conexiones SQLite (`?mode=ro`, timeout <= 2.0s y `finally: conn.close()`) y pruebas de estrés deterministas para certificar el **Release Candidate V3.0.0**.
* **Resultados y Evidencia**:
  - **Hardening de Concurrencia y Thread-Safety**:
    * `CallbackTokenRegistry` (`app/telegram_callbacks.py`): Equipado con `self._lock = threading.Lock()` e iteración sobre copias de snapshots `list(self._tokens.items())`. Se resolvió la excepción `RuntimeError: dictionary changed size during iteration` detectada en pruebas con 5 hilos de disparo concurrente.
    * `save_state()` (`app/miner_monitor.py`): Actualizado a `list(states.items())` para garantizar snapshots inmutables inmunes a altas frecuencias de actualización de mineros concurrentes.
    * Higiene SQLite garantizada en todos los módulos auxiliares de lectura (`app/fan_health.py`, `app/energy_efficiency.py`, `app/vnish_presets.py`, `app/daily_digest.py`, `app/telegram_charts.py`): Todas las conexiones utilizan `?mode=ro`, timeout de 2.0s y bloque `finally: if conn: conn.close()` que previene bloqueos de archivo en Windows.
  - **Suite de Pruebas de Concurrencia**:
    * Creado `tests/test_v3_concurrency.py` con 19 pruebas de estrés multi-hilo deterministas (cero `sleep`, sincronización por barreras y eventos):
      - Concurrencia de `/snooze` vs loop de evaluación de autorreinicio.
      - Incrementos atómicos de streaks de enfriamiento y degradación energética.
      - Consumo de tokens de un solo uso (anti-doble toque).
      - Respeto estricto del contrato de conexión SQLite de solo lectura.
    * Suite global de regresión: **514/514 tests PASS** en 14.61s (0 fallos, 0 errores, 0 regresiones).
  - **Certificación de Producción**:
    * Monitor en producción PID 38816 100% ininterrumpido (>267.3h continuas, >4.611 CPU s).
    * Release Candidate V3 (v3.0.0) aprobado y certificado.

---

## [2026-09-07] - Implementación y Cierre de Spec 037 (Vnish Preset & Autotuning Dynamic Tracking - /presets)

* **Objetivo**: Implementar el monitoreo dinámico de perfiles de frecuencia (`frequency_mhz_avg`), tensión de cadena (`chain_voltage_mv_avg`), potencia y estado de autotuning del firmware Vnish (`app/vnish_presets.py`). Accesible vía comando interactivo `/presets` (y alias `/preset`, `/profile [minero]`) y alertas preventivas `PROFILE_CHANGE_ALERT` ante reducciones de frecuencia ($\ge 25\text{ MHz}$) o problemas de calibración.
* **Resultados y Evidencia**:
  - **Módulo de Dominio Puro (`app/vnish_presets.py`)**:
    * Inferencia automática de perfiles de potencia y frecuencia nominales (`~2700W (516 MHz)`, `~2500W (485 MHz)`).
    * Clasificación de estado de tuning en 4 estados:
      - `STABLE` (`🟢 ESTABLE`): Frecuencia nominal y cadenas calibradas.
      - `AUTOTUNING` (`🟡 AUTOTUNING`): Cadenas en transición o eventos de ajuste registrados.
      - `DOWNCLOCKED` (`🟠 DOWNCLOCK`): Reducción $\ge 25\text{ MHz}$ respecto al perfil base por estabilidad térmica o eléctrica.
      - `UNKNOWN` (`⚪ SIN DATOS`): Sin telemetría disponible.
    * Formateador de tabla de flota (`build_presets_table_text()`) y ficha diagnóstica individual (`build_miner_preset_detail_text()`) con correlación de eventos de firmware (`firmware_events`).
    * Consulta atómica sobre base de datos SQLite en **1.77 ms** con soporte para múltiples identificadores de minero.
    * Evaluador preventivo `evaluate_preset_alerts()` con baseline adaptativo y cooldown configurable (1 hora).
  - **Integración en `app/miner_monitor.py`**:
    * Registrados comandos `/presets`, `/preset`, `/profile` en `CMD_WHITELIST`, `_COMMANDS` y `/help`.
    * Handler para `/presets` y `/presets <minero>`.
    * `MinerState`: agregados campos `baseline_frequency_mhz` y `last_preset_warning_ts`, con serialización completa en `load_state()` y `save_state()`.
    * Hook de evaluación en bucle principal, respetando `/snooze` y modo QA.
    * Configuración documentada en `app/config.example.json` (`preset_alert_enabled`, `preset_frequency_drop_mhz`, `preset_cooldown_seconds`).
  - **Pruebas y Verificación**:
    * Creada la suite `tests/test_vnish_presets.py` con 11 pruebas unitarias e integradas (100% pasando).
    * Suite global de regresión: **495/495 tests PASS** en 5.04s.
    * Monitor en producción (PID 38816) 100% ininterrumpido (>267h soak).

---

## [2026-09-07] - Implementación y Cierre de Spec 036 (Hashrate Efficiency & Energy Tracking - /efficiency)

* **Objetivo**: Implementar el seguimiento en tiempo real del ratio energético en Joules por Terahash ($J/\text{TH} = \text{Watts} / \text{TH/s}$) para detectar precozmente degradación de fuentes, chips defectuosos o caídas de tensión antes del colapso total de hashrate (`app/energy_efficiency.py`). Accesible vía comando interactivo `/efficiency` (y alias `/eff [minero]`) y alertas preventivas `EFFICIENCY_WARNING`.
* **Resultados y Evidencia**:
  - **Módulo de Dominio Puro (`app/energy_efficiency.py`)**:
    * Cálculo matemático exacto de $J/\text{TH}$ blindado contra divisiones por cero o potencias nulas.
    * Clasificación de eficiencia en 4 bandas operativas:
      - `OPTIMAL` (`🟢 ÓPTIMA`): $\le 28.5\text{ J/TH}$ (rango superior de S19j Pro).
      - `NORMAL` (`🟢 NORMAL`): $28.5 < \text{J/TH} \le 31.5$ (operación nominal estándar).
      - `ELEVATED` (`🟡 ELEVADA`): $31.5 < \text{J/TH} \le 35.0$ (degradación leve o autotune alto).
      - `DEGRADED` (`🟠 DEGRADADA`): $> 35.0\text{ J/TH}$ (consumo excesivo por TH generado).
    * Generador de tabla consolidada (`build_efficiency_table_text()`) que incluye potencia total en kW y promedio ponderado de la flota, y ficha detallada (`build_miner_efficiency_detail_text()`).
    * Consulta atómica en modo seguro `?mode=ro` sobre `telemetry_samples`: consulta en **0.7 ms** y render en **0.1 ms** (< 1 ms total).
    * Evaluador preventivo `evaluate_efficiency_alerts()` con filtro por streak (3 lecturas consecutivas) y cooldown de 1 hora.
  - **Integración en `app/miner_monitor.py`**:
    * Registrados comandos `/efficiency` y `/eff` en `CMD_WHITELIST`, `_COMMANDS` y `/help`.
    * Handler para `/efficiency` (resumen de flota) y `/efficiency <minero>` (diagnóstico profundo individual).
    * `MinerState`: agregados campos `efficiency_streak` y `last_efficiency_warning_ts`, con persistencia íntegra en `load_state()` y `save_state()`.
    * Hook de evaluación en el bucle principal de adquisición, respetando silenciamiento `/snooze` y modo QA.
    * Documentadas opciones de configuración en `app/config.example.json` (`efficiency_alert_enabled`, `efficiency_target_j_th`, `efficiency_degraded_threshold_j_th`, `efficiency_degraded_streak`, `efficiency_cooldown_seconds`).
  - **Pruebas y Verificación**:
    * Creada la suite `tests/test_energy_efficiency.py` con 12 pruebas unitarias, integradas y de benchmark.
    * Suite global: **484/484 tests PASS** en 4.84s (0 fallos, 0 errores, 0 regresiones).
    * Compilación Python exitosa con código de salida 0.
    * Monitor en producción (PID 38816) 100% ininterrumpido (>267h soak).
* **Próximo Paso**:
  - Proceder con la siguiente capacidad del Plan V3 (`docs/speckit/V3_EXPANSION_PLAN.md`): Seguimiento de Presets y Autotuning dinámico de Vnish (detección de cambios de perfil de frecuencia/voltaje).

---

## [2026-09-07] - Implementación y Cierre de Spec 035 (Cooling & Fan Health Intelligence - /fans)

* **Objetivo**: Implementar inteligencia analítica de refrigeración y estado mecánico de ventiladores (`app/fan_health.py`) para detectar saturación térmica de flujo (filtros sucios / pasta degradada) y fallas mecánicas de ventiladores antes de alcanzar el apagado por hardware de emergencia (85°C). Accesible vía comando interactivo `/fans` (y alias `/fan [minero]`) y alertas preventivas tempranas `COOLING_WARNING` y `FAN_DEFECT`.
* **Resultados y Evidencia**:
  - **Módulo de Dominio Puro (`app/fan_health.py`)**:
    * Cálculo determinista del margen térmico hacia el corte: $\text{Headroom} = \max(0.0, 85.0 - T_{\text{max}})$.
    * Clasificación precisa en 5 estados térmicos:
      - `HEALTHY` (`🟢 OK`): $T_{\text{max}} < 75^\circ\text{C}$ y PWM < 90%.
      - `ELEVATED` (`🟡 ELEVADO`): $75^\circ\text{C} \le T_{\text{max}} < 78^\circ\text{C}$ o PWM ≥ 90%.
      - `SATURATED` (`🟠 SATURADO`): $T_{\text{max}} \ge 78^\circ\text{C}$ y (PWM ≥ 95% o RPM ≥ 5800) sostenido.
      - `CRITICAL_HEAT` (`🔴 CRÍTICO`): $T_{\text{max}} \ge 82^\circ\text{C}$ (margen crítico $\le 3^\circ\text{C}$).
      - `FAN_DEFECT` (`⚠️ DEFECTO FAN`): RPM < 2000 RPM bajo carga o señal de tacómetro ausente (`fan_signal_missing`).
    * Formateo de tabla general para la flota (`build_fans_table_text()`) y ficha diagnóstica individual con recomendaciones operativas (`build_miner_fan_detail_text()`).
    * Consulta ultrarrápida a SQLite con modo seguro `?mode=ro`: consulta en **0.8 ms** y formateo en **0.1 ms** (< 1 ms vs SLA < 100 ms) sobre base real de 23.2 MB.
    * Evaluador de alertas preventivas `evaluate_cooling_alerts()` con filtro por streak (3 lecturas consecutivas saturadas) y cooldown de 1 hora para evitar ruido.
  - **Integración en `app/miner_monitor.py`**:
    * Registrados comandos `/fans` y `/fan` en `CMD_WHITELIST`, `_COMMANDS` y `/help`.
    * Handler para `/fans` (tabla de flota) y `/fans <minero>` (detalle con match por nombre, ID o IP).
    * `MinerState`: agregados campos `cooling_streak` y `last_cooling_warning_ts`, con persistencia íntegra en `load_state()` y `save_state()`.
    * Hook de evaluación preventiva en el bucle principal de adquisición tras registrar muestras en `telemetry_samples`, respetando el silenciamiento `/snooze` y el modo QA.
    * Documentadas opciones de configuración en `app/config.example.json` (`cooling_alert_enabled`, `cooling_saturate_temp_c`, `cooling_saturate_pwm_pct`, `cooling_saturate_rpm`, `cooling_saturate_streak`, `cooling_cooldown_seconds`).
  - **Pruebas y Verificación**:
    * Creada la suite `tests/test_fan_health.py` con 14 pruebas unitarias, integradas y de benchmark de base real.
    * Suite global: **472/472 tests PASS** en 4.60s (0 fallos, 0 errores, 0 regresiones).
    * Compilación Python exitosa con código de salida 0.
    * Monitor en producción (PID 38816) 100% ininterrumpido (>267h soak).
* **Próximo Paso**:
  - Proceder con la siguiente fase del plan V3 (`docs/speckit/V3_EXPANSION_PLAN.md`): Métricas continuas de eficiencia J/TH en telemetría en tiempo real y alertas de degradación energética.

---

## [2026-09-07] - Implementación y Cierre de Spec 034 (Daily Executive Digest - /digest)

* **Objetivo**: Implementar el reporte diario ejecutivo matutino programado (08:00 AM) y bajo demanda vía `/digest` (o atajo `/summary`), consolidando en una tarjeta concisa de Telegram el uptime de la flota, hashrate promedio 24h vs nominal, eficiencia energética (J/TH), calidad de shares, anomalías operativas y verificación de integridad del backup SQLite.
* **Resultados y Evidencia**:
  - **Módulo de Agregación Analítica (`app/daily_digest.py`)**:
    * Consulta atómica en modo estricto de solo lectura (`?mode=ro`) a `telemetry_samples`, `operational_events` y `reboot_decisions` sobre la ventana de 24 horas (`now_ts - 86400`).
    * Métricas calculadas con fórmulas rigurosas:
      - Uptime %: `(ok_samples / total_samples) * 100`.
      - Hashrate Promedio: suma de promedios por ASIC activo en la ventana.
      - Eficiencia: promedio ponderado de $\text{Watts} / (\text{TH/s}) = \text{J/TH}$.
      - Shares: porcentaje de aceptación y rechazo sobre deltas reales acumulados.
      - Anomalías e incidentes: conteo de severidades warning/critical y decisiones de reinicio.
    * `inspect_latest_backup()`: lee metadatos en `backups/verified/` con validación de manifest SHA-256 e integridad.
    * `is_digest_due()`: evaluador determinista de fecha calendario y hora local argentina (UTC-3).
    * Rendimiento sobresaliente en producción real (23.2 MB): consulta en **27.2 ms**, render en **0.07 ms** (total 27.3 ms vs SLA < 1000 ms). Cero bloqueos de escritura.
  - **Integración en `app/miner_monitor.py`**:
    * Registrados comandos `/digest` y `/summary` en `CMD_WHITELIST`, `_COMMANDS`, `/help` e índice de ayuda.
    * Hook de despacho matutino automático incorporado en el loop principal de evaluación, respetando la hora configurada (08:00) y blindado contra duplicados con `_LAST_DAILY_DIGEST_DATE`.
    * Persistencia de fecha de envío en `app/state.json`.
    * Documentadas opciones `daily_digest_enabled: true` y `daily_digest_time: "08:00"` en `app/config.example.json`.
  - **Pruebas y Verificación**:
    * Creada la suite `tests/test_daily_digest.py` con 10 pruebas unitarias e integradas (programación, rollover de fecha, inspección de backups, base SQLite temporal con telemetría sintética y benchmark en vivo sobre la BD real).
    * Suite global: **458/458 tests PASS** en 4.69s (0 fallos, 0 errores, 0 regresiones).
    * Compilación Python exitosa con código de salida 0.
    * Monitor en producción (PID 38816) 100% ininterrumpido.
* **Próximo Paso**:
  - Toda la iniciativa **Telegram Max (Specs 031, 032, 033 y 034)** se encuentra 100% implementada y certificada.
  - Proceder con las siguientes expansiones del Plan V3 (`docs/speckit/V3_EXPANSION_PLAN.md`): Detección temprana de falla de ventiladores (Fan Health) y métricas continuas de eficiencia J/TH en telemetría en tiempo real.

---

## [2026-09-07] - Implementación y Cierre de Spec 033 (Miner Maintenance Snooze - /snooze)

* **Objetivo**: Implementar el silenciamiento temporal de alertas, recordatorios periódicos, reportes degradados y autorreinicios por minero o para toda la flota durante ventanas de mantenimiento físico, limpieza o cambio de fuentes/ventiladores vía comandos (`/snooze`, `/unsnooze`, `/snoozed`) y botón táctil 1-Tap `[ 🔕 Silenciar 1h ]`.
* **Resultados y Evidencia**:
  - **Módulo de Dominio Puro (`app/telegram_snooze.py`)**:
    * Parser de argumentos `parse_snooze_args()` con soporte para minutos (`45m`, `30min`), horas (`2h` -> 120m) y acotamiento seguro entre 1 y 1440 min (24h).
    * Predicado de verificación `is_miner_snoozed()` y formateadores `format_snooze_remaining()` y `format_snooze_tag()`.
    * Generador de respuesta para `/snoozed` (`build_snooze_status_text()`).
    * Filtro de episodios `filter_snoozed_episodes()` que suprime alertas de episodios y recordatorios persistentes para mineros silenciados, preservando notificaciones de recuperación.
  - **Integración en `app/miner_monitor.py`**:
    * Extendido `MinerState` con `snooze_until_ts: Optional[float] = None`.
    * Persistencia completa en `load_state()` y `save_state()` en `app/state.json`.
    * Despachador de callbacks: acción `snz` en `_handle_callback_query()` silencia el minero por la duración indicada, responde con notificación toast interactiva y actualiza el teclado a estado asentado `[ 🔕 Silenciado (60m) ]`.
    * Registrados comandos `/snooze`, `/unsnooze`, `/snoozed` en `CMD_WHITELIST`, `_COMMANDS`, y `/help`.
    * **Seguridad Crítica**: Bloqueo absoluto de autorreinicio en el loop de evaluación cuando `is_miner_snoozed` es verdadero (registrado como `AUTO_REBOOT_SNOOZED`).
    * Etiqueta visual en `/status`: Cada minero silenciado muestra `[🔕 Silenciado: Xm rest.]`.
  - **Pruebas y Verificación**:
    * Creada la suite `tests/test_telegram_snooze.py` con 12 tests pasando (parsing, unidades, clamping, predicados, formateo, filtrado de episodios, bloqueo de autorreinicios, callback `snz`, y persistencia en `state.json`).
    * Suite global: **448/448 tests PASS** en 4.50s (0 fallos, 0 errores, 0 regresiones).
    * Compilación Python exitosa con código de salida 0.
    * Monitor en producción (PID 38816) 100% ininterrumpido.
* **Próximo Paso**:
  - Proceder con la Spec 034 (`034-daily-executive-digest`) para el reporte diario consolidado a hora programada y bajo demanda vía `/digest`.

---

## [2026-09-07] - Implementación y Cierre de Spec 032 (Telegram Visual Charts - /chart)

* **Objetivo**: Implementar la generación y envío nativo de gráficos PNG al chat de Telegram (`/chart [miner|fleet] [horas]`) y cablear el botón táctil `[ 📊 Ver Gráfico ]` de la Spec 031, con renderizado 100% en memoria RAM (BytesIO) y cero archivos temporales en disco.
* **Resultados y Evidencia**:
  - **Motor de Renderizado (`app/telegram_charts.py`)**:
    * Consultas a SQLite en modo estricto de solo lectura (`?mode=ro`) sobre `telemetry_samples`.
    * Renderizado en 2 subpaneles con Matplotlib:
      - Panel superior: Curva de hashrate (verde esmeralda) con área sombreada, umbral nominal (ámbar discontinuo), y promedio de la ventana.
      - Panel inferior: Curva de temperatura máxima de chips (rojo carmesí) y velocidad de ventiladores (azul punteado).
    * Rendimiento medido sobre base real de 23.2 MB: consulta en **2.2 ms**, renderizado en **217.5 ms** (total 219.7 ms vs SLA < 1.5s).
    * Cero basura en disco: Todo se transmite directamente mediante `io.BytesIO` como `image/png`.
  - **Integración en `app/miner_monitor.py`**:
    * Añadido helper `send_telegram_photo()` con envío multipart a `sendPhoto`.
    * Registrado comando `/chart` en `CMD_WHITELIST`, `COMMAND_REGISTRY` y en el índice de `/help`.
    * Cableada la acción de callback `chart:<miner_id>` en `_handle_callback_query()`.
  - **Pruebas y Verificación**:
    * Creada la suite `tests/test_telegram_charts.py` con 6 pruebas unitarias e integradas (firma mágica PNG, extracción de muestras, renderizado de flota, manejo de mineros vacíos, mock de `sendPhoto` y despacho de callback).
    * Documentación actualizada en `README.md` y `docs/speckit/RUNBOOK.md`.
  - **Suite Global**: **436/436 tests PASS** en 4.45s (0 fallos, 0 errores, 0 skips).
  - **Producción**: Monitor vivo (PID 38816) con >267 horas ininterrumpidas.
* **Próximo Paso**:
  - Proceder con la Spec 033 (`033-miner-maintenance-snooze`) para el silenciamiento temporal de alertas durante tareas de mantenimiento físico.

---

## [2026-09-07] - Implementación y Cierre de Spec 031 (Telegram Interactive Callbacks & Inline Keyboards)

* **Objetivo**: Implementar la primera especificación de la iniciativa Telegram Max (V3), incorporando botones táctiles interactivos (Inline Keyboards con 1-Tap) en las alertas de episodios para diagnósticos instantáneos y un flujo de confirmación segura de reinicio en dos toques con expiración a los 60 segundos y estricta autenticación de chat_id.
* **Resultados y Evidencia**:
  - **Fases 1 y 2 (Gemini 3.8 Flash High)**:
    * Creado el módulo puro `app/telegram_callbacks.py` con `CallbackTokenRegistry` (máximo 10 tokens en memoria, TTL de 60s), analizador de gramática (`diag`, `chart`, `snz`, `rb_req`, `rb_cfm`, `rb_ccl`, `noop`) cumpliendo el límite estricto de 64 bytes de la API de Telegram, y constructores de teclados (`build_alert_keyboard`, `build_confirmation_keyboard`, `build_settled_keyboard`).
    * Creada la suite inicial de 9 pruebas en `tests/test_telegram_callbacks.py`.
  - **Fase 3 (Claude Sonnet 4.6 Thinking)**:
    * Implementados los helpers HTTP seguros `answer_callback_query` y `edit_message_reply_markup` en `app/miner_monitor.py`.
    * Extendida `send_telegram` y la tupla de la cola de envíos para adjuntar opcionalmente `reply_markup`.
    * Integrado el despacho de `callback_query` en `_poll_telegram_updates()` y la función de módulo `_handle_callback_query()`.
    * Conectada la generación automática de teclados en `app/alert_episodes.py` para alertas de episodio único.
  - **Fases 4 y 5 (Gemini 3.8 Flash High)**:
    * Añadidas pruebas de integración en `tests/test_telegram_callbacks.py` (14 tests unitarios en total) validando el rechazo inmediato de usuarios no autorizados (`show_alert=True`), expiración limpia de tokens (>60s), flujo de confirmación y flujo de cancelación.
    * Documentación actualizada en `README.md`, `docs/speckit/RUNBOOK.md` y evidencia consolidada en `specs/031-telegram-interactive-callbacks/evidence.md`.
  - **Suite Global**: **430/430 tests PASS** en 4.34s (0 fallos, 0 errores, 0 skips).
  - **Producción**: Monitor vivo (PID 38816) con >267 horas de ejecución ininterrumpida y 0 alertas espurias.
* **Próximo Paso**:
  - Proceder con la Spec 032 (`032-telegram-visual-charts`) para la generación y envío nativo de gráficos visuales PNG vía Telegram (`/chart`).

---

## [2026-09-07] - Certificación Oficial de Release v2.0.0 y Normalización Integral de Documentación

* **Objetivo**: Concluir la sincronización de ramas (`main` y `codex/022-adaptive-acquisition`), publicar el tag de release `v2.0.0`, formalizar la Enmienda 1.5.0 de la Constitución adoptando Gemini 3.8 Flash High como motor primario, y ejecutar la normalización integral de la documentación del proyecto (30 especificaciones, guías de SpecKit, Runbook operativo y README raíz).
* **Resultados y Evidencia**:
  - **Sincronización Git y Tag v2.0.0**:
    * Publicado tag oficial `v2.0.0` sobre el commit de certificación `79f0172`.
    * Sincronizada la rama principal `main` mediante fast-forward limpio sin alterar el árbol de trabajo ni interrumpir el proceso de producción vivo (PID 38816). Ambas ramas y GitHub alineadas al 100%.
  - **Enmienda 1.5.0 a la Constitución**:
    * Actualizado el Principio VII en `.specify/memory/constitution.md` y las directivas en `AGENTS.md` y `prompt.txt` para incorporar a Gemini 3.8 Flash High (y Gemini 3.7 compatible) como motor primario, preservando la delegación escalada hacia Claude Sonnet 4.6 (Thinking) y Claude Opus 4.6 (Thinking).
  - **Normalización Documental**:
    * `README.md`: Documentadas las herramientas auxiliares de V2 (Prometheus, Grafana, Backups, Watchdog, Release Audit), corregida errata de ruta en `tools/debug_4028.py` y actualizado alcance a Specs 001-030.
    * `docs/speckit/`: Normalizados `README.md`, `RUNBOOK.md` (con procedimientos para `metrics_exporter.py` y `release_audit.py`), `TECHNOLOGY_STRATEGY.md`, `INTERFACE_STRATEGY.md` (decisión formal `no_build`), `HASHCORE_TOOLKIT_STRATEGY.md` y `MINER_DIAGNOSTICS.md`.
    * `specs/`: Normalizadas las casillas y checklists de Definition of Done en Specs 022, 023, 024 (`blocked_external`), 025, 026 y 028, y archivadas formalmente las fundaciones 001 y 002. Cero tareas pendientes en la totalidad de los 30 paquetes.
  - **Suite Global**: **416/416 tests PASS** en 3.51s con 0 fallos y 0 errores.
  - **Producción**: Monitor vivo (PID 38816) con >267 horas de operación ininterrumpida y heartbeat fresco.
* **Próximo Paso**:
  - Modo de operación pasiva y monitoreo estable en producción.

---

## [2026-09-07] - Implementación, Validación y Aprobación Formal de Spec 029 (V2 Release Stabilization - APPROVE)

* **Objetivo**: Ejecutar el congelamiento de código y dependencias, auditar los estados terminales de Specs 021-028, validar exhaustivamente las 25 filas de la matriz de regresión R001-R025, certificar la recuperación de datos mediante simulacro de restore SQLite y formalizar la decisión de aprobación del Release Candidate V2 tras más de 168 horas de soak ininterrumpido en producción.
* **Resultados y Evidencia**:
  - **T001 (Auditoría de Estados Terminales)**: Verificadas las 8 especificaciones predecesoras con disposiciones terminales formales: Spec 021 (`accepted`), Spec 022 (`accepted`), Spec 023 (`accepted`), Spec 024 (`blocked_external`), Spec 025 (`accepted`), Spec 026 (`accepted`), Spec 027 (`no_build`) y Spec 028 (`accepted`). Cero paquetes pendientes.
  - **T002, T005 & T006 (Freeze Manifest y Herramienta de Auditoría)**:
    * Creada la herramienta desacoplada `tools/release_audit.py` y la suite `tests/test_release_gate.py` (12 tests unitarios).
    * Calculado el digest determinista de runtime payload SHA-256: `58d451f19363a266b36c5d3fb17442ef837ea0ed31a443990098eed2c0153b42` sobre exactamente 43 archivos de código y configuración.
    * Generado el artefacto canónico sanitizado en `artifacts/v2_release_candidate_manifest.json` (0 contraseñas, 0 tokens de Telegram, 0 IPs privadas, 0 rutas absolutas de disco).
  - **T003, T007-T010 (Matriz de Regresión R001-R025)**:
    * Evaluadas las 25 filas de `regression-matrix.md` con resultado 100% satisfactorio (`pass` o `not_applicable` respaldado por evidencia terminal).
    * Suite global ejecutada: **416/416 tests PASS** en 3.46s (0 fallos, 0 errores, 0 skips).
    * Sintaxis y compilación: 27 archivos Python py_compilados, 5 scripts PowerShell validados sin errores de parser, 4 archivos JSON de runtime verificados.
    * Invariantes de máquina de estados, auto-reboot, Telegram, deduplicación de polling y mutex exclusorio verificados determinísticamente.
  - **T011 (Simulacro de Backup Online y Staging Restore - R020)**:
    * Ejecutado drill sobre la base real de producción `data/miner_alerts.db` (23.2 MB respaldados en caliente en 2.529s, SHA-256 `0b5e53e8...`).
    * Restauración en staging con resultado `passed` (`checksum_ok: true`, `integrity_ok: true`, `schema_ok: true`, `counts_ok: true`).
  - **T016-T017 (Observación Continua en Producción - R024 y R025)**:
    * El monitor en producción (PID 38816) acumuló **267.2 horas continuas de uptime (961.928 segundos > 168 horas objetivo)** y **31.695 ticks completados** con `queue_depth: 0`, 0 fallos de acción y 0 alarmas espurias.
  - **T020 (Decisión Formal de Release)**:
    * Decisión formal adoptada: **`APPROVE`**.
    * Se certifica el Release Candidate V2 de Miner Alerts listo para operación definitiva.
* **Próximo Paso**:
  - Preparar el commit final y el tag de release `v2.0.0` en Git.

---

## [2026-08-30] - Evaluación y Cierre Formal de Spec 027 (Operator Interface Decision - no_build)

* **Objetivo**: Ejecutar el scorecard de flujos de trabajo W01-W06 de la Spec 027 tras la superación de sus dependencias (Spec 025 y Spec 028) para determinar si las interfaces existentes (Telegram, Grafana y Dashboard HTML estático) satisfacen la totalidad de requerimientos del operador sin necesidad de construir un nuevo servicio web local (FastAPI/Uvicorn/HTMX).
* **Resultados y Evidencia**:
  - **T001 (Verificación de Dependencias)**: Comprobada la presencia de evidencia de salida válida en Spec 025 (snapshot, exporter, dashboards Grafana y hook de monitor) y Spec 028 (backup SQLite 256 páginas, retención 14/8/12 y simulacro de restore staging superado en 6.2s). Gate desbloqueado.
  - **T002-T003 (Scorecard de Flujos W01-W06)**: Completadas 30 corridas cronometradas (3 repeticiones consecutivas por par interfaz-flujo).
    * **W01** (Salud del monitor y pipeline): Telegram `/status` (2.1s << 30s objetivo) y Grafana `monitor_liveness.json` (1.4s).
    * **W02** (Mineros requiriendo atención): Telegram `/status` (2.2s << 30s objetivo) y HTML estático (2.9s).
    * **W03** (Episodio irregular más reciente): Telegram `/diagnose` (3.3s << 90s objetivo) y HTML estático (11.0s).
    * **W04** (Causa y procedencia de reinicio): Telegram `/diagnose` (3.2s << 90s objetivo) y HTML estático (9.2s).
    * **W05** (Degradación local vs flota): Grafana `fleet_overview.json` (2.7s << 60s objetivo) y HTML estático (4.0s).
    * **W06** (Recuperación vs degradación persistente): Grafana `fleet_overview.json` (4.1s << 120s objetivo) y HTML estático (15.0s).
    * **Campos P1 Faltantes**: Exactamente **0** campos faltantes. Cada flujo P1 cuenta con al menos un dueño probado.
  - **T004 (Decisión Formal)**: Conforme a FR-002, FR-013 y `contracts/operator-interface.md`, se aprueba la resolución **`no_build`**. Se evita el consumo de recursos, dependencias superfluas y superficie de ataque al no construir un servidor web redundante.
  - **T005 (Auditoría de Rutas Condicionales)**: Verificada la ausencia total de `app/operator_api.py`, `app/operator_views.py`, `templates/operator/`, `tests/test_operator_api.py`, `requirements-interface.txt` y servicios asociados. Tareas condicionales T006-T017 marcadas N/A.
  - **T018 (Sincronización Documental)**: Actualizados `evidence.md`, `workflow-scorecard.md`, `tasks.md`, `ROADMAP.md` y `DELIVERY_PLAN.md`.
  - **Suite Global**: **404/404 tests PASS** en 3.8s (0 fallos, 0 errores, 0 skips). El monitor en producción PID 38816 permanece 100% inalterado y aislado.
* **Próximo Paso**:
  - Proceder con la **Spec 029 (V2 Release Stabilization)**: integración global, auditoría de consistencia documental, simulacro de restore cruzado y preparación del Release Candidate.

---

## [2026-08-30] - Superación Formal de Gate D+3 (72h Soak) de Spec 022 y Cierre de Spec 023 y Spec 025

* **Objetivo**: Verificar el cumplimiento formal de las 72 horas continuas de soak en producción para Spec 022 (Adaptive Acquisition) bajo PID 38816, habilitar la ruta de lectura de incidentes en producción (Spec 023 T019) y cablear la instantánea atómica de observabilidad en el monitor (Spec 025 T006).
* **Resultados y Evidencia**:
  - **Spec 022 Gate D+3 PASSED**: Alcanzadas **73.45 horas de uptime continuo (264.431 segundos > 259.200s requeridos)** bajo PID 38816 con **8.766 ticks completados**, `queue_depth: 0`, 100% de cobertura de supervisión watchdog (`unhealthy_count=0`, `action_count=0`) y 0 fallos. Spec 022 queda 100% cerrada.
  - **Spec 023 Activación**: Activada la ruta de análisis e inferencia de causa raíz en lectura `/diagnose` y tableros. Todos los 344 tests deterministas pasan.
  - **Spec 025 Integración Hook (T006)**: Incorporada la función `write_monitor_metrics_snapshot_safe` en el ciclo final de cada tick completado en `app/miner_monitor.py` bajo el flag seguro `metrics_snapshot_enabled`.
  - **Suite Global**: **404/404 tests PASS** en 4.38s (0 fallos, 0 errores, 0 retrazos).

---

## [2026-08-30] - Implementación de Módulos Base, Exporter y Dashboards de Spec 025 (Prometheus & Grafana - T001-T005, T007-T011)

* **Objetivo**: Implementar el generador de instantáneas sanitizadas de métricas `app/metrics_snapshot.py`, el exportador HTTP Prometheus `tools/metrics_exporter.py`, la configuración de Docker Compose aislada y los tableros de Grafana sin comprometer la ejecución viva del monitor.
* **Resultados y Evidencia**:
  - **T001**: Definidas y registradas las 26 familias de métricas de Prometheus con el presupuesto estricto de cardinalidad: 23 series globales + 20 por minero (máximo 103 series para la flota de 4 mineros, con techo de seguridad de pruebas <=128).
  - **T002**: Creada la suite `tests/test_metrics_snapshot.py` (7 tests unitarios) cubriendo: valores numéricos estrictamente finitos (rechazo de NaN e Infinito), rechazo de direcciones IP en nombres de mineros, validación estricta de enums (estados, calidad de adquisición, estado del collector, entregas de Telegram), detección de duplicados y detección de obsolescencia a los 60 segundos.
  - **T003-T004**: Creada la suite `tests/test_metrics_exporter.py` (6 tests unitarios) cubriendo: exposición solo de salud ante snapshots obsoletos o ausentes (sin filtrar métricas antiguas de mineros), cardinalidad exacta de 103 series con flota activa y 101 series ante mineros offline con nulos, tiempo de raspado <250 ms (~10 ms medidos), verificación estática de Compose (imágenes fijadas, puertos loopback 127.0.0.1, exportador sin puertos públicos y 0 montajes prohibidos) y validación JSON de tableros.
  - **T005 & T007**: Implementados `app/metrics_snapshot.py` y `tools/metrics_exporter.py` en Python puro con la biblioteca estándar (0 dependencias externas en el entorno local).
  - **T008-T010**: Creados `Dockerfile.metrics`, `docker-compose.observability.yml`, `observability/prometheus/prometheus.yml` y los 3 tableros Grafana provisionados (`fleet_overview.json`, `monitor_liveness.json`, `telegram_delivery.json`). Agregadas las claves por defecto en `app/config.example.json` (`metrics_snapshot_enabled: false`).
  - **T011**: Suite global en **404/404 tests PASS** en 3.58s (0 fallos, 0 errores). El monitor en producción continuó superando las 60 horas continuas de soak bajo PID 38816 con 0 colas y 0 demoras.
* **Próximo Paso**:
  - Aguardar la finalización formal del Gate D+3 de Spec 022 a las 16:11:40 para cablear el hook al monitor (T006) e iniciar la activación en vivo de Spec 023 y Spec 025.

---

## [2026-08-29] - Implementación y Cierre de Spec 028 (Backup, Retention & Restore - T001-T014)

* **Objetivo**: Implementar la herramienta desacoplada de backups SQLite en caliente (`tools/event_store_backup.py`), retención determinista UTC 14/8/12, simulacro de recuperación en staging con detección de alteraciones y tarea programada de Windows (`tools/install_backup_task.ps1`).
* **Resultados y Evidencia**:
  - **T001**: Verificados el modo WAL (`PRAGMA journal_mode = WAL`) y versión de esquema v6. Verificados los requisitos de directorio con marcador de raíz `.miner-alerts-backup-root-v1` y rutas estrictamente disjuntas.
  - **T002-T004**: Creada la suite `tests/test_event_store_backup.py` con 10 tests cubriendo: backups concurrentes en caliente por lotes de 256 páginas, generación de manifiesto v1 con SHA-256, verificación de integridad SQLite (`PRAGMA integrity_check == 'ok'`), validación de marcador de raíz, prevención de rutas superpuestas, exclusión mutua mediante `.backup.lock` (`skipped_locked`), umbral de espacio libre en disco (`blocked_space`), retención determinista por unión UTC (14 días, 8 semanas, 12 meses) con dry-run seguro, simulacro de restore en staging con detección de manipulación de bytes y prohibición de sobrescribir la base de datos viva.
  - **T005-T007**: Implementada `tools/event_store_backup.py` con backups online paginados (`pages=256, sleep=0.01`), manifiesto v1 y promoción atómica de directorios a `verified/<backup_id>`.
  - **T008-T010**: Implementado el comando `--action restore-staging`, el instalador de tarea programada de Windows `tools/install_backup_task.ps1` (`pythonw.exe`, `Highest`, `IgnoreNew`, 5 min límite) y documentado el runbook manual de recuperación de desastres en `docs/speckit/RUNBOOK.md`.
  - **T011-T014**: Ejecutado simulacro real en producción sobre la base activa `data/miner_alerts.db` (20.4 MB respaldados en 6.2 segundos, backup ID `20260830T013845Z_b4dbb112`, SHA-256 verificado, resultado `passed` en restore staging). Suite global crece a **391/391 tests PASS** en 3.4s. El monitor en producción continuó operando de forma ininterrumpida sin impacto en latencia ni en la cola.
* **Próximo Paso**:
  - Avanzar con Spec 025 (Métricas de Prometheus y Grafana) o aguardar el cierre del Gate D+3 de Spec 022 mañana a las 16:11:40.

---

## [2026-08-29] - Implementación y Cierre de Spec 026 (Hashcore Capability Inventory - T001-T018)

* **Objetivo**: Implementar la herramienta desacoplada de inventario de capacidades de Hashcore Toolkit (`tools/hashcore_inventory.py`), verificar metadatos de instalación local y asegurar el bloqueo de subprocesses ante ausencia de allowlist aprobada.
* **Resultados y Evidencia**:
  - **T001**: Auditadas las costuras de acción de Hashcore en `app/miner_monitor.py:1654-1768` (SHA-256: `c31064ce2d5120ff26506acd91affb58b8ded64ff463cab0424f18ad70034039`). Plantillas verificadas para `reboot` y `restart`.
  - **T002-T003**: Línea base estática reproducida en modo metadata-only con cero subprocesos. Allowlist preservada vacía con resultado formal `blocked`.
  - **T004-T006**: Creada la suite `tests/test_hashcore_inventory.py` con 10 tests cubriendo: modo metadata-only sin subprocesos, rechazo de allowlists ausentes/mismatched, rechazo estricto de plantillas/IPs/rutas en argv, invalidación por cambio de huella digital, clasificación de comandos y límites de ejecución (shell=False, DEVNULL, no-window, 10s timeout, 64 KiB).
  - **T007-T011**: Implementada `tools/hashcore_inventory.py` sin imports del monitor. Verificados metadatos reales de instalación: `hashcore-toolkit.exe` (808.960 bytes, SHA `9db1842103c6abdea30913b9a3b0e0abcb3ba2fd103b689c45caee98312847eb`, versión PE `1.6.0+167`), wrapper `toolkit_cli.bat` (181 bytes, SHA `2c204d87365dd94231b62c42cde5f5adbc219f1842cfae3c4bead35f4a338daf`). Artefacto canónico generado en `artifacts/spec026-hashcore-inventory.json`.
  - **T012-T014**: Evaluación de capacidades completada con 0 candidatos aceptados ante allowlist bloqueada.
  - **T015-T018**: Suite global en **381/381 tests PASS** (0 fallos, 0 errores). Monitor en producción 100% aislado e inalterado.
* **Próximo Paso**:
  - Avanzar con Spec 025 (Métricas de Prometheus y Grafana) o Spec 028 (Backups de Base de Datos).

---

## [2026-08-29] - Ejecución del Discovery Gate de Spec 024 (Electrical Source Discovery - T001-T004)

* **Objetivo**: Relevar las fuentes de telemetría eléctrica del parque minero, auditar la no-equivalencia entre señales DC de hashboard y tensión de red AC, y emitir el reporte formal de capacidades sin comprometer el monitor en producción.
* **Resultados y Evidencia**:
  - **T001**: Auditados los 4 mineros Antminer S19j Pro. Se verificó que `chain_voltage_mv_avg` (~13-14.5 V DC) y `chain_power_w_total` (~3000 W DC) corresponden estrictamente a la etapa de conversión interna de las placas hashboards y no a la entrada de red eléctrica AC.
  - **T002**: Generado el reporte formal sanitizado de capacidades en `artifacts/spec024-electrical-capability-report.json` conforme a `contracts/capability-report.md`.
  - **T003**: Registrada formalmente la ausencia de hardware dedicado de medición de energía AC (PDU inteligente, UPS de red o medidor Modbus/SNMP) en la subred de minería.
  - **T004**: Decisión formal del Discovery Gate: **`blocked` (missing_hardware_dependency)**. En cumplimiento de la Constitución, se retienen adaptadores y dependencias hasta contar con hardware físico real verificado, evitando telemetría falsa o inferencias no probadas.
* **Próximo Paso**:
  - Continuar con paquetes independientes de software puro (Spec 025 / Spec 028) mientras concluye el soak D+3 de Spec 022.

---

## [2026-08-29] - Superación Formal del Gate D+1 de Spec 022 (Adaptive Acquisition)

* **Objetivo**: Auditar el período de soak de 24 horas continuas en producción para Spec 022, verificar estabilidad de adquisición adaptativa concurrente, registrar evidencia y evaluar el backlog operativo.
* **Auditoría Runtime y Evidencia (42.7h continuas post-rollout)**:
  - Proceso de producción PID 38816 iniciado el 2026-08-27 16:11:40 alcanzó **153.800 segundos continuos (42.72 horas > 86.400s requeridos)** sin reinicios, caídas ni fallos de proceso.
  - Heartbeat operativo: **5.099 ticks completados** sin interrupción con `queue_depth = 0`.
  - Base SQLite: 2.036 muestras de telemetría procesadas e ingeridas en paralelo con 2 workers.
  - Watchdog de vida: 2.563 evaluaciones continuas ejecutadas con 0 alarmas, 0 fallas (`healthy=true`, `reasons=none`, `action_count=0`).
  - Seguridad de flota: Cero reinicios espurios o bloqueos. Los 4 mineros operan 100% estables en `STATE_OK` a ~95-99 TH/s.
  - Verificación formal: `tools/observe_liveness.py --stage d1 --since 2026-08-27T16:12:00` confirmó `passed: true` sin fallos.
  - Gate D+1 superado formalmente. Gate D+3 (72h soak) activo en curso hasta 2026-08-30 16:11:40 (~29h restantes).
* **Próximo Paso**:
  - Preparar el cierre de Spec 022 (T014) y coordinar el siguiente paquete del programa (Spec 023 T019 tras cierre de D+3, o descubrimiento de hardware en Spec 024).

---

## [2026-08-27] - Cierre de Spec 021 (D+3), Enmienda Constitucional v1.4.0 y Activación en Producción de Spec 022 (T009-T013)

* **Objetivo**: Cerrar formalmente Spec 021 con evidencia de 77h de soak en producción, ratificar la Constitución v1.4.0 con la regla de maximización de Gemini 3.7 y completar la validación, cableado y activación en producción de Spec 022 (Adaptive Acquisition).
* **Cierre de Spec 021 (Liveness Watchdog)**:
  - Uptime continuo de 77h 20m (278.4k s > 259.2k s), PID 8520 estable, 9.193 ticks y 0 incidentes. 1 auto-reboot legítimo en minero 25 auditado. Spec 021 cerrada formalmente al 100%.
* **Enmienda Constitucional v1.4.0 y Actualización de AGENTS.md**:
  - Ratificada la Enmienda 1.4.0 formalizando la regla de *Maximización de Gemini 3.7 Flash High y Delegación Escalada*: Gemini 3.7 como motor primario (análisis, lógica pura, schemas, suites completas de tests, benchmarks y trazabilidad en turnos iterativos y bounded); Claude Sonnet 4.6 (Thinking) reservado para concurrencia viva multi-hilo en producción y máquinas de estado/reboot; Claude Opus 4.6 (Thinking) estrictamente para deadlocks cíclicos.
* **Spec 022 T009 y T011 (Claude Sonnet 4.6 Thinking)**:
  - T009: Aislamiento read-only de dataclasses congeladas `DiagnosticProbeResult` y `EpisodeDiagnosticEnvelope`; filtrado mecánico de envelopes DIAGNOSTIC en `dispatch_authoritative`; 0 mutaciones a `miner_states`.
  - T011: Validación estricta de invariantes: `acquisition.py` verificado libre de imports de `hashcore`, `subprocess`, mutación de streaks, tokens de Telegram o startup guard. 24 nuevos tests en `tests/test_t009_t011_invariants.py`.
* **Spec 022 T012 (Gemini 3.7 Flash High)**:
  - Implementado `tests/test_t012_shadow_and_rollback.py` con 3 tests formales: paridad determinista (SC-006 / FR-012), ensayo de rollback dinámico a 4 fases con 0 leases residuales (FR-012 / SC-006) y simulación de 100 ciclos de flota con presupuesto estricto de requests y memoria de `PollHealth` acotada a `maxlen=32` (SC-005 / FR-011 / FR-014).
* **Spec 022 T013: Cableado en Loop y Activación en Producción**:
  - Cableado de `BoundedAcquirer` en el loop principal `while True:` de `app/miner_monitor.py` con fallback completo al método secuencial sincrónico en caso de excepción.
  - Eliminado UTF-8 BOM de `app/config.json` y activado `"adaptive_acquisition_enabled": true`.
  - Servicio NSSM `MinerAlerts` reiniciado exitosamente en producción con nuevo **PID 38816** (16:11:40). Mutex adquirido limpiamente.
  - Startup safety guard activo (600s). Logs confirman: `ADAPTIVE_ACQUISITION enabled=true workers=2` y `acquirer_ready=true endpoints=4`.
  - Watchdog confirmó recuperación a las 16:11:54 y permanece 100% `healthy=true`. Ticks avanzando continuamente con `queue_depth=0`.
* **Estado Final de Pruebas**: **371/371 tests PASS** (0 fallos, 0 errores, 0 skips).
* **Próximo Paso**:
  - Observación activa del gate D+1 (2026-08-28 16:11:40) y D+3 (2026-08-30 16:11:40) de Spec 022. T014 sincronización documental.

---

## [2026-08-26] - Spec 023 Fases 3 y 4 (Adaptador /diagnose, Dashboard, Validación Determinista y Rendimiento T014-T018)

* **Objetivo**: Integrar el adaptador defensivo en `/diagnose`, proyectar evaluaciones en el dashboard de operaciones sin duplicar scoring, formalizar la validación determinista SC-001 a SC-004 y probar latencia/consultas acotadas SC-005 a SC-007.
* **Trabajo Realizado por Sonnet 4.6 (Thinking)**:
  - **Spec 023 T014 (Adaptador Telegram `/diagnose`)**: Integrado bloque defensivo en `app/miner_monitor.py:2182-2360` tras `incident_fusion_enabled`. Mide latencia con `time.monotonic()`; ante $\ge 2.0$s o excepción de BD, aplica fallback incondicional a `build_miner_diagnosis_text`. Invariantes de acción preservados (0 mutaciones de estado/cooldowns). 8 nuevos tests en `tests/test_t014_diagnose_adapter.py`.
  - **Spec 023 T015 (Dashboard de Operaciones)**: Integrado `incident_assessments` en `tools/operations_dashboard.py` con consulta acotada `_latest_assessments` y renderizado puro `_render_assessment_rows` (fecha, sujeto, estado, ruleset, digest). Invariante FR-011 verificado: cero llamadas a funciones de inferencia o scoring en el dashboard. 10 nuevos tests en `tests/test_operations_dashboard.py`.
* **Trabajo Realizado por Gemini 3.7 Flash High**:
  - **Spec 023 T017 (Validación Determinista SC-001 a SC-004)**: Creado `tests/test_t017_deterministic_validation.py` con 17 pruebas formales. Demostrado determinismo del digest SHA-256 ante 25 permutaciones de entrada; no-confirmación por timing/proximidad temporal (techo `suspected`); visibilidad explícita de contradicciones y missing evidence con pie de seguridad; no-causalidad eléctrica en patrones de flota sin PDU externa e invariante de 0 campos de acción en `IncidentAssessment`.
  - **Spec 023 T018 (Rendimiento, Latencia < 2s y Crecimiento de BD)**: Creado `tests/test_t018_performance_and_growth.py` con 4 pruebas de estrés y límites. Poblada base de 24h (2.880 muestras de telemetría para 4 mineros + eventos + decisiones + firmware); comprobada latencia de evaluación de 0.08s (muy por debajo de los 2.0s de presupuesto, SC-005); número de queries estrictamente acotado a 6 ($O(1)$, no $O(N)$, FR-014); guardado repetido 50 veces verificado idempotente (1 sola fila persistida, sin crecimiento de tamaño de BD, SC-007); invariante de 0 mutaciones ni dependencias de acción (SC-006).
  - **Auditoría y Mantenimiento de Entorno**: Resolución de conflicto de hook de telemetría, actualización de `specs/023-incident-evidence-fusion/tasks.md` y `evidence.md`, sincronización de `docs/speckit/ROADMAP.md` y preparación de `prompt.txt`.
* **Estado Final de Pruebas**: **344/344 PASS** (0 fallos, 0 errores, 0 skips).
* **Pendiente**:
  - **T019**: Ventana de activación controlada en producción y observación D+0/D+1/D+3 tras salida de Spec 022.
  - **Gate D+3 Spec 021**: Cierre final de soak y autorización para activación de Spec 022.

---

## [2026-08-17] - Spec 023 Fases 1-3 (evidence_fusion.py, Renderer, DB Persistence) y Trabajo Independiente Gemini 3.6

* **Objetivo**: Completar los contratos rojos de Spec 023, implementar el módulo puro `app/evidence_fusion.py`, la persistencia idempotente en EventStore, el renderizador semántico y las validaciones/fixtures independientes.
* **Trabajo Realizado por Sonnet 4.6 (Thinking)**:
  - **Spec 023 T004-T007 (Red Contracts)**: Creados 43 tests de contratos rojos en `tests/test_evidence_fusion.py` y `tests/test_event_store.py` cubriendo techos de confianza (`compute_confidence_ceiling`), max cause level (`max_cause_level`), fixtures de replay (`detect_fleet_pattern`, `is_within_attribution_window`), tablas aditivas `incident_assessments` / `assessment_fact_refs` e invariantes de acción (cero imports de Hashcore/miner_monitor).
  - **Spec 022 T007 (Persistencia de Calidad v6)**: Bump de `SCHEMA_VERSION` a 6 en `app/event_store.py`, agregadas columnas nullable `acquisition_authority` y `acquisition_reason_code` en `telemetry_samples` y `record_sample`.
  - **Spec 023 T008-T011 (`app/evidence_fusion.py`)**: Creado módulo puro (sin IO, sin wall-clock, sin mutación) con `FusionConfig`, `EvidenceFact`, `CauseHypothesis`, `IncidentAssessment`, `classify_freshness`, `map_clock_quality`, `validate_fact_code`, `sort_facts_canonical`, `compute_evidence_digest`, `compute_confidence_ceiling`, `max_cause_level`, `evaluate_hypothesis`, `detect_fleet_pattern`, `is_within_attribution_window`.
  - **Spec 023 T012 (Persistencia DB)**: Tablas `incident_assessments` e `assessment_fact_refs` creadas en `EventStore`, índice único `ux_assessment_replay` e implementación de `save_assessment` (idempotente) y `load_assessment`.
* **Trabajo Realizado por Gemini 3.6 Flash High**:
  - **Spec 023 T013 (`app/evidence_fusion.py`)**: Funciones puras de renderizado `render_assessment_text` y `render_assessment_telegram` en 6 secciones estrictas (`contracts/incident-assessment.md`) con pie de página `[LECTURA / SIN ACCION AUTOMATICA]`. Pruebas unitarias en `TestSharedSemanticRenderer`.
  - **Spec 023 T016 (`app/config.example.json`)**: Agregadas claves por defecto `incident_fusion_enabled: false`, `incident_fusion_context_hours: 24`, `incident_fusion_fleet_window_seconds: 60`.
  - **CHK-GEM-01**: Creado `tests/test_evidence_fusion_fixtures.py` con 5 pruebas unitarias puras de invariante de digest SHA-256 e inmutabilidad bajo barajado aleatorio y valores `NaN`/`Infinity`.
  - **CHK-GEM-02**: Función `validate_acquisition_config_dict` en `app/acquisition.py` con topes de 2 workers, 5.0s timeout y 12.0s deadline + tests en `tests/test_acquisition.py`.
  - **CHK-GEM-03**: Dataclasses inmutables `DiagnosticProbeResult` y `EpisodeDiagnosticEnvelope` en `app/acquisition.py` + tests en `tests/test_acquisition.py`.
  - **CHK-GEM-04**: Sincronización de tablas de trazabilidad en `specs/022-adaptive-acquisition/tasks.md` y `specs/023-incident-evidence-fusion/tasks.md`.
* **Estado Final de Pruebas**: **305/305 PASS** (0 fallos, 0 errores, 0 skips).
* **Pendiente Exclusivo para Claude (Sonnet 4.6 / Opus 4.6)**:
  - **T014**: Adaptador `/diagnose` tras feature flag `incident_fusion_enabled` en `app/miner_monitor.py` manteniendo fallback a `build_miner_diagnosis_text`.
  - **T015**: Integración del renderizador en `tools/operations_dashboard.py`.
  - **T017-T018**: Pruebas de integración, latencia < 2s y no causalidad eléctrica de flota sin PDU.
  - **Gate D+3 Spec 021**: Cierre final y activación en producción de Spec 022 (`adaptive_acquisition_enabled=true`).

---

## [2026-08-16] - Spec 023 T004-T007 Red Contracts y Spec 022 T007 Quality Persistence

* **Objetivo**: Completar todos los contratos rojos de Fase 1 de Spec 023 (T004-T007) e implementar la persistencia de calidad de adquisición de Spec 022 (T007).
* **Realizado por Sonnet**:
  - **Spec 023 T004 (FR-003-FR-006)**: 24 pruebas red contract en `tests/test_evidence_fusion.py` para `compute_confidence_ceiling` (techos por staleness, future_skew, unparsed clock, partial_collector, temporal_proximity), `max_cause_level` (offline/low/fleet-sin-PDU/temporal-proximity no pueden confirmar), y `evaluate_hypothesis` (contradicciones visibles, ausencia ≠ contradicción).
  - **Spec 023 T005 (FR-006, FR-007)**: 15 pruebas red contract de fixtures de replay: `detect_fleet_pattern` (aislado vs flota dentro/fuera de ventana), `is_within_attribution_window` (300s ✓, 900s ✓, 901s ✗, pre-acción ✗), y `map_clock_quality` con clock parsed/unparsed de firmware Vnish.
  - **Spec 023 T006 (FR-009, FR-014, SC-007)**: 6 pruebas red contract en `tests/test_event_store.py` para tablas `incident_assessments` / `assessment_fact_refs`, métodos `save_assessment` / `load_assessment` e índice único `ux_assessment_replay`. Fallan correctamente con `AssertionError` hasta T012.
  - **Spec 023 T007 (FR-008, SC-006)**: 4 pruebas de invariantes de acción en `tests/test_evidence_fusion.py`: sin import de hashcore, sin import de miner_monitor, sin campos de acción en `IncidentAssessment`, y `compute_evidence_digest` no muta la entrada. Hacen skip limpio cuando el módulo no existe.
  - **Spec 022 T007**: Bump de `SCHEMA_VERSION` a 6 en `app/event_store.py`. Columnas `acquisition_authority TEXT` y `acquisition_reason_code TEXT` (nullable, NULL en filas legacy) en `telemetry_samples` vía `_TELEMETRY_COLUMNS` y DDL. `record_sample` persiste ambas desde el mapping `telemetry`. 4 tests de migración anteriores actualizados a v6. 4 tests nuevos verdes en `AcquisitionQualityPersistenceTests`.
* **Estado del Test Suite**: 80 tests rojos en `test_evidence_fusion.py` (78 errors `ModuleNotFoundError` + 2 skips), 5 failures esperados en `test_event_store.py` (contratos T006), 211 tests no-rojos PASS (0 fallos, 0 errores, 1 skip). Ningún código de producción, config, estado, servicio ni minero fue modificado.

---

## [2026-08-15] - Spec 023 Red Contracts y Evaluación Gate D+3 (Análisis de Avance Opus)

* **Objetivo**: Evaluar el gate D+3 de Spec 021, inventariar fuentes del EventStore para fusión de evidencia y crear tests red-contract para la configuración y normalización de Spec 023.
* **Realizado por Opus**:
  - **Gate D+3 de Spec 021**: Evaluado a las 19:23 ART — 50.01 h transcurridas de 72.00 h requeridas (~22h restantes). Tarea automática `MinerAlertsLivenessD3` programada para 2026-08-16 17:28 ART. La activación de Spec 022 permanece bloqueada y `adaptive_acquisition_enabled=false` se mantiene como default seguro.
  - **T001 — Inventario de Fuentes**: Confirmadas 5 tablas del EventStore (schema v5) y 6 analyzers reutilizables en `app/`. Hallazgo clave: la persistencia de calidad de Spec 022 (`authority`, `reason_code`) **no está disponible** (T007 de Spec 022 permanece abierto). Las tareas T008+ de Spec 023 quedan bloqueadas hasta completar T007.
  - **T002 — Red Contracts de Configuración (FR-013)**: 14 tests en `tests/test_evidence_fusion.py` cubriendo `FusionConfig.from_mapping`, defaults deshabilitados, validación de rangos (`context_hours` 1-168, `fleet_window_seconds` 30-300), rechazo de NaN/Infinity y fallback exacto.
  - **T003 — Red Contracts de Normalización (FR-001/2/10/12/15)**: 32 tests en `tests/test_evidence_fusion.py` cubriendo `EvidenceFact` inmutabilidad, `classify_freshness`, `map_clock_quality`, `validate_fact_code` fail-closed, `sort_facts_canonical` y `compute_evidence_digest` determinístico SHA-256.
  - **Validación de Tests**: 46 tests nuevos fallan con `ModuleNotFoundError: No module named 'app.evidence_fusion'` (razón roja correcta). 206 tests existentes pasan sin regresiones (0 fallos, 0 errores). Ningún código de producción fue modificado.
  - **Spec Kit Tracking**: T001, T002 y T003 marcados como completados en `specs/023-incident-evidence-fusion/tasks.md` y documentados en `evidence.md`.
* **Pendiente por Agotamiento de Cuota de Opus**:
  - Empaquetar los tests red contract y cambios de documentación en un commit feature-scoped y realizar `git push`.
  - Continuar con las tareas T004-T007 (Red contracts de techos de confianza y migración de base de datos de Spec 023).

---

## [2026-08-15] - Sprint Telegram UX y Estabilización (Análisis de Avance Opus)

* **Objetivo**: Ejecutar el sprint de estabilización y UX Telegram según `prompt.txt` para compactar mensajes, agrupar incidentes, validar gates de Spec 021/022 y preparar el despliegue.
* **Realizado por Opus (Fases 1 a 4 + Validación Parcial)**:
  - **Fase 1 (Relevamiento Determinístico)**: Se inspeccionó el pipeline de alertas (`miner_monitor.py` -> `IrregularEpisodeCoordinator` -> `render_episode_notification_batch` -> `send_telegram` -> `_TELEGRAM_QUEUE` -> `telegram_sender_worker`). Se confirmaron valores en runtime (`coalesce_seconds` = 30.0s, schedule de fallas persistentes = `[300, 600, 900, 1800, 3600, 7200]`, normalización de `/e<ID>` a `/event`). Se verificó que Spec 021 D+1 PASÓ con éxito (`passed: true`, 86700s > 86400s). Se documentó el análisis en `phase1_pipeline_analysis.md`.
  - **Fase 2 (Contratos UX)**: Se establecieron los contratos para alertas compactas (`ALERTA MINEROS`), recuperaciones completas (`RECUPERADOS`), recordatorios de persistencia (`SIGUE AFECTADO · <duración>`), separación por punto `·`, unidades de edad (`30s`/`5m`), y traslado de IPs/detalles diagnósticos exclusivamente a `/e<ID>`.
  - **Fase 3 (Pruebas Primero)**: Se crearon las suites de pruebas determinísticas `tests/test_compact_ux.py` (10 tests de contratos de agrupación, orden y no filtrado de IP) y `tests/test_compact_format.py` (9 tests de formato exacto de línea, cabeceras y separadores).
  - **Fase 4 (Implementación Mínima)**: Se modificó `app/alert_episodes.py` agregando `_format_age()`, `_compact_alert_line()`, `_compact_recovery_lines()`, `_compact_persistent_line()` y actualizando `render_episode_notification_batch()`. Se actualizaron 3 aserciones en `tests/test_alert_episodes.py`. Se confirmó que la lógica del monitor (`app/miner_monitor.py`), state machine, auto-reboot, cooldowns, startup guard, offset y polling permanecieron **sin cambios**.
  - **Fase 5 (Spec 022 Wiring T006 COMPLETADO)**: Con D+1 APROBADO, se integró `AcquisitionConfig` en `app/miner_monitor.py` y defaults deshabilitados en `app/config.example.json` (`adaptive_acquisition_enabled=false`). Se preservó el path secuencial estricto. Se agregó `test_disabled_sequential_fallback_wiring_preserves_sequential_path` en `tests/test_acquisition.py`.
  - **Fase 6 (Validación Formal COMPLETADA)**: Compilación `py_compile` limpia, validación JSON de `config.example.json` correcta y 201/201 tests PASADOS sin regresiones.
* **Pendiente (Fases 7 a 10)**:
  - **Fase 7 (Prueba Telegram Controlada)**: Prueba en vivo de comandos `/help`, `/status`, `/info`, `/e<ID>` con `DBG_TELEGRAM=1`.
  - **Fase 8 (Documentación Spec Kit)**: Actualización completa de Spec Kit docs, `ROADMAP.md` y `DELIVERY_PLAN.md`.
  - **Fase 9 (Deploy Controlado)**: Reinicio controlado del servicio NSSM `MinerAlerts` si corresponde, con validación de PID, mutex y heartbeat.
  - **Fase 10 (Cierre Git)**: Commits feature-scoped y push a `codex/022-adaptive-acquisition`.
* **Archivos Modificados por Opus**:
  - `app/alert_episodes.py` (renderizador compacto)
  - `tests/test_alert_episodes.py` (actualización de aserciones de formato)
  - `tests/test_compact_ux.py` (nuevo)
  - `tests/test_compact_format.py` (nuevo)

## [2026-08-14] - Spec 022: Isolated Adaptive Acquisition Core

* **Objetivo**: Iniciar la adquisicion adaptativa sin conectar ni activar el
  nuevo scheduler en el monitor productivo.
* **Resultado**:
  - Tras 19 h 40 min de observacion saludable autorizada por el propietario, se
    habilitaron solo contratos y modulo aislado; D+1 sigue bloqueando wiring y
    D+3 sigue bloqueando activacion.
  - Se agregaron outcomes API 4028 tipados, envelopes con autoridad/calidad,
    epochs sin catch-up, leases por minero, executor acotado y PollHealth.
  - El transporte acepta solo `summary`/`stats`, mantiene timeout acotado, no
    reintenta y no conserva textos de excepcion o endpoints en diagnosticos.
  - Veinte contratos deterministas prueban orden estable, aislamiento de peers,
    presupuestos numericos, compatibilidad de boards, resultados late y firewall
    de autoridad diagnostica. La suite paso veinte ejecuciones consecutivas.
  - Speckit QA y la regresion completa final 181/181 pasaron; compilacion, JSON,
    trazabilidad, imports de autoridad y diff confirmaron que monitor/config no
    cambiaron. El servicio continuo sano, sin reinicio y con cola cero.
  - Un capturador secuencial read-only cerro T001 con 10 muestras: 40 summary y
    40 stats exitosos, cero retries, ciclo P50 171.031 ms y P95 204.077 ms. El
    artefacto ignorado usa alias genericos y el servicio conservo PID y salud.
    Capturas sin exitos ahora retornan estado/exit code fallido en vez de un OK
    enganoso.
  - `app/miner_monitor.py`, configuracion, servicio, Telegram, mineros y
    Hashcore permanecieron sin cambios.
* **Archivos principales**:
  - `app/acquisition.py`
  - `tests/test_acquisition.py`
  - `specs/022-adaptive-acquisition/`
  - `docs/speckit/ROADMAP.md`
  - `docs/speckit/DELIVERY_PLAN.md`

## [2026-08-13] - Specs 022-029: Implementation Planning Hardening

* **Objetivo**: Convertir adquisicion adaptativa y fusion de evidencia en planes
  implementables y conservadores antes de tocar el runtime productivo.
* **Resultado**:
  - Spec 022 quedo mapeada al request path secuencial real, con envelopes
    autoritativos, calidad/razones estables, deadlines, leases, limites de
    requests y configuracion deshabilitada por defecto.
  - Antes de D+1, Spec 022 sumo fixture sanitizado y test design sin codigo
    ejecutable. Un muestreo pasivo de heartbeat midio seis intervalos entre
    30.191 y 30.275 segundos; un D0 nuevo paso con watchdog sano, cola cero,
    collector recuperado 16/16 y los cuatro mineros OK. No se cruzo el gate de
    implementacion ni se activo adquisicion adaptativa.
  - Spec 023 quedo mapeada a las tablas EventStore y analizadores existentes,
    con reglas exactas para observed/suspected/confirmed, clocks, freshness,
    contradicciones y no-causalidad electrica.
  - Se definieron replay canonico, digest de evidencia, persistencia aditiva e
    idempotente, queries acotadas y un renderer compartido con fallback al
    `/diagnose` actual.
  - El programa, roadmap y calendario ahora reflejan Specs 020/030 completas,
    Spec 021 activa con D+1/D+3 pendientes y Specs 022-029 planificadas.
  - Specs 024-029 ahora tienen trazabilidad explicita de cada FR/SC hacia sus
    tareas, mas una matriz transversal de readiness, bloqueos y riesgos.
  - Spec 025 define un snapshot atomico sin secretos, 26 familias metricas,
    formula de cardinalidad, descarte de series stale y aislamiento estricto de
    exporter/Prometheus/Grafana sin montar config, SQLite ni acciones.
  - Spec 028 define backup SQLite online con promocion atomica, roots marcados y
    disjuntos, retencion UTC 14/8/12 por union y restore solo a staging con
    hash/integrity/schema/counts; no existe restore automatico sobre produccion.
  - Spec 024 confirma que voltage/power de cadenas y errores PSU son evidencia
    interna, no medicion AC; exige hardware real, allowlist read-only, sin scans
    genericos y un collector acotado antes de correlacion electrica.
  - Spec 026 separa inventario estatico de invocacion: se probo sin ejecutar
    procesos una instalacion Toolkit `1.6.0+167` y que su wrapper reenvia `%*`.
    Metadata-only sera el default; la allowlist queda vacia/bloqueada hasta
    evidencia vendor, con binding por fingerprints, argv fijo, timeout,
    no-window, stdin deshabilitado, streams acotados y sanitizacion obligatoria.
  - Spec 027 fija workflows P1, campos, tres repeticiones y tiempos para decidir
    no-build antes de adoptar frameworks. El dashboard estatico genero HTML
    real desde SQLite read-only y paso 5/5 tests, pero la decision sigue
    bloqueada por Specs 025/028. Si hiciera falta MVP, queda limitado a
    loopback, GET/HEAD, queries 50/200 y 30 dias, sin config/acciones/IO miner.
  - Spec 029 convierte el cierre V2 en un gate determinista: estados terminales
    por spec, digest separado del runtime, matriz R001-R025, severidades P0/P1,
    rollback sin tocar SQLite/state y una sola observacion continua de 168 horas
    con reportes diarios y checkpoint a las 72 horas.
* **Validaciones ejecutadas**:
  - Cobertura explicita FR/SC/tareas, links relativos, placeholders,
    consistencia de estados y `git diff --check`.
  - Este bloque es exclusivamente documental; no cambio codigo, config local,
    estado, base productiva, servicio ni mineros.
* **Archivos principales**:
  - `specs/022-adaptive-acquisition/*`
  - `specs/023-incident-evidence-fusion/*`
  - `specs/024-electrical-source-discovery/*`
  - `specs/025-prometheus-metrics/*`
  - `specs/026-hashcore-capability-inventory/*`
  - `specs/027-operator-interface-decision/*`
  - `specs/028-backup-retention-restore/*`
  - `specs/029-v2-release-stabilization/*`
  - `docs/speckit/SPEC_PROGRAM.md`
  - `docs/speckit/ROADMAP.md`
  - `docs/speckit/DELIVERY_PLAN.md`
  - `docs/speckit/HASHCORE_TOOLKIT_STRATEGY.md`

## [2026-08-13] - Spec 021: Monitor Liveness Watchdog (Observation Pending)

* **Objetivo**: Detectar de forma independiente si el servicio existe pero el
  monitor, sus ticks o sus workers dejaron de progresar, sin crear una segunda
  autoridad de acciones sobre mineros.
* **Resultado**:
  - El monitor publica un heartbeat versionado y atomico despues de cada tick
    completo, con evidencia sanitaria de proceso, workers, cola y collector.
  - Un watchdog read-only clasifica servicio, proceso, tick, Telegram y
    collector; deduplica incidentes, reintenta entregas fallidas y cierra al
    recuperar.
  - La tarea Windows usa `pythonw.exe`, no se solapa y soporta una lease de
    mantenimiento con expiracion automatica.
  - La tarea SYSTEM oculta quedo activa, el baseline SCM fue exportado y la
    recuperacion se configuro con demoras 60s/60s/300s.
  - El proceso nuevo publico heartbeat desde el primer tick; tres evaluaciones
    programadas fueron sanas y una prueba Telegram independiente llego al chat.
  - Una finalizacion controlada del arbol de servicio probo la recuperacion SCM:
    tras la primera demora de 60s aparecieron wrapper PID `35836` y monitor PID
    `35788`, con mutex unico, guard de 600s y heartbeat fresco.
* **Validaciones ejecutadas**:
  - Contratos liveness 19/19, regresion reboot/Telegram 26/26 y suite completa
    148/148 PASS.
  - `py_compile`, parser PowerShell, `git diff --check` y escenarios sinteticos
    kill/hang/stale-worker sin autoridad Hashcore: PASS.
  - Activacion y recovery: PID/mutex/guard/config/heartbeat/tarea/SCM,
    finalizacion controlada, reinicio automatico y `/status` productivo PASS;
    no hubo accion Hashcore. Solo D+1/D+3 quedan abiertos.
  - Control D+0 casi dos horas despues: 114 evaluaciones watchdog consecutivas
    sanas, heartbeat fresco, incidente cerrado, flota completa `OK`, collector
    16/16 y cero eventos, decisiones de reboot o acciones desde la recuperacion.
  - Regresion D+0: suite completa 148/148, `py_compile` y `git diff --check`
    PASS. Los gates temporales D+1/D+3 permanecen abiertos.
  - Se agrego un observador read-only reproducible para D+0/D+1/D+3 que cruza
    servicio, heartbeat, cadencia watchdog, persistencia SQLite, collector y
    ausencia de acciones automaticas sin importar autoridad del monitor.
  - La ejecucion D+0 paso y el intento D+1 anticipado fue rechazado con exit 2;
    asi el cierre temporal ya no depende de inspeccion manual ni puede marcarse
    completo antes de las 24/72 horas reales.
  - Ocho contratos del observador y la suite completa 156/156 pasaron junto a
    Speckit QA, compilacion, redaccion, autoridad e ignores.
  - Dos tareas SYSTEM one-shot quedaron listas con `pythonw.exe` para capturar
    automaticamente D+1 y D+3 cinco minutos despues de sus limites reales. Son
    read-only, no se solapan, arrancan al volver el host y escriben solo reportes
    ignorados; no modificaron el servicio ni los mineros.
  - Si una captura bajo `pythonw.exe` falla, ahora deja igualmente un envelope
    JSON sanitizado con razon estable y tipo de excepcion, nunca el mensaje que
    podria contener datos locales. La ruta forzada de error quedo probada.
  - Antes de D+1 se endurecio la evidencia: los reportes pasan por reemplazo
    atomico y el instalador relee principal, ejecutable, argumentos y fecha de
    cada tarea antes de declarar exito.
  - Un control D+0 a las 20:57 paso con 215 evaluaciones sanas, procesos y
    workers frescos, cola cero y ninguna decision/accion automatica. Las tareas
    D+1/D+3 protegidas y su recibo elevado continuaban presentes; la regresion
    completa quedo en 157/157.
  - Un nuevo control read-only a las 21:23 fallo correctamente por el ultimo
    collector `partial` (8/16): 25/26 seguian OFFLINE mientras servicio,
    watchdog, workers y cola estaban sanos. 23/24 habian reiniciado y recuperado
    sin ninguna accion automatica. El hallazgo queda abierto para D+1/D+3.
* **Archivos principales**:
  - `app/liveness.py`
  - `app/miner_monitor.py`
  - `tools/monitor_watchdog.py`
  - `tools/install_watchdog_task.ps1`
  - `tools/observe_liveness.py`
  - `tools/install_liveness_observation_tasks.ps1`
  - `tests/test_monitor_liveness.py`
  - `tests/test_liveness_observation.py`
  - `specs/021-monitor-liveness-watchdog/*`

## [2026-08-13] - Spec 030: Telegram Messaging Quality (Complete / Pushed)

* **Objetivo**: Hacer mas legibles y confiables las respuestas y alertas del bot sin modificar estados, polling ni decisiones de reboot.
* **Resultado**:
  - Los textos largos se normalizan y dividen en partes ordenadas de hasta 3900 caracteres.
  - Los comandos no entran en dedupe/coalescing y, con cola llena, usan un envio directo acotado sin expulsar la respuesta ya pendiente.
  - La cola registra bypass, descarte y error sin copiar payloads; las notificaciones mantienen su politica previa.
  - `/help` y `/help <comando>` salen del registro central y muestran `/rb<ID>`, `/reboot_no_ok` y `/c<code>` como atajos oficiales.
  - Los resultados de auto-reboot enlazan `/why` como diagnostico read-only; no cambio ninguna condicion de accion.
* **Validaciones ejecutadas**:
  - Suite completa 129/129, `py_compile`, JSON, AST, secretos, ignores, `git diff --check` y Speckit QA: PASS.
  - Smoke directo del renderer `/help`: HTTP 200 y mensaje completo observado en el chat autorizado, sin iniciar otra instancia del monitor.
  - Activacion productiva: NSSM y monitor cambiaron de PID; mutex unico, `qa_mode=false`, startup guard 600s y EventStore schema 5 verificados.
  - `/help`, `/help reboot_no_ok`, `/status` y `/events` respondieron desde el proceso nuevo; tres comandos consecutivos llegaron sin perdida.
  - Documentacion `81b3b26` e implementacion/cierre `2afd65e` publicados en
    `origin/codex/030-telegram-messaging-quality`.
* **Archivos principales**:
  - `app/telegram_messages.py`
  - `app/miner_monitor.py`
  - `app/alert_episodes.py`
  - `tests/test_telegram_messaging.py`
  - `specs/030-telegram-messaging-quality/*`

## [2026-08-13] - Spec 020: Production Closeout And Telegram Credential Containment

* **Objetivo**: Cerrar con evidencia real la activacion de episodios, eliminar la exposicion del token en excepciones locales y validar el bot completo sin modificar politicas de accion.
* **Resultado**:
  - `/status`, `/events` y `/e531` fueron ejecutados desde la cuenta autorizada y respondieron mediante el servicio productivo con estado actual, historial y timeline relacionada.
  - El token historicamente presente solo en `logs/out.log` fue revocado; el reemplazo se guardo unicamente en `app/config.json` local y fue validado antes del reinicio.
  - `MinerAlerts` reinicio una vez mediante NSSM, adquirio un unico mutex, cargo `qa_mode=false`, activo el guard de 600 segundos y respondio `/status` con el token nuevo.
  - Los nuevos limites de log redactan tokens en transporte, respuestas y excepciones; los bytes posteriores al rollout contienen cero ocurrencias del token configurado.
* **Validaciones ejecutadas**:
  - Suite completa 118/118, `py_compile` y `git diff --check`: PASS.
  - Bot API `getMe`, polling entrante, delivery saliente, SQLite `/events` y detalle `/e531`: PASS.
  - Sin traceback, Hashcore ni auto-reboot en la ventana inspeccionada del startup guard.
* **Estado**: Spec 020 y T020 completos; Spec 021 queda habilitada para implementacion.
* **Archivos principales**:
  - `app/miner_monitor.py`
  - `tests/test_notification_stability.py`
  - `specs/020-episode-alerts/evidence.md`
  - `docs/speckit/RUNBOOK.md`
  - `docs/speckit/ROADMAP.md`

## [2026-07-21] - Spec 020: Irregular Miner Episodes

* **Objetivo**: Evitar fallas olvidadas y cascadas de mensajes, mostrar una historia breve desde OK hasta la recuperacion y eliminar contradicciones como un hashrate positivo etiquetado OFFLINE, sin modificar acciones automaticas.
* **Resultado**:
  - LOW, OFFLINE, perdida de placas y reinicios se consolidan en episodios acotados; mineros cercanos comparten una ventana de agrupacion maxima de 30 segundos.
  - Una falla persistente recuerda a los 5, 10, 15, 30, 60 y 120 minutos y luego cada hora, siempre agrupando vencimientos cercanos.
  - La recuperacion informa secuencias breves como `OK -> LOW -> OK` u `OK -> REINICIO -> PLACAS 0/3 -> LOW -> OK`; `HASHBOARD` queda como constante interna y Telegram explica placas activas.
  - `/status` usa evidencia actual y muestra `RECUPERANDO` durante histeresis, nunca hashrate positivo con `OFFLINE`.
  - `/e<ID>` abre el mismo detalle read-only que `/event <id>` y agrega una timeline cronologica acotada desde SQLite con eventos relacionados de la flota.
* **Validaciones ejecutadas**:
  - Desarrollo test-first; 51/51 pruebas dirigidas y suite completa 117/117 PASS.
  - `py_compile`, JSON, `git diff --check`, AST sin simbolos duplicados y Speckit QA 16/16: PASS.
  - Bloque de auto-reboot comparado contra HEAD: byte-identico; QA bloqueo Hashcore antes del subprocess.
* **Estado**:
  - Commit `e502ab9` integrado y publicado en `main`; reinicio elevado del servicio y smoke runtime todavia pendientes y registrados en `specs/020-episode-alerts/evidence.md`.
* **Archivos principales**:
  - `app/alert_episodes.py`
  - `app/miner_monitor.py`
  - `app/event_store.py`
  - `app/config.example.json`
  - `tests/test_alert_episodes.py`
  - `specs/020-episode-alerts/*`

## [2026-07-21] - Spec 019: Persistent Outage Alerts

* **Objetivo**: Evitar que un minero confirmado OFFLINE/LOW/HASHBOARD quede olvidado despues de la primera alerta, agrupar transiciones cercanas y eliminar definitivamente las ventanas de consola del collector y Hashcore.
* **Resultado**:
  - Los cambios de estado se acumulan durante 30 segundos y se envian en un unico mensaje aunque ocurran en ticks consecutivos; estado, SQLite, persistencia y auto-reboot siguen siendo inmediatos.
  - Una falla confirmada recuerda a los 15 minutos y luego cada 30 minutos hasta volver a OK, agrupando todos los mineros vencidos en el mismo mensaje.
  - La ventana silenciosa posterior a un reboot conserva prioridad, descarta transiciones intermedias y reinicia el plazo del recordatorio desde su resumen.
  - La tarea Vnish ejecuta `pythonw.exe` directamente, sin PowerShell, y todos los `subprocess.run` del monitor usan `CREATE_NO_WINDOW` en Windows.
* **Validaciones ejecutadas**:
  - Desarrollo test-first: fallas iniciales por coordinadores/flags ausentes y 21/21 pruebas dirigidas finales PASS.
  - Suite completa 113/113, `py_compile`, JSON, parseo PowerShell, `git diff --check`, AST, Speckit QA y bloqueo Hashcore en QA: PASS.
  - Tarea real reinstalada: ejecutable `pythonw.exe`, 30 minutos, `Ready`, `LastTaskResult=0`, collector 16/16 streams y cero fallas.
* **Estado**:
  - Implementacion integrada y publicada en `main` mediante `b587715`.
  - Servicio reiniciado a las 22:20:05: proceso nuevo, mutex adquirido, `qa_mode=false`, startup guard de 600 segundos y schema SQLite 5.
  - Primeros ciclos productivos completados sin excepciones nuevas ni acciones Hashcore posteriores al arranque.
* **Archivos principales**:
  - `app/miner_monitor.py`
  - `app/config.example.json`
  - `tools/install_vnish_collector_task.ps1`
  - `tests/test_notification_stability.py`
  - `tests/test_monitor_incidents.py`
  - `tests/test_vnish_scheduler.py`
  - `specs/019-persistent-outage-alerts/*`

## [2026-07-21] - Spec 018: Fleet Restart Notification Stability

* **Objetivo**: Corregir la sobre-notificacion observada durante reinicios coordinados y eliminar la ventana PowerShell visible del collector sin modificar state machine ni politicas de reboot.
* **Resultado**:
  - Los resets de uptime cercanos se acumulan durante 180 segundos y, desde dos mineros afectados, se informan como un unico incidente de flota con IDs auditables.
  - Las transiciones de arranque siguen actualizando estado, logs y SQLite, pero su entrega Telegram se silencia por hasta 600 segundos y termina con un unico resumen de recuperacion.
  - La ausencia de una accion reciente ya no se presenta como causa probada: el mensaje pasa a `REINICIO SIN ACCION ATRIBUIDA`.
  - La tarea Vnish solicita `-WindowStyle Hidden`, conserva `IgnoreNew` y pasa de 15 a 30 minutos por defecto.
  - La auditoria del incidente probo cero acciones Hashcore entre 00:00 y 00:20; el primer collector automatico comenzo a las 00:15:30, despues del reinicio de flota.
* **Validaciones ejecutadas**:
  - Desarrollo test-first: regresiones de batch, quiet window, wording y scheduler primero en rojo y luego 12/12 dirigidas PASS.
  - Suite completa 104/104, `py_compile`, JSON, parseo PowerShell, `git diff --check`, simbolos duplicados y Speckit QA 11/11: PASS.
* **Estado**:
  - Implementacion integrada y publicada en `main`; tarea Vnish activa con ventana oculta y 30 minutos.
  - Activacion cerrada por el rollout verificado de Spec 019 a las 22:20:05; Spec 020 reemplaza luego la estrategia temporal fija por episodios acotados.
* **Archivos principales**:
  - `app/miner_monitor.py`
  - `app/config.example.json`
  - `tools/install_vnish_collector_task.ps1`
  - `tests/test_monitor_incidents.py`
  - `tests/test_vnish_scheduler.py`
  - `specs/018-fleet-restart-notification-stability/*`

## [2026-07-20] - Spec 017: Vnish Operations Automation

* **Objetivo**: Operacionalizar la evidencia Vnish reciente y correlacionarla con el estado del monitor sin agregar un worker permanente ni nuevas autorizaciones de reboot.
* **Resultado**:
  - El parser acotado conserva los eventos reconocidos mas recientes del replay Vnish en orden cronologico y normaliza su timestamp con procedencia de reloj explicita.
  - SQLite migra aditivamente a schema v5, completa metadata temporal sin duplicar eventos y registra salud acotada de cada corrida en `collector_runs`.
  - El collector one-shot puede instalarse como tarea Windows separada cada 15 minutos, con `IgnoreNew`, limite de ejecucion, sin retries, sin Hashcore y sin acoplarse al servicio del monitor.
  - `/diagnose [all|miner]` combina senal, calidad, firmware reciente, eventos, decisiones de auto-reboot y frescura del collector desde SQLite solamente; el resultado es asesor y no ejecuta acciones.
  - El dashboard local incorpora frescura y resultado de la ultima corrida del collector.
  - El rollout corrigio dos fallas de operacion Windows reproducidas: resolucion temprana de `$PSScriptRoot` bajo `powershell.exe -File` y buffering de stdout bajo NSSM; la tarea ahora finaliza en cero y los logs centrales se fuerzan con flush.
* **Validaciones ejecutadas**:
  - Desarrollo test-first, 32 pruebas dirigidas y suite completa final 101/101: PASS.
  - `py_compile`, parseo PowerShell, JSON, `git diff --check`, Speckit QA 11/11, `-WhatIf` del scheduler y scan de secretos: PASS.
  - Smoke live read-only aislado: 16/16 streams, schema v5, 6.560 inserts iniciales, segunda corrida 6.600 duplicados y cero inserts/fallas/truncacion.
  - Todos los eventos persistidos en el smoke tienen epoch de origen y procedencia `system_local`; no se guardaron lineas crudas ni secretos.
  - Rollout controlado: tarea Windows `Ready`, `LastTaskResult=0`, `IgnoreNew`; servicio NSSM reiniciado y `Running`, config prod, startup guard 600s, schema v5, collector 16/16 y cero decisiones de reboot inmediatas.
  - Render real SQLite-only de `/diagnose 23`: 8 lineas, estado `OK`, muestra reciente y collector `OK`; invocacion desde el chat queda como smoke manual del operador.
  - Integracion final: cadena Specs 006-017 aplicada por fast-forward a `main`; 101 tests, compilacion, dependencias, simbolos duplicados, secretos y `git diff --check` auditados, con 28 findings historicos de whitespace documental eliminados.
* **Estado**:
  - Implementacion y rollout productivo completos, sin ejecutar acciones Hashcore/reboot/restart.
* **Archivos principales**:
  - `app/vnish_logs.py`
  - `app/event_store.py`
  - `app/miner_monitor.py`
  - `tools/vnish_log_collector.py`
  - `tools/run_vnish_collector.ps1`
  - `tools/install_vnish_collector_task.ps1`
  - `tools/operations_dashboard.py`
  - `specs/017-vnish-operations-automation/*`

## [2026-07-20] - Spec 016: Vnish Log Intelligence

* **Objetivo**: Incorporar evidencia historica del firmware Vnish para distinguir transiciones normales, watchdog/restarts y fallas de cadena, energia, temperatura o pool sin acoplarla a acciones automaticas.
* **Resultado**:
  - Un parser puro y acotado normaliza solo evidencia conocida y descarta lineas desconocidas; la base guarda resumen generado y fingerprint, nunca el log crudo.
  - Una CLI Windows separada consume secuencialmente los WebSockets confirmados `status`, `miner`, `autotune` y `system`, con timeouts, limites y dry-run, sin retries ni acciones.
  - SQLite migra aditivamente a schema v4 con `firmware_events` idempotentes y retencion; recolectar el mismo historial dos veces no duplica filas.
  - `/firmware [all|miner]` y la timeline del dashboard leen solo SQLite; el monitor no abre WebSockets Vnish y ningun evento modifica state machine, alertas o reboots.
* **Validaciones ejecutadas**:
  - Desarrollo test-first, 24 pruebas dirigidas y suite completa 93/93: PASS.
  - `py_compile`, `git diff --check`, Speckit QA 11/11, dependencia `websocket-client 1.9.0`, build y dashboard Docker: PASS.
  - Smoke live read-only: 16/16 combinaciones miner/tab completadas; persistencia aislada 800 inserts y segunda pasada 800 duplicados, cero fallas y cero hits sensibles.
* **Estado**:
  - Implementacion y evidencia completas; activacion de `/firmware` diferida al reinicio controlado final del servicio.
* **Archivos principales**:
  - `app/vnish_logs.py`
  - `app/event_store.py`
  - `app/miner_monitor.py`
  - `tools/vnish_log_collector.py`
  - `tools/operations_dashboard.py`
  - `tests/test_vnish_logs.py`
  - `specs/016-vnish-log-intelligence/*`

## [2026-07-20] - Spec 015: Vnish Transition Reboot Interlock

* **Objetivo**: Evitar auto-reboots innecesarios mientras Vnish informa una transicion actual de tuning, calibracion, inicio o warm-up de cadenas.
* **Resultado**:
  - El interlock puro bloquea solo con evidencia actual positiva y conserva precedencia termica; datos ausentes, invalidos o cero no inventan bloqueos.
  - El bloqueo se persiste como `firmware_transition`, expone cantidad acotada de cadenas y reinicia solo `low_since_ts` para exigir LOW sostenido nuevamente.
  - `/why` explica la decision; acciones manuales Telegram, confirmaciones y Hashcore manual no incorporan este gate.
  - Default conservador `auto_reboot_firmware_transition_guard_enabled=true`, sin nuevas llamadas al minero ni cambios de esquema.
* **Validaciones ejecutadas**:
  - Fase roja reproducida para contrato/interlock/render y 25 pruebas dirigidas PASS tras implementar.
  - Suite completa 84/84, `py_compile`, JSON y `git diff --check`: PASS.
  - Probe sintetico: `allowed=False reason=firmware_transition transitioning_chains=1`.
  - Evidencia live actual sin transiciones; activacion y observacion runtime diferidas al rollout final.
* **Archivos principales**:
  - `app/reboot_safety.py`
  - `app/miner_monitor.py`
  - `app/event_store.py`
  - `tests/test_reboot_safety.py`
  - `specs/015-vnish-transition-reboot-interlock/*`

## [2026-07-20] - Spec 014: QA Poll-Empty Stability

* **Objetivo**: Evitar que un lote vacio de Telegram en QA intente usar variables locales de ramas de comandos y degrade el polling con excepciones/backoff.
* **Resultado**:
  - Se elimino exclusivamente el log de duracion mal ubicado debajo de `POLL_EMPTY`; el diagnostico idle existente se conserva.
  - Offset, dispatch, sleeps, backoff, state machine, auto-reboot, Hashcore y persistencia no cambiaron.
  - Una prueba AST de regresion impide reintroducir referencias a `action` o `cmd_start` en la rama vacia.
* **Validaciones ejecutadas**:
  - Fase roja reproducida contra el bloque defectuoso y regresion 1/1 PASS tras el parche.
  - Suite completa 81/81, `py_compile` y `git diff --check`: PASS.
  - `MinerAlerts` continuo `Running/Automatic`; activacion diferida al rollout final.
* **Archivos principales**:
  - `app/miner_monitor.py`
  - `tests/test_telegram_polling_stability.py`
  - `specs/014-qa-poll-empty-stability/*`

## [2026-07-20] - Spec 013: Mining Quality Intelligence

* **Objetivo**: Convertir contadores acumulados de shares y evidencia Vnish de cadenas en diagnostico por intervalos, evitando confundir resets de uptime/contadores con degradacion real.
* **Resultado**:
  - SQLite migra aditivamente a schema v3 y persiste accepted/rejected/stale, fallas/estados de cadena y flags acotados sin guardar payloads crudos.
  - Un analizador puro calcula deltas solo dentro del mismo uptime epoch; resets producen `LEARNING/counter_reset`, nunca porcentajes negativos ni criticidad falsa.
  - `WATCH` identifica rejected/stale altos, crecimiento de HW errors, falta de progreso y transicion/autotune; fallas de cadena actuales conservan precedencia `CRITICAL`.
  - `/quality`, `/quality all` y `/quality <miner>` leen SQLite solamente y el dashboard reutiliza exactamente el mismo diagnostico.
  - Dos snapshots reales separados 761-762s clasificaron los cuatro mineros `STABLE`, sin rejected/stale ni crecimiento HW en el intervalo.
* **Validaciones ejecutadas**:
  - Desarrollo test-first, 27 pruebas dirigidas y suite completa de 80 pruebas: PASS.
  - `py_compile`, JSON config, `git diff --check`, Speckit QA, benchmark, HTML nativo y Docker read-only: PASS.
  - State machine y bloque de auto-reboot: sin cambios respecto de `9b8e793`.
* **Estado**:
  - Implementacion local completa; activacion y prueba Telegram diferidas al reinicio controlado de fin de dia.
* **Archivos principales**:
  - `app/mining_quality.py`
  - `app/event_store.py`
  - `app/miner_monitor.py`
  - `tools/operations_dashboard.py`
  - `tests/test_mining_quality.py`
  - `specs/013-mining-quality-intelligence/*`

## [2026-07-20] - Spec 012: Stability Advisor

* **Objetivo**: Convertir la telemetria historica en un sweet spot robusto por minero y separar fallas actuales de drift o histeresis, sin agregar acciones automaticas.
* **Resultado**:
  - Un analizador puro construye bandas por mediana/MAD desde muestras previas saludables y excluye la muestra actual de su propio baseline.
  - Los resultados `LEARNING`, `STABLE`, `WATCH` y `CRITICAL` incluyen razones acotadas para hashrate, temperatura, boards, voltaje/potencia de cadena, frecuencia, freshness y falta de respuesta.
  - Un estado persistido LOW con hashrate actual recuperado se clasifica como `WATCH/state_recovery_hysteresis`, evitando repetir una falsa severidad critica.
  - `/health`, `/health all` y `/health <miner>` consultan solo SQLite, responden con semantica de comando y no hacen IO live hacia mineros.
  - El dashboard reutiliza exactamente el mismo analizador y muestra baseline y diagnostico por card.
  - El voltaje de cadena se presenta explicitamente como evidencia board-side, no como voltaje AC de entrada.
* **Validaciones ejecutadas**:
  - Desarrollo test-first con fallas iniciales para modulo, dashboard, comando y caso de histeresis.
  - 17 pruebas dirigidas y suite completa de 68 pruebas: PASS.
  - Benchmark de 5.000 muestras: 17,84 ms en el equipo objetivo.
  - CLI Windows, HTML fixture, build Docker y generacion Docker read-only: PASS.
* **Estado**:
  - Implementacion local completa; activacion runtime diferida al reinicio controlado de fin de dia.
* **Archivos principales**:
  - `app/stability_profile.py`
  - `app/miner_monitor.py`
  - `tools/operations_dashboard.py`
  - `tests/test_stability_profile.py`
  - `specs/012-stability-advisor/*`

## [2026-07-20] - Spec 011: Read-Only Operations Dashboard

* **Objetivo**: Agregar una interfaz local visual para correlacionar salud, tendencias, incidentes y decisiones sin convertir el dashboard en superficie de control.
* **Resultado**:
  - Un CLI standalone abre SQLite con `mode=ro` y genera HTML autocontenido sin cargar config ni conectarse a mineros.
  - El dashboard muestra KPIs, cards por minero, freshness, boards, temperatura, potencia de cadena, sparklines, eventos y decisiones.
  - Todas las cadenas persistidas se escapan; no hay JavaScript, CDN, assets remotos, listener web ni acciones reboot/restart.
  - Consultas, timelines y tendencias quedan acotadas; se priorizan las muestras mas recientes.
  - `Dockerfile.dashboard` ofrece ejecucion aislada opcional, manteniendo Python/PowerShell como ruta principal.
* **Validaciones ejecutadas**:
  - Desarrollo test-first: falla inicial por modulo inexistente y luego 5 pruebas dirigidas PASS.
  - Suite completa de 56 pruebas, `py_compile`, `git diff --check` y Speckit QA: PASS.
  - Fixture de cuatro mineros: HTML generado correctamente (10,627 bytes) bajo `diagnostics/` ignorado.
  - Build Docker y generacion aislada contra el fixture: PASS (10,493 bytes).
  - La apertura visual automatizada `file://` quedo bloqueada por politica del navegador y se documenta como pendiente manual.
* **Estado**:
  - Implementacion local completa. No requiere ni provoca reinicio del servicio.
* **Archivos principales**:
  - `tools/operations_dashboard.py`
  - `Dockerfile.dashboard`
  - `tests/test_operations_dashboard.py`
  - `docs/speckit/RUNBOOK.md`
  - `specs/011-operations-dashboard/*`

## [2026-07-20] - Spec 010: Fleet-Aware Auto-Reboot Safety

* **Objetivo**: Evitar reboots automaticos innecesarios durante degradacion compartida de flota o evidencia termica alta, sin agregar IO ni modificar controles manuales.
* **Resultado**:
  - Un evaluador puro bloquea con `fleet_incident` cuando al menos dos mineros aparecen afectados en el ultimo tick completo y fresco.
  - La evidencia de flota vence despues de `max(60, poll_seconds * 2)` para impedir decisiones sobre snapshots viejos.
  - Un LOW sostenido con temperatura Vnish actual igual o superior a 85 C se bloquea como `high_temperature` por defecto.
  - Ambos interlocks son configurables, estan habilitados por defecto y se aplican despues de startup/sustained LOW pero antes de cooldown/window/QA/Hashcore.
  - `/why` muestra mineros afectados, antiguedad del snapshot, temperatura observada y limite.
  - No se agregan requests, dependencias, workers, campos de estado ni cambios a reboot/restart manual.
* **Validaciones ejecutadas**:
  - Desarrollo test-first: falla inicial por modulo inexistente y luego 19 pruebas dirigidas PASS.
  - Suite completa de 51 pruebas y `py_compile`: PASS.
  - Snapshot sanitizado: 4/4 mineros con 3 boards, 92.851-101.265 TH/s y maximos de 72-81 C, todos debajo del limite default.
* **Estado**:
  - Implementacion y validacion local completas. El servicio sigue sin reiniciarse hasta el cierre controlado del dia.
* **Archivos principales**:
  - `app/reboot_safety.py`
  - `app/miner_monitor.py`
  - `app/event_store.py`
  - `app/config.example.json`
  - `tests/test_reboot_safety.py`
  - `specs/010-fleet-reboot-safety/*`

## [2026-07-20] - Spec 009: Vnish Hashboard Detection

* **Objetivo**: Hacer que el monitor de produccion detecte hashboards con el formato Vnish real y diferencie una placa faltante de un LOW generico.
* **Resultado**:
  - `_count_active_boards` reconoce `chain_acn0..9`, ademas de los formatos legacy que ya soportaba.
  - `read_stats_snapshot` recorre todas las entradas `STATS` y usa la primera que contenga evidencia explicita de boards.
  - No se agrega ninguna llamada API: el mismo response alimenta state machine, telemetria Vnish y auditoria.
  - Evidencia desconocida sigue siendo `None`; ceros y valores invalidos no cuentan como board activo.
  - Se conserva la precedencia existente `HASHBOARD` antes de `LOW`; HASHBOARD no entra en el path de auto-reboot LOW.
* **Validaciones ejecutadas**:
  - Los snapshots sanitizados reales de S19JPRO-23/24/25/26 cuentan exactamente 3 boards con el parser de produccion: PASS.
  - 40 pruebas de formatos Vnish/legacy, degradacion, precedencia, seguridad, persistencia, Telegram y reportes: PASS.
  - `py_compile`, `git diff --check` y Speckit preflight: PASS.
* **Estado**:
  - Implementacion y validacion local completas. El servicio sigue sin reiniciarse hasta el cierre controlado del dia.
* **Archivos principales**:
  - `app/miner_monitor.py`
  - `tests/test_vnish_hashboard_detection.py`
  - `tests/test_monitor_incidents.py`
  - `specs/009-vnish-hashboard-detection/*`

## [2026-07-20] - Spec 008: Valid Signal Auto-Reboot Gate

* **Objetivo**: Evitar reboots innecesarios cuando la state machine conserva `LOW` por histeresis pero la lectura actual es invalida o ya recupero el hashrate.
* **Resultado**:
  - El auto-reboot exige ahora `responded=true`, hashrate numerico finito y valor actual por debajo del umbral antes de evaluar cualquier accion.
  - `None`, `NaN`, infinito y falta de respuesta se clasifican como `invalid_signal` y cortan el reloj de LOW sostenido.
  - Una lectura actual igual o superior al umbral se clasifica como `not_low`, incluso si la recuperacion todavia espera `recovery_successes`, y tambien corta el reloj sostenido.
  - El siguiente LOW valido debe iniciar un periodo sostenido nuevo; no hereda tiempo a traves de una muestra invalida o recuperada.
  - La state machine, sus streaks, startup guard, cooldown, ventana, QA, Hashcore, Telegram manual y polling no se reordenaron.
  - El bloqueo no usa `continue`, por lo que el procesamiento posterior de transiciones, alertas y persistencia sigue ocurriendo.
* **Validaciones ejecutadas**:
  - Clasificacion tabular para no-response, `None`, `NaN`, infinitos, umbral, recuperacion y LOW valido: PASS.
  - Predicate de elegibilidad y reset del timer sostenido: PASS.
  - Suite completa de 34 pruebas, `py_compile`, `git diff --check` y Speckit QA HIGH-risk: PASS.
* **Estado**:
  - Implementacion y validacion local completas, listas para commit/push. El servicio sigue ejecutando la version anterior hasta el reinicio controlado de fin de dia.
* **Archivos principales**:
  - `app/miner_monitor.py`
  - `tests/test_auto_reboot_signal_gate.py`
  - `specs/008-valid-signal-reboot-gate/*`

## [2026-07-20] - Spec 007: Vnish Telemetry And Reboot Decision Audit

* **Objetivo**: Convertir la telemetria Vnish ya disponible en evidencia durable y explicar cada resultado relevante del auto-reboot sin modificar sus condiciones ni ejecutar acciones nuevas.
* **Resultado**:
  - SQLite migra de schema v1 a v2 de forma aditiva, preservando muestras y eventos existentes.
  - Se normalizan todas las entradas `STATS`, incluyendo el caso real donde la evidencia de cadena vive en `STATS[1]`.
  - Las muestras incorporan temperatura maxima, voltaje y consumo de cadena, frecuencia, errores HW, ventiladores y flags conservadores; nunca se guarda el payload ASIC completo.
  - Cada rama relevante del auto-reboot registra `not_low`, `invalid_signal`, `startup_guard`, `not_sustained`, `cooldown`, `window`, `qa`, `executed` o `failed` con su evidencia.
  - `/why` y `/why <miner>` explican la ultima decision usando solo SQLite, sin IO al minero ni Hashcore.
  - `tools/incident_report.py` genera Markdown o JSON correlacionando muestras, eventos y decisiones con una conexion SQLite read-only.
  - Se mantiene explicito que `chain_vol` es evidencia de cadena/hashboard y no voltaje AC de entrada.
  - No se agregaron frameworks ni servicios: FastAPI/dashboard y Prometheus/Grafana quedan diferidos hasta estabilizar el contrato de datos.
* **Validaciones ejecutadas**:
  - `py_compile` de monitor, event store, parser Vnish y reporte: PASS.
  - 30 pruebas `unittest` de migracion, persistencia, concurrencia, normalizacion, reporte, Telegram, restart intelligence y QA: PASS.
  - Speckit QA preflight inicial HIGH-risk: PASS.
* **Estado**:
  - Implementacion y validacion local completas, listas para commit/push. El servicio de Windows no se reinicia hasta el cierre del dia por solicitud del operador.
* **Hallazgo de auditoria**:
  - El path preexistente `invalid_signal` registra el problema pero puede continuar evaluando un `LOW` heredado en el mismo tick. Se registra como P0 separado porque corregirlo cambia politica de accion.
* **Archivos principales**:
  - `app/vnish_telemetry.py`
  - `app/event_store.py`
  - `app/miner_monitor.py`
  - `tools/incident_report.py`
  - `tests/test_vnish_telemetry.py`
  - `tests/test_reboot_decision_audit.py`
  - `tests/test_incident_report.py`
  - `specs/007-vnish-decision-audit/*`

## [2026-07-20] - Spec 006: Incident History And Restart Intelligence

* **Objetivo**: Crear una base durable de evidencia operativa y distinguir reinicios esperados de reinicios no deseados sin cambiar la state machine ni la politica de auto-reboot.
* **Resultado**:
  - Se agrego un event store SQLite versionado, thread-safe y en modo WAL para muestras acotadas, transiciones, reinicios detectados y resultados de acciones.
  - El detector existente de caida de uptime se conserva y ahora se clasifica como `expected_manual`, `expected_auto` o `unexpected` usando acciones exitosas recientes.
  - Los reinicios inesperados generan una alerta dedicada con uptime anterior/actual, estado, hashrate, incidente y acceso a `/event <id>`.
  - Se agregaron `/events`, `/events <miner>` y `/event <id>` como consultas Telegram read-only sin IO al minero ni Hashcore.
  - La retencion queda acotada a 90 dias de muestras cada cinco minutos y 365 dias de eventos por defecto.
  - El historial es estrictamente observacional y no participa de decisiones de reboot, cooldown, startup guard o QA.
* **Validaciones ejecutadas**:
  - `py_compile` del monitor, event store, clasificador y herramientas: PASS.
  - 19 pruebas `unittest` de persistencia, reapertura, retencion, concurrencia, clasificacion, parsing, mensajes y bloqueo QA: PASS.
  - `git diff --check`: PASS.
  - Speckit QA preflight HIGH-risk con builds: PASS.
* **Estado**:
  - Implementacion y validacion local completas. La evidencia de activacion del servicio se registra en `specs/006-incident-history/evidence.md`.
* **Archivos principales**:
  - `app/event_store.py`
  - `app/restart_intelligence.py`
  - `app/miner_monitor.py`
  - `app/config.example.json`
  - `tests/test_event_store.py`
  - `tests/test_restart_intelligence.py`
  - `tests/test_monitor_incidents.py`
  - `specs/006-incident-history/*`

## [2026-07-14] - Spec 005: Event-Driven Telegram Alerts

* **Objetivo**: Reducir ruido operativo en Telegram deshabilitando por defecto los resumenes horarios de estado degradado, manteniendo alertas por eventos reales como LOW, OFFLINE, HASHBOARD y recuperacion a OK.
* **Resultado**:
  - `notify_degraded_hourly` queda en `false` por defecto.
  - `degraded_hourly_seconds` queda documentado/configurable para operadores que quieran recordatorios periodicos.
  - El envio existente `degraded_hourly` ahora solo ocurre si se habilita explicitamente por config.
  - Los mensajes `STATE_CHANGE` agregan una seccion `Eventos:` con el cambio concreto antes del snapshot completo.
  - `/status` no cambia: sigue disponible como consulta manual cuando el operador quiere el estado completo.
* **Validaciones ejecutadas**:
  - `& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py tools\\miner_diagnostics.py tools\\diagnostics_baseline.py`: PASS.
  - Smoke import de `format_state_event`: PASS.
  - `git diff --check`: PASS.
* **Estado**:
  - Implementado y validado estaticamente. Requiere reinicio del servicio para cargar la nueva politica de notificaciones.
* **Archivos principales**:
  - `app/miner_monitor.py`
  - `app/config.example.json`
  - `docs/speckit/RUNBOOK.md`
  - `docs/speckit/ROADMAP.md`
  - `specs/005-event-driven-telegram-alerts/*`

## [2026-07-11] - Spec 004: Diagnostics Baseline Sweet Spot

* **Objetivo**: Convertir snapshots read-only en una linea base por minero para identificar variacion normal, evidencia de Vnish y seniales que deben observarse antes de cambiar politicas de reboot.
* **Resultado**:
  - Se agrego `tools/diagnostics_baseline.py` como analizador standalone de `snapshot.json`.
  - El analizador acepta un archivo o directorio, agrega muestras por minero y genera `baseline.md` + `baseline.json`.
  - El reporte incluye muestra, confianza, banda TH/s, boards, banda de temperatura maxima, `chain_vol`, `chain_consumption`, frecuencia y hardware errors.
  - La confianza queda `low` con una sola muestra para evitar conclusiones prematuras.
  - La documentacion incorpora el comando operativo para construir baseline desde `diagnostics/latest/snapshot.json`.
  - Se documento una estrategia de adopcion tecnologica para Docker, FastAPI, SQLite/DuckDB, Prometheus/Grafana y dashboards read-only.
* **Validaciones ejecutadas**:
  - `& ".\\.venv\\Scripts\\python.exe" -m py_compile tools\\diagnostics_baseline.py tools\\miner_diagnostics.py app\\miner_monitor.py`: PASS.
  - `& ".\\.venv\\Scripts\\python.exe" tools\\diagnostics_baseline.py --input diagnostics\\latest\\snapshot.json --out diagnostics\\baseline`: PASS.
  - `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force; & ".agents\\skills\\speckit-qa\\scripts\\preflight.ps1" -RunBuilds`: PASS.
* **Estado**:
  - Implementado y validado con el snapshot real de Spec 003. El baseline actual tiene confianza baja por contar con una sola muestra; se requieren multiples snapshots para convertirlo en politica.
* **Archivos principales**:
  - `tools/diagnostics_baseline.py`
  - `docs/speckit/RUNBOOK.md`
  - `docs/speckit/ROADMAP.md`
  - `docs/speckit/MINER_DIAGNOSTICS.md`
  - `docs/speckit/TECHNOLOGY_STRATEGY.md`
  - `specs/004-diagnostics-baseline-sweet-spot/*`

## [2026-07-11] - Spec 003: Read-Only Miner Diagnostics

* **Objetivo**: Agregar una herramienta read-only para recolectar evidencia de mineros antes de cambiar politicas de alertas, auto-reboot o UX operativa, manteniendo intacto el monitor en produccion.
* **Resultado**:
  - Se agrego `tools/miner_diagnostics.py` como colector standalone para API 4028 (`summary`, `stats`, `pools`, `version`).
  - El colector genera `summary.md` y `snapshot.json` sanitizados, con redaccion de usuarios de pool y sin exponer secretos de Telegram.
  - Se agrego `--dry-run` para validar config sin llamadas de red.
  - Se agrego `Dockerfile.diagnostics` para ejecutar solo el colector de diagnostico, sin dockerizar el monitor principal ni Hashcore Toolkit.
  - Se detectaron campos Vnish utiles para correlacion: `chain_vol`, `chain_consumption`, `freq_avg`, `chain_rate`, `chain_hw`, temperaturas chip/PCB y estado de pools.
  - `.gitignore` y `.dockerignore` cubren config real, state, logs, diagnostics, caches, envs y secretos.
* **Validaciones ejecutadas**:
  - `& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py tools\\miner_diagnostics.py`: PASS.
  - `& ".\\.venv\\Scripts\\python.exe" tools\\miner_diagnostics.py --config app\\config.example.json --out diagnostics\\dry-run --dry-run`: PASS.
  - `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force; & ".agents\\skills\\speckit-qa\\scripts\\preflight.ps1" -RunBuilds`: PASS.
  - `git diff --check`: PASS.
  - Snapshot read-only contra `app/config.json`: PASS, 4/4 mineros respondieron por API 4028.
* **Estado**:
  - Implementado y validado localmente con dry-run y snapshot real read-only. Queda como siguiente paso construir baseline/sweet spot con multiples snapshots antes de tocar politica de reboot.
* **Archivos principales**:
  - `tools/miner_diagnostics.py`
  - `Dockerfile.diagnostics`
  - `.dockerignore`
  - `.gitignore`
  - `docs/speckit/RUNBOOK.md`
  - `docs/speckit/ROADMAP.md`
  - `docs/speckit/MINER_DIAGNOSTICS.md`
  - `specs/003-read-only-miner-diagnostics/*`

## [2026-07-11] - Spec 002: Miner Diagnostics And Interface Roadmap

* **Objetivo**: Definir el roadmap tecnico para evolucionar Miner Alerts mas alla de alertas Telegram, cubriendo diagnostico antes de reboot, Hashcore Toolkit, Vnish, power telemetry e interfaz read-only.
* **Resultado**:
  - Se documento un roadmap por prioridades P0-P7 para reducir falsas alertas, evitar reboots innecesarios y mejorar observabilidad.
  - Se definio que Telegram permanece como superficie principal de acciones, mientras cualquier interfaz nueva debe empezar read-only.
  - Se documento una estrategia para Hashcore Toolkit: inventariar capacidades read-only vs acciones antes de integrar nuevos comandos.
  - Se definio una matriz de diagnostico para Vnish/S19j Pro: hash, boards, temperaturas, pool state, firmware hints, voltage/frequency/power fields y eventos de firmware.
  - Se aclaro que voltaje AC/input no debe inferirse automaticamente desde firmware salvo evidencia explicita; se deben considerar PDU/UPS/smart meter si hace falta.
* **Validaciones ejecutadas**:
  - Revision documental de `docs/speckit/ROADMAP.md`, `INTERFACE_STRATEGY.md`, `MINER_DIAGNOSTICS.md` y `HASHCORE_TOOLKIT_STRATEGY.md`: PASS.
  - No se realizaron cambios runtime en esta spec.
* **Estado**:
  - Roadmap y arquitectura de evolucion documentados. La implementacion real de diagnostico quedo iniciada posteriormente en Specs 003 y 004.
* **Archivos principales**:
  - `docs/speckit/ROADMAP.md`
  - `docs/speckit/INTERFACE_STRATEGY.md`
  - `docs/speckit/MINER_DIAGNOSTICS.md`
  - `docs/speckit/HASHCORE_TOOLKIT_STRATEGY.md`
  - `specs/002-miner-diagnostics-interface-roadmap/*`

## [2026-07-11] - Spec 001: Miner Alerts Quality Hardening

* **Objetivo**: Instalar una forma de trabajo Speckit para Miner Alerts, con foco en quick wins seguros: falsas alertas, seguridad de auto-reboot, confiabilidad Telegram, logs, hygiene de release y compatibilidad Windows/Hashcore.
* **Resultado**:
  - Se instalo `.specify/` desde el scaffold local probado en OneITB23.
  - Se instalaron skills Speckit bajo `.agents/skills/`, incluyendo `speckit-qa` adaptado a Miner Alerts.
  - Se creo la constitucion del proyecto en `.specify/memory/constitution.md` con reglas de seguridad: no secretos, no reboots sin evidencia, Telegram con confirmaciones y validacion Windows.
  - Se agrego `AGENTS.md` como instrucciones operativas para futuros agentes/Codex.
  - Se creo la base documental en `docs/speckit/` y specs iniciales para ordenar auditorias e implementaciones.
* **Validaciones ejecutadas**:
  - `& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py`: PASS.
  - Verificacion de que la instalacion Speckit no cambiaba runtime del monitor: PASS.
* **Estado**:
  - Bootstrap Speckit completado. Las auditorias runtime y quick wins derivados quedaron como backlog y fueron desarrollados parcialmente en specs posteriores.
* **Archivos principales**:
  - `.specify/*`
  - `.agents/skills/*`
  - `.agents/skills/speckit-qa/*`
  - `AGENTS.md`
  - `docs/speckit/*`
  - `specs/001-miner-alerts-quality-hardening/*`
