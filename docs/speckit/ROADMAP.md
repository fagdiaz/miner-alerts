# Miner Alerts Speckit Roadmap

**Last reviewed**: 2026-09-08
**Specification program**: `docs/speckit/SPEC_PROGRAM.md`
**Delivery calendar**: `docs/speckit/DELIVERY_PLAN.md`

## Resumen Ejecutivo y Progreso del Programa

- **Progreso Acumulado del Proyecto (desde Spec 001)**: `100%` (44 de 44 especificaciones del programa completadas y verificadas con evidencia en producción y suite de tests: 621 tests PASS).

### 🏆 Avances Principales Desde el Inicio (Spec 001 a Spec 030)

1. **[COMPLETADO] Specs 001 a 019 — Arquitectura Base y Telemetría**: Polling autoritativo API 4028, base SQLite (esquema v1-v6), integración Hashcore Toolkit, captura de logs Vnish, diagnósticos de calidad y perfil de estabilidad.
2. **[COMPLETADO] Spec 020 — Estabilización de Estados y Autoreinicio**: Máquina de 5 estados estables (`OK`, `LOW`, `OFFLINE`, `HASHBOARD`), interlocks térmicos/de flota y cero reinicios espurios (`e502ab9`).
3. **[COMPLETADO] Spec 030 — Calidad de Mensajería Telegram**: Cola de entrega por prioridad, división segura de mensajes extensos y protección anti-rate limit (`2afd65e`).
4. **[COMPLETADO] Spec 021 — Watchdog de Vida y Recuperación SCM**: Supervisión fuera de proceso, heartbeat y prueba SCM aprobada; gate D+1 (86.7k s) y D+3 (278.4k s / 77.3h) superados con éxito continuo; spec cerrada.
5. **[COMPLETADO] Spec 022 — Adquisición Adaptativa y UX Telegram Compacto**: Producción activa con PID 38816 (2 workers paralelos). Gate D+1 (42.7h) y Gate D+3 (73.45h / 264.4k s, 8.766 ticks, 0 alarmas, watchdog 100% healthy) superados con éxito continuo; spec cerrada.
6. **[COMPLETADO] Spec 023 — Fusión de Evidencia de Incidentes**: Módulo puro `app/evidence_fusion.py` (T001-T018), rutas de lectura `/diagnose` activadas (T019), tablas aditivas `incident_assessments` e `assessment_fact_refs`, validación determinista y rendimiento verificado (344 tests PASS).
7. **[DISCOVERY GATE COMPLETADO - BLOQUEADO POR HARDWARE] Spec 024 — Descubrimiento de Telemetría Eléctrica**: Relevamiento completado (T001-T004). Prohibida la inferencia de AC desde voltajes DC de hashboards; resultado formal `blocked: missing_hardware_dependency` ante ausencia de PDU/UPS de red. Adaptadores pausados sin deuda técnica ni falsas asunciones.
8. **[COMPLETADO] Spec 026 — Inventario de Capacidades Hashcore**: Herramienta desacoplada `tools/hashcore_inventory.py` (T001-T018), 10 nuevos tests unitarios (381 tests PASS global), metadatos de instalación PE verificados (`1.6.0+167`, wrapper `toolkit_cli.bat` SHA `2c204d87`, exe `hashcore-toolkit.exe` SHA `9db18421`), cero llamadas a subprocess en modo metadata y allowlist vacía con resultado `blocked` sin alterar el monitor en producción.
9. **[COMPLETADO] Spec 028 — Backups, Retención y Recuperación por Etapas**: Herramienta desacoplada `tools/event_store_backup.py` y script instalador `tools/install_backup_task.ps1` (T001-T014), 10 nuevos tests unitarios (391 tests PASS global), backup online por lotes de 256 páginas, retención determinista UTC 14/8/12, simulacro de restore en staging superado con éxito sobre la BD real de 20.4 MB en 6.2s y runbook de desastre documentado en `docs/speckit/RUNBOOK.md`.
10. **[COMPLETADO] Spec 025 — Métricas de Prometheus y Paneles Grafana**: Módulo de instantáneas `app/metrics_snapshot.py` (T001-T005), exportador `tools/metrics_exporter.py` (T007), stack Docker Compose aislado `docker-compose.observability.yml` (T008), 3 tableros Grafana (T009), hook atómico en el monitor (T006), 13 tests unitarios (404 tests PASS global).
11. **[COMPLETADO] Spec 027 — Decisión de Interfaz de Operación**: Scorecard de flujos W01-W06 ejecutado (30 corridas verificadas). Todas las necesidades P1 cubiertas por Telegram (`/status`, `/diagnose`), Grafana (`fleet_overview`, `monitor_liveness`) y Dashboard HTML estático (`tools/operations_dashboard.py`). Decisión formal `no_build` adoptada sin código adicional, preservando la superficie mínima y cero impacto en recursos.
12. **[COMPLETADO] Spec 029 — Estabilización Final y Candidato de Release V2**: Congelamiento determinista de payload SHA-256 (`58d451f1...`, 43 archivos), validación total de matriz R001-R025 (416 tests PASS), simulacro de restore staging de SQLite superado en 2.5s (23.2 MB), herramienta `tools/release_audit.py`, observación acumulada de 267.2 horas en producción bajo PID 38816 con 0 caídas, y aprobación formal (`APPROVE`) del Release Candidate V2.

