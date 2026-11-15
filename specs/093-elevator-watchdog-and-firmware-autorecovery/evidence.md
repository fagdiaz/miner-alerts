# Evidencia de Ejecución: Spec 093 — Watchdog de Elevadores Eléctricos, Corrección de Rachas y Auto-Recuperación de Firmware

**Fecha**: 2026-10-27  
**Feature**: `specs/093-elevator-watchdog-and-firmware-autorecovery`  
**Estado**: CERTIFICADO (Preflight QA PASS, Tests 1536 PASS)

---

## 1. Incidente Físico y Hallazgos Forenses

### Evento Real:
- Relé físico del elevador 2 (`elevator_2`) se trabó por sobretensión, cortando suministro eléctrico a `S19JPRO-25` (192.168.100.25) y `S19JPRO-26` (192.168.100.26).
- Durante el corte (~95 minutos), Telegram **no envió** la alerta de minero offline ni la alerta de corte de circuito.
- Al restaurar energía, `S19JPRO-26` arrancó en firmware stock de Bitmain (`BMMiner 1.0.0`) en lugar de VNish 1.2.6.

### Causas Raíz Identificadas:
1. **Reseteo Prematuro de Rachas (`app/core/engine.py`)**:
   - En `DetectionHook.execute`, la condición `if new_state == STATE_OK:` borraba incondicionalmente `state.offline_streak = 0`.
   - Cuando fallaba un minero, el tick 1 incrementaba la racha a 1. Debido a la histeresis de alerta (`fails_before_alert = 3`), `classify_state` devolvía el estado previo (`STATE_OK`).
   - El hook evaluaba `new_state == STATE_OK` y reseteaba la racha a 0 en el mismo tick. Por ende, la racha jamás alcanzaba 3 y el minero nunca transitaba a `OFFLINE`.
2. **Discriminador de Corte de Fase Desconectado (`app/core/pipeline.py`)**:
   - `process_phase_drop_cycle` (implementado en Spec 051) estaba importado pero no se invocaba en ningún hook del pipeline V6.0 (`GovernanceHook`).
3. **Ausencia de Escalera de Auto-Recuperación de Firmware Stock**:
   - Las placas de control BeagleBone Black de Bitmain caen a la partición NAND de fábrica ante cortes bruscos. No existía lógica para emitir un reboot digest HTTP `/cgi-bin/reboot.cgi` o reflash con restauración de perfil de manera desatendida.

---

## 2. Acciones Inmediatas y Mitigación en Vivo

1. **Reinicio Digest a Minero 26**:
   - Se emitió POST `/cgi-bin/reboot.cgi` con autenticación Digest `root:root` a `192.168.100.26`.
   - El equipo reinició cargando VNish 1.2.6 con su perfil dorado intacto (`top_preset: 2500`, `preset: 2300`, Binance Pool `fagdiaz.19216810026`).
   - Hashrate recuperado: 3/3 cadenas activas operando a >87 TH/s nominal.

2. **Implementación de Arquitectura de Auto-Recuperación**:
   - `app/core/engine.py`: Corrección de lógica de reseteo de rachas en `DetectionHook`.
   - `app/governance/firmware_recovery.py`: Módulo autónomo con reinicio Bitmain stock, reflash VNish y restauración de matrices.
   - `app/core/pipeline.py`: Conexión de `process_phase_drop_cycle` y `handle_stock_firmware_recovery` en `GovernanceHook`.
   - `app/core/restart_intelligence.py`: Manejador de stock firmware fallback en reinicios.

---

## 3. Comandos de Verificación Ejecutados

### A. Pruebas Unitarias e Integración Spec 093
```powershell
& ".\.venv\Scripts\python.exe" -m pytest -v tests/test_spec093_elevator_and_firmware_recovery.py
```
**Resultado**: 6 passed in 0.76s.

### B. Compilación de Sintaxis Python
```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\core\engine.py app\core\pipeline.py app\governance\firmware_recovery.py app\core\restart_intelligence.py tests\test_spec093_elevator_and_firmware_recovery.py
```
**Resultado**: Código de salida 0 (sin errores).

### C. Suite Completa de Regresión
```powershell
& ".\.venv\Scripts\python.exe" -m pytest -q tests/
```
**Resultado**: 1536 passed, 75 subtests passed in 40.65s (0 fallos).

