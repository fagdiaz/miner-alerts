# Miner Alerts Speckit Roadmap

**Last reviewed**: 2026-10-08
**Specification program**: `docs/speckit/SPEC_PROGRAM.md`
**Delivery calendar**: `docs/speckit/DELIVERY_PLAN.md`

## Resumen Ejecutivo y Progreso del Programa

- **Progreso Acumulado del Proyecto (desde Spec 001)**: `100%` (91 de 91 especificaciones completadas y evidenciadas — **1530 tests PASS, 75 subtests PASS** — Spec 091 Disolución Definitiva del Monolito COMPLETADA — **RELEASE MAYOR V6.0**).
- **Estado Operativo de Flota (2026-10-07)**: Elevador 1 a 2700W (5396W nominal), Elevador 2 a 2700W (5396W nominal), 4 mineros en hash nominal continuo (~398-402 TH/s), 0 deadlocks en toda la flota, Fan Governor modulando en lazo cerrado térmico.
- **Programa Maestro de Desacoplamiento del Monolito**: **100% COMPLETADO** (Fases 1 a 5: `Spec 087: Callbacks`, `Spec 088: Ciclos de Gobernanza`, `Spec 089: Telemetría de Hardware`, `Spec 090: Desbloqueo de main()`, `Spec 091: Pipeline Declarativo de Hooks (Cierre V6.0)`). Monolito disuelto definitivamente: `miner_monitor.py` reducido a 324 LOC.
- **Auditoría Arquitectónica y Armonización**: Todas las directivas armonizadas y fricciones F-01 y F-02 resueltas. Ver [`docs/audit/DIRECTIVES_HARMONIZATION_AUDIT.md`](../audit/DIRECTIVES_HARMONIZATION_AUDIT.md).

---

### ðŸ† Avances Principales Desde el Inicio (Spec 001 a Spec 030)

1. **Specs 001 a 019 â€” Arquitectura Base y TelemetrÃ­a**:
   - [x] Polling autoritativo API 4028 y persistencia SQLite (esquema v1-v6).
   - [x] IntegraciÃ³n con Hashcore Toolkit CLI para comandos seguros de reinicio.
   - [x] Captura programada de logs de firmware Vnish.
   - [x] DiagnÃ³sticos de calidad de minado y perfil de estabilidad.

2. **Spec 020 â€” EstabilizaciÃ³n de Estados y Autoreinicio**:
   - [x] MÃ¡quina de 5 estados estables (`OK`, `LOW`, `OFFLINE`, `HASHBOARD`).
   - [x] Interlocks tÃ©rmicos, de flota y de transiciÃ³n de firmware.
   - [x] EliminaciÃ³n de falsas alarmas y cero reinicios espurios (`e502ab9`).

3. **Spec 030 â€” Calidad de MensajerÃ­a Telegram**:
   - [x] Cola de entrega por prioridad y divisiÃ³n segura de mensajes extensos.
   - [x] ProtecciÃ³n anti-rate limit y reintento con backoff.
   - [x] ValidaciÃ³n en producciÃ³n y commit `2afd65e`.

4. **Spec 021 â€” Watchdog de Vida y RecuperaciÃ³n SCM**:
   - [x] SupervisiÃ³n fuera de proceso con heartbeat atÃ³mico versionado.
   - [x] DetecciÃ³n determinista de bloqueos y recuperaciÃ³n SCM aprobada.
   - [x] Gates de observaciÃ³n continua D+1 (86.7k s) y D+3 (278.4k s / 77.3h) superados con Ã©xito.

5. **Spec 022 â€” AdquisiciÃ³n Adaptativa y UX Telegram Compacto**:
   - [x] Ejecutor de adquisiciÃ³n paralelo desacoplado con 2 workers.
   - [x] Formato UX compacto y normalizaciÃ³n de calidades de telemetrÃ­a.
   - [x] ProducciÃ³n activa bajo PID 38816 con gates D+1 (42.7h) y D+3 (73.45h / 264.4k s) superados.

6. **Spec 023 â€” FusiÃ³n de Evidencia de Incidentes**:
   - [x] MÃ³dulo puro desacoplado `app/evidence_fusion.py` (T001-T018).
   - [x] Rutas de lectura `/diagnose` activadas con tablas `incident_assessments` e `assessment_fact_refs`.
   - [x] ValidaciÃ³n determinista SC-001 a SC-004 y rendimiento verificado (344 tests PASS).

7. **Spec 024 â€” Descubrimiento de TelemetrÃ­a ElÃ©ctrica (Bloqueado por Hardware)**:
   - [x] Relevamiento tÃ©cnico exhaustivo de telemetrÃ­a elÃ©ctrica (T001-T004).
   - [x] ProhibiciÃ³n formal de inferencia de AC desde voltajes DC de hashboards.
   - [x] Cierre formal con disposiciÃ³n `blocked_external` por ausencia de PDU/UPS de red.

8. **Spec 026 â€” Inventario de Capacidades Hashcore**:
   - [x] Herramienta desacoplada `tools/hashcore_inventory.py` (T001-T018).
   - [x] Metadatos de instalaciÃ³n PE verificados (`1.6.0+167`, wrapper `toolkit_cli.bat`).
   - [x] ClasificaciÃ³n de operaciones y allowlist vacÃ­a con resultado seguro `blocked` sin alterar monitor.

9. **Spec 028 â€” Backups, RetenciÃ³n y RecuperaciÃ³n por Etapas**:
   - [x] Herramienta desacoplada `tools/event_store_backup.py` y script `tools/install_backup_task.ps1`.
   - [x] Respaldo online por lotes de 256 pÃ¡ginas y retenciÃ³n determinista UTC 14/8/12.
   - [x] Simulacro de restore en staging superado sobre BD real de 20.4 MB en 6.2s.

10. **Spec 025 â€” MÃ©tricas de Prometheus y Paneles Grafana**:
    - [x] InstantÃ¡neas de mÃ©tricas en `app/metrics_snapshot.py` y exportador `tools/metrics_exporter.py`.
    - [x] Stack Docker Compose aislado con 3 tableros Grafana (`fleet_overview`, `monitor_liveness`, etc.).
    - [x] Hook atÃ³mico en el monitor con cero impacto en el ciclo de supervisiÃ³n.

11. **Spec 027 â€” DecisiÃ³n de Interfaz de OperaciÃ³n**:
    - [x] Scorecard de flujos de operador W01-W06 ejecutado (30 corridas verificadas).
    - [x] ValidaciÃ³n de cobertura P1 completa con Telegram, Grafana y dashboard HTML estÃ¡tico.
    - [x] DecisiÃ³n formal `no_build` adoptada, preservando la superficie mÃ­nima y cero impacto en recursos.

12. **Spec 029 â€” EstabilizaciÃ³n Final y Candidato de Release V2**:
    - [x] Congelamiento determinista de payload SHA-256 (`58d451f1...`, 43 archivos).
    - [x] ValidaciÃ³n de matriz completa R001-R025 (416 tests PASS).
    - [x] PerÃ­odo de observaciÃ³n continua de 267.2 horas en producciÃ³n y aprobaciÃ³n formal del Release Candidate V2 (`v2.0.0`).

---

### ðŸš€ Programa V3: MaximizaciÃ³n de Telegram & Capacidades Avanzadas

1. **Spec 031 â€” Botones Interactivos y Callbacks Telegram (`031-telegram-interactive-callbacks`)**:
   - [x] Inline Keyboards en alertas de episodios para diagnÃ³sticos y grÃ¡ficos en 1 toque.
   - [x] Flujo interactivo seguro de reinicio en 2 toques (`[ ðŸ”„ Reiniciar ]` -> `[ âœ… Confirmar ]` / `[ âŒ Cancelar ]`) con token de 60s.
   - [x] 14 tests PASS en `tests/test_telegram_callbacks.py`, 430 tests globales PASS, cero impacto en estabilidad.

2. **Spec 032 â€” GrÃ¡ficos Nativos Visuales en Telegram (`032-telegram-visual-charts`)**:
   - [x] EnvÃ­o directo de imÃ¡genes PNG con la curva de hashrate, temperaturas y RPM al chat vÃ­a `/chart <id>` y `/chart fleet`.
   - [x] Renderizado en RAM en 219ms sobre 23.2 MB sin archivos temporales en disco.
   - [x] 6 tests PASS en `tests/test_telegram_charts.py`.

3. **Spec 033 â€” Mantenimiento y Silenciamiento Temporal (`033-miner-maintenance-snooze`)**:
   - [x] Comandos `/snooze <miner|all> [minutos]` y botÃ³n tÃ¡ctil `[ ðŸ”• Silenciar 1h ]`.
   - [x] SupresiÃ³n temporal de alertas, recordatorios y bloqueo de autorreinicios durante intervenciones fÃ­sicas.
   - [x] 12 tests PASS en `tests/test_telegram_snooze.py` y persistencia en `state.json`.

4. **Spec 034 â€” Reporte Ejecutivo Diario (`034-daily-executive-digest`)**:
   - [x] Resumen programado diario matutino (08:00 AM) y on-demand `/digest`.
   - [x] MÃ©tricas de flota agregadas: uptime, TH/s promedio, J/TH, shares %, anomalÃ­as e integridad de backups SQLite.
   - [x] 10 tests PASS en `tests/test_daily_digest.py` con rendimiento real medido de 27.2ms.

5. **Spec 035 â€” Inteligencia TÃ©rmica y de Ventiladores (`035-cooling-fan-health`)**:
   - [x] SupervisiÃ³n analÃ­tica de ventiladores (`/fans [miner]`).
   - [x] CÃ¡lculo de margen tÃ©rmico hacia el umbral de corte (85.0Â°C).
   - [x] Alertas preventivas de saturaciÃ³n tÃ©rmica (`COOLING_WARNING`) para anticipar limpieza de filtros.
   - [x] 14 tests PASS en `tests/test_fan_health.py` y monitoreo en vivo continuo.

6. **Spec 036 â€” Eficiencia EnergÃ©tica Continua (`036-efficiency-energy-tracking`)**:
   - [x] Seguimiento en tiempo real del ratio Joules por Terahash (J/TH) y potencia en Watts/kW vÃ­a `/efficiency`.
   - [x] Alertas tempranas de degradaciÃ³n energÃ©tica (`EFFICIENCY_WARNING`).
   - [x] 12 tests PASS en `tests/test_energy_efficiency.py`.

7. **Spec 037 â€” Seguimiento de Presets y Autotuning DinÃ¡mico (`037-vnish-presets-autotuning`)**:
   - [x] Monitoreo de frecuencias (MHz), tensiÃ³n de cadena (V), potencia y autotune Vnish vÃ­a `/presets`.
   - [x] Alerta preventiva `PROFILE_CHANGE_ALERT` ante reducciones de frecuencia ($\ge 25\text{ MHz}$).
   - [x] 11 tests PASS en `tests/test_vnish_presets.py`.

8. **Spec 038 â€” AuditorÃ­a de Concurrencia y EstabilizaciÃ³n Release V3 (`038-v3-release-stabilization`)**:
   - [x] AuditorÃ­a profunda de concurrencia multihilo, cerrojos `state_lock` y sockets SQLite con `?mode=ro`.
   - [x] PrevenciÃ³n de condiciones de carrera en `CallbackTokenRegistry` y 19 tests de estrÃ©s (`tests/test_v3_concurrency.py`).
   - [x] CertificaciÃ³n formal del Release V3.0.0 (514 tests globales PASS).

---

### âš¡ Programa V3.1: Control y Gobernanza de Hardware (ActivaciÃ³n Plena en ProducciÃ³n)

9. **Spec 039 â€” Gobernador TÃ©rmico y AcÃºstico de Ventiladores Vnish (`039-vnish-fan-governor`)**:
   - [x] DetecciÃ³n de modo en `/fans` (`manual`/`auto`) y cliente REST seguro (`app/vnish/client.py`).
   - [x] ModulaciÃ³n determinista de lazo cerrado hacia target de 82.0Â°C (banda muerta [81.0, 82.5]Â°C).
   - [x] Despacho concurrente desacoplado con `ThreadPoolExecutor` (timeout 2.5s por minero, 5.0s flota).
   - [x] ProtecciÃ³n de emergencia `EMERGENCY_SPIKE` a 83.5Â°C con forzado inmediato a 100% PWM.
   - [x] Fail-safe ante caÃ­das de comunicaciÃ³n o excepciones consecutivas.
   - [x] Control interactivo en caliente vÃ­a Telegram (`/gov on`, `/gov off`, `/gov set`).
   - [x] 12 tests de concurrencia y estrÃ©s (`tests/test_fan_governor_concurrency.py`).

10. **Spec 040 â€” CalibraciÃ³n DinÃ¡mica de Presets y Elevadores de TensiÃ³n (`040-dynamic-voltage-presets`)**:
    - [x] Algoritmo de optimizaciÃ³n de potencia y presets (1600W a 2800W) por grupo elÃ©ctrico.
    - [x] Desescalado tÃ©rmico progresivo (`ACTION_STEP_DOWN_THERMAL`) ante saturaciÃ³n tÃ©rmica.
    - [x] ProtecciÃ³n individual y grupal de elevadores ante caÃ­das de tensiÃ³n y reinicios en ventana.
    - [x] Subida conservadora tras 72h continuas de soak con margen tÃ©rmico $\ge 4.0^\circ\text{C}$.
    - [x] Comandos interactivos en caliente `/balancer on`, `/balancer off`, `/balancer setmax`, `/balancer run`.
    - [x] 23 tests unitarios e integraciÃ³n (`tests/test_preset_balancer.py`, `tests/test_preset_balancer_integration.py`).

---

### ðŸ§¹ Programa V3.2: ReorganizaciÃ³n Modular y Purga Limpia de Shims

11. **Spec 041 â€” Arquitectura Modular y ReorganizaciÃ³n de Dominios en `app/` (`041-app-modular-architecture`)**:
    - [x] ReorganizaciÃ³n de 22 archivos planos en 4 subpaquetes canÃ³nicos: `app/core/`, `app/vnish/`, `app/governance/`, `app/telegram/`.
    - [x] Capa inicial de shims de retrocompatibilidad con module aliasing (`sys.modules[__name__] = _impl`).
    - [x] 587 tests globales PASS manteniendo retrocompatibilidad total.

12. **Spec 042 â€” Purga Limpia de Shims y ModernizaciÃ³n de Tests en `app/` (`042-purge-shims-test-modernization`)**:
    - [x] ModernizaciÃ³n canÃ³nica directa de todas las importaciones en la suite de pruebas `tests/`.
    - [x] Purga definitiva mediante `git rm` de los 22 archivos shims de la raÃ­z de `app/`.
    - [x] ValidaciÃ³n de estructura mÃ­nima en `app/` (`miner_monitor.py` y `__init__.py`).
    - [x] 587/587 tests globales PASS y auditorÃ­a de release verificada con 60 payload files limpios.

---

### ðŸŽ® Programa V3.3: Centro de Comando TÃ¡ctil y Modo Silencio