---

### 🚀 Programa V3: Maximización de Telegram & Capacidades Avanzadas

1. **[COMPLETADO] Spec 031 — Botones Interactivos y Callbacks Telegram (`031-telegram-interactive-callbacks`)**:
   - *Objetivo*: Inline Keyboards en alertas de episodios para diagnósticos y gráficos en 1 toque.
   - *Valor y Beneficio*: Flujo interactivo seguro de reinicio en 2 toques (`[ 🔄 Reiniciar ]` -> `[ ✅ Confirmar ]` / `[ ❌ Cancelar ]`) con token de 60s, eliminando tipeo manual sin riesgos de toques accidentales.
   - *Resultados*: 14 tests PASS en `tests/test_telegram_callbacks.py`, 430 tests globales PASS, cero impacto en estabilidad.
   - *Modelo*: Gemini 3.8 Flash High (Fases 1, 2, 4, 5) + Claude Sonnet 4.6 Thinking (Fase 3).

2. **[COMPLETADO] Spec 032 — Gráficos Nativos Visuales en Telegram (`032-telegram-visual-charts`)**:
   - *Objetivo*: Envío directo de imágenes PNG con la curva de hashrate, temperaturas y RPM al chat vía `/chart <id>` y `/chart fleet`.
   - *Resultados*: 6 tests PASS en `tests/test_telegram_charts.py`, 436 tests globales PASS, renderizado en RAM en 219ms sobre 23.2 MB, cero archivos temporales.
   - *Modelo*: Gemini 3.8 Flash High.

3. **[COMPLETADO] Spec 033 — Mantenimiento y Silenciamiento Temporal (`033-miner-maintenance-snooze`)**:
   - *Objetivo*: Modo `/snooze <miner|all> [minutos]` y botón 1-Tap `[ 🔕 Silenciar 1h ]` para suprimir alertas, recordatorios persistentes y bloquear autorreinicios durante intervenciones físicas programadas con auto-expiración.
   - *Resultados*: 12 tests PASS en `tests/test_telegram_snooze.py`, 448 tests globales PASS, persistencia en `state.json`, bloqueo de autorreinicio en caliente y cero impacto en producción.
   - *Modelo*: Gemini 3.8 Flash High.

4. **[COMPLETADO] Spec 034 — Reporte Ejecutivo Diario (`034-daily-executive-digest`)**:
   - *Objetivo*: Resumen programado diario matutino (08:00 AM) y on-demand `/digest` con uptime de flota, TH/s promedio, J/TH, shares %, anomalías y verificación de integridad de backups SQLite.
   - *Resultados*: 10 tests PASS en `tests/test_daily_digest.py`, 458 tests globales PASS, rendimiento real medido de 27.2 ms de consulta y 0.07 ms de render, cero bloqueos de escritura y despacho blindado una sola vez al día.
   - *Modelo*: Gemini 3.8 Flash High.

5. **[COMPLETADO] Spec 035 — Inteligencia Térmica y de Ventiladores (`035-cooling-fan-health`)**:
   - *Objetivo*: Supervisión analítica de ventiladores (`/fans [miner]`), cálculo de margen térmico hacia el corte (85.0°C), y alertas preventivas de saturación térmica (`COOLING_WARNING`) para anticipar limpieza de filtros antes del disparo de temperatura por hardware.
   - *Resultados*: 14 tests PASS en `tests/test_fan_health.py`, 472 tests globales PASS en 4.60s, consulta SQLite en < 1ms sobre base de 23.2 MB, cero bloqueos y monitoreo en vivo PID 38816 100% ininterrumpido.
   - *Modelo*: Gemini 3.8 Flash High.

6. **[COMPLETADO] Spec 036 — Eficiencia Energética Continua (`036-efficiency-energy-tracking`)**:
   - *Objetivo*: Seguimiento en tiempo real del ratio Joules por Terahash (J/TH), potencia de cadenas en Watts/kW, y alertas tempranas de degradación energética (`EFFICIENCY_WARNING`) vía `/efficiency` (alias `/eff`).
   - *Resultados*: 12 tests PASS en `tests/test_energy_efficiency.py`, 484 tests globales PASS en 4.84s, consulta SQLite en < 1ms, cero bloqueos y monitoreo en vivo PID 38816 100% ininterrumpido.
   - *Modelo*: Gemini 3.8 Flash High.

7. **[COMPLETADO] Spec 037 — Seguimiento de Presets y Autotuning Dinámico (`037-vnish-presets-autotuning`)**:
   - *Objetivo*: Monitoreo de frecuencias (MHz), tensión de cadena (V), potencia y calibración autotune del firmware Vnish vía `/presets` (alias `/preset`, `/profile [minero]`) y alerta preventiva `PROFILE_CHANGE_ALERT` ante reducciones de frecuencia ($\ge 25\text{ MHz}$).
   - *Resultados*: 11 tests PASS en `tests/test_vnish_presets.py`, 495 tests globales PASS en 5.04s, consulta SQLite en 1.77ms sobre BD de 23.2 MB, cero bloqueos y monitor en vivo PID 38816 100% ininterrumpido.
   - *Modelo*: Gemini 3.8 Flash High.