### D. Preflight QA (`speckit-qa`)
```powershell
& powershell -ExecutionPolicy Bypass -File .agents\skills\speckit-qa\scripts\preflight.ps1 -RunBuilds
```
**Resultado**:
```json
{"Status":"PASS","FeatureDir":"F:\\02-ASIC - mineros\\miner-alerts\\specs\\093-elevator-watchdog-and-firmware-autorecovery","MissingRequiredFiles":[],"Checklist":{"Total":0,"Open":0},"Scope":{"Python":true,"Telegram":false,"Reboot":true,"Config":false,"Docs":true},"DirtyPathCount":7,"Gates":[{"Name":"git-diff-check","Status":"PASS","ExitCode":0,"Summary":""},{"Name":"python-py-compile","Status":"PASS","ExitCode":0,"Summary":""}]}
```


## 2026-11-12 — Hotfix térmico validado; activación BLOQUEADA por Windows

- Logs hasta 16:56 UTC-3: 18 downsteps rechazados HTTP 400, 6 pausas y 6
  reanudaciones térmicas; 2 detecciones elapsed_drop (no equivalen a todos los ciclos).
- API /api/v1/autotune/presets del M24: no existe 2100; sí 2150, 2000, 1850,
  1800, 1740. /api/v1/presets devuelve 404. Se usa la escalera compartida validada.
- ViaBTC principal activa y aceptando shares en los cuatro mineros. No se cambiaron pools.
- Se intentó contención M24: preset/top 2150 y min 1740, API éxito y readback correcto;
  se autorizó y ejecutó un reinicio de minado. Automatización anterior volvió a 2300/
  techo 2500. NO declarar mitigación persistente ni potencia 2150 efectiva.
- Se preparó configuración local (backup ignorado diagnostics/heat-20261112/config-before.json):
  caps M23 2300, M24 2150, M25 2150, M26 2000; fan mínimo 100%; pre-clamp de
  recuperación 1800 (el default del engine era 2300); cooldown de mensajes térmicos 900 s;
  techos horario/solar 2300. Pendiente de recarga y aplicación física secuencial.
- Hotfix del código: ladder válida, prioridad de preset observado frente a balancer dry-run,
  piso 1740, confirmación de errores en downstep/pause/resume/unclamp, no resume si falló
  preset, conservación de pausa para reintento y avisos por minero/tipo con slot crítico propio.
- Arquitectura: sin nuevos hilos/locks. Estado térmico modificado por DetectionHook;
  descubrimiento de preset asíncrono conserva su contrato. Datos observados pueden ser
  concurrentemente refrescados; fallos de escritura ya no publican el target como observado.

Validación:
1. `.\.venv\Scripts\python.exe -m py_compile app/miner_monitor.py app/governance/thermal_guard.py` PASS.
2. `.\.venv\Scripts\python.exe -m pytest tests/test_emergency_thermal_guard.py tests/test_thermal_incident_regression.py -q`: 40 PASS.
3. Misma selección con DBG_TELEGRAM=1 y DBG_TELEGRAM_COMMANDS_ONLY=1: 40 PASS, sin Telegram real.
4. Suite inicial sandbox: 64 fallos por SQLite URI en ruta temporal con # y restricciones IPC.
   Primera ejecución fuera del sandbox: 1552 PASS, 4 errores por permisos pytest-of-Fran.
5. `.\.venv\Scripts\python.exe -m pytest tests/ -q --basetemp=diagnostics/heat-20261112/pytest-isolated-1`:
   1556 PASS, 75 subtests PASS, 42.34 s. Evidencia cruda ignorada pytest-isolated.txt.
6. `preflight_stabilize.ps1 -RunTests false -CheckFleet true`: 6/7 PASS;
   único FAIL: H004 abierta por activación/observación incompletas. Suite reutilizada del paso 5.
   Sintaxis, secretos, alineación config, servicio RUNNING y API 4028 de 4/4 PASS.