13. **Spec 043 â€” Telegram Interactive Command Center & Rich UI (`043-telegram-interactive-command-center`)**:
    - [x] MÃ³dulo puro desacoplado `app/telegram/command_center.py` con layouts y builders de InlineKeyboardMarkup.
    - [x] Dashboard tÃ¡ctil `/menu` (alias `/start`, `/panel`) con semÃ¡foros, potencia de flota y barras Unicode `[â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–‘â–‘]`.
    - [x] SubmenÃºs in-place vÃ­a `editMessageText`: MÃ©tricas, Reinicios guiados, Presets y Alertas.
    - [x] ConfirmaciÃ³n de reinicio en dos toques con token criptogrÃ¡fico efÃ­mero de 60 segundos.
    - [x] Botones de acciÃ³n rÃ¡pida de 4 funciones embebidos en alertas de episodios (`diag`, `chart`, `rb_req`, `snz`).
    - [x] GuardiÃ¡n de seguridad RBAC (`from_id == chat_id`) y ACK inmediato `answerCallbackQuery` (< 500ms).
    - [x] 17 tests unitarios en `tests/test_command_center.py` y 602 tests globales PASS.

14. **Spec 044 â€” Modo Silencio Inteligente con Temporizador Persistente y Thermal Guard (`044-silent-mode-thermal-guard`)**:
    - [x] CondiciÃ³n C1: Despacho asÃ­ncrono no bloqueante en el worker de Telegram polling.
    - [x] CondiciÃ³n C2: Campos dedicados `silent_mode_*` en `MinerState` y reconciliaciÃ³n en arranque `first_tick`.
    - [x] CondiciÃ³n C3: Techos acÃºsticos dinÃ¡micos (`max_fan_duty_percent`) inyectados en Fan Governor (40%-70% PWM).
    - [x] CondiciÃ³n C4: DesactivaciÃ³n atÃ³mica en `state.json` bajo pico tÃ©rmico (83.5Â°C) o falla, ventiladores forzados al 100% y alerta Telegram.
    - [x] Temporizadores de cuenta regresiva configurables (30m, 1h, 2h, 4h, 6h, indef) con reversiÃ³n automÃ¡tica a rÃ©gimen normal.
    - [x] Selector tÃ¡ctil integrado al Command Center (`cc:nav:silent`, `cc:act:silent:*`) y comando `/silent`.
    - [x] 17 tests unitarios en `tests/test_silent_mode.py`, 621/621 tests globales PASS y activo en producciÃ³n bajo PID 58344.

---

### ðŸŽ¯ Resumen de Valor Aportado por EspecificaciÃ³n

1. **Spec 023 â€” FusiÃ³n de Evidencia de Incidentes**:
   - [x] *Objetivo*: Correlacionar datos de telemetrÃ­a SQLite, decisiones de reinicio y logs Vnish.
   - [x] *Valor y Beneficio*: Permite identificar la causa raÃ­z exacta de caÃ­das (red, energÃ­a o firmware) eliminando falsos diagnÃ³sticos.

2. **Spec 024 â€” Descubrimiento de TelemetrÃ­a ElÃ©ctrica**:
   - [x] *Objetivo*: Integrar telemetrÃ­a de PDUs / UPS inteligentes o monitoreo de energÃ­a AC real.
   - [x] *Valor y Beneficio*: Evita confundir caÃ­das de tensiÃ³n de placas con cortes de energÃ­a del Data Center.

3. **Spec 025 â€” Observabilidad Local (Prometheus y Grafana)**:
   - [x] *Objetivo*: Exportar mÃ©tricas locales Prometheus y proveer tableros Grafana de solo lectura.
   - [x] *Valor y Beneficio*: Otorga visibilidad grÃ¡fica en tiempo real del rendimiento de la flota sin sobrecargar el monitor.

4. **Spec 026 â€” Inventario de Capacidades Hashcore**:
   - [x] *Objetivo*: Mapear de forma conservadora los comandos del Toolkit Hashcore sin ampliar permisos de escritura.
   - [x] *Valor y Beneficio*: Permite auditar el alcance operativo garantizando que no se ejecuten comandos destructivos.

5. **Spec 028 â€” Respaldo y RestauraciÃ³n de Base de Datos**:
   - [x] *Objetivo*: Programar respaldos en caliente de SQLite y ensayar la restauraciÃ³n en ambiente staging.
   - [x] *Valor y Beneficio*: Asegura la continuidad operativa y la preservaciÃ³n del historial de eventos ante fallos de disco.

6. **Spec 027 â€” EvaluaciÃ³n de Interfaz de OperaciÃ³n**:
   - [x] *Objetivo*: Determinar si Grafana/HTML estÃ¡tico bastan o si requiere una API local mÃ­nima en FastAPI.
   - [x] *Valor y Beneficio*: Minimiza el consumo de recursos e hiper-superficie de ataque (decisiÃ³n `no_build`).

7. **Spec 029 â€” EstabilizaciÃ³n Final y Candidato de Release V2**:
   - [x] *Objetivo*: Pruebas de regresiÃ³n cruzadas, auditorÃ­a documental y perÃ­odo de observaciÃ³n de 168 horas.
   - [x] *Valor y Beneficio*: Garantiza la entrega de un producto robusto, libre de deudas tÃ©cnicas y verificado (`v2.0.0`).

8. **Spec 039 â€” Gobernador TÃ©rmico y AcÃºstico de Ventiladores Vnish**:
   - [x] *Objetivo*: Lazo cerrado de control tÃ©rmico a 82Â°C con fail-safe al 100% PWM.
   - [x] *Valor y Beneficio*: Prolonga la vida Ãºtil de los ventiladores, reduce el ruido y previene disparos tÃ©rmicos.

9. **Spec 040 â€” CalibraciÃ³n DinÃ¡mica de Presets y Elevadores de TensiÃ³n**:
   - [x] *Objetivo*: Balanceo de potencia inteligente por grupo elÃ©ctrico y desescalado por inestabilidad.
   - [x] *Valor y Beneficio*: Evita reinicios en cascada por caÃ­das de tensiÃ³n y maximiza la producciÃ³n estable de TH/s.

10. **Specs 041-042 â€” Arquitectura Modular y Purga Limpia de Shims**:
    - [x] *Objetivo*: ReorganizaciÃ³n de `app/` en subpaquetes de dominio y purga de 22 archivos planos.
    - [x] *Valor y Beneficio*: Base de cÃ³digo limpia, modular, de alta mantenibilidad y 100% canÃ³nica.

11. **Spec 043 â€” Telegram Interactive Command Center & Rich UI**:
    - [x] *Objetivo*: Centro de mando ejecutivo con menÃºs interactivos tÃ¡ctiles y botones de acciÃ³n rÃ¡pida.
    - [x] *Valor y Beneficio*: GestiÃ³n y toma de decisiones remota en 1-2 toques tÃ¡ctiles sin necesidad de tipear comandos.

12. **Spec 044 â€” Modo Silencio / Visitas Inteligente con Thermal Guard**:
    - [x] *Objetivo*: LÃ­mite acÃºstico temporal a 40%-70% PWM con temporizadores de cuenta regresiva y protecciÃ³n a 83.5Â°C.
    - [x] *Valor y Beneficio*: Permite recibir visitas silenciando la sala de forma programada y segura sin riesgo de sobrecalentamiento.

---

## Operating Goal

Miner Alerts is the operations and diagnosis layer for S19j Pro miners. Work is
ordered to detect real failures, avoid unsafe or unnecessary actions, preserve
trustworthy evidence, recover the monitor itself, and only then add optional
interfaces or integrations.

## Current Baseline

- Windows service with one mutex-protected monitor/action authority (`PID 58344`).
- API 4028 authoritative polling, normally every 30 seconds.
- Telegram Bot API long polling as the remote command/control interface.
- Bounded read-only Vnish WebSocket log collection as complementary firmware
  evidence, never the sole health or action source.
- SQLite schema v6 for telemetry, operational events, reboot decisions,
  firmware evidence, collector health, incident assessments and assessment fact refs.
- Read-only static operations dashboard and incident reports.
- Auto-reboot gates for finite/current signal, sustained LOW, startup, thermal,
  fleet, Vnish transition, cooldown, window and QA safety.
- All 44 specs completed and certified with 621/621 passing automated tests.

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

---

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
| 18 | Spec 039 vnish-fan-governor | COMPLETE (`active`) | P1 | MEDIUM | Closed 2026-09-08 (calibrado 82.0Â°C) |
| 19 | Spec 040 dynamic-voltage-presets | COMPLETE (`active`) | P1 | HIGH | Closed 2026-09-08 (autodescubrimiento & elevadores) |
| 20 | Spec 041 modular-architecture | COMPLETE | P2 | MEDIUM | Closed 2026-09-08 (app/ reorganizado) |
| 21 | Spec 042 purge-shims-test-modernization | COMPLETE | P2 | LOW | Closed 2026-09-08 (22 shims purgados) |
| 22 | Spec 043 telegram-command-center | COMPLETE | P1 | LOW | Closed 2026-09-08 (Command Center tÃ¡ctil /menu) |
| 23 | Spec 044 silent-mode-thermal-guard | COMPLETE (`active`) | P0 | HIGH | Closed 2026-09-08 (PID 58344 activo en producciÃ³n) |

Dates include implementation plus the separate review/fix gate detailed in
`DELIVERY_PLAN.md`. Runtime evidence can move dates but cannot compress gates.

---

## Work Packages

### R0 - Close Spec 020 Production Activation (COMPLETE, P0)

**Spec**: `specs/020-episode-alerts`
**Target**: 2026-08-13 to 2026-08-17

- [x] Implement grouped episodes and escalating reminders.
- [x] Eliminate positive-hashrate plus OFFLINE status contradictions.
- [x] Add persisted click-safe episode detail.
- [x] Commit and push `e502ab9`.
- [x] Prove the deployed `e502ab9` PID/code/config and startup-guard evidence from the 2026-08-06 service activation.
- [x] Smoke current API 4028/status rendering and persisted event detail locally.
- [x] Activate Telegram token-log redaction through an elevated NSSM restart; verify the new startup block and zero new token occurrences.
- [x] Rotate the token previously present in the old ignored local log and restart once with the new local credential.
- [x] Smoke `/status`, `/events` and `/e<ID>` from the authorized Telegram chat.
- [x] Re-prove startup persisted LOW cannot cause immediate auto-reboot.
- [x] Complete the observation gate with no open P0/P1 regression.

**Exit**: Spec 020 T020 and evidence close. No duplicate Spec 021 is created for this work.

---

### R0.5 - Telegram Messaging Quality (COMPLETE, P0)

**Spec**: `specs/030-telegram-messaging-quality`

- [x] Bounded UTF-8-safe splitting below the Telegram text ceiling.
- [x] Command-aware queue admission with bounded direct fallback under pressure.
- [x] Explicit queue drop/bypass outcomes without logging message payloads.
- [x] Central help aligned with `/rb<ID>`, `/reboot_no_ok` and `/c<code>`.
- [x] Preserve episode cadence, notification dedupe and all action-policy gates.
- [x] Complete one elevated NSSM restart and read-only Telegram smoke.

**Invariant**: no state, polling, threshold, cooldown or Hashcore decision change.

---

### R1 - Monitor Liveness And Recovery (COMPLETE, P0)

**Spec**: `specs/021-monitor-liveness-watchdog`

- [x] Atomic versioned heartbeat after completed fleet ticks.
- [x] Independent service/process/tick/Telegram-worker/collector assessment.
- [x] Hidden Windows watchdog definition with bounded notification dedupe.
- [x] Install the hidden task and configure SCM recovery with rollback export.
- [x] Deterministic kill, hang and stale-worker classification with no action authority.
- [x] Prove the activated PID, mutex, startup guard and fresh scheduled heartbeat.
- [x] Prove SCM recovery firing with a new PID, mutex, startup guard and heartbeat.
- [x] Complete D+1/D+3 observation (77.3h continuous soak).

**Invariant**: no second monitor and no miner/Hashcore access from the watchdog.

---

### R2 - Acquisition Resilience (COMPLETE, P1)

**Spec**: `specs/022-adaptive-acquisition`

- [x] Pure typed authoritative/diagnostic envelope and epoch contracts.
- [x] Bounded executor, lease and peer-isolation contracts without runtime wiring.
- [x] Explicit valid/partial/invalid/timeout/error/late quality normalization.
- [x] Optional diagnostic recovery probes that cannot update state or actions (T009).
- [x] Baseline/shadow comparison for latency, requests, sample age and alerts (T012).
- [x] Monitor runtime wiring and activation under PID 38816.
- [x] D+1 and D+3 soak gate passed with over 267 hours of uninterrupted execution.

**Invariant**: thresholds, hysteresis, polling offset and action policy unchanged.

---

### R3 - Incident Evidence Fusion (COMPLETE, P1)

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

---

### R4 - Electrical Source Discovery (COMPLETE / BLOCKED_EXTERNAL, P1)

**Spec**: `specs/024-electrical-source-discovery`

- [x] Establish that miner chain voltage is not AC input voltage.
- [x] Inventory actual PSU/PDU/UPS/meter model and documented telemetry.
- [x] Close discovery gate with explicit BLOCKED_EXTERNAL disposition (no external hardware sensors).
- [x] Zero writes, zero phantom sensors, zero actions.

**Exit**: Blocked dependency formal record; safe no-op.

---

### R5 - Prometheus Metrics And Grafana (COMPLETE, P1)

**Spec**: `specs/025-prometheus-metrics`

- [x] Atomic sanitized metrics snapshot from the native monitor.
- [x] Separate `prometheus_client` exporter with bounded cardinality.
- [x] Optional pinned Docker Compose Prometheus/Grafana stack.
- [x] Local-only fleet, freshness, liveness, episode and delivery dashboards.
- [x] Redaction, resource, series-count and outage-isolation proof.

**Invariant**: metrics are not canonical history and never trigger actions.

---

### R6 - Hashcore Capability Inventory (COMPLETE, P2)

**Spec**: `specs/026-hashcore-capability-inventory`

- [x] Establish static planning baseline: Toolkit `1.6.0+167`, wrapper/executable present.
- [x] Implement metadata-only inventory as the zero-process default.
- [x] Run only exact fingerprint-bound vendor-proven help/version discovery with timeout/no-window.
- [x] Classify every operation read-only, mutating or unknown.
- [x] Compare read-only capabilities with API 4028/Vnish overlap.
- [x] Require a new high-risk spec for every future action.

**Invariant**: production action scope remains existing reboot/restart only.

---

### R7 - Backup, Retention And Restore (COMPLETE, P1)

**Spec**: `specs/028-backup-retention-restore`

- [x] SQLite online backup with atomic promotion and SHA-256 manifest.
- [x] Path-guarded 14 daily / 8 weekly / 12 monthly retention.
- [x] Hidden non-overlap Scheduled Task and free-space guard.
- [x] Restore only to staging with checksum, integrity, schema and row checks.
- [x] One production backup plus successful staging restore drill.

**Invariant**: never copy a live `.db` blindly and never overwrite production automatically.

---

### R8 - Operator Interface Decision (COMPLETE / NO_BUILD, P2)

**Spec**: `specs/027-operator-interface-decision`

- [x] Score real workflows across Telegram, static HTML and Grafana.
- [x] Baseline the existing SQLite `mode=ro` static generator and its safety tests.
- [x] Execute three consecutive fixed P1 workflow runs (W01-W06) with 30/30 passes.
- [x] Close no-build when current interfaces meet all P1 targets without missing fields.
- [x] Reject additional web servers/APIs to maintain minimal attack surface.

**Invariant**: Telegram remains the only remote action surface.

---

### R9 - V2 Release Stabilization (COMPLETE / APPROVED, P0)

**Spec**: `specs/029-v2-release-stabilization`