8. **[COMPLETADO] Spec 038 — Auditoría de Concurrencia y Estabilización Release V3 (`038-v3-release-stabilization`)**:
   - *Objetivo*: Auditoría profunda de concurrencia multihilo, cerrojos `state_lock`, prevención de deadlocks en callbacks/colas y suite determinista de tests de estrés (`tests/test_v3_concurrency.py`).
   - *Resultados*: 19 tests PASS en `tests/test_v3_concurrency.py`, 514 tests globales PASS en 14.61s, resolución de race condition en `CallbackTokenRegistry`, snapshots inmutables en `save_state()`, higiene SQLite `?mode=ro` con `finally: conn.close()`, PID 38816 > 267.3h continuo y Release Candidate V3 (v3.0.0) aprobado.
   - *Modelo*: Claude Sonnet 4.6 (Thinking) + Gemini 3.8 Flash High (Colaboración Multi-Modelo).

---

### 🎉 Release V3.0.0 Certificado y Aprobado (Specs 031 a 038): 100% COMPLETADAS Y CERTIFICADAS

El programa completo de expansión V3 (Specs 031 a 038) está cerrado y validado, con 514 tests automáticos aprobados y cero impacto sobre el monitor vivo PID 38816 (>267.3h soak).

---

### ⚡ Programa V3.1: Control y Gobernanza de Hardware (Activación Plena en Producción)

9. **[COMPLETADO Y ACTIVO EN PRODUCCIÓN] Spec 039 — Gobernador Térmico y Acústico de Ventiladores Vnish (`039-vnish-fan-governor`)**:
   - *Objetivo*: Detección de modo en `/fans` (`manual`/`auto`), cliente REST seguro (`app/vnish_client.py`) y algoritmo de lazo cerrado determinista (`app/fan_governor.py`) modulando coolers hacia la temperatura sana de 83.0°C (banda muerta [82.0, 83.5]°C), reduciendo el estrés acústico y el desgaste mecánico sin comprometer hashrate.
   - *Calibración y Hardening*:
     * Target: 83.0°C; Deadband: [82.0, 83.5]°C; Emergencia: 84.0°C (spike inmediato a 100% PWM).
     * Modulación descendente de ventiladores (-2%) ante temperaturas < 82.0°C y ascendente (+3%) ante > 83.5°C.
     * Concurrencia HTTP: ThreadPoolExecutor con timeout de 2.5s por minero, 5.0s límite de flota y `shutdown(wait=False)`.
     * Fail-Safe: Retorno forzado a 100% ante `/gov off`, $\ge 3$ fallos consecutivos o excepciones.
     * Configurado como **ACTIVO POR DEFECTO** (`fan_governor_enabled: true`, `fan_governor_dry_run: false`), con control manual interactivo en caliente vía Telegram (`/gov on`, `/gov off`, `/gov set`).
   - *Resultados*: Fases 1 a 5 completadas al 100% (T001-T021), 12 tests de concurrencia y estrés (`tests/test_fan_governor_concurrency.py`), 576 tests globales PASS.
   - *Modelo*: Gemini 3.8 Flash High + Claude Sonnet 4.6 Thinking.

10. **[COMPLETADO Y ACTIVO EN PRODUCCIÓN] Spec 040 — Calibración Dinámica de Presets y Elevadores de Tensión (`040-dynamic-voltage-presets`)**:
    - *Objetivo*: Algoritmo inteligente de optimización de Costo/Beneficio que evalúa la estabilidad eléctrica por elevador de tensión, frecuencia de reinicios y margen térmico, calibrando el preset de potencia Vnish (de 1600W a 2800W) para maximizar el hashrate efectivo continuo y prevenir caídas en cascada.
    - *Calibración y Hardening*:
      * Desescalado Térmico (`ACTION_STEP_DOWN_THERMAL`): Si a 2700W con ventiladores al 100% la temperatura es $\ge 84.0^\circ\text{C}$ (margen $\le 1.0^\circ\text{C}$ frente al corte de 85°C), desescala secuencialmente de potencia (`2700W -> 2500W -> 2300W`).
      * Protección de Elevadores: Desescalado rápido individual ante $\ge 2$ reinicios en 24h y desescalado grupal en cascada si $\ge 2$ mineros del mismo elevador reinician en ventana de 30m.
      * Subida conservadora: Requiere 72h de soak continuo sin reinicios y margen térmico $\ge 4.0^\circ\text{C}$.
      * Mitigación de Spam: Alertas de autotune de Vnish suprimidas (`preset_alert_enabled: false`) y saturación térmica ajustada a 84.0°C/98% PWM/cooldown 2h.
      * Configurado como **ACTIVO POR DEFECTO** (`preset_balancer_enabled: true`, `preset_balancer_dry_run: false`), con control manual interactivo en caliente vía Telegram (`/balancer on`, `/balancer off`, `/balancer setmax`, `/balancer run`).
    - *Resultados*: Fases 1 a 5 completadas al 100% (T001-T020), 23 tests unitarios e integración (`tests/test_preset_balancer.py`, `tests/test_preset_balancer_integration.py`), **576 tests globales PASS**.
    - *Modelo*: Gemini 3.8 Flash High (100% autónomo).