Bloqueo real: Stop-Service desde proceso autorizado falla por falta de elevación administrativa.
Start-Process powershell.exe -Verb RunAs devuelve operación cancelada por Windows. No se
reinició el servicio, no se aplicó la ventana snooze preparada y no se alteró state.json.
El servicio continúa vivo con código/config anteriores. No commit/push ni certificación de release.
Script listo: diagnostics/heat-20261112/deploy.ps1 (requiere PowerShell administrador).
Tras activación: aplicar cap por minero con apply_miner.py desde raíz (runpy para imports),
esperar estabilización de uno antes del siguiente, verificar restart_required=false, piscinas,
consumo, temperatura, cadenas, logs y al menos 15–30 min sin nuevos ciclos. No afirmar causa AC
sin mediciones externas de tensión; no se dispone de ese dato.


### Continuación autorizada — 2026-11-12 16:59–17:05 UTC-3

El usuario confirmó UAC. Despliegue administrativo completado 16:59:25: nuevo bloque
CONFIG sha=c45de830, startup guard600, EventStore available/schema7, servicio RUNNING.
Se respaldó state con servicio detenido y se aplicó snooze10min. Código/config ahora activos.
Caps físicos confirmados por lectura: M23=2300/top2300, M25=2150/top2150,
M26=2000/top2000; piso1740, switcher activo, restart_required=false en los tres.
M24 recibió preset2150/top2150 y reinicio de minado. Una pausa térmica persistida de antes
del despliegue colisionó con ese reinicio: resume falló mientras el minero inicializaba.
El hotfix correctamente conservó la pausa y NO anunció recuperación exitosa.
Se intentó reconciliación de estado con servicio detenido, pero segundo UAC fue cancelado;
el script de reconciliación NO se ejecutó. Se eligió alternativa operacional autorizada:
pausa real de M24 vía API y fans100; esperar recuperación del guardián desde estado coherente.
Conectividad Telegram y observación en vivo en curso; no declarar aún estabilidad certificada.


17:06:26 UTC-3: guardián reanudó M24 a 2000 W, temperatura69 C, resume_ok=True.
La recuperación por API resolvió la pausa pendiente sin editar state con proceso vivo.
Telegram getMe HTTP200 ok=True (solo consulta, sin mensaje de prueba).
M23/M25/M26 cap físico y restart_required=false verificados; M24 en arranque controlado.
Máximo configurado M24 continúa2150, techo físico de recuperación2000 bajo lock térmico.
Comienza observación final una vez que los cuatro mantengan mining; no afirmar estabilidad
basándose únicamente en el retorno exitoso de la API de reanudación.


### Activación final — 2026-11-12 17:12:30 UTC-3

Hallazgo de contrato VNish: resume/start retorna éxito pero puede conservar ajustes
pendientes; se cambió el actuador por defecto de recuperación térmica a restart_mining
(reinicio del proceso de minado detenido, no del control board), preservando inyección
de pruebas y gate QA. Se agregó prueba específica que prohíbe usar plain resume.
Validación final: 41 pruebas focalizadas PASS; suite completa 1557 PASS +75 subtests
PASS en42.22s con --basetemp=diagnostics/heat-20261112/pytest-isolated-2.
Compilación miner_monitor.py y thermal_guard.py PASS.
Se aplicó una vez el preset2000 pendiente a M24; API confirma restart_required=false.
M24 entró en auto-tuning del preset nuevo a2000 W, sin elevar potencia a2300.
Config local M24 endurecida a target2000/max2000W. Caps finales: 2300/2000/2150/2000.
UAC final aceptado por operador. Despliegue17:12:30: CONFIG sha810b32c6, servicioRUNNING,
startup guard600, EventStore available/schema7, balancer observa2300/2000/2150/2000.
State respaldado con servicio detenido; snooze breve180s. No edición de state en vivo.
Observación posterior en diagnostics/heat-20261112/observation.jsonl. Pendiente cierre
H004 cuando concluya la ventana acotada de observación; no commit/push automático.


## 2026-11-14 — Reconciliación: validada, recarga administrativa pendiente

Configuración dinámica del operador es vigente. Servicio aún con sha810b32c6 del12/11
17:12 mientras archivo actual tiene C3, minfan30 y nuevos avisos. No afirmar recarga.
Alertas generales=True, snooze vencido; Telegram getMe y getChatMember HTTP200 ok,
bot miembro sin restricción de envío. No se enviaron mensajes manuales de prueba.