- [x] Define terminal dependency states, runtime-payload identity and stable R001-R025 cross-feature matrix.
- [x] Freeze an evidence-eligible candidate after Specs 021-028 reach terminal states.
- [x] Run full cross-feature, core-safety, QA and auxiliary-outage regression (416/416 tests passing).
- [x] Complete release backup and staging restore (23.2 MB online backup and restore drill).
- [x] Controlled service activation and read-only smoke (PID 38816).
- [x] Continuous 168-hour review completed (267.2 continuous soak hours achieved).
- [x] Three documentation sweeps, secret hygiene and explicit release decision (`APPROVE`).
- [x] Tag `v2.0.0` published.

---

### R10 - Telegram Max, Intelligence & Concurrency Release V3 (COMPLETE / APPROVED, P0)

**Specs**: `specs/031-telegram-interactive-callbacks` a `specs/038-v3-release-stabilization`

- [x] Spec 031: Botones interactivos Telegram inline (1-tap) y flujo de confirmaciÃ³n en 2 pasos para reinicios seguros (`app/telegram/callbacks.py`).
- [x] Spec 032: GrÃ¡ficos nativos de telemetrÃ­a en formato PNG generados en RAM sin almacenamiento en disco (`app/telegram/charts.py`).
- [x] Spec 033: Modo mantenimiento y silenciamiento temporal con bloqueo de autoreinicios (`app/telegram/snooze.py`).
- [x] Spec 034: Reporte ejecutivo diario programado (08:00 AM) y on-demand (`app/telegram/digest.py`).
- [x] Spec 035: Inteligencia tÃ©rmica, cÃ¡lculo de headroom a 85Â°C y alertas predictivas de saturaciÃ³n de ventiladores (`app/governance/fan_health.py`).
- [x] Spec 036: Seguimiento en tiempo real de eficiencia energÃ©tica ($J/\text{TH}$) y alertas de degradaciÃ³n (`app/governance/energy_efficiency.py`).
- [x] Spec 037: AuditorÃ­a dinÃ¡mica de presets Vnish y alertas de downclocking ($\ge 25\text{ MHz}$) (`app/vnish/presets.py`).
- [x] Spec 038: Endurecimiento de concurrencia multihilo, mitigaciÃ³n de condiciones de carrera, 19 tests de estrÃ©s (`tests/test_v3_concurrency.py`), 514 tests globales PASS y certificaciÃ³n del Release V3.0.0.

**Invariant**: cero impacto sobre la mÃ¡quina de estados, aislamiento estricto de hilos lectores SQLite con `?mode=ro`.

---

### R11 - Fan Governor & Dynamic Presets Governance (COMPLETE / ACTIVE, P0)

**Specs**: `specs/039-vnish-fan-governor` y `specs/040-dynamic-voltage-presets`

- [x] ModulaciÃ³n de lazo cerrado tÃ©rmico en `app/governance/fan_governor.py` hacia temperatura Ã³ptima de 82.0Â°C.
- [x] ProtecciÃ³n de emergencia ante picos tÃ©rmicos `EMERGENCY_SPIKE` a 83.5Â°C con forzado inmediato a 100% PWM.
- [x] Algoritmo de balanceo por elevador de tensiÃ³n (`app/governance/preset_balancer.py`) mitigando caÃ­das en cascada.
- [x] Desescalado tÃ©rmico individual ante saturaciÃ³n y desescalado grupal por inestabilidad de red.
- [x] Control manual y comandos en caliente `/gov` y `/balancer` vÃ­a Telegram.
- [x] 35 tests unitarios e integraciÃ³n pasando (`tests/test_fan_governor_concurrency.py`, `tests/test_preset_balancer.py`).
- [x] Activado y verificado en producciÃ³n con telemetrÃ­a continua.

---

### R12 - Modular Domain Architecture & Shim Purge (COMPLETE, P2)

**Specs**: `specs/041-app-modular-architecture` y `specs/042-purge-shims-test-modernization`

- [x] ReorganizaciÃ³n de los 22 archivos planos en 4 subpaquetes de dominio desacoplados (`app/core/`, `app/vnish/`, `app/governance/`, `app/telegram/`).
- [x] ImplementaciÃ³n inicial de shims de retrocompatibilidad con module aliasing.
- [x] ModernizaciÃ³n canÃ³nica de todas las rutas de importaciÃ³n en la suite de pruebas `tests/`.
- [x] Purga definitiva mediante `git rm` de los 22 archivos shims en la raÃ­z de `app/`.
- [x] Estructura de `app/` reducida estrictamente al orquestador `miner_monitor.py` y el inicializador `__init__.py`.
- [x] 587/587 tests globales PASS y auditorÃ­a de release verificada (60 payload files).

---

### R13 - Telegram Interactive Command Center (COMPLETE, P1)

**Spec**: `specs/043-telegram-interactive-command-center`

- [x] MÃ³dulo puro desacoplado `app/telegram/command_center.py` con layouts y builders de InlineKeyboardMarkup.
- [x] Dashboard tÃ¡ctil `/menu` (alias `/start`, `/panel`) con semÃ¡foros, barras de progreso Unicode `[â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–‘â–‘]` y mÃ©tricas de flota.
- [x] SubmenÃºs in-place vÃ­a `editMessageText`: MÃ©tricas, Reinicios guiados, Presets y Alertas.
- [x] Flujo de confirmaciÃ³n de reinicio en dos toques con token criptogrÃ¡fico efÃ­mero de 60 segundos.
- [x] Acciones rÃ¡pidas de 4 botones embebidas en alertas de incidentes (`diag`, `chart`, `rb_req`, `snz`).
- [x] GuardiÃ¡n de seguridad RBAC (`from_id == chat_id`) y acuse inmediato `answerCallbackQuery` (< 500ms).
- [x] 17 tests unitarios en `tests/test_command_center.py` y 602 tests globales PASS.

---

### R14 - Modo Silencio Inteligente & Safety Thermal Guard (COMPLETE / ACTIVE, P0)

**Spec**: `specs/044-silent-mode-thermal-guard`

- [x] Cumplimiento de CondiciÃ³n C1: Despacho asÃ­ncrono no bloqueante en el worker de Telegram polling.
- [x] Cumplimiento de CondiciÃ³n C2: Campos `silent_mode_*` independientes en `MinerState` y reconciliaciÃ³n en arranque `first_tick`.
- [x] Cumplimiento de CondiciÃ³n C3: InyecciÃ³n dinÃ¡mica de techos acÃºsticos (`max_fan_duty_percent`) al Fan Governor.
- [x] Cumplimiento de CondiciÃ³n C4: DesactivaciÃ³n atÃ³mica en `state.json` bajo pico tÃ©rmico (83.5Â°C) o falla con ventiladores al 100% y alerta Telegram.
- [x] Temporizadores de cuenta regresiva configurables (30m, 1h, 2h, 4h, 6h, indef) con reversiÃ³n automÃ¡tica a rÃ©gimen normal.
- [x] IntegraciÃ³n de selector tÃ¡ctil en el Command Center (`cc:nav:silent`, `cc:act:silent:*`) y comando `/silent`.
- [x] 17 tests unitarios en `tests/test_silent_mode.py` y 17 tests en `tests/test_command_center.py`.
- [x] 621/621 tests globales PASS, release audit verificado y activo en producciÃ³n bajo PID 58344.

### Spec 045: Telegram Mobile Help Center & Categorized Navigation (Completado)
- [x] Cumplimiento de CondiciÃ³n C1: Tarjetas y vistas interactivas con lÃ­neas de datos <= 32 caracteres visibles sin tags Markdown.
- [x] Cumplimiento de CondiciÃ³n C2: CatÃ¡logo canÃ³nico Ãºnico `HELP_COMMANDS` y `HELP_CATEGORIES` en `app/telegram/help_center.py` con 28 comandos e inclusiÃ³n de `/menu` y `/silent` con todos sus aliases reales.
- [x] Cumplimiento de CondiciÃ³n C3: Parser `parse_help_callback` con gramÃ¡tica cerrada (`help:nav:home`, `help:cat:<id>`, `help:cmd:<name>`) y validaciÃ³n estricta de longitud <= 64 bytes UTF-8. ACK temprano (<50ms) en `_handle_help_callback`.
- [x] Cumplimiento de CondiciÃ³n C4: Vistas interactivas < 1,500 caracteres (muy por debajo de 3,600 caracteres) evitando particionado con pÃ©rdida de tags Markdown.
- [x] Cumplimiento de CondiciÃ³n C5: SanitizaciÃ³n con `escape_markdown` y mediciÃ³n con `strip_markdown`.
- [x] Cumplimiento de CondiciÃ³n C6: Fallback directo de entrega preserva `reply_markup` ante `queue=None` o saturaciÃ³n de cola.
- [x] Cumplimiento de CondiciÃ³n C7: Cero alteraciones en la mÃ¡quina de estados, bucle de monitoreo, auto-reboot ni workers concurrentes.
- [x] ConexiÃ³n de router `help:` en `_handle_callback_query`, ACK temprano, in-place editing y botÃ³n en Command Center (`cc:nav:main` <-> `help:nav:home`).
- [x] 35 tests especÃ­ficos (29 puros + 5 integraciÃ³n + 1 fallback) y 660/660 tests globales PASS (0 fallos, 0 regresiones).

### Spec 046: Mobile-First Card Layout & UX Harmonization across Fleet Reports (Completado)
- [x] Cumplimiento de CondiciÃ³n C1: Tarjetas verticales con viÃ±etas `â€¢` y ancho estricto <= 32 columnas visibles para `/status`, `/fans`, `/efficiency` y `/presets`.
- [x] Cumplimiento de CondiciÃ³n C2: Renderizadores puros desacoplados y deterministas (`render_fleet_status_card`, `build_fans_table_text`, `build_efficiency_table_text`, `build_presets_table_text`) sin I/O ni sockets.
- [x] Cumplimiento de CondiciÃ³n C3: Callbacks `diag:ref:*` (`status`, `fans`, `eff`, `presets`) con validaciÃ³n <= 64 bytes UTF-8 y ACK inmediato (< 50ms).
- [x] Cumplimiento de CondiciÃ³n C4: Longitud total acotada (< 1,500 caracteres), previniendo desbordes o particionado roto de Markdown.
- [x] Cumplimiento de CondiciÃ³n C5: SanitizaciÃ³n Markdown robusta en todos los renderizadores.
- [x] Cumplimiento de CondiciÃ³n C6: Fallback tÃ¡ctil completo y legibilidad garantizada sin markups.
- [x] Cumplimiento de CondiciÃ³n C7: Cero modificaciones en FSM, auto-reboot, lÃ­mites del Fan Governor ni adquisiciÃ³n de telemetrÃ­a.
- [x] Teclado inline universal de 1 toque: `[ ðŸ”„ Actualizar ] [ ðŸ“± MenÃº ]` (con `[ ðŸ“Š MÃ©tricas ]` en `/status`).
- [x] Router de callbacks en `miner_monitor.py` con ediciÃ³n in-place y RBAC.
- [x] 15 tests especÃ­ficos (9 unitarios en `test_fleet_cards.py` + 6 integraciÃ³n en `test_telegram_callbacks.py`) y 675/675 tests globales PASS (0 fallos, 0 regresiones).

### Spec 047: Mobile-First Card Layout for Balancer, Digest & Operational Events (Completado)
- [x] Cumplimiento de CondiciÃ³n C1: Tarjetas verticales con viÃ±etas `â€¢` y ancho estricto <= 32 columnas visibles para `/balancer`, `/elevadores`, `/digest`, `/snoozed`, `/events`, `/event <id>` y `/why`.
- [x] Cumplimiento de CondiciÃ³n C2: Renderizadores puros desacoplados y deterministas sin I/O ni sockets (`build_balancer_table_text`, `build_miner_balancer_detail_text`, `build_elevator_sensitivity_text`, `format_daily_digest`, `build_snooze_status_text`, `render_event_list`, `render_event_detail`, `render_reboot_decision`).
- [x] Cumplimiento de CondiciÃ³n C3: Callbacks `diag:ref:*` (`balancer`, `elev`, `digest`, `events`) con validaciÃ³n <= 64 bytes UTF-8 y ACK inmediato (< 50ms).
- [x] Cumplimiento de CondiciÃ³n C4: Longitud total acotada (< 2,000 caracteres) y wrapping estricto con `wrap_mobile_lines`.
- [x] Cumplimiento de CondiciÃ³n C5: SanitizaciÃ³n y separaciÃ³n mÃ³vil estÃ¡ndar con viÃ±etas `â€¢` y separador `â”€` * 28.
- [x] Cumplimiento de CondiciÃ³n C6: Fallback tÃ¡ctil completo y legibilidad garantizada sin markups.
- [x] Cumplimiento de CondiciÃ³n C7: Cero modificaciones en FSM, auto-reboot, lÃ­mites del Fan Governor ni adquisiciÃ³n de telemetrÃ­a.
- [x] Teclados inline de refresco en 1 toque en dispatcher para `/balancer`, `/elevadores`, `/digest` y `/events`.
- [x] Router de callbacks en `miner_monitor.py` con ediciÃ³n in-place, RBAC y pase de `event_store`.
- [x] 12 tests especÃ­ficos (8 unitarios en `test_mobile_diagnostics.py` + 4 integraciÃ³n en `test_telegram_callbacks.py`) y 687/687 tests globales PASS (0 fallos, 0 regresiones).

### Spec 048: Safe Fleet Shutdown & Multi-Select Maintenance Mode (Completado)
- [x] CondiciÃ³n C1 (LÃ­mite Estricto Mobile-First <= 32 Columnas): 100% de las tarjetas y lÃ­neas cumplen ancho de 32 columnas visibles.
- [x] CondiciÃ³n C2 (Parada y ReanudaciÃ³n Segura Vnish): Wrappers transaccionales `safe_stop_mining` y `safe_resume_mining` contra `POST /api/v1/mining/stop` y `resume`.
- [x] CondiciÃ³n C3 (Purga TÃ©rmica Activa 45s): DesconexiÃ³n de carga hash (0W), barrido forzado con coolers por 45s y confirmaciÃ³n "ÃREA ELÃ‰CTRICA SEGURA".
- [x] CondiciÃ³n C4 (Selector TÃ¡ctil MultiselecciÃ³n): Matriz interactiva de casillas `â¬œ`/`â˜‘ï¸` con bitmask compacta (`0000` $\leftrightarrow$ `1010`) en callbacks <= 21 bytes.
- [x] CondiciÃ³n C5 (ConfirmaciÃ³n en 2 Pasos con Token CriptogrÃ¡fico): Ephemeral 60s token en `CallbackTokenRegistry`.
- [x] CondiciÃ³n C6 (Auto-Snooze de Mantenimiento 4h): SupresiÃ³n de falsas alarmas y autorreinicios; auto-unsnooze en `/resume`.
- [x] CondiciÃ³n C7 (Interlocks y ArmonizaciÃ³n): Bloqueo de reboots manuales y automÃ¡ticos; omitir mineros detenidos en Fan Governor y Balancer; insignias `â¸ï¸ DETENIDO`; comandos `/shutdown` y `/resume` registrados en `/help`.
- [x] 34 tests especÃ­ficos (17 unitarios en `test_fleet_shutdown.py` + 4 en `test_command_center.py` + 13 integraciÃ³n en `test_safe_fleet_shutdown_integration.py`) y 721/721 tests globales PASS (0 fallos, 0 regresiones).
- [x] Servicio Windows `MinerAlerts` reiniciado y verificado operativo en producciÃ³n bajo PID 32436.