11. **[COMPLETADO] Spec 041 — Arquitectura Modular y Reorganización de Dominios en `app/` (`041-app-modular-architecture`)**:
    - *Objetivo*: Reorganizar los 22 archivos planos en `app/` en 4 subpaquetes de dominio desacoplados (`app/core/`, `app/vnish/`, `app/governance/`, `app/telegram/`), manteniendo `app/miner_monitor.py` como punto de entrada raíz y preservando 100% de retrocompatibilidad mediante shims con module aliasing (`sys.modules[__name__] = _impl`).
    - *Dominios Reorganizados*:
      * `app/core/`: red API 4028, SQLite `EventStore`, episodios de alerta, fusión de evidencia, liveness/watchdog, métricas snapshot, calidad de minado y seguridad de reinicios (10 módulos).
      * `app/vnish/`: cliente REST, autotuning/presets, parser de logs y telemetría (4 módulos).
      * `app/governance/`: fan governor en lazo cerrado, preset balancer por elevador, salud térmica de fans y eficiencia energética (4 módulos).
      * `app/telegram/`: callbacks interactivos, gráficos PNG en RAM, digests diarios, split de mensajes y mantenimiento snooze (5 módulos).
    - *Resultados*: Fases 1 a 6 completadas al 100% (T001-T042), **587 tests globales PASS** en 11.26s, cero quiebres en importaciones externas ni monkey-patching en tests, auditoría de release aprobada (83 archivos).
    - *Modelo*: Gemini 3.8 Flash High (100% autónomo).

12. **[COMPLETADO] Spec 042 — Purga Limpia de Shims y Modernización de Tests en `app/` (`042-purge-shims-test-modernization`)**:
    - *Objetivo*: Culminación del ordenamiento arquitectónico integral de `app/` para alcanzar la máxima pulcritud posible: eliminación definitiva de los 22 archivos shims/fachadas planos sueltos en la raíz de `app/` tras la modernización directa de toda la suite de tests en `tests/` para importar exclusivamente de los 4 subpaquetes de dominio canónicos (`app.core`, `app.vnish`, `app.governance`, `app.telegram`), dejando en `app/` únicamente el orquestador raíz `miner_monitor.py` y el inicializador de paquete `__init__.py` junto con los archivos locales de runtime.
    - *Resultados*: Fases 1 a 6 completadas al 100% (T001-T020), 22 archivos shims purgados vía `git rm`, **587/587 tests globales PASS** en 10.68s, auditoría de release aprobada (`tools/release_audit.py --check-only`) con payload optimizado de 60 archivos limpios, cero impacto y servicio de producción 100% continuo.
    - *Modelo*: Gemini 3.8 Flash High (100% autónomo).

---

### 🎮 Programa V3.2: Centro de Comando Táctil y Modo Silencio (RFC Aprobado)

13. **[COMPLETADO Y CERTIFICADO] Spec 043 — Telegram Interactive Command Center & Rich UI (`043-telegram-interactive-command-center`)**:
    - *Objetivo*: Dashboard táctil centralizado `/menu` con `InlineKeyboardMarkup`, navegación in-place (`editMessageText`), semáforos, barras de estado y botones contextuales de acción rápida en alertas con confirmación en dos toques para reinicios.
    - *Resultados*: Fases 1 a 4 completadas al 100% (T001-T015), 15 tests unitarios en `tests/test_command_center.py`, **602/602 tests globales PASS** en 10.99s, release audit PASS (61 payload files), servicio en producción ininterrumpido.
    - *Modelo*: Gemini 3.8 Flash High (100% autónomo).

14. **[COMPLETADO Y CERTIFICADO] Spec 044 — Modo Silencio Inteligente con Temporizador Persistente y Thermal Guard (`044-silent-mode-thermal-guard`)**:
    - *Objetivo*: Reducción acústica de ventiladores a 40%-70% PWM con regulación térmica a 82°C, temporizador multiescala persistente (30m a 6h e indefinido) con reversión automática a régimen normal, integración directa táctil al Command Center (`/menu`) y Guardián Térmico de seguridad atómico ante emergencias (83.5°C).
    - *Cumplimiento Constitucional P0*: Despacho desacoplado en Telegram polling (C1), campos `silent_mode_*` independientes en `MinerState` reconciliados en `first_tick` (C2), límites acústicos dinámicos en Fan Governor (C3), y anulación atómica en `state.json` bajo pico térmico `EMERGENCY_SPIKE` con forzado al 100% PWM y alerta prioritaria (C4).
    - *Resultados*: Fases 1 a 6 completadas al 100% (T001-T018), 17 tests en `tests/test_silent_mode.py` y 17 tests en `tests/test_command_center.py`, **621/621 tests globales PASS** en 10.95s, release audit PASS (61 payload files, SHA-256 verificado).
    - *Modelo*: Gemini 3.8 Flash High (Implementación integral de código, FSM, tests y layouts táctiles) + Claude Sonnet 4.6 Thinking (Auditoría previa de condiciones C1-C4).

---

