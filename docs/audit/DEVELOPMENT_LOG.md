# Historial de Desarrollo y Cambios - Miner Alerts

Este archivo registra las specs y cambios completados que tienen respaldo en el codigo, la documentacion o evidencia operativa vigente, en orden cronologico inverso.
La entrada mas reciente debe agregarse inmediatamente debajo de este bloque.

## [2026-08-27] - Cierre de Gate D+3 (Spec 021 Liveness Watchdog) y Desbloqueo de Spec 022

* **Objetivo**: Auditar el período de soak de 72 horas continuas en producción para Spec 021, cerrar la especificación con evidencia runtime y desbloquear la fase de activación de Spec 022 (Adaptive Acquisition).
* **Auditoría Runtime y Evidencia (77h 20m continuas)**:
  - Proceso de producción (PID 8520, wrapper 4568) iniciado el 2026-08-24 08:43:14 superó formalmente las 72h con 278.435 segundos acumulados (77.34 horas) sin un solo reinicio, cuelgue o fallo de proceso.
  - Ticks de flota completados: 9.193 con cola 0. Edades de workers y tick estrictamente frescas (< 35s).
  - Watchdog de vida evaluó 4.642 muestras con 0 alarmas tras el calentamiento inicial del colector.
  - Seguridad operativa: 1 auto-reboot legítimo y controlado en minero 25 (2026-08-25 10:23:06) tras 604s de hashrate 0.0 TH/s, respetando todos los interlocks. Flota actual 100% OK (`ok_streak` = 12.267).
  - T013 y Definition of Done de Spec 021 marcados como completados en `specs/021-monitor-liveness-watchdog/tasks.md` y documentados en `evidence.md`. Spec 021 cerrada formalmente al 100%.
* **Próximo Paso**:
  - Desbloqueada la activación de Spec 022 (Adquisición Adaptativa). Siguiente tarea: T011 (Verificaciones de invariantes de acción/estado y preparación de rollout en modo shadow).

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