Captura inicial: M23 2298W/81C/top2300; M24 2148W/82C/top2500;
M25 2148W/77C/top2150; M26 1998W/77C/top2000. Config pide2700/2500/2700/2500.
Preset configurado2150/2000/1800/1800 NO representa el tier nativo activo real.

Cambios de código: observador power_notifications.py en DetectionHook, sin actuadores;
confirmación90s, cooldown900s, startup/pausa/snooze/QA ignorados. El loop de detección es
único propietario del estado transitorio del observador; no nuevos hilos ni locks.
Se descubrió fallback de auto_restart_min_elapsed_seconds=120 en engine (ejemplo180,
config ausente). Interrumpió inicialización M25 a13:17 con preclamp1800. Se alineó fallback,
ejemplo y config a600s. Política de reinicio restante sin cambios; solo mayor gracia.

Actuación: techos M23/M24/M25 alineados2700/2500/2700; min1740; rise79/dec84/check300.
Primer POST solo de switcher fue rechazado400 sin cambio. POST con preset guardado fue
aceptado, pero VNish reaplicó ese preset, bajando temporalmente a2150/2000/1800 W.
No afirmar que cambiar top preserva el tier nativo aunque restart_required seaFalse.
M25 restaurado a2150 requirió un reinicio de minado autorizado; el supervisor viejo lo
interrumpió a120s y pre-clampeó1800. Volvió a producir a13:19, sin ajustes pendientes.
No seguir reiniciando ni forzando M25. Primero recargar gracia600, luego dejar subir VNish.
M26 conserva techo2000 hasta activar esa gracia y completar alineación escalonada.

Validación:
- py_compile miner_monitor.py, core/engine.py, governance/power_notifications.py PASS.
- pytest tests/ --basetemp=diagnostics/reconcile-20261114/pytest-temp:1561 PASS+75 subtests.
- Tras fallback600: pytest tests/ --basetemp=diagnostics/reconcile-20261114/pytest-temp-final:
  1561 PASS+75 subtests PASS en44.08s. Evidencia cruda ignorada pytest-final.txt.
- Pruebas del observador verifican ruido, arranque, cooldown, cambios bidireccionales,
  falta de telemetría y mantenimiento. No mensajes ni acciones reales desde pruebas.
- UAC para Restart-Service terminó cancelado/expirado. No hay restart-result.txt nuevo.

PENDIENTE: usuario acepta elevación o ejecuta restart.ps1 con PowerShell administrador.
Luego verificar CONFIG sha actual, completar techoM26 usando el tier REAL observado
(no el preset configurado), aplicar una vez solo si firmware exige restart y esperar
al menos600s sin autorreinicio antes de observar ascensos nativos. No subir todo simultáneo.
El helper align.py fue corregido para tomar el tier real, pero requiere verificar settings
pendientes y resolverlos antes de declarar éxito. No tocar pools, no editar state en vivo.

Preflight 14/11 13:22:13 (-RunTests false -CheckFleet true):6/7 PASS;
único FAIL es DoD por H004/R004 pendientes. Suite final reutilizada1561+75 PASS.
Con DBG_TELEGRAM=1 y DBG_TELEGRAM_COMMANDS_ONLY=1: tests/test_power_notifications.py
más tests/test_restart_intelligence.py:15 PASS. No mensajes reales desde pruebas.


## Continuación 2026-11-14 18:00 UTC-3 — recarga confirmada

El operador informa que abrió Codex como administrador y autoriza cerrar el sistema.
Verificación local: app26.1111.2228.0 packageStatus=Ok; runtime nuevo26.1112.737.0=Ok;
runtime anterior26.1111.570.0=NotAvailable. No evidencia suficiente de corrupción.
GetTokenInformation(TokenElevation) aplicado por ctypes a app/agent/ejecutor confirma
not_elevated en los tres. require_escalated sale del sandbox pero no obtiene token UAC.
Consulta SCM fuera de sandbox funciona: MinerAlerts RUNNING, PID4884, inicioAuto.
La app pudo abrirse sin que esta cadena de procesos quedara elevada; no atribuir a una
actualización concreta sin prueba. Reporte público similar: github.com/openai/codex/issues/46682.
No se cambió registro, seguridad, permisos de WindowsApps ni instalación de Codex.