### 🎯 Objetivos a Futuro, Hitos Pendientes y Valor Aportado

1. **Spec 023 — Fusión de Evidencia de Incidentes**:
   - *Objetivo*: Correlacionar datos de telemetría SQLite, decisiones de reinicio y logs Vnish.
   - *Valor y Beneficio*: Permite identificar la causa raíz exacta de caídas (red, energía o firmware) eliminando falsos diagnósticos y guiando el mantenimiento preventivo de la granja.

2. **Spec 024 — Descubrimiento de Telemetría Eléctrica**:
   - *Objetivo*: Integrar telemetría de PDUs / UPS inteligentes o monitoreo de energía AC real.
   - *Valor y Beneficio*: Evita confundir caídas de tensión de placas con cortes de energía del Data Center, protegiendo los equipos ante fluctuaciones eléctricas externas.

3. **Spec 025 — Observabilidad Local (Prometheus y Grafana)**:
   - *Objetivo*: Exportar métricas locales Prometheus y proveer tableros Grafana de solo lectura.
   - *Valor y Beneficio*: Otorga visibilidad gráfica en tiempo real del rendimiento de la flota (TH/s totales, temperaturas, rejected shares) sin sobrecargar el monitor.

4. **Spec 026 — Inventario de Capacidades Hashcore**:
   - *Objetivo*: Mapear de forma conservadora los comandos del Toolkit Hashcore sin ampliar permisos de escritura.
   - *Valor y Beneficio*: Permite auditar el alcance operativo de acciones sobre los mineros garantizando que no se ejecuten comandos destructivos o no autorizados.

5. **Spec 028 — Respaldo y Restauración de Base de Datos**:
   - *Objetivo*: Programar respaldos en caliente de SQLite y ensayar la restauración en ambiente staging.
   - *Valor y Beneficio*: Asegura la continuidad operativa y la preservación del historial de eventos ante fallos de disco o corrupción de base de datos.

6. **Spec 027 — Evaluación de Interfaz de Operación**:
   - *Objetivo*: Determinar si Grafana/HTML estático bastan o si requiere una API local mínima en FastAPI.
   - *Valor y Beneficio*: Minimiza el consumo de recursos e hiper-superficie de ataque al evitar construir paneles web complejos si las herramientas estáticas cumplen la operación.

7. **Spec 029 — Estabilización Final y Candidato de Release V2**:
   - *Objetivo*: Pruebas de regresión cruzadas, auditoría documental y período de observación de 168 horas.
   - *Valor y Beneficio*: Garantiza la entrega de un producto robusto, libre de deudas técnicas, con documentación 100% verificada y listo para operación autónoma en producción.

---

## Operating Goal

Miner Alerts is the operations and diagnosis layer for S19j Pro miners. Work is
ordered to detect real failures, avoid unsafe or unnecessary actions, preserve
trustworthy evidence, recover the monitor itself, and only then add optional
interfaces or integrations.

## Current Baseline

- Windows service with one mutex-protected monitor/action authority.
- API 4028 authoritative polling, normally every 30 seconds.
- Telegram Bot API long polling as the remote command/control interface.
- Bounded read-only Vnish WebSocket log collection as complementary firmware
  evidence, never the sole health or action source.
- SQLite schema v6 for telemetry, operational events, reboot decisions,
  firmware evidence, collector health, incident assessments and assessment fact refs.
- Read-only static operations dashboard and incident reports.
- Auto-reboot gates for finite/current signal, sustained LOW, startup, thermal,
  fleet, Vnish transition, cooldown, window and QA safety.
- Spec 020 is committed/pushed and runtime-closed as `e502ab9`. Spec 030
  messaging quality is committed/pushed as `2afd65e` and active in production.
  Spec 021 liveness is activated and its D+1 observation gate passed (86,700s > 86,400s).
  Spec 022 has completed T001-T010 (pure acquisition executor, schema v6 quality persistence,
  config bounds validation and episode probe dataclasses).
  Spec 023 has completed T001-T013 and T016 (pure evidence_fusion module, schema v6 assessment persistence,
  shared semantic renderers and config defaults) with 305/305 passing tests.

## Architecture Direction

1. API 4028 polling remains authoritative because the deployed endpoint is
   request/response and has no proven health push contract.
2. Vnish WebSockets remain bounded and read-only for asynchronous firmware
   evidence.
3. An independent watchdog supervises process, tick and worker progress; a
   protocol change cannot replace monitor liveness supervision.
4. Acquisition may use bounded concurrency, but only one 30-second
   authoritative envelope per miner may update state/action semantics.
5. Prometheus/Grafana are the preferred optional observability stack. They read
   sanitized snapshots and cannot trigger actions.
6. Docker is limited to auxiliary observability. The monitor and Hashcore remain
   Windows-native.
7. Electrical protocol selection follows real hardware discovery. No AC voltage
   is inferred from hashboard telemetry.
8. FastAPI is conditional after static HTML and Grafana are measured. Web
   actions and remote exposure are excluded.
9. OpenTelemetry, broker-only MQTT and continuous Vnish workers remain deferred
   until concrete prerequisites exist.

## Delivery Queue

