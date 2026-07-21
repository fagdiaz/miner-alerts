# Historial de Desarrollo y Cambios - Miner Alerts

Este archivo registra las specs y cambios completados que tienen respaldo en el codigo, la documentacion o evidencia operativa vigente, en orden cronologico inverso.
La entrada mas reciente debe agregarse inmediatamente debajo de este bloque.

---

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