Logs confirman recarga real17:59:24, configshaefa85f7d igual al archivo actual. Incluye
avisos de potencia=True, gracia600s, minfan30 y objetivosC3. EventStore available/schema7.
No se necesita otra recarga para los cambios ya validados1561+75PASS. No editar state vivo.

18:04 M25: captura2148W/77C, tres cadenas produciendo. Escritura con preset observado2150,
top2700/min1740. Retorno200, restart_required=False, minería continúa sin reinicio.
Es un resultado distinto al intento anterior; no generalizar que siempre requiere restart.
Esperar ventana de asentamiento antes de M26. Capturas evening-observation.jsonl ignoradas.


18:07:30: captura muestra M25 subir nativamente2148->2298 W, temperatura78 C,
mining uptime continuo y restart_required=False. 18:08:56: [POWER_CHANGE]
miner=S19JPRO-25 2150->2300W confirmed=90s; no errores de entrega posteriores.
18:10–18:11: M26 observado1998W/76C; preset2000/top2500/min1740 aceptados200,
restart_required=False, sin reinicio de minado. Ambas intervenciones de la tarde
conservaron producción y no requirieron reinicio de ASIC ni del proceso de minado.
Minero activoC3 por encima de umbral de subida se mantiene en su tier por temperatura;
no forzar nominal cuando falte margen. Continúa observación final de los dos elevadores.


18:14:01: M26 subió nativamente de1998 a2149W, temperatura77C, uptime continuo,
restart_required=False. Ya se observaron ambos powerups pedidos. A18:14:24 se completan
15min desde recarga17:59:24, sin nuevas pausas térmicas ni reinicios en la observación.
H004 se cierra reconciliando la política vigenteC3 del operador; no se certifican
retroactivamente los caps transitorios del día12 ni una observaciónD+1 que no fue registrada.
R004: alineación y powerups observados; se ejecuta preflight final completo a continuación.


## Cierre verificado — 2026-11-14 18:17 UTC-3

Preflight completo speckit-stabilize: PASS,8/8, cero gates fallidos,18:16:33.
Comando: preflight_stabilize.ps1 -RunTests true -CheckFleet true. TEMP/TMP se apuntaron
al directorio local ignorado stabilize-temp; PYTEST_ADDOPTS fijó --basetemp local para
evitar los fallos anteriores del sandbox y permisos de temporales. Resultado de pytest:
1561 PASS,75 subtests PASS en93.88s. Sintaxis, diff-check, secretos, alineación de ejemplo,
NSSM RUNNING, APIs4/4 y DoD PASS. Evidencia cruda: stabilize-final.json (ignorada).

Recarga efectiva17:59:24, shaefa85f7d. Captura final2026-11-14T18:17:31.472029-03:00:4/4mining,12cadenas
produciendo, ViaBTC principal activa4/4, restart_required=False4/4. Consumo ASIC reportado
8744W, hashrate343.16TH/s. Temperaturas80/80/80/78C; no medición AC de tablero.
Firmware/config: techos2700/2500/2700/2500, mínimo1740, rise79/decrease84/check300.
Potencias ACTIVAS2298/1999/2298/2149W. No confundir preset guardado con tier activo.

M25 subió2150->2300; M26 subió2000->2150. Avisos confirmados90s registrados a18:08:56
y18:15:26. Desde recarga hasta captura final:0reinicios detectados,0pausas térmicas,
0acciones térmicas fallidas y0errores Telegram en out.log. Se verifica generación del aviso
y ausencia de error registrado; no se afirma confirmación de lectura en el teléfono.

Se completan H004/R004 con la política dinámica actual del operador. No se certifica
retroactivamente la observación del día12. No se agregaron actuadores, ni se modificó
state en vivo, ni se reiniciaron mineros durante la alineación de la tarde.
Código/config ya recargados. No hay pendientes de activación ni UAC para este cierre.
Commit/push permanecen manuales; no activar una nueva spec antes del cierre de release
manual exigido por la constitución. Salud futura y D+1 requieren evidencia futura.


### Extensión de observación hasta18:19 UTC-3
M26 efectuó un segundo powerup nativo2150→2300W, a79°C, sin reinicio ni ajustes
pendientes. No se repitió un aviso inmediato dentro del cooldown900s, conforme al
criterio anti-spam. Los cuatro siguenOK; observación completa supera19min desde recarga.
Captura18:19:01:2298/1999/2298/2299W; temperaturas80/80/80/79°C; ~343.5TH/s.
Se detuvo únicamente el lector auxiliar de observación al finalizar; MinerAlerts continúa.