| Order | Work package | Status | Priority | Risk | Target |
| --- | --- | --- | --- | --- | --- |
| Gate | Spec 020 episode-alerts closeout | COMPLETE | P0 | HIGH | Closed 2026-08-13 |
| Hotfix | Spec 030 Telegram messaging quality | COMPLETE | P0 | MEDIUM | Closed 2026-08-13 |
| 1 | Spec 021 monitor-liveness-watchdog | COMPLETE | P0 | HIGH | Closed 2026-08-20 |
| 2 | Spec 022 adaptive-acquisition | COMPLETE | P1 | HIGH | Closed 2026-08-27 (267h+ runtime proven) |
| 3 | Spec 023 incident-evidence-fusion | COMPLETE | P1 | MEDIUM | Closed 2026-08-28 |
| 4 | Spec 024 electrical-source-discovery | COMPLETE (`blocked_external`) | P1 | MEDIUM | Closed 2026-08-28 (no external AC hardware) |
| 5 | Spec 025 prometheus-metrics | COMPLETE | P1 | MEDIUM | Closed 2026-08-29 |
| 6 | Spec 026 hashcore-capability-inventory | COMPLETE | P2 | MEDIUM | Closed 2026-08-29 |
| 7 | Spec 028 backup-retention-restore | COMPLETE | P1 | HIGH | Closed 2026-08-30 |
| 8 | Spec 027 operator-interface-decision | COMPLETE (`no_build`) | P2 | MEDIUM | Closed 2026-08-30 |
| 9 | Spec 029 v2-release-stabilization | COMPLETE (`approved`) | P0 | HIGH | Closed 2026-09-07 (`v2.0.0` released) |
| 10 | Spec 031 telegram-interactive-callbacks | COMPLETE | P1 | LOW | Closed 2026-09-07 |
| 11 | Spec 032 telegram-visual-charts | COMPLETE | P1 | LOW | Closed 2026-09-07 |
| 12 | Spec 033 miner-maintenance-snooze | COMPLETE | P1 | MEDIUM | Closed 2026-09-07 |
| 13 | Spec 034 daily-executive-digest | COMPLETE | P2 | LOW | Closed 2026-09-07 |
| 14 | Spec 035 cooling-fan-health | COMPLETE | P1 | LOW | Closed 2026-09-07 |
| 15 | Spec 036 efficiency-energy-tracking | COMPLETE | P1 | LOW | Closed 2026-09-07 |
| 16 | Spec 037 vnish-presets-autotuning | COMPLETE | P2 | LOW | Closed 2026-09-07 |
| 17 | Spec 038 v3-release-stabilization | COMPLETE (`approved`) | P0 | HIGH | Closed 2026-09-07 (`v3.0.0` released) |
| 18 | Spec 039 vnish-fan-governor | COMPLETE (`active`) | P1 | MEDIUM | Closed 2026-09-08 (calibrado 82.0°C) |
| 19 | Spec 040 dynamic-voltage-presets | COMPLETE (`active`) | P1 | HIGH | Closed 2026-09-08 (autodescubrimiento & elevadores) |

Dates include implementation plus the separate review/fix gate detailed in
`DELIVERY_PLAN.md`. Runtime evidence can move dates but cannot compress gates.

## Work Packages

### R0 - Close Spec 020 Production Activation (`COMPLETE`, P0)

**Spec**: `specs/020-episode-alerts`
**Target**: 2026-08-13 to 2026-08-17

- [x] Implement grouped episodes and escalating reminders.
- [x] Eliminate positive-hashrate plus OFFLINE status contradictions.
- [x] Add persisted click-safe episode detail.
- [x] Commit and push `e502ab9`.
- [x] Prove the deployed `e502ab9` PID/code/config and startup-guard evidence
  from the 2026-08-06 service activation.
- [x] Smoke current API 4028/status rendering and persisted event detail locally.
- [x] Activate Telegram token-log redaction through an elevated NSSM restart;
  verify the new startup block and zero new token occurrences.
- [x] Rotate the token previously present in the old ignored local log and
  restart once with the new local credential.
- [x] Smoke `/status`, `/events` and `/e<ID>` from the authorized Telegram chat.
- [x] Re-prove startup persisted LOW cannot cause immediate auto-reboot.
- [x] Complete the observation gate with no open P0/P1 regression.

**Exit**: Spec 020 T020 and evidence close. No duplicate Spec 021 is created for
this work.

### R0.5 - Telegram Messaging Quality (`COMPLETE`, P0)

**Spec**: `specs/030-telegram-messaging-quality`

- [x] Bounded UTF-8-safe splitting below the Telegram text ceiling.
- [x] Command-aware queue admission with bounded direct fallback under pressure.
- [x] Explicit queue drop/bypass outcomes without logging message payloads.
- [x] Central help aligned with `/rb<ID>`, `/reboot_no_ok` and `/c<code>`.
- [x] Preserve episode cadence, notification dedupe and all action-policy gates.
- [x] Complete one elevated NSSM restart and read-only Telegram smoke.

**Invariant**: no state, polling, threshold, cooldown or Hashcore decision change.

### R1 - Monitor Liveness And Recovery (`COMPLETE`, P0)

**Spec**: `specs/021-monitor-liveness-watchdog`