### Spec 049: Active Thermal Purge Ramp & Acoustic Contrast on Safe Shutdown (Completado)
- [x] CondiciÃ³n C1 (Mobile-First <= 32 Columnas): Tarjetas `render_shutdown_in_progress` y `render_safe_area_card` adaptadas con `visible_line_width <= 32`.
- [x] CondiciÃ³n C2 (Rampa Forzada 100% PWM): ModulaciÃ³n concurrente inmediata al 100% de PWM en todos los mineros detenidos con `execute_parallel_fan_duty(miners, 100)`.
- [x] CondiciÃ³n C3 (Enfriamiento Ultra-RÃ¡pido 45s): EvacuaciÃ³n masiva de calor latente con 0W en hashboards, derrumbando chips a <35Â°C.
- [x] CondiciÃ³n C4 (Contraste AcÃºstico al Segundo 45): CaÃ­da brusca al piso de reposo (40% PWM / ~2.400 RPM, ~720 RPM sin carga) sincronizada exactamente con la notificaciÃ³n `ÃREA ELÃ‰CTRICA SEGURA`.
- [x] CondiciÃ³n C5 (Seguridad en ReanudaciÃ³n): `/resume` reactiva la ventilaciÃ³n preventiva (100% PWM) antes del arranque de placas, asegurando flujo tÃ©rmico seguro.
- [x] CondiciÃ³n C6 (Trazabilidad): Eventos `purge_fan_ramp` y `purge_idle_drop` registrados en SQLite `event_store`.
- [x] 4 nuevos tests (2 unitarios en `test_fleet_shutdown.py` + 2 integraciÃ³n en `test_safe_fleet_shutdown_integration.py`) y 727/727 tests globales PASS (0 fallos, 0 regresiones).


---

## Deferred Technology

- [ ] OpenTelemetry until multiple long-lived services, remote backends or tracing requirements justify an OTLP pipeline.
- [ ] MQTT until a selected physical device publishes trustworthy telemetry.
- [ ] Continuous Vnish WebSocket workers until bounded collection demonstrably misses time-critical evidence and reconnection semantics are proven.
- [ ] Remote/public web UI, web actions, React SPA and cloud deployment.
- [ ] Windows monitor containerization while Hashcore and service integration remain host-local.

---

## Completed Capability Baseline

- [x] Persistent SQLite history and reboot-decision audit.
- [x] Current finite-signal and persisted-startup safety.
- [x] Vnish board, temperature, fleet and firmware-transition interlocks.
- [x] Stability, quality, firmware and read-only diagnosis intelligence.
- [x] Bounded Vnish log collection with no-window scheduling.
- [x] Static operations dashboard.
- [x] Telegram no-silence delivery and click-safe actions.
- [x] Persistent/episode alerts and truthful current status in committed code.
- [x] Botones interactivos Telegram inline (1-tap) y flujo de confirmaciÃ³n en 2 pasos (Spec 031).
- [x] EnvÃ­o de grÃ¡ficos nativos de telemetrÃ­a en PNG sin archivos en disco (Spec 032).
- [x] Silenciamiento temporal y bloqueo de reinicios por mantenimiento programado (Spec 033).
- [x] Reporte ejecutivo diario programado y bajo demanda (Spec 034).
- [x] DiagnÃ³stico predictivo de saturaciÃ³n tÃ©rmica y degradaciÃ³n de ventiladores (Spec 035).
- [x] MÃ©trica en tiempo real de Joules por Terahash y alertas de consumo (Spec 036).
- [x] AuditorÃ­a dinÃ¡mica de perfiles de autotuning Vnish y caÃ­das de frecuencia (Spec 037).
- [x] Blindaje de concurrencia en memoria y sockets SQLite para consultas analÃ­ticas (Spec 038).
- [x] Gobernador de lazo cerrado tÃ©rmico y acÃºstico Vnish a 82.0Â°C (Spec 039).
- [x] CalibraciÃ³n y balanceo dinÃ¡mico de potencia y presets por elevador de tensiÃ³n (Spec 040).
- [x] Arquitectura modular de 4 dominios desacoplados en `app/` (Spec 041).
- [x] Purga definitiva de shims y modernizaciÃ³n canÃ³nica de tests (Spec 042).
- [x] Centro de Comando tÃ¡ctil interactivo `/menu` con submenÃºs in-place y seguridad RBAC (Spec 043).
- [x] Modo Silencio / Visitas acotado al 30%â€“50% PWM a 82.0Â°C con elevadores independientes, temporizadores y Thermal Guard a 83.5Â°C (Spec 044 - Recalibrado).
- [x] Centro de Ayuda tÃ¡ctil interactivo `/help` con navegaciÃ³n por categorÃ­as y tarjetas Mobile-First <= 32 cols (Spec 045).
- [x] Formato Mobile-First vertical con tarjetas <= 32 cols y refresco en 1 toque para /status, /fans, /efficiency, /presets (Spec 046).
- [x] Formato Mobile-First vertical con tarjetas <= 32 cols y refresco en 1 toque para /balancer, /elevadores, /digest, /snoozed, /events (Spec 047).
- [x] Apagado Seguro de Flota y Selector MultiselecciÃ³n de Mantenimiento ElÃ©ctrico con Purga TÃ©rmica (Spec 048).
- [x] Rampa de Purga TÃ©rmica Activa y Contraste AcÃºstico en Parada Segura (Spec 049).
- [x] GuardiÃ¡n de RecuperaciÃ³n Post-Blackout con BotÃ³n 1-Tap y Auto-ReanudaciÃ³n (Spec 050).
- [x] Discriminador RÃ¡pido de Corte de Fase vs CaÃ­da de Conectividad (Spec 051).
- [x] Refuerzo de Concurrencia de Gobernanza y EstabilizaciÃ³n Release V4 (Spec 053).
- [x] Resiliencia de Persistencia Post-Blackout y Ãmbito Global en Ciclo Principal (Release Hotfix V4.0.1, 797 tests PASS).
- [x] RecalibraciÃ³n de Modo Silencio 30%â€“50% PWM, RegulaciÃ³n a 82Â°C y AutonomÃ­a por Elevador (Spec 044 Update, 800 tests PASS).
- [x] CalibraciÃ³n de Piso DinÃ¡mico a 30% PWM en Fan Governor para ModulaciÃ³n AutÃ³noma a 82Â°C (Hotfix V4.0.3, 802 tests PASS).
- [x] TelemetrÃ­a Profunda por Cadena y DiagnÃ³stico Predictivo de Hashboard (Spec 054, 835 tests PASS).


---

## Future Strategic Initiatives (V4 / Next Horizon)

Las propuestas tÃ©cnicas detalladas de mejora para el sistema se encuentran documentadas en [`docs/proposals/SYSTEM_IMPROVEMENT_PROPOSALS.md`](../proposals/SYSTEM_IMPROVEMENT_PROPOSALS.md).

### Iniciativa 1 â€” IntegraciÃ³n PDU/UPS Inteligente (ContinuaciÃ³n Spec 024)
- [ ] Relevar especificaciÃ³n tÃ©cnica de fabricantes y protocolos soportados (SNMPv3 / Modbus TCP).
- [ ] DiseÃ±ar adaptador de lectura de tensiÃ³n AC real sin inferencias desde DC.
- [ ] Validar con perÃ­odo de sombra de 72 horas antes de incorporar a mÃ©tricas de flota.

### Iniciativa 2 â€” TelemetrÃ­a Avanzada Externa (Prometheus Pushgateway / OTLP)
- [ ] Evaluar exportador remoto seguro hacia Grafana Cloud o stack centralizado.
- [ ] DiseÃ±ar autenticaciÃ³n mutua TLS y buffer offline ante cortes de Internet.

### Iniciativa 3 â€” Perfiles de Eficiencia Estacional (Verano/Invierno)
- [ ] Modelar calibraciÃ³n programÃ¡tica de targets tÃ©rmicos (80Â°C verano / 83Â°C invierno).
- [ ] Automatizar conmutaciÃ³n estacional segÃºn temperatura ambiente exterior.

### Iniciativa 4 â€” Rampa de Purga TÃ©rmica Activa y Contraste AcÃºstico en Parada Segura (Spec 049 - Completado)
- [x] Forzar ventiladores al 100% durante los 45s de purga tras `stop_mining` para expulsar activamente el calor residual de los disipadores.
- [x] CaÃ­da instantÃ¡nea a reposo (40% PWM / ~2.400 RPM, ~720 RPM sin carga) en el segundo 45 simultÃ¡neo al envÃ­o de la notificaciÃ³n "ÃREA ELÃ‰CTRICA SEGURA".
- [x] Contraste acÃºstico evidente para el operador (del rugido de purga al susurro de reposo) y enfriamiento acelerado de chips de 65Â°C a <35Â°C antes del corte de energÃ­a.
- [x] Tarjeta de Telegram con indicaciÃ³n explÃ­cita del piso de reposo (40% PWM) previo a la apertura de la llave termomagnÃ©tica.

### Iniciativa 5 â€” GuardiÃ¡n de RecuperaciÃ³n Post-Blackout (Spec 050 - Completado)
- [x] DetecciÃ³n proactiva de mineros que inician en `miner_state: stopped` tras el retorno de tensiÃ³n de un corte de red.
- [x] NotificaciÃ³n ejecutiva con botÃ³n tÃ¡ctil 1-tap `[ â–¶ï¸ Reanudar Flota ]` y auto-reanudaciÃ³n configurable con ventana de gracia.
- [x] Respeto estricto de interlocks de mantenimiento (Spec 048) y silenciamiento temporal (Spec 033).
- [x] RestauraciÃ³n automÃ¡tica de ventiladores al 100% PWM al reanudar el minado.

### Iniciativa 6 â€” Discriminador RÃ¡pido de Corte de Fase vs CaÃ­da de Conectividad (Spec 051 - Completado)
- [x] ClasificaciÃ³n instantÃ¡nea (<3s): si el host local/switch sigue activo y los mineros de un elevador o la flota caen al unÃ­sono, clasificar de inmediato como disparo de tÃ©rmica o corte general.
- [x] SupresiÃ³n de reintentos lentos e histeresis de 3 ticks habitual, encolando tarjeta ejecutiva Mobile-First en Telegram con prioridad mÃ¡xima.
- [x] Autochequeo de enlace de red del host para suprimir falsas alarmas si el host quedÃ³ aislado.
- [x] ExclusiÃ³n de mineros en mantenimiento deliberado (Spec 048) o silenciamiento activo (Spec 033).
- [x] Cooldown antispam de 300s y trazabilidad completa en EventStore (`electrical_phase_drop`).

### Iniciativa 7 â€” Programador de Ventanas de Mantenimiento ElÃ©ctrico (Spec 052 - Completado)
- [x] ProgramaciÃ³n diferida de maniobras elÃ©ctricas (ej. `/schedule_maintenance in 2h 3h`, `14:30 2h`).
- [x] Desescalado suave y progresivo de presets de potencia antes de la ventana fijada (Pre-Ramp T-10m a 2300W, T-5m a 2100W) y parada segura en T-0 con purga tÃ©rmica de 45s a 100% y reposo a 40% PWM.
- [x] CancelaciÃ³n en caliente mediante botÃ³n 1-tap `[ âŒ Cancelar Ventana ]` y persistencia en `state.json`.

### Iniciativa 8 â€” TelemetrÃ­a Profunda por Cadena y DiagnÃ³stico Predictivo de Hashboard (Spec 054 - Completado)
- [x] Ingesta y normalizaciÃ³n periÃ³dica de telemetrÃ­a de cadenas `/api/v1/chains` (sensores de temperatura por chip, chips funcionales/esperados, voltajes y estado I2C).
- [x] DetecciÃ³n temprana de anomalÃ­as fÃ­sicas de sensor y bus (`state: error`, `chip: 54`, `loc: 28`) para predecir `chain_break` antes del reinicio abrupto.
- [x] AcumulaciÃ³n estructurada de telemetrÃ­a en SQLite (`chain_telemetry_samples`) para anÃ¡lisis forense, correlaciÃ³n de fallas y minerÃ­a de datos.
- [x] Tarjeta de alerta preventiva y comando interactivo `/chains` en Telegram con visualizaciÃ³n ejecutiva del estado por hashboard.
- [x] Herramienta analÃ­tica de lÃ­nea de comandos `tools/analyze_chain_breaks.py` para cruce de fallas y predicciÃ³n de fin de vida de placas.

### Iniciativa 9 â€” Auto-Reboot ante Falla de Placa y RecuperaciÃ³n AutomÃ¡tica de Hashboard (Spec 055 - Completado)
- [x] ExtensiÃ³n de la puerta pura `auto_reboot_signal_allows_evaluation` para admitir `STATE_HASHBOARD` (0/3 placas con temporizador activo) manteniendo compatibilidad 100% con `STATE_LOW`.
- [x] Temporizador monÃ³tono `hashboard_since_ts` en `MinerState` inicializado al entrar en falla y reseteado al recuperar 3/3 placas o ante reinicio.
- [x] CanalizaciÃ³n completa a travÃ©s de los 6 interlocks constitucionales (Startup Guard, ventana sostenida 600s, Thermal Guard 85Â°C, Fleet Incident Guard >= 2, Firmware Transition Guard, Cooldown 1800s, LÃ­mite de ventana 3/24h).
- [x] EjecuciÃ³n controlada vÃ­a Hashcore CLI (`run_hashcore_cli`), reseteo de temporizadores y tarjeta ejecutiva especializada en Telegram.
- [x] Registro determinista en `reboot_decisions` del `EventStore` con `trigger="hashboard_failure"`.
- [x] CertificaciÃ³n global con 854/854 tests unitarios y de regresiÃ³n PASS.

### Iniciativa 10 â€” RecuperaciÃ³n Escalonada de Dos Niveles (Spec 056 - Completado)
- [x] DiscriminaciÃ³n segura entre Auto-Restart de software (Nivel 1, `/api/v1/mining/restart` en 15-20s) y Auto-Reboot completo de hardware (Nivel 2, Hashcore CLI en 3-4m).
- [x] `evaluate_auto_restart_candidate` con filtros transitorios, cooldown de 300s y lÃ­mite de reintentos (2 intentos antes de ceder a Nivel 2).
- [x] Worker asÃ­ncrono no bloqueante `_async_execute_mining_restart` y notificaciones Telegram de Nivel 1.
- [x] CertificaciÃ³n con 881 tests PASS.

### Iniciativa 11 â€” Gobernanza de Intervenciones & Contingencia AsimÃ©trica Adaptativa (Spec 057 - Completado)
- [x] Modo global "Vnish Libre" (solo lectura/supervisiÃ³n) con interlocking de 100% de los actuadores mutantes (Reinicios L1/L2, Fan Governor, Preset Balancer y Contingencia) preservando telemetrÃ­a, SQLite y alertas.
- [x] MenÃº tÃ¡ctil e interactivo en Telegram Command Center (`[ ðŸ›¡ï¸ Intervenciones: ðŸŸ¢ ON / ðŸ”´ LIBRE ]`) con selectores individuales y temporizadores de cuenta regresiva (30m, 1h, 2h, 4h, Indef) para reactivaciÃ³n segura automÃ¡tica.
- [x] Contingencia elÃ©ctrica asimÃ©trica por elevador relativa al estado actual: reducciÃ³n exclusiva del minero canario (S19JPRO-24 en Elevador 1, S19JPRO-25 en Elevador 2) ante perturbaciÃ³n matutina de red, manteniendo intacto al compaÃ±ero.
- [x] Prueba en los lÃ­mites: descenso escalonado si el canario vuelve a reiniciar, y reducciÃ³n del compaÃ±ero solo ante perturbaciÃ³n severa.
- [x] Rampa de Step-Up Soak: tras 2 horas continuas sin reinicios, recuperaciÃ³n progresiva hacia los presets nominales.
- [x] Comandos rÃ¡pidos `/interventions` y `/contingency` y persistencia atÃ³mica en `state.json`.
- [x] CertificaciÃ³n global con 902/902 tests unitarios y de regresiÃ³n PASS.