## Producción nocturna14/11 — análisis y hotfix

Lectura de495103muestras acumuladas (rango desdeagosto); análisis principal30d con
exposición normalizada aproximando30s por muestra. Eventos:82reinicios detectadosM25 y
60M26 en30d, frente11/11M23/M24. Cohortes45s:40episodios25+26 y4episodios23+24;
filtrando classification=unexpected:23pares25+26 frente2pares23+24. No equivalen a
40cortes eléctricos: incluyen intervenciones y limitaciones de atribución históricas.

Incidente21:48:47/51: logs VNish deM25/M26 registran lectura de registro fallida y chain#1
break, apagado ordenado del minado y reinicio del proceso. Telemetría previa79C ambos,
2298/2299W; último cambio relevante M25a18:07:26 yM26a18:18:56. M23/M24 continúan
uptime. No prueba de sobretemperatura, cambio inmediato de potencia o orden del monitor.
No afirmar corte completo de energía ni reinicioLinux; no hay mediciónAC de entrada.
Conclusión: perturbación compartida en ramaelevador2 probable; calle/elevador/protección
siguen sin poder separarse. Datos de PSU/chain sonDC y no sustituyen tensión de red.

Exposición30d: M25a2700W≈346.3h,60reinicios próximos/17.33por100h,100.26TH/s activo;
a2500W≈236.7h,10reinicios/4.23por100h,93.86TH/s activo. Estimación con mediana de
recuperación produce98.84vs93.55TH/s; no fingir que2500maximiza SHA neto. El límite2500
es un compromiso explícito de continuidad/eficiencia: se renuncia a≈5TH/s para reducir
la concentración de reinicios. Comparación observacional con clima, selección y cambios
de firmware; no lucro monetario calculado sin tarifa/rendimiento de pool.

Aplicación: config localM25target2500/max2500, perfil de recuperación alineado;M23permite2700,
M24/M26hasta2500. Maxconfig elevador2=5000W, no 5200. FirmwareM25 alineado sinreinicio,
real ya2499W. No capbajo permanente en toda la flota ni segundo actor de potencia.

Hallazgos corregidos:
- pipeline comparaba last_active_boards=None contraint y abortaba recuperación firmware;
  helper puro descarta falta de datos como evidencia de stock, salvo flag explícito.
- QA de handle_stock_firmware_recovery no bloqueaba los threads; ahora retorna antes.
- stock_firmware_reflash_enabled=False era ignorado; ahora impide el flash.
- Correlación45s por grupo captura reinicios aunque socket siga respondiendo; evento
  elevator_cascade_detected compatible con sensibilidad histórica. Aviso neutral900s/grupo;
  no nuevo actuador ni atribución eléctrica confirmada. Estado acotado solo deDetectionHook.
- dry-run del balancer falseaba presetaplicado/timestamps/locks, presupuesto compartido y
  boost de ventilación. Ahora conserva proyecciones diagnósticas, copia estado de presupuesto
  y no modifica campos de acción ni envía confirmaciones de acción. Pruebas antiguas que
  exigían esa mutación se modernizan; prueba de escritura real conserva cobertura.

Validación: primeros1576+75PASS; tras aislar dry-run1577+75PASS46.04s. CompilaciónPASS.
Dos fallos iniciales SQLite en sandbox por temporales no reflejaron regresión; fuera de
sandbox quedó un contrato legacy de simulación, actualizado a estado no aplicado.
Pruebas QA y reflash-disabled verifican cero creación de threads. Replay del evento real
produce elevador2; sin actuadores. No se provocó otra caída para probar el aviso en vivo.

Activaciones:22:05:52 primera recarga;22:11:33 final incluye separación de simulación,
configsha997550ad. EventStore disponible. Ningún minero reiniciado por los ajustes nocturnos.
Perfiles dorados tenían topviejos e ignore_fan_speed=False: alineados con política actual,
sin cambiar pools, red ni credenciales. Backups ignorados en diagnostics/production-20261114.