Its implementation, deterministic no-action validation, elevated Windows
activation and controlled SCM recovery proof are complete. D+1/D+3 gates closed.

- [x] Atomic versioned heartbeat after completed fleet ticks.
- [x] Independent service/process/tick/Telegram-worker/collector assessment.
- [x] Hidden Windows watchdog definition with bounded notification dedupe.
- [x] Install the hidden task and configure SCM recovery with rollback export.
- [x] Deterministic kill, hang and stale-worker classification with no action authority.
- [x] Prove the activated PID, mutex, startup guard and fresh scheduled heartbeat.
- [x] Prove SCM recovery firing with a new PID, mutex, startup guard and heartbeat.
- [x] Complete D+1/D+3 observation (77.3h continuous soak).

**Invariant**: no second monitor and no miner/Hashcore access from the watchdog.

### R2 - Acquisition Resilience (`COMPLETE`, P1)

**Spec**: `specs/022-adaptive-acquisition`

- [x] Pure typed authoritative/diagnostic envelope and epoch contracts.
- [x] Bounded executor, lease and peer-isolation contracts without runtime wiring.
- [x] Explicit valid/partial/invalid/timeout/error/late quality normalization.
- [x] Optional diagnostic recovery probes that cannot update state or actions (T009).
- [x] Baseline/shadow comparison for latency, requests, sample age and alerts (T012).
- [x] Monitor runtime wiring and activation under PID 38816.
- [x] D+1 and D+3 soak gate passed with over 267 hours of uninterrupted execution.

**Invariant**: thresholds, hysteresis, polling offset and action policy unchanged.

### R3 - Incident Evidence Fusion (`COMPLETE`, P1)

**Spec**: `specs/023-incident-evidence-fusion`

- [x] Normalize persisted episode, Vnish, quality, pool, action and fleet facts.
- [x] Build stable per-miner historical baselines from eligible samples.
- [x] Separate observed, suspected and confirmed conclusions.
- [x] Show supporting, contradicting and missing evidence.
- [x] Persist versioned assessments for deterministic replay.
- [x] Integrate Telegram `/diagnose` adapter behind feature flag `incident_fusion_enabled` (T014).
- [x] Integrate shared renderer in operations dashboard (T015).
- [x] Deterministic validation SC-001 through SC-004 (T017).
- [x] Measure bounded query count, 24-hour latency under 2s and DB growth (T018).

**Invariant**: assessments are advisory and never authorize actions.

### R4 - Electrical Source Discovery (`COMPLETE / BLOCKED_EXTERNAL`, P1)

**Spec**: `specs/024-electrical-source-discovery`

- [x] Establish that miner chain voltage is not AC input voltage.
- [x] Inventory actual PSU/PDU/UPS/meter model and documented telemetry.
- [x] Close discovery gate with explicit BLOCKED_EXTERNAL disposition (no external hardware sensors).
- [x] Zero writes, zero phantom sensors, zero actions.

**Exit**: Blocked dependency formal record; safe no-op.

### R5 - Prometheus Metrics And Grafana (`COMPLETE`, P1)

**Spec**: `specs/025-prometheus-metrics`

- [x] Atomic sanitized metrics snapshot from the native monitor.
- [x] Separate `prometheus_client` exporter with bounded cardinality.
- [x] Optional pinned Docker Compose Prometheus/Grafana stack.
- [x] Local-only fleet, freshness, liveness, episode and delivery dashboards.
- [x] Redaction, resource, series-count and outage-isolation proof.

**Invariant**: metrics are not canonical history and never trigger actions.

### R6 - Hashcore Capability Inventory (`COMPLETE`, P2)

**Spec**: `specs/026-hashcore-capability-inventory`

- [x] Establish static planning baseline: Toolkit `1.6.0+167`, wrapper/executable present.
- [x] Implement metadata-only inventory as the zero-process default.
- [x] Run only exact fingerprint-bound vendor-proven help/version discovery with timeout/no-window.
- [x] Classify every operation read-only, mutating or unknown.
- [x] Compare read-only capabilities with API 4028/Vnish overlap.
- [x] Require a new high-risk spec for every future action.

**Invariant**: production action scope remains existing reboot/restart only.

### R7 - Backup, Retention And Restore (`COMPLETE`, P1)

**Spec**: `specs/028-backup-retention-restore`

- [x] SQLite online backup with atomic promotion and SHA-256 manifest.
- [x] Path-guarded 14 daily / 8 weekly / 12 monthly retention.
- [x] Hidden non-overlap Scheduled Task and free-space guard.
- [x] Restore only to staging with checksum, integrity, schema and row checks.
- [x] One production backup plus successful staging restore drill.

**Invariant**: never copy a live `.db` blindly and never overwrite production automatically.

### R8 - Operator Interface Decision (`COMPLETE / NO_BUILD`, P2)

**Spec**: `specs/027-operator-interface-decision`

- [x] Score real workflows across Telegram, static HTML and Grafana.
- [x] Baseline the existing SQLite `mode=ro` static generator and its safety tests.
- [x] Execute three consecutive fixed P1 workflow runs (W01-W06) with 30/30 passes.
- [x] Close no-build when current interfaces meet all P1 targets without missing fields.
- [x] Reject additional web servers/APIs to maintain minimal attack surface.