### Iniciativa 12 â€” Desacoplamiento y ModularizaciÃ³n ArquitectÃ³nica del Monolito (Horizonte V5.0)
- Documento de Plan de AcciÃ³n: [`docs/speckit/archive/plans/ACTION_PLAN_V5_MODULARIZATION.md`](archive/plans/ACTION_PLAN_V5_MODULARIZATION.md)
- **Fase 0 â€” Quick Wins Inmediatos**:
  - [x] **QW-01**: ExtracciÃ³n de teclados y menÃºs tÃ¡ctiles (integrada en Spec 058).
  - [x] **QW-02**: RotaciÃ³n automÃ¡tica de registros con `RotatingFileHandler` en `logs/out.log` para prevenir saturaciÃ³n de disco bajo el servicio Windows.
  - [x] **QW-03**: Saneamiento y purga de funciones y wrappers legados de ayuda (`render_legacy_help_index()`) obsoletos tras Spec 045.
  - [x] **QW-04**: ExtracciÃ³n de `_build_state_payload()` fuera de `state_lock` reduciendo a 0ms la retenciÃ³n del lock de memoria durante `os.fsync()` en Windows NTFS (902 tests PASS).
- **Fase 1 â€” Spec 058: Desacoplamiento de Telegram Command Center & Dispatcher (MT-01)**:
  - [x] Desacoplamiento del bucle procedural de `telegram_polling_worker` (-2,669 LOC extraÃ­das de `miner_monitor.py`).
  - [x] Arquitectura orientada a handlers desacoplados: `app/telegram/router.py`, `app/telegram/poller.py` y `app/telegram/commands/` (`status`, `fans`, `reboot`, `interventions`, `diagnostics`, `maintenance`, `help`).
  - [x] Suite de pruebas unitarias aisladas (`tests/test_telegram_dispatcher.py` con 8 tests nuevos), con 910/910 tests globales PASS.
- **Fase 2 â€” Spec 059: Protocolos de Red y Clientes de Hardware (MT-02)**:
  - [x] ExtracciÃ³n del protocolo TCP Socket 4028 (`query_cgminer`, parsers de summary, pools, version, stats, conteo de placas hashboard y temperaturas) a `app/network/cgminer_client.py`.
  - [x] ExtracciÃ³n del actuador de hardware Hashcore Toolkit CLI a `app/network/hashcore_client.py` con guardarraÃ­les QA y flags windowless en Windows (`CREATE_NO_WINDOW`).
  - [x] Cliente formal y tipado para la API REST de Vnish a `app/network/vnish_client.py` (`VnishClient`) con context manager, timeouts acotados de 2.5s y manejo de excepciones.
  - [x] Suite de 18 pruebas unitarias en `tests/test_network_clients.py` con 928/928 tests globales PASS (cero regresiones).
- **Fase 3 â€” Spec 060: Core Daemon & Contenedor de Estado (ST-01 & ST-02 - Milestone V5.0)**:
  - [x] FormalizaciÃ³n de `app/core/state_manager.py` con jerarquÃ­a estricta anti-deadlock (`state_lock` Nivel 1 -> `_SAVE_STATE_LOCK` Nivel 2, con fsync fuera de `state_lock`).
  - [x] Motor de supervisiÃ³n declarativo con arquitectura de hooks por tick en `app/core/engine.py` (`CoreSupervisoryEngine`, `TickResult`).
  - [x] InyecciÃ³n de dependencias `MonitorContext` y factorÃ­a `build_monitor_context` en `app/core/context.py`.
  - [x] ConexiÃ³n aditiva de `StateManager` y `MonitorContext` en `main()` de `miner_monitor.py` preservando el 100% de contratos `inspect.getsource(main)`.
  - [x] Suite de 7 pruebas unitarias en `tests/test_core_daemon.py` con **935/935 tests globales PASS** (cero fallos, cero regresiones). Milestone V5.0 certificado.

### Iniciativa 13 â€” Resiliencia de Almacenamiento SQLite WAL Mode & Integrity Check (Spec 061 - Completada)
- Documento de Plan de EvoluciÃ³n: [`docs/speckit/archive/plans/ACTION_PLAN_POST_V5_EVOLUTION.md`](archive/plans/ACTION_PLAN_POST_V5_EVOLUTION.md)
- EspecificaciÃ³n: [`specs/061-sqlite-wal-integrity/spec.md`](../../specs/061-sqlite-wal-integrity/spec.md)
- Evidencia: [`specs/061-sqlite-wal-integrity/evidence.md`](../../specs/061-sqlite-wal-integrity/evidence.md)
- [x] VerificaciÃ³n de integridad asÃ­ncrona (`_integrity_check_worker`) en arranque sin retrasar el booteo ni el Startup Guard.
- [x] Aislamiento automÃ¡tico de base corrupta a `data/miner_alerts_corrupt_<epoch>.db` y auto-recreaciÃ³n limpia del esquema v7 ante fallo de sectores tras apagÃ³n.
- [x] Checkpointing determinista en Windows NTFS: `PRAGMA wal_checkpoint(PASSIVE)` horario y `PRAGMA wal_checkpoint(TRUNCATE)` diario fuera de horas pico.
- [x] Techo blando de tamaÃ±o con `PRAGMA max_page_count = 262144` (~1 GB) para evitar saturaciÃ³n de disco.
- [x] Pool de lectura multi-lector `create_readonly_connection` con manejo defensivo de `SQLITE_BUSY_SNAPSHOT` y reintentos con backoff exponencial (11 tests en `tests/test_event_store_wal_resilience.py`, 946/946 tests PASS).

### Iniciativa 14 â€” HW Error Tripwire & Rollback AutomÃ¡tico de Overclock (Spec 062 - Completado)
- Documento de Plan de EvoluciÃ³n: [`docs/speckit/archive/plans/ACTION_PLAN_POST_V5_EVOLUTION.md`](archive/plans/ACTION_PLAN_POST_V5_EVOLUTION.md)
- EspecificaciÃ³n: [`specs/062-hw-error-tripwire/spec.md`](../../specs/062-hw-error-tripwire/spec.md) | Evidencia: [`specs/062-hw-error-tripwire/evidence.md`](../../specs/062-hw-error-tripwire/evidence.md)
- [x] MÃ©trica de errores de hardware no volÃ¡til en `StabilityMetrics` (`hw_errors_delta_10m`, `hw_error_rate_pct`) calculada vÃ­a `EventStore`.
- [x] Regla de disparo `ACTION_STEP_DOWN_HW_ERRORS` en `evaluate_balancer_step()` con umbral combinado (`hw_error_rate_pct >= 0.5%` AND `hw_errors_delta_10m >= 200`).
- [x] Candado de 48 horas (`hw_error_lock_until_ts`, `hw_error_locked_preset`) persistido en `state.json` bloqueando re-escalado optimista.
- [x] Interlock anti-cascada post-reboot L1/L2 impidiendo que el firmware restablezca 2700W por defecto.
- [x] Tarjeta de notificaciÃ³n mÃ³vil en Telegram `<= 32` columnas (`render_hw_error_tripwire_card()`).
### Iniciativa 15 â€” Gobernador TÃ©rmico con Conciencia Estacional (Spec 063 - Completado)
- Documento de Plan de EvoluciÃ³n: [`docs/speckit/archive/plans/ACTION_PLAN_POST_V5_EVOLUTION.md`](archive/plans/ACTION_PLAN_POST_V5_EVOLUTION.md)
- EspecificaciÃ³n: [`specs/063-ambient-thermal-pid/spec.md`](../../specs/063-ambient-thermal-pid/spec.md) | Evidencia: [`specs/063-ambient-thermal-pid/evidence.md`](../../specs/063-ambient-thermal-pid/evidence.md)
- [x] ExtracciÃ³n de `inlet_temp_c` en `VnishTelemetry` y `normalize_vnish_stats()` desde `stats_response` existente sin requests HTTP adicionales.
- [x] ExtensiÃ³n de `GovernorConfig` con parÃ¡metros estacionales (`winter_target_temp_c`, `summer_min_duty_percent`, etc.).
- [x] FunciÃ³n pura `resolve_seasonal_parameters()` en `app/governance/fan_governor.py` con 3 guardarraÃ­les inviolables.
- [x] AdaptaciÃ³n dinÃ¡mica de curvas en `compute_governor_step(..., ambient_temp_c=...)`.
- [x] AgregaciÃ³n grupal de $T_{\text{amb}}$ y orquestaciÃ³n en `execute_governor_cycle()`.
- [x] Suite completa de tests en `tests/test_fan_governor_seasonal.py`.
### Iniciativa 16 â€” TelemetrÃ­a Visual y GrÃ¡ficos Multi-Miner en Telegram (Spec 064 - Completado)
- Documento de Plan de EvoluciÃ³n: [`docs/speckit/archive/plans/ACTION_PLAN_POST_V5_EVOLUTION.md`](archive/plans/ACTION_PLAN_POST_V5_EVOLUTION.md)
- EspecificaciÃ³n Activa: [`specs/064-multi-miner-charts/spec.md`](../../specs/064-multi-miner-charts/spec.md) | Evidencia: [`specs/064-multi-miner-charts/evidence.md`](../../specs/064-multi-miner-charts/evidence.md)
- [x] Consultas y renderizado de grÃ¡ficos por grupo elÃ©ctrico (`fetch_group_chart_data`, `render_group_chart_png`) en `charts.py`.
- [x] Soporte para comandos `/chart elevator_1`, `/chart elevator_2`, `/chart fleet` en `ChartCommand`.
- [x] Selector interactivo de rango con teclado inline `[ 1h ] [ 6h ] [ 24h ] [ 7d ]` (`build_chart_range_keyboard`).
- [x] AcciÃ³n `chart_range` en `parse_callback_data()` y dispatcher en `_handle_callback_query()`.
- [x] ActualizaciÃ³n in-place mediante `edit_telegram_photo()` con `editMessageMedia` y `attach://file_0`.
- [x] GestiÃ³n estricta de memoria `matplotlib` (`Agg`, `plt.close(fig)`) y suite de pruebas de estrÃ©s (11 tests en `tests/test_multi_miner_charts.py`, 996/996 tests PASS).

### Iniciativa 17 â€” Pipeline Declarativo de Hooks en CoreSupervisoryEngine (Spec 065 - ST-04 - Completado)
- EspecificaciÃ³n: [`specs/065-supervisory-hooks/spec.md`](../../specs/065-supervisory-hooks/spec.md) | Evidencia: [`specs/065-supervisory-hooks/evidence.md`](../../specs/065-supervisory-hooks/evidence.md)
- [x] `HookStage` (enum `IntEnum` con 7 etapas ordenadas: PRE_TICK < ACQUISITION < DETECTION < GOVERNANCE < ACTUATOR < PERSISTENCE < POST_TICK).
- [x] Clase base `SupervisoryHook` y dataclass `HookResult` (ok, duration_seconds, error).
- [x] `CoreSupervisoryEngine.register_hook()` con ordenamiento determinista y `execute_tick()` con contenciÃ³n defensiva por hook individual.
- [x] GarantÃ­a invariante: etapa `PERSISTENCE` siempre se ejecuta incluso si todas las etapas previas fallan.
- [x] Hooks canÃ³nicos: `PersistenceHook` (PERSISTENCE), `GovernanceInterlockHook` (GOVERNANCE), `TimingGuardHook` (PRE_TICK).
- [x] IntegraciÃ³n aditiva en `main()` de `miner_monitor.py` con `_poll_interval_seconds` y modelo monotÃ³nico `poll_seconds = max(0.0, interval - elapsed); time.sleep(poll_seconds)`.
- [x] Suite `tests/test_supervisory_hooks.py` con 47 tests (13 clases) cubriendo orden de etapas, contenciÃ³n, timing monotÃ³nico y hooks canÃ³nicos. **1043/1043 tests PASS** (0 regresiones).

### Iniciativa 18 â€” Cold-Boot Fleet Grace Period Post-Arranque (Spec 066 - PROP-001 - Completado)
- Documento de Propuestas: [`docs/proposals/SYSTEM_IMPROVEMENT_PROPOSALS.md`](../proposals/SYSTEM_IMPROVEMENT_PROPOSALS.md)
- EspecificaciÃ³n: [`specs/066-cold-boot-grace/spec.md`](../../specs/066-cold-boot-grace/spec.md) | Evidencia: [`specs/066-cold-boot-grace/evidence.md`](../../specs/066-cold-boot-grace/evidence.md)
- [x] ConfiguraciÃ³n `"startup_fleet_grace_period_seconds": 180` y `"startup_fleet_grace_threshold_ths": 50.0`.
- [x] SupresiÃ³n activa de streaks de falla (`offline_streak = 0`, `low_streak = 0`) y reseteo de timers sostenidos durante la fase `WARMING_UP`.
- [x] InhibiciÃ³n de alertas de episodios irregulares (`EPISODE_ALERT`) a Telegram durante la ventana de calentamiento de 180 segundos.
- [x] ConsolidaciÃ³n temprana de arranque con tarjeta limpia `ðŸŸ¢ FLOTA RESTABLECIDA` al alcanzar $\ge 50$ TH/s en toda la flota.
- [x] ConsolidaciÃ³n por timeout tras 180s con tarjeta `STARTUP [FIN PERÃODO DE GRACIA]` y reconocimiento de iniciales (`acknowledge_active_initials()`).
- [x] SincronizaciÃ³n continua de `monitor_ctx.governance = _GLOBAL_INTERVENTION_GOV` en cada tick e inyecciÃ³n en `extra_tick_data` para hooks.
- [x] Suite de 15 pruebas unitarias en `tests/test_startup_grace_period.py`. **1062/1062 tests globales PASS** (0 regresiones).

### Iniciativa 19 â€” Latido de Gateway y SupresiÃ³n de Tormentas de Red Local (Spec 067 - PROP-005 - Completado)
- Documento de Propuestas: [`docs/proposals/SYSTEM_IMPROVEMENT_PROPOSALS.md`](../proposals/SYSTEM_IMPROVEMENT_PROPOSALS.md)
- EspecificaciÃ³n: [`specs/067-gateway-heartbeat/spec.md`](../../specs/067-gateway-heartbeat/spec.md) | Evidencia: [`specs/067-gateway-heartbeat/evidence.md`](../../specs/067-gateway-heartbeat/evidence.md)
- [x] Worker daemon ultraliviano de latido `GatewayHeartbeatWorker` en `app/network/gateway_heartbeat.py` (TCP connect 50ms, fallback puerto 53, cierre explÃ­cito de sockets).
- [x] SupresiÃ³n de falsos conatos de desconexiÃ³n masiva (`STATE_OFFLINE`) durante parpadeos de switch Ethernet o microcortes de router local (ventana default 15s).
- [x] Suite de 7 pruebas unitarias en `tests/test_gateway_heartbeat.py`. **1072/1072 tests globales PASS** (0 fallos, 0 regresiones).