Análisis térmico30d: M23sube2300→2500(n25) mediana+3C,p90+4C en3min;2500→2700(n25)
p90+4.3C. Se observóM23a2500/84C. Umbral nativo de subidaM23reducido79→78C conservando
max2700/min1740/decrease84/check300, sin reinicio ni ajustes pendientes; persistidoenperfil.
POSTparcial de temperatura rechazado400 sin efecto; objeto switcher completo leído del
firmware aceptado200. Otros umbrales conservados79; no cambios al umbral crítico de parada.


### Corrección de semántica de potencia real en el guardián térmico

El preset JSON guardado puede diferir del tier realmente activo de VNish. Usarlo como
fuente primaria podía ordenar una reducción que no redujera la carga real, o bajar demasiado.
La decisión activa ahora prioriza potencia medida; DetectionHook pasa chain_power_w_total
fresco por argumento opcional, sin alterar el estado del FanGovernor para ese propósito.
En pausa no hay potencia: se conserva el siguiente tier seguro medido antes del stop en
thermal_resume_preset, campo opcional persistido. Se valida contra la escalera y el techo
configurado antes de reanudar. El campo no es trigger: requiere la pausa, enfriamiento,
duración, QA y mantenimiento ya existentes. Un estado legado sin ese dato usa1740W
conservador al reanudar. Fallos de aplicación conservan pausa/hint para reintento; éxito los limpia.
No nuevos threads/locks. Solo DetectionHook escribe ese dato y la persistencia usa el
mismo contrato existente. Tests prueban roundtrip, hint inválido y límite rebajado en config.
47tests térmicosPASS; se ejecuta regresión completa antes de la recarga final.


Regresión térmica final completa:1583PASS+75subtestsPASS44.61s, en pytest-thermal-final.txt.
Se validaron modelos y state_manager nuevos, legacy sin campo, límites y persistencia.
Sin cambios posteriores al código validado antes de recarga. No acciones reales desde tests.


## Cierre técnico nocturno — 14/11/2026 22:37 UTC-3

**Preflight de software PASS, 8/8 compuertas, a las22:35:16.** 1583 pruebas y75 subpruebas
PASS en92.84s. Sintaxis, diff, secretos, config, servicio, flota y DoD automatizadosPASS.
La instalación de código final se verificó a22:31:50, con estado persistido nuevo presente.
Se usaron TEMP/TMP y basetemp locales para no confundir errores del sandbox con regresiones.

Captura final2026-11-14T22:37:44.578494-03:00: cuatro mineros minando, doce cadenas produciendo, ViaBTC
activa4/4, ningún restart_required. Potencia reportada9443W; hashrate360.11TH/s.
Actuales:2298/2148/2499/2498W; temperaturas81/79/82/82°C. M25/M26 sostienen el régimen
pareado de2500W; M23 se reguló de2500a2300W por temperatura, sin reiniciar.
Desde22:11:33 hasta22:37:44: **cero reinicios detectados**. El código final lleva~6min
en vivo; el régimen físico fue observado~26min. Se mantienen separados esos períodos.

Las pruebas cubren None, QA, reflash deshabilitado, simulación sin side-effects y cálculo
correcto de potencia/reanudación térmica. No se provocó otra falla eléctrica para ensayar
la correlación; ese circuito lógico se verificó con replay y pruebas deterministas.

**Incidente físico abierto.** Esta ventana inmediata no demuestra que desapareció la
perturbación compartida de la rama2. Falta registroAC de entrada/salida correlacionado con
un evento para decidir calle, elevador o protección. No se certifica reparación eléctrica
ni máximo monetario global. Se aplicó una política operativa basada en evidencia y límites.

Código/config/perfiles ya activos; no pendientes de UAC o despliegue. Commit y push siguen
manuales. No activar otra spec antes del cierre manual de release y los gates aplicables.


## Verificación solicitada — 2026-11-15 14:34 UTC-3

Revisión de solo lectura documentada en docs/audit/OPERATIONAL_CHECK_20261115.md.
SCM RUNNING, heartbeat actualizado, cola0; GETsummary/status4ASIC y
getMe/getWebhookInfo/getChat200. Cuatro mineros minando (~345.6TH/s promedio30min).
Se detectan dos fallos sendMessage sin reencolado, atribución incorrecta de un soft
restart y nuevo chain_break individualM26 con recuperación. Hallazgos abiertos,
no declarar reparación ni entregaTelegram certificada. Sin cambios de producción.