**Invariant**: Telegram remains the only remote action surface.

### R9 - V2 Release Stabilization (`COMPLETE / APPROVED`, P0)

**Spec**: `specs/029-v2-release-stabilization`

- [x] Define terminal dependency states, runtime-payload identity and stable R001-R025 cross-feature matrix.
- [x] Freeze an evidence-eligible candidate after Specs 021-028 reach terminal states.
- [x] Run full cross-feature, core-safety, QA and auxiliary-outage regression (416/416 tests passing).
- [x] Complete release backup and staging restore (23.2 MB online backup and restore drill).
- [x] Controlled service activation and read-only smoke (PID 38816).
- [x] Continuous 168-hour review completed (267.2 continuous soak hours achieved).
- [x] Three documentation sweeps, secret hygiene and explicit release decision (`APPROVE`).
- [x] Tag `v2.0.0` published.

### R10 - Telegram Max, Intelligence & Concurrency Release V3 (`COMPLETE / APPROVED`, P0)

**Specs**: `specs/031-telegram-interactive-callbacks` a `specs/038-v3-release-stabilization`

- [x] Spec 031: Botones interactivos Telegram inline (1-tap) y flujo de confirmación en 2 pasos para reinicios seguros (`app/telegram_callbacks.py`).
- [x] Spec 032: Gráficos nativos de telemetría en formato PNG generados en RAM sin almacenamiento en disco (`app/telegram_charts.py`).
- [x] Spec 033: Modo mantenimiento y silenciamiento temporal con bloqueo de autoreinicios (`app/telegram_snooze.py`).
- [x] Spec 034: Reporte ejecutivo diario programado (08:00 AM) y on-demand (`app/daily_digest.py`).
- [x] Spec 035: Inteligencia térmica, cálculo de headroom a 85°C y alertas predictivas de saturación de ventiladores (`app/fan_health.py`).
- [x] Spec 036: Seguimiento en tiempo real de eficiencia energética ($J/\text{TH}$) y alertas de degradación (`app/energy_efficiency.py`).
- [x] Spec 037: Auditoría dinámica de presets Vnish y alertas de downclocking ($\ge 25\text{ MHz}$) (`app/vnish_presets.py`).
- [x] Spec 038: Endurecimiento de concurrencia multihilo, mitigación de condiciones de carrera, 19 tests de estrés (`tests/test_v3_concurrency.py`), 514 tests globales PASS y certificación del Release V3.0.0.

**Invariant**: cero impacto sobre la máquina de estados, aislamiento estricto de hilos lectores SQLite con `?mode=ro`.

## Deferred Technology

- OpenTelemetry until multiple long-lived services, remote backends or tracing
  requirements justify an OTLP pipeline.
- MQTT until a selected physical device publishes trustworthy telemetry.
- Continuous Vnish WebSocket workers until bounded collection demonstrably
  misses time-critical evidence and reconnection semantics are proven.
- Remote/public web UI, web actions, React SPA and cloud deployment.
- Windows monitor containerization while Hashcore and service integration remain
  host-local.

## Completed Capability Baseline

- [x] Persistent SQLite history and reboot-decision audit.
- [x] Current finite-signal and persisted-startup safety.
- [x] Vnish board, temperature, fleet and firmware-transition interlocks.
- [x] Stability, quality, firmware and read-only diagnosis intelligence.
- [x] Bounded Vnish log collection with no-window scheduling.
- [x] Static operations dashboard.
- [x] Telegram no-silence delivery and click-safe actions.
- [x] Persistent/episode alerts and truthful current status in committed code.
- [x] Botones interactivos Telegram inline (1-tap) y flujo de confirmación en 2 pasos (Spec 031).
- [x] Envío de gráficos nativos de telemetría en PNG sin archivos en disco (Spec 032).
- [x] Silenciamiento temporal y bloqueo de reinicios por mantenimiento programado (Spec 033).
- [x] Reporte ejecutivo diario programado y bajo demanda (Spec 034).
- [x] Diagnóstico predictivo de saturación térmica y degradación de ventiladores (Spec 035).
- [x] Métrica en tiempo real de Joules por Terahash y alertas de consumo (Spec 036).
- [x] Auditoría dinámica de perfiles de autotuning Vnish y caídas de frecuencia (Spec 037).
- [x] Blindaje de concurrencia en memoria y sockets SQLite para consultas analíticas (Spec 038).

## Future Strategic Initiatives (V4 / Next Horizon)

Strategic exploration and specifications for next-generation capabilities:
- **Spec 039 — Vnish REST API Client & Electrical Adaptive Governor**: Control dinámico de presets y ventiladores por lazo cerrado para mitigar disparos en elevadores de tensión sensibles.

## Governance

- All 38 specifications in the program are complete, verified with evidence, and closed.
- Version 3.0.0 is released, certified, and fully hardened with 514/514 tests PASS.
- Production action authority remains strictly centralized in the Windows monitor.
- External read-only surfaces (Grafana, static dashboard, backup CLI) operate decoupled from the monitor.
- Any future modifications or V4 scope must adhere to SpecKit discipline and constitutional gates.