### Iniciativa 20 â€” Canal IPC de Alta Frecuencia Monitor â†” Watchdog vÃ­a Named Pipes (Spec 068 - PROP-007 - Completada & Certificada)
- Documento de Plan y EspecificaciÃ³n: [`specs/068-watchdog-ipc-pipe/spec.md`](../../specs/068-watchdog-ipc-pipe/spec.md) | Evidencia: [`specs/068-watchdog-ipc-pipe/evidence.md`](../../specs/068-watchdog-ipc-pipe/evidence.md)
- **Estado**: Completada & Certificada. Servidor y cliente IPC nativo en Windows NT con SDDL `D:(A;;GRGW;;;WD)` y fallback a socket loopback `127.0.0.1:4029`. Total **1176 tests PASS**.
- [x] Servidor Named Pipe nativo en Windows (`\\.\pipe\MinerAlertsWatchdog`) vÃ­a `ctypes` (sin dependencias `pywin32`) con fallback a Loopback TCP (`127.0.0.1:4029`).
- [x] Protocolo Ping-Pong (`PING <nonce>` -> `PONG <nonce> <seq> <uptime>`) con timeout de 100ms y detecciÃ³n de deadlocks en el bucle principal (`tick_sequence` congelado).
- [x] MÃ¡quina de estados de 3 etapas y volcado forense automÃ¡tico de trazas de hilos (`sys._current_frames()`) antes de `Restart-Service`.

### Iniciativa 21 â€” TelemetrÃ­a Profunda por Cadena & DiagnÃ³stico Predictivo Chain Break (Spec 069 - PROP-008 - Completada & Certificada)
- Documento de Plan y EspecificaciÃ³n: [`specs/069-chain-telemetry-break-prediction/spec.md`](../../specs/069-chain-telemetry-break-prediction/spec.md) | Evidencia: [`specs/069-chain-telemetry-break-prediction/evidence.md`](../../specs/069-chain-telemetry-break-prediction/evidence.md)
- **Estado**: Completada & Certificada tras auditorÃ­a QA especialista y hardening de robustez. Motor predictivo `PredictiveChainEngine` implementado, Ã­ndice compuesto WAL creado, reglas I2C/dÃ©ficit/elÃ©ctricas certificadas con 23 nuevas pruebas y 1204 tests globales PASS.
- [x] Ãndice compuesto optimizado `ix_chain_telemetry_miner_chain_time` en SQLite WAL para consultas de evaluaciÃ³n en $< 15\text{ ms}$ (medido $< 1\text{ ms}$).
- [x] Helper resiliente `fetch_chain_samples_window` con reintentos ante `SQLITE_BUSY_SNAPSHOT` y `_cursor_rows_to_dicts` universal.
- [x] Regla de alerta preventiva de bus I2C: notificaciÃ³n proactiva en Telegram si `sensors_error_count > 0` persiste por $> 12\text{ h}$ con significancia $N \ge 24$ (cubriendo el caso del Minero 24 Cadena 2).
- [x] Discriminador de perturbaciÃ³n elÃ©ctrica de grupo (`elevator_1` vs `elevator_2`) vs degradaciÃ³n fÃ­sica de silicio suprimiendo alertas falsas individuales ante caÃ­das simultÃ¡neas con soporte de claves compuestas.
- [x] Formateador de alertas mÃ³viles Telegram ($\le 32$ columnas), soporte explÃ­cito de Cadena 0 (Board 0) y deduplicaciÃ³n con cooldown de 24h (`state.chain_warnings_ts`).
- [x] Suite de pruebas unitarias (`tests/test_chain_predictive_rules.py`, 20 tests) y benchmark de rendimiento (`tests/test_chain_query_performance.py`, 3 tests). Total 1204 tests PASS.

### Iniciativa 22 â€” ModularizaciÃ³n del Core Fase B â€” Desacoplamiento Seguro de `inspect.getsource(main)` (Spec 070 - ST-05 - Completada & Certificada)
- Documento de Plan y EspecificaciÃ³n: [`specs/070-core-modularization-decoupling/spec.md`](../../specs/070-core-modularization-decoupling/spec.md)
- **Estado**: Completada & Certificada. Fases A, B, C y D finalizadas. Desacoplamiento total de introspecciÃ³n de cÃ³digo fuente en tests legados y extracciÃ³n funcional a `DetectionHook` y `ActuatorHook`. Total 1160 tests PASS.
- [x] ConstrucciÃ³n del arnÃ©s de comportamiento funcional `tests/test_supervisory_core_behavioral.py` reproduciendo los 37 tests de invariantes mediante caja negra sobre `SupervisoryBehavioralHarness`.
- [x] CertificaciÃ³n de paridad dual: validaciÃ³n de 37 tests legados + 37 tests de comportamiento (total **1156/1156 tests PASS**).
- [x] ExtracciÃ³n segura del bucle procedural de `main()` hacia `DetectionHook` y `ActuatorHook` (Fase C) eliminando introspecciÃ³n de cÃ³digo fuente en los 4 archivos de tests legados.
- [x] CertificaciÃ³n global de la suite: **1160/1160 tests PASS** sin regresiones y servicio Windows `MinerAlerts` en ejecuciÃ³n continua (Fase D).

### Iniciativa 23 â€” ConsolidaciÃ³n de Pool SQLite Resiliente & Barrera de Hilos Daemon (Spec 071 - P0/P1 - Completada)
- Plan de AcciÃ³n y Saneamiento: [`docs/speckit/archive/plans/ACTION_PLAN_REPO_CLEANUP_AND_ROADMAP.md`](archive/plans/ACTION_PLAN_REPO_CLEANUP_AND_ROADMAP.md)
- EspecificaciÃ³n: [`specs/071-sqlite-pool-and-thread-hardening/spec.md`](../../specs/071-sqlite-pool-and-thread-hardening/spec.md) | Evidencia: [`specs/071-sqlite-pool-and-thread-hardening/evidence.md`](../../specs/071-sqlite-pool-and-thread-hardening/evidence.md)
- [x] FunciÃ³n defensiva `_async_restore_locked_preset_tripwire` en `miner_monitor.py` para blindar el hilo `RestoreLock_{name}` con captura total de excepciones y logging estructurado (P0).
- [x] ExposiciÃ³n formal de `open_readonly_connection(db_path)` en `app/core/event_store.py` con fallback y pragmas resilientes (P1).
- [x] MigraciÃ³n de las 7 conexiones directas ad-hoc a SQLite (`energy_efficiency`, `fan_health`, `preset_balancer`, `charts`, `daily_digest`, `presets`) hacia el pool resiliente con reintento automÃ¡tico ante `SQLITE_BUSY_SNAPSHOT`.
- [x] Barrera defensiva en `ShutdownPurgeNotify` y nombres descriptivos en hilos de mensajerÃ­a (`TelegramSender`, `TelegramPolling`).
- [x] Suites de pruebas en `tests/test_sqlite_readonly_consolidation.py` y `tests/test_tripwire_thread_hardening.py`. **1079/1079 tests globales PASS** (+7 nuevos, 0 regresiones).

### Iniciativa 24 â€” UnificaciÃ³n de SerializaciÃ³n de Estado & Desacoplamiento de Shims (Spec 072 - P2 - Completada & Certificada)
- Plan de AcciÃ³n y Saneamiento: [`docs/speckit/archive/plans/ACTION_PLAN_REPO_CLEANUP_AND_ROADMAP.md`](archive/plans/ACTION_PLAN_REPO_CLEANUP_AND_ROADMAP.md)
- [x] DelegaciÃ³n de `_build_state_payload()` en `StateManager.serialize_miner_state()` unificando la fuente de verdad de `MinerState`.
- [x] ExtracciÃ³n del helper compartido `find_assessment_by_target()` y `format_miner_key()` eliminando copy-paste en comandos de Telegram (`diagnostics`, `fans`, `reboot`, `maintenance`).
- [x] CentralizaciÃ³n de `_dicts()` en `app/core/mining_quality.py`.
- [x] Retiro y saneamiento de shims procedurales preservando contratos de `inspect.getsource(main)`.
- [x] Suite de pruebas en `tests/test_state_serialization_parity.py` y `tests/test_find_assessment_by_target.py`. **1113/1113 tests globales PASS** (0 fallos, 0 regresiones).

### Iniciativa 25 â€” ReutilizaciÃ³n de Clientes en Tools & AlineaciÃ³n de ConfiguraciÃ³n (Spec 073 - P3 - Completada)
- Plan de AcciÃ³n y Saneamiento: [`docs/speckit/archive/plans/ACTION_PLAN_REPO_CLEANUP_AND_ROADMAP.md`](archive/plans/ACTION_PLAN_REPO_CLEANUP_AND_ROADMAP.md)
- [x] MigraciÃ³n de `tools/miner_diagnostics.py` y `debug_4028.py` a `app.network.cgminer_client`.
- [x] Script auditor de configuraciÃ³n `tools/audit_config.py` validando paridad entre `config.example.json` y `config.json`.
- [x] ConsolidaciÃ³n de fixtures duplicadas en tests compactos de Telegram (`tests/fixtures_compact_ux.py`).
- [x] Suite de pruebas en `tests/test_miner_diagnostics_client.py` y `tests/test_audit_config.py`. **1119/1119 tests globales PASS** (0 fallos, 0 regresiones).

### Iniciativa 26 â€” Amortiguador de Inrush Pareado de Elevador (Spec 074 - PROP-009 - Laboratorio & ValidaciÃ³n Completada)
- EspecificaciÃ³n: [`specs/074-paired-elevator-contingency/spec.md`](../../specs/074-paired-elevator-contingency/spec.md) | Evidencia: [`specs/074-paired-elevator-contingency/evidence.md`](../../specs/074-paired-elevator-contingency/evidence.md) | Propuesta: [`docs/proposals/PROP-009-contingency-stabilization-hypotheses.md`](../proposals/PROP-009-contingency-stabilization-hypotheses.md)
- **Estado**: Laboratorio & ValidaciÃ³n Completada (1219 tests PASS). Preparado para auditorÃ­a de concurrencia y subprocesos con Claude Sonnet 4.6 (Thinking) antes de despliegue a producciÃ³n.
- [x] NormalizaciÃ³n canÃ³nica de identificadores de mineros (`normalize_miner_name`) en bÃºsquedas y disparadores de contingencia (H1).
- [x] Clampeo de `preset_switcher.top_preset` (`clamp_top_preset=True`) en `app/vnish/client.py` para anular interferencia del demonio tÃ©rmico de Vnish (H2).
- [x] Desescalada preventiva transitoria del compaÃ±ero robusto (-1 peldaÃ±o / 300s) durante inrush inductivo y auto-restauraciÃ³n en `soak_tick` (H3).
- [x] SupresiÃ³n de `ACTION_RECOVERY_MAX_COOLING` durante ventana de arranque (`is_warming_up`) y umbral de potencia de hashboard ($< 500\text{W}$) en `fan_governor.py` (H4).
- [x] Suite dedicada `tests/test_paired_elevator_contingency.py` (15 tests PASS). Suite global del proyecto: **1219/1219 tests PASS** (0 regresiones).
- [x] Despliegue en producciÃ³n certificado (1221 tests PASS, Servicio Windows PID 19204).

### Iniciativa 27 â€” RecuperaciÃ³n Suave de Hasheo, Headroom Chilling y Blindaje Anticolapso de Fuentes APW12 (Spec 075 - PROP-010)
- EspecificaciÃ³n: [`specs/075-soft-landing-recovery/spec.md`](../../specs/075-soft-landing-recovery/spec.md) | Plan: [`specs/075-soft-landing-recovery/plan.md`](../../specs/075-soft-landing-recovery/plan.md) | Propuesta: [`docs/proposals/PROP-010-soft-landing-recovery-psu-protection.md`](../proposals/PROP-010-soft-landing-recovery-psu-protection.md)
- **Estado**: ImplementaciÃ³n y AuditorÃ­a de Concurrencia Completadas (T001-T007). Lista para CertificaciÃ³n en ProducciÃ³n (T008).
- [x] Ventana de normalizaciÃ³n pasiva de 120s (`settle_window`) ante detenciÃ³n de hasheo.
- [x] Desescalada preventiva pre-reinicio (`soft_landing_clamp` a 1800W con `clamp_top_preset=True`) para suprimir picos $di/dt$ y evitar el Latch-Off de la fuente APW12.
- [x] InhibiciÃ³n de reintentos agresivos ante falla fÃ­sica persistente (`CHAIN_FAULT` / `stock_firmware_fallback`) para evitar someter a la fuente a ciclos destructivos inÃºtiles.
- [x] Protocolo de enfriamiento proactivo (*Headroom Chilling*): Balancer solicita 100% PWM temporal al Governor para enfriar minero de 2500W a $\le 78.5^\circ\text{C}$ y desbloquear el salto a 2700W (+6 TH/s).
- [x] CalibraciÃ³n de emergencia de Governor a 83.0Â°C.
- [x] Suite completa de regresiÃ³n: **1236/1236 tests PASS** (0 fallos, 0 regresiones).

### Iniciativa 28 â€” ReinstalaciÃ³n AutÃ³noma de Firmware VNish en NAND y CalibraciÃ³n de Escalera de Hardware S19j Pro (Spec 076 - PROP-011 - Completada & Certificada)
- EspecificaciÃ³n: [`specs/076-firmware-reflash-and-ladder/spec.md`](../../specs/076-firmware-reflash-and-ladder/spec.md) | Plan: [`specs/076-firmware-reflash-and-ladder/plan.md`](../../specs/076-firmware-reflash-and-ladder/plan.md) | Evidencia: [`specs/076-firmware-reflash-and-ladder/evidence.md`](../../specs/076-firmware-reflash-and-ladder/evidence.md) | Propuesta: [`docs/proposals/PROP-011-autonomous-firmware-reflash-and-hardware-ladder.md`](../proposals/PROP-011-autonomous-firmware-reflash-and-hardware-ladder.md)
- **Estado**: ImplementaciÃ³n, AuditorÃ­a QA y CertificaciÃ³n en ProducciÃ³n Completadas (T001-T008). 1262/1262 tests PASS.
- [x] CalibraciÃ³n 1:1 de `DEFAULT_PRESET_LADDER` con los 9 peldaÃ±os reales de VNish 1.2.6 (`1740W`, `1800W`, `1850W`, `2000W`, `2150W`, `2300W`, `2500W`, `2700W`, `2970W`) y piso mÃ­nimo de contingencia en `2150W` (eliminando rechazos HTTP 400 y atrapamiento en 1800W).
- [x] MÃ³dulo `app/network/firmware_flasher.py` con verificaciÃ³n de stock Bitmain (`is_stock_bitmain`) y carga multipart HTTP Digest `/cgi-bin/upgrade.cgi` (`flash_bitmain_nand`).
- [x] Aprovisionamiento post-flasheo (`app/governance/miner_provisioner.py`) inyectando pools de Binance, preset 2300W/2700W y matriz de 378 chips afinados desde perfiles guardados.
- [x] Comando Telegram `/flash_vnish <miner>` con confirmaciÃ³n interactiva de 2 pasos (`flash_cfm`/`flash_ccl` o `CONFIRM`) y ejecuciÃ³n en worker desacoplado `FlashWorker_{miner}`.
- [x] Suite de pruebas dedicadas (`test_firmware_flasher.py`, `test_miner_provisioner.py`, `test_telegram_flash_command.py`) y validaciÃ³n de regresiÃ³n completa (**1262/1262 tests PASS**).
- [x] Servicio Windows `MinerAlerts` reiniciado y certificado en producciÃ³n.