Ampliación Telegram Desktop: operador abrió la sesión; recepción real de mensajes
confirmada. Status etiqueta falsamente Silenciado ante snooze vencido; digest cuenta
accionesreboot pero etiqueta reinicios y omite restart_detected; M26 alterna cinco
avisosLOW/HASHBOARD11:40–11:44. Avisos potencia00:18/12:06 no aparecen en historial
leído. Detalles y contratos en OPERATIONAL_CHECK_20261115.md. Sin cambios de código.


## Iteración M — Correcciones de Telegram, 15/11/2026

QA previo: `.agents/skills/speckit-qa/scripts/preflight.ps1 -RunBuilds`, PASS.
Regresión final: `python -m pytest tests/ -q --basetemp=diagnostics/messaging-20261115/pytest-release`,
con DBG_TELEGRAM=1 y DBG_TELEGRAM_COMMANDS_ONLY=1: 1604 PASS +75 subtests PASS, 47.19 s.
21 pruebas nuevas del incidente; compilación explícita de monitor, engine, event_store,
delivery, transition_notices, sender, fleet_cards y daily_digest: PASS. `git diff --check`: PASS.
El contrato del fallback conserva timeout1.5/4; mocks actualizados con Telegram ok=true.
Prueba inicial de atribución usaba fechas artificiales cercanas a epoch0 y activaba
el timestamp legado shutdown0; se corrigió la fecha del fixture, sin cambiar política.

Servicio recargado por restart.ps1 acotado a Restart-Service, sin edición de estado/config.
Resultado15:13:47 Running. Capturas before/after conservan uptime creciente en los cuatro
ASIC; 4/4 mining,12cadenas,ViaBTC activa yrestart_required=false. Snapshot15:14:51:
344.93TH/s,9043W reportados,80/83/81/81C. HeartbeatPID33444, cola0, tick/sender~5s.
Render Status con estado real no contiene Silenciado; digest cuenta6restart_detected24h
y0órdenesreboot. Artefactos en diagnostics/messaging-20261115/, sin secretos en docs.

Implementación y riesgos: docs/audit/STABILIZATION_REPORT_20261115_MESSAGING.md.
Sin outbox persistente: retries acotados pueden duplicar si se perdió respuesta; tras
agotamiento se registra fallo. No se provocaron caídas de red ni ASIC. Hallazgos físicos
siguen abiertos. Nuevas specs094/095 solo diseñadas; ninguna activa ni implementada.
Gate final speckit-stabilize se registra a continuación al terminar. Commit/push manuales.


### Gate final y observación de cierre — 15/11/2026 15:19 UTC-3

`preflight_stabilize.ps1 -RunTests $true -CheckFleet $true`: PASS,8/8 compuertas,
15:17:59. Suite raíz1604 PASS+75subtests PASS en95.59s. TEMP/TMP en carpeta local
ignoraday PYTEST_ADDOPTS con basetemp específico; primer intento de invocación sin
valores booleanos no ejecutó el gate y se corrigió el comando (parámetros Object).
ReporteJSON: diagnostics/messaging-20261115/stabilize.json.

Captura final15:19:11:4/4mining,12cadenas,ViaBTC activa, restart_required=false.
345.04TH/s instantáneos,9043W reportados,80/83/81/81C; uptime creciente en todos.
Proceso nuevo15:13:46,~5min25s de observación; cola0, poller43s, sender30s, tick25s.
Watchdog real15:18:54healthy=true. No se confunden líneas simuladas de pytest con
incidencias reales del watchdog. D+1 sigue pendiente; diagnóstico físicoM26 abierto.
No se ensayó entrega en vivo cortando Telegram ni se provocaron acciones de ASIC.

Limpieza: cleanup_transients.ps1 -DryRun $true ejecutado,22candidatos; se preservaron
logs forenses, caches y toda evidencia. Escaneo adicional de archivos nuevos ydiff:
sin patrones de token real. Config/state ignorados ysin staging. Commit/pushmanuales.


El15/11 el operador autorizó explícitamente cerrar093 con commit/push y continuar094.
Se publica el software validado; D+1 y diagnóstico físico siguen registrados como abiertos.
Se verifica remoto antes de push; config/state/datos locales excluidos del índice.