### Iniciativa 29 â€” Gobernanza Escalonada de Elevadores, Bajada Compartida y Soft-Contingencia Horaria (Spec 077 - PROP-012 - Completada & Certificada)
- EspecificaciÃ³n: [`specs/077-staggered-elevator-governance/spec.md`](../../specs/077-staggered-elevator-governance/spec.md) | Plan: [`specs/077-staggered-elevator-governance/plan.md`](../../specs/077-staggered-elevator-governance/plan.md) | Evidencia: [`specs/077-staggered-elevator-governance/evidence.md`](../../specs/077-staggered-elevator-governance/evidence.md) | Propuesta: [`docs/proposals/PROP-012-staggered-elevator-governance-and-soft-contingency.md`](../proposals/PROP-012-staggered-elevator-governance-and-soft-contingency.md)
- **Estado**: ImplementaciÃ³n, AuditorÃ­a QA y CertificaciÃ³n en ProducciÃ³n Completadas (T001-T007). 1288/1288 tests PASS.
- [x] Cola global de transiciÃ³n escalonada para la instalaciÃ³n (*Facility-Wide Staggered Queue*): 1 minero a la vez ejecuta cambios de preset por ciclo con ventana de reposo obligatoria de 180s (*Facility Settle Window*) en la bajada compartida.
- [x] Presupuesto dinÃ¡mico por transformador elevador ($\le 5000\text{W}$ en horario pico, $\le 5400\text{W}$ en horario valle) y preferencia de equilibrio simÃ©trico (priorizar parejas 2x 2500W antes de combinaciones asimÃ©tricas 2700W/2300W).
- [x] Soft-Contingencia Horaria quirÃºrgica: en dÃ­as hÃ¡biles (Lunes a Viernes), desescalada paulatina (1 minero cada 180s) hacia 2500W en pico matutino (08:30-10:30 hs) y nocturno (19:30-22:30 hs). 19 horas libres y 100% de fines de semana habilitan plena potencia (2700W x4).
- [x] Co-gobernanza con VNish: fijaciÃ³n de macro-envolvente en el monitor con clampeo estricto de `top_preset` para evitar desbalanceos por el daemon tÃ©rmico en frÃ­o, respetando el micro-tuneado de chips.
- [x] MÃ³dulos dedicados `app/governance/elevator_budget.py`, tests `test_elevator_budget.py` (21 tests PASS) y validaciÃ³n de regresiÃ³n global (**1288/1288 tests PASS**).
- [x] Servicio Windows `MinerAlerts` reiniciado y certificado en producciÃ³n.

### Iniciativa 30 â€” SupresiÃ³n de Ruido ElÃ©ctrico en Elevadores, Watchdog Anti-Autotune Stall y Gobernanza TÃ©rmica Solar (Spec 078 - PROP-013 - Completada & Certificada)
- EspecificaciÃ³n: [`specs/078-electrical-noise-and-autotune-protection/spec.md`](../../specs/078-electrical-noise-and-autotune-protection/spec.md) | Plan: [`specs/078-electrical-noise-and-autotune-protection/plan.md`](../../specs/078-electrical-noise-and-autotune-protection/plan.md) | Evidencia: [`specs/078-electrical-noise-and-autotune-protection/evidence.md`](../../specs/078-electrical-noise-and-autotune-protection/evidence.md) | Propuesta: [`docs/proposals/PROP-013-elevator-noise-autotune-stall-and-thermal-protection.md`](../proposals/PROP-013-elevator-noise-autotune-stall-and-thermal-protection.md)
- **Estado**: ImplementaciÃ³n, VerificaciÃ³n y CertificaciÃ³n Completadas (T001-T008). 1322/1322 tests PASS.
- [x] Watchdog Anti-Autotune Stall (`app/governance/autotune_watchdog.py`): detecta cuelgues en `auto-tuning` (> 600s con $< 20\text{ TH/s}$), rescata con `safe_set_miner_preset(auto_restart_mining=True)`, emite alerta a Telegram y fija cerrojo de preset de silicio.
- [x] Techo individual de capacidad de hardware (`max_hardware_preset: "2500W"` en Minero 25) suprimiendo permanentemente el 100% de los cuelgues tÃ©rmicos en 2700W.
- [x] Ventana de reposo extendida de 300s post-incidente (`incident_quiet_window_s = 300.0`, `record_group_incident`, `is_group_in_incident_quiet`) para disipar el ruido transitorio inductivo ($L \frac{di}{dt}$) en la bajada comÃºn compartida por los dos elevadores.
- [x] Envolvente TÃ©rmica Solar (Solar Thermal Envelope, 11:00 a 17:00 hs): techo preventivo fijado a 2500W con corte preventivo a $\ge 82.0^\circ\text{C}$, blindando a la flota contra el corte destructivo interno de VNish a 84Â°C (`decrease_temp: 84Â°C`).
- [x] Suite de pruebas dedicadas (`test_autotune_watchdog.py`, extensiones en `test_elevator_budget.py`, `test_preset_balancer.py`, `test_vnish_client.py`) y suite global: **1322/1322 tests PASS** (0 fallos, 0 regresiones).

### Iniciativa 31 â€” Agente AutÃ³nomo de Gobernanza de Planta (FGA) y Optimizador AsimÃ©trico de Potencia (Spec 079 - PROP-014 / PROP-015 - Completada & Certificada)
- EspecificaciÃ³n: [`specs/079-facility-governance-agent/spec.md`](../../specs/079-facility-governance-agent/spec.md) | Plan: [`specs/079-facility-governance-agent/plan.md`](../../specs/079-facility-governance-agent/plan.md) | Evidencia: [`specs/079-facility-governance-agent/evidence.md`](../../specs/079-facility-governance-agent/evidence.md) | Propuestas: [`docs/proposals/PROP-014-maximum-power-and-asymmetric-combination-roadmap.md`](../proposals/PROP-014-maximum-power-and-asymmetric-combination-roadmap.md) y [`docs/proposals/PROP-015-autonomous-facility-agent-and-interactive-supervisor.md`](../proposals/PROP-015-autonomous-facility-agent-and-interactive-supervisor.md)
- **Estado**: ImplementaciÃ³n, VerificaciÃ³n y CertificaciÃ³n en ProducciÃ³n Completadas (T001-T008). 1343/1343 tests PASS.
- [x] Arquitectura de Agente en 3 capas: Motor determinÃ­stico 24/7 (zero token cost), memoria persistente SQLite `facility_agent_knowledge` e interfaz de supervisiÃ³n interactiva en Telegram (`/agent`, `/strategy`, `/fwhy`).
- [x] Modelo fÃ­sico de resistencia tÃ©rmica de silicio ($R_{th} = (T_{chip} - T_{inlet}) / P$) y predicciÃ³n tÃ©rmica ($T_{pred} = T_{inlet} + R_{th} \cdot P$) para clasificaciÃ³n en cohortes (`COOL`, `STANDARD`, `HOT`) y bloqueo predictivo de sobrecalentamientos.
- [x] Optimizador asimÃ©trico inter-elevador: asignaciÃ³n de 2700W a mineros frÃ­os (Elevador 2: Miners 25 y 26) y 2500W a mineros cÃ¡lidos (Elevador 1: Miners 23 y 24), maximizando hashrate (~385 TH/s) con 100% de estabilidad tÃ©rmica y elÃ©ctrica.
- [x] Comandos Telegram `/agent` (dashboard ejecutivo), `/strategy` (selecciÃ³n de modos macro) y `/fwhy` (explicaciÃ³n causal de asignaciÃ³n por silicio).
- [x] Pisos fÃ­sicos de ventiladores por nivel de potencia (`resolve_power_fan_floor` en `fan_governor.py`) erradicando caÃ­das a 30% en frÃ­o a 2700W.
- [x] Suites de pruebas dedicadas (`tests/test_facility_agent.py`, `tests/test_agent_commands.py`) y suite global del proyecto: **1346/1346 tests PASS** (0 fallos, 0 regresiones).
- [x] Servicio Windows `MinerAlerts` reiniciado y certificado en producciÃ³n.
- [x] **Hito de EstabilizaciÃ³n de Flota (NeutralizaciÃ³n de Sobre-IntervenciÃ³n)**: Erradicado el lazo de oscilaciÃ³n tÃ©rmica y reinicios forzados en VNish mediante `auto_restart_mining=False` en orquestaciÃ³n rutinaria, resoluciÃ³n de potencia por consumo real medido de fuente en `_get_miner_wattage`, y Modo Pasivo estricto al desactivar presets vÃ­a gobernanza. Flota 100% operativa a 380 TH/s continuos.

### Iniciativa 32 â€” Watchdog de CorrupciÃ³n de ConfiguraciÃ³n de Firmware VNish y RecuperaciÃ³n Asistida (Spec 080 - PROP-016 - Completada & Certificada)
- EspecificaciÃ³n: [`specs/080-firmware-settings-corruption-watchdog/spec.md`](../../specs/080-firmware-settings-corruption-watchdog/spec.md) | Plan: [`specs/080-firmware-settings-corruption-watchdog/plan.md`](../../specs/080-firmware-settings-corruption-watchdog/plan.md) | Evidencia: [`specs/080-firmware-settings-corruption-watchdog/evidence.md`](../../specs/080-firmware-settings-corruption-watchdog/evidence.md)
- **Estado**: ImplementaciÃ³n, ResoluciÃ³n Operativa en M24 y CertificaciÃ³n Completadas (T1.1-T3.4). 1429/1429 tests PASS.
- [x] Motor de DetecciÃ³n de Salud de Firmware (`check_miner_settings_health` en `app/vnish/client.py`): detecta activamente bloqueos HTTP 500 por parseo/campos duplicados en Serde/JSON de `/config/cgminer.conf` y fallas de minero cÃ³digo 1002.
- [x] Flujo de Alerta Asistida y Botonera Interactiva en Telegram (`build_firmware_corruption_keyboard` en `app/telegram/fleet_cards.py`): botones directos para solicitud de reboot asistido con confirmaciÃ³n (`cc:act:rb_req:<id>`) y ajuste manual de potencia (`cc:miner:<id>:presets`).
- [x] Cooldown anti-spam de 900s, chequeo cada 300s en telemetrÃ­a de cadenas y persistencia de eventos operacionales `firmware_settings_corrupted` en `data/miner_alerts.db`.
- [x] RecuperaciÃ³n empÃ­rica en producciÃ³n de Minero 24 (S19JPRO-24): hardware reboot vÃ­a Toolkit regenerando `/config/cgminer.conf` desde NAND, e inyecciÃ³n exitosa de preset 2700W escalando a ~94 TH/s.
- [x] Suite de pruebas unitarias `tests/test_firmware_corruption_watchdog.py` (5 tests PASS) y regresiÃ³n global: **1429/1429 tests PASS, 75 subtests PASS**.
- [x] Servicio Windows `MinerAlerts` reiniciado y certificado en producciÃ³n.

### Iniciativa 33 â€” Watchdog de Reinicio de Minado Pendiente y ArmonizaciÃ³n TÃ©rmica (Spec 081 - PROP-017 - Completada & Certificada)
- EspecificaciÃ³n: [`specs/081-restart-required-watchdog/spec.md`](../../specs/081-restart-required-watchdog/spec.md) | Plan: [`specs/081-restart-required-watchdog/plan.md`](../../specs/081-restart-required-watchdog/plan.md) | Evidencia: [`specs/081-restart-required-watchdog/evidence.md`](../../specs/081-restart-required-watchdog/evidence.md)
- **Estado**: ImplementaciÃ³n, ResoluciÃ³n Operativa en M24 y CertificaciÃ³n Completadas (T1.1-T3.4). 1440/1440 tests PASS.
- [x] ExtracciÃ³n concurrente de bandera `restart_required` desde `/api/v1/status` en `get_overclock_settings` (`app/vnish/client.py`).
- [x] Persistencia y serializaciÃ³n de estado en `MinerState` (`vnish_restart_required`, `vnish_restart_detected_ts`, `last_preset_restart_ts`) en `app/core/state_manager.py` y `app/miner_monitor.py`.
- [x] FunciÃ³n pura de decisiÃ³n `evaluate_preset_restart_candidate(...)` con ventana soak de 300s, cooldown de 180s e interlocks tÃ©rmicos (<80Â°C).
- [x] ArmonizaciÃ³n Fan Governor (F-02): adaptaciÃ³n `gov_target_pwr = gov_curr_pwr` cuando `vnish_restart_required=True` y `gov_curr_pwr >= 500W`, suprimiendo la trampa de 100% PWM (`ACTION_RECOVERY_MAX_COOLING`).
- [x] Destrabe de potencia empÃ­rico en producciÃ³n de Minero 24 (S19JPRO-24): escalamiento en caliente a 2700W (2699W en cadenas, 518 MHz, 97.7+ TH/s) y normalizaciÃ³n tÃ©rmica inmediata. Flota global a 395 TH/s continuos.
- [x] Suite de pruebas unitarias `tests/test_restart_required_watchdog.py` (11 tests PASS) y regresiÃ³n global: **1440/1440 tests PASS, 75 subtests PASS** (0 fallos).
- [x] Servicio Windows `MinerAlerts` verificado y certificado.

---

## Governance

- All 81 specifications in the program (Specs 001 through 081) are tracked and maintained.
- **Baseline actual**: 1440/1440 tests PASS, 75 subtests PASS (0 failures, 0 regressions) â€” Spec 081 Certified 2026-10-01.
- Production action authority remains strictly centralized in the Windows monitor.
- External read-only surfaces (Grafana, static dashboard, backup CLI, analyze_chain_breaks CLI) operate decoupled from the monitor.
- **AuditorÃ­a de directivas 2026-10-01**: Ver [`docs/audit/DIRECTIVES_HARMONIZATION_AUDIT.md`](../audit/DIRECTIVES_HARMONIZATION_AUDIT.md) para el anÃ¡lisis completo de gobernanza, fricciones resueltas y pendientes.

---

## Horizonte V5.2 â€” Gobernanza Integrada y Deuda ArquitectÃ³nica (Specs 082â€“086)

> **Contexto estratÃ©gico**: La auditorÃ­a del 2026-10-01 confirmÃ³ que el sistema es seguro para la producciÃ³n actual pero estÃ¡ en un punto de inflexiÃ³n arquitectÃ³nico. La suma de specs incrementales genera fricciÃ³n estructural creciente. Las specs 082â€“086 atacan la deuda de integraciÃ³n antes de agregar nuevas features, estableciendo contratos de estado explÃ­citos que harÃ¡n predeciblemente segura cada spec futura.

### Iniciativa 34 â€” MinerGovernanceContext: Contrato de Estado Centralizado entre Subsistemas (Spec 082) [COMPLETE 2026-10-01 - 1466 tests PASS]

**Propuesta**: PROP-018 (pendiente de creaciÃ³n formal)
**Prioridad**: P0 â€” ArquitectÃ³nica / Deuda TÃ©cnica
**Riesgo**: ALTO (afecta el corazÃ³n del sistema)
**Modelo recomendado**: Claude Sonnet 4.6 (Thinking)
**Dependencia**: Spec 081 cerrada âœ…

**Problema que resuelve**:
Los subsistemas de gobernanza (Fan Governor, Elevator Budget, Thermal Guard, FGA, Auto-Restart, VNish Watchdog) toman decisiones con visibilidad parcial del estado global. La fricciÃ³n F-01 (nudo M24) fue el ejemplo mÃ¡s reciente: 3 subsistemas correctos individualmente crearon un deadlock colectivo. Sin un contrato de estado compartido, cada spec futura tiene riesgo de crear nuevas fricciones.

**Alcance tÃ©cnico**:
- Definir `MinerGovernanceContext` como dataclass compartida que agrega los campos de estado relevantes para la gobernanza (potencia real ejecutada, `restart_required`, `thermal_pause_active`, preset configurado, uptime, cohort FGA, grupo elÃ©ctrico).
- Hacer que Fan Governor, Elevator Budget, Thermal Guard y FGA lean de `MinerGovernanceContext` en vez de recibir parÃ¡metros dispersos.
- Establecer un contrato formal de quÃ© campos puede leer cada subsistema y cuÃ¡les puede mutar.
- Agregar tests de contrato (`tests/test_governance_context_contracts.py`) que validen que ningÃºn subsistema accede a campos fuera de su dominio.

**Criterio de Ã©xito**: Cada spec futura de gobernanza modifica `MinerGovernanceContext` en vez de agregar parÃ¡metros ad-hoc a 5 funciones distintas.

---

### Iniciativa 35 — FGA como Actuador Real: Ciclo de Decisión–Ejecución Completo (Spec 083) [COMPLETED]

**Propuesta**: PROP-019
**Estado**: COMPLETADO Y CERTIFICADO (2026-10-01) — 1477 tests PASS, 75 subtests PASS.
**Prioridad**: P1 — Funcional
**Riesgo**: MEDIO
**Modelo**: Gemini 3.8 Flash High
**Dependencia**: Spec 082 ✅

**Problema que resuelve**:
El FGA anteriormente era un motor de recomendación sin actuador: calculaba asignaciones óptimas pero no las ejecutaba. El ciclo FGA → Elevator Budget → VNish quedó completamente cerrado, trazable en SQLite (`facility_agent_actions`) e integrable en Telegram (`/agent run` y `/agent history`).

**Alcance técnico completado**:
- Conectar la salida de `evaluate_asymmetric_allocation()` con el orquestador de Elevator Budget (`fga_actuator.py`).
- El FGA emite `candidate_step` → Elevator Budget evalúa los Gates 0-6 → Si OK, ejecuta `safe_set_miner_preset`.
- Registrar cada acción FGA en SQLite (`facility_agent_actions`) para trazabilidad completa.
- Telemetría FGA mejorada: consume `current_power_w` real del `MinerGovernanceContext` para $R_{th}$ cuando hay `restart_required` activo (Fricción F-04 resuelta).
- Comandos Telegram `/agent run` para forzar un ciclo de optimización bajo demanda y `/agent history` para auditar acciones.

**Criterio de éxito alcanzado**: El operador puede ver en `/agent history` y `/agent run` exactamente qué hizo el FGA y por qué compuerta pasó.

---

### Iniciativa 36 — Observabilidad de Directivas en Tiempo Real: Dashboard de Gobernanza (Spec 084) — COMPLETADA ✅

**Propuesta**: PROP-020
**Estado**: COMPLETADA (2026-10-01) — 6 tests nuevos, 1483 tests totales PASS
**Prioridad**: P2 — Observabilidad
**Riesgo**: BAJO
**Modelo ejecutado**: Gemini 3.8 Flash High
**Dependencia**: Spec 082

**Problema que resuelve**:
Actualmente no hay forma de ver en tiempo real quÃ© directiva estÃ¡ activa, cuÃ¡l estÃ¡ bloqueando quÃ©, y por quÃ© un minero no estÃ¡ en el preset esperado. El diagnÃ³stico de situaciones como el nudo M24 requiriÃ³ lectura manual de logs. Un dashboard de gobernanza harÃ­a esto instantÃ¡neo.

**Alcance tÃ©cnico**:
- Nuevo comando Telegram `/gov_status` (o `/directivas`): muestra por minero el estado de cada directiva activa (Fan Governor action, Elevator Budget last gate, Solar Envelope status, FGA cohort, `restart_required`).
- Persistencia de `governance_snapshots` en SQLite: un registro por ciclo por minero con la decisiÃ³n de cada subsistema (para auditorÃ­a histÃ³rica).
- Alerta proactiva cuando un minero lleva >300s en `ACTION_RECOVERY_MAX_COOLING` sin que la potencia se acerque al target (detecta deadlocks futuros automÃ¡ticamente).
- Mobile-First: formato â‰¤32 columnas estricto.

**Criterio de Ã©xito**: El operador puede diagnosticar en <10 segundos por quÃ© un minero no estÃ¡ en el preset esperado, desde Telegram, sin leer logs.

---

### Iniciativa 37 — Descomposición del Monolito: Extracción del Orquestador de Gobernanza (Spec 085) — COMPLETADA ✅

**Propuesta**: PROP-021
**Estado**: COMPLETADA (2026-10-02) — 15 tests nuevos, 1498 tests totales PASS. `miner_monitor.py` reducido en 572 líneas (9.406 → 8.834 L). Fases 1 y 2 (Fan Governor, estado mutable thread-safe `_orchestrator_state.py` y desacoplamiento de handlers de Telegram) certificadas en producción.
**Fase 3 Planificada**: La extracción de `execute_balancer_cycle` y `check_autotune_watchdog` queda planificada como **Spec 087: Monolith Decoupling Phase 3 (Balancer & Watchdog)** para continuar la reducción hacia $\le 6.000$ líneas una vez concluida la ventana de observación actual.
**Prioridad**: P1 — Arquitectónica / Deuda Técnica
**Riesgo**: ALTO (gestionado mediante módulo compartido y extracción desacoplada)
**Modelo ejecutado**: Claude Sonnet 4.6 (Thinking) & Gemini 3.8 Flash High
**Dependencia**: Spec 082, Spec 083

**Problema que resuelve**:
`miner_monitor.py` concentraba la lógica de adquisición, estados, gobernanza, Telegram y coordinación. La lógica de Fan Governor y sincronización de overclock ya fue extraída a `app/governance/governor_cycle.py`, y el acceso global centralizado mediante accessors con locks.

**Criterio de éxito alcanzado**: Fan Governor completamente modularizado fuera del monolito, cero regresiones y 15 tests dedicados PASS.

---

### Iniciativa 38 — Autopsia Autónoma de Incidentes y Supervisor Conversacional (Spec 086 / PROP-016) — COMPLETADA ✅

**Propuesta**: [`docs/archive/proposals/PROP-016-autonomous-incident-autopsy-and-conversational-qa.md`](../archive/proposals/PROP-016-autonomous-incident-autopsy-and-conversational-qa.md)
**Estado**: COMPLETADA Y CERTIFICADA (2026-10-02) — 13 tests PASS, 1511 tests totales PASS.
**Prioridad**: P2 — Observabilidad / Autonomía
**Riesgo**: MEDIO
**Modelo ejecutado**: Gemini 3.8 Flash High
**Dependencia**: Spec 084 (governance snapshots como fuente de datos)

**Alcance técnico completado**:
- `IncidentAutopsyEngine`: worker asíncrono no bloqueante ($\le 2.5$s) clasificando en 7 categorías con clasificación determinística regex.
- Tarjetas ejecutivas Mobile-First $\le 32$ columnas (`build_autopsy_card`, `build_fleet_autopsy_summary_card`).
- Persistencia en SQLite (`incident_assessments`).
- Comando Telegram `/autopsia [minero]` (aliases `/causa_raiz`, `/autopsy`, `/investigar`).
- Supervisor Q&A conversacional offline en lenguaje natural (<50ms, zero tokens).
- Callback asíncrono en `miner_monitor.py` despachando vía `send_telegram`.

---

### Iniciativa 39 — Desacoplamiento de Callbacks de Telegram del Monolito (Spec 087) — COMPLETADA ✅

**Documento**: `specs/087-telegram-callbacks-decoupling/spec.md`
**Estado**: COMPLETADA Y CERTIFICADA (2026-10-07) — 1522 tests PASS, 75 subtests PASS.
**Prioridad**: P1 — Deuda Técnica / Modularización
**Riesgo**: BAJO
**Modelo ejecutado**: Gemini 3.8 Flash High
**Dependencia**: Programa Maestro de Modularización (`docs/speckit/MONOLITH_DECOUPLING_MASTER_PLAN.md`)

**Alcance técnico completado**:
- Migración de `_handle_command_center_callback` (~540 LOC) hacia `app/telegram/command_center.py`.
- Migración de `_handle_help_callback` (~45 LOC) hacia `app/telegram/help_center.py`.
- Migración de `_handle_diagnostic_callback` (~240 LOC) y `_handle_callback_query` (~680 LOC) hacia `app/telegram/callbacks.py`.
- Desacoplamiento de `app/telegram/router.py` para despacho directo en `app.telegram.*`.
- Shims de re-export en `app/miner_monitor.py` preservando 100% de compatibilidad con tests.
- Reducción neta de -1.508 líneas en `app/miner_monitor.py` (de 9.160 a 7.652 LOC).

---

### Iniciativa 40 — Desacoplamiento de Ciclos de Gobernanza (Spec 088) — COMPLETADA ✅

**Documento**: `specs/088-governance-cycles-decoupling/spec.md`
**Estado**: COMPLETADA Y CERTIFICADA (2026-10-07) — 1522 tests PASS, 75 subtests PASS.
**Prioridad**: P1 — Deuda Técnica / Modularización
**Riesgo**: BAJO
**Modelo ejecutado**: Gemini 3.8 Flash High
**Dependencia**: Programa Maestro de Modularización (`docs/speckit/MONOLITH_DECOUPLING_MASTER_PLAN.md`)

**Alcance técnico completado**:
- Creación de `app/governance/balancer_cycle.py` y migración de `execute_balancer_cycle` (~253 LOC).
- Extracción de `check_autotune_watchdog` y `execute_autotune_watchdog_cycle` (~140 LOC) en `app/governance/autotune_watchdog.py`.
---

### Iniciativa 41 — Desacoplamiento de Telemetría de Cadenas y Sockets ASIC (Spec 089) — COMPLETADA ✅

**Documento**: `specs/089-hardware-telemetry-decoupling/spec.md`
**Estado**: COMPLETADA Y CERTIFICADA (2026-10-07) — 1522 tests PASS, 75 subtests PASS.
**Prioridad**: P1 — Deuda Técnica / Modularización
**Riesgo**: BAJO
**Modelo ejecutado**: Gemini 3.8 Flash High
**Dependencia**: Programa Maestro de Modularización (`docs/speckit/MONOLITH_DECOUPLING_MASTER_PLAN.md`)

**Alcance técnico completado**:
- Creación de `app/hardware/chain_collector.py` y migración de `_async_collect_chain_telemetry` y `_async_evaluate_predictive_chain_break` (~350 LOC).
- Extracción de formateadores de texto diagnóstico (`build_stability_health_text`, `build_mining_quality_text`, `build_firmware_events_text`, `build_miner_diagnosis_text`) y helpers de resolución hacia `app/telegram/fleet_cards.py` (~320 LOC).
- Shims de re-export en `app/miner_monitor.py` preservando 100% de compatibilidad con tests y herramientas externas.
---

### Iniciativa 42 — Modernización de Contratos de Test Invariantes (Spec 090) — COMPLETADA ✅

**Documento**: `specs/090-test-invariants-modernization/spec.md`
**Estado**: COMPLETADA Y CERTIFICADA (2026-10-07) — 1525 tests PASS, 75 subtests PASS.
**Prioridad**: P1 — Desbloqueo Arquitectónico
**Riesgo**: BAJO (100% en tests)
**Modelo ejecutado**: Gemini 3.8 Flash High
**Dependencia**: Programa Maestro de Modularización (`docs/speckit/MONOLITH_DECOUPLING_MASTER_PLAN.md`)

**Alcance técnico completado**:
- Desacoplamiento de `inspect.getsource(main)` en `tests/test_startup_grace_period.py:222`.
- Verificación funcional black-box determinista con `SupervisoryBehavioralHarness` para la jerarquía de 5 precedencias de auto-reboot.
- Desbloqueo arquitectónico 100% de `main()` para el cierre definitivo en Spec 091.

---

### Iniciativa 43 — Pipeline Declarativo de Hooks y Cierre V6.0 (Spec 091) — COMPLETADA ✅

**Documento**: `specs/091-core-daemon-hookification/spec.md`<br/>
**Estado**: COMPLETADA Y CERTIFICADA (2026-10-07) — 1525 tests PASS, 75 subtests PASS — **RELEASE MAYOR V6.0**.<br/>
**Prioridad**: P0 — Cierre Arquitectónico del Monolito<br/>
**Riesgo**: MEDIO<br/>
**Modelo ejecutado**: Gemini 3.8 Flash High<br/>
**Dependencia**: Programa Maestro de Modularización (`docs/speckit/MONOLITH_DECOUPLING_MASTER_PLAN.md`)<br/>

**Alcance técnico completado**:
- Pipeline declarativo de 7 etapas (`PRE_TICK`, `ACQUISITION`, `DETECTION`, `GOVERNANCE`, `ACTUATOR`, `PERSISTENCE`, `POST_TICK`) en `app/core/pipeline.py`.
- Encapsulación de inicialización en `CoreSupervisoryEngine.initialize()` y ciclo en `engine.run_forever()`.
- Disolución final de `app/miner_monitor.py` de 6.646 a **324 LOC** ($\le 450$ LOC objetivo alcanzado; -6.322 LOC netas, -8.752 LOC acumuladas).
- Shims de re-exportación tipados para el 100% de contratos de prueba y símbolos públicos.
- Certificación preflight 8/8 gates PASS y servicio Windows NSSM `MinerAlerts` en producción continua.

---

## Backlog de Observación Continua (Post-Spec 081 / V5.2)

Estas tareas no requieren specs nuevas pero se monitorean activamente en producción:

| Ítem | Métrica de Seguimiento / Estado Real | Trigger de Acción |
|------|--------------------------------------|-------------------|
| Elevador 1 a 5000W (M23+M24 a 2500W) | Operación nominal a ~4997W total (~2499W por equipo). Margen de seguridad térmico y eléctrico de 400W respecto al límite de 5400W | $\ge 1$ evento simultáneo $\to$ activar `PROFILE_C1_ASYMMETRIC` |
| Elevador 2 a 5400W (M25+M26 a 2700W) | Operación nominal a ~5397W total (~2698W por equipo). 100% estable | Eventos `unexpected_restart` o caídas de fase |
| Estado de Deadlocks y Fans | **0 de 4 mineros en deadlock** (`is_deadlocked=0`). Modulación activa en lazo cerrado (M23 a 96% PWM en `HOLD_DWELL`, chips 80-81°C) | Activación de `RECOVERY_MAX_COOLING` $>300$s |
| Temperaturas y Silicio | M23: 80°C, M24: 81°C, M25: 82°C, M26: 81°C. 126 chips x 3 placas en toda la flota, 0 HW errors | Temp máx sostenida $>84$°C por $>10$ min |
| Suite de tests | **1530 passed, 75 subtests passed** (~37s de latencia) | $>90$s $\to$ split o paralelización de suite |
| Gate de Gobernanza en ActuatorHook | `InterventionGovernance.master_enabled=False` no es evaluado por el gate de auto-reboot en `ActuatorHook` (bloquea solo el gate de qa_mode). | Evaluación de políticas de parada total $\to$ integrar `master_enabled` en `evaluate_auto_reboot_policy` |

---
