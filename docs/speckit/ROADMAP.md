# Miner Alerts Speckit Roadmap

**Last reviewed**: 2026-09-15
**Specification program**: `docs/speckit/SPEC_PROGRAM.md`
**Delivery calendar**: `docs/speckit/DELIVERY_PLAN.md`

## Resumen Ejecutivo y Progreso del Programa

- **Progreso Acumulado del Proyecto (desde Spec 001)**: `100%` (67 de 67 especificaciones del programa completadas y verificadas con evidencia en producción y suite de tests: 1072 tests PASS — Release V5.1.0 Gateway Heartbeat & Network Storm Suppression Certificada).
- **Horizonte V5.1 en Curso**: Specs 068, 069 y 070 completamente auditadas arquitectónicamente y listas para ejecución segura.


---

### 🏆 Avances Principales Desde el Inicio (Spec 001 a Spec 030)

1. **Specs 001 a 019 — Arquitectura Base y Telemetría**:
   - [x] Polling autoritativo API 4028 y persistencia SQLite (esquema v1-v6).
   - [x] Integración con Hashcore Toolkit CLI para comandos seguros de reinicio.
   - [x] Captura programada de logs de firmware Vnish.
   - [x] Diagnósticos de calidad de minado y perfil de estabilidad.

2. **Spec 020 — Estabilización de Estados y Autoreinicio**:
   - [x] Máquina de 5 estados estables (`OK`, `LOW`, `OFFLINE`, `HASHBOARD`).
   - [x] Interlocks térmicos, de flota y de transición de firmware.
   - [x] Eliminación de falsas alarmas y cero reinicios espurios (`e502ab9`).

3. **Spec 030 — Calidad de Mensajería Telegram**:
   - [x] Cola de entrega por prioridad y división segura de mensajes extensos.
   - [x] Protección anti-rate limit y reintento con backoff.
   - [x] Validación en producción y commit `2afd65e`.

4. **Spec 021 — Watchdog de Vida y Recuperación SCM**:
   - [x] Supervisión fuera de proceso con heartbeat atómico versionado.
   - [x] Detección determinista de bloqueos y recuperación SCM aprobada.
   - [x] Gates de observación continua D+1 (86.7k s) y D+3 (278.4k s / 77.3h) superados con éxito.

5. **Spec 022 — Adquisición Adaptativa y UX Telegram Compacto**:
   - [x] Ejecutor de adquisición paralelo desacoplado con 2 workers.
   - [x] Formato UX compacto y normalización de calidades de telemetría.
   - [x] Producción activa bajo PID 38816 con gates D+1 (42.7h) y D+3 (73.45h / 264.4k s) superados.

6. **Spec 023 — Fusión de Evidencia de Incidentes**:
   - [x] Módulo puro desacoplado `app/evidence_fusion.py` (T001-T018).
   - [x] Rutas de lectura `/diagnose` activadas con tablas `incident_assessments` e `assessment_fact_refs`.
   - [x] Validación determinista SC-001 a SC-004 y rendimiento verificado (344 tests PASS).

7. **Spec 024 — Descubrimiento de Telemetría Eléctrica (Bloqueado por Hardware)**:
   - [x] Relevamiento técnico exhaustivo de telemetría eléctrica (T001-T004).
   - [x] Prohibición formal de inferencia de AC desde voltajes DC de hashboards.
   - [x] Cierre formal con disposición `blocked_external` por ausencia de PDU/UPS de red.

8. **Spec 026 — Inventario de Capacidades Hashcore**:
   - [x] Herramienta desacoplada `tools/hashcore_inventory.py` (T001-T018).
   - [x] Metadatos de instalación PE verificados (`1.6.0+167`, wrapper `toolkit_cli.bat`).
   - [x] Clasificación de operaciones y allowlist vacía con resultado seguro `blocked` sin alterar monitor.

9. **Spec 028 — Backups, Retención y Recuperación por Etapas**:
   - [x] Herramienta desacoplada `tools/event_store_backup.py` y script `tools/install_backup_task.ps1`.
   - [x] Respaldo online por lotes de 256 páginas y retención determinista UTC 14/8/12.
   - [x] Simulacro de restore en staging superado sobre BD real de 20.4 MB en 6.2s.

10. **Spec 025 — Métricas de Prometheus y Paneles Grafana**:
    - [x] Instantáneas de métricas en `app/metrics_snapshot.py` y exportador `tools/metrics_exporter.py`.
    - [x] Stack Docker Compose aislado con 3 tableros Grafana (`fleet_overview`, `monitor_liveness`, etc.).
    - [x] Hook atómico en el monitor con cero impacto en el ciclo de supervisión.

11. **Spec 027 — Decisión de Interfaz de Operación**:
    - [x] Scorecard de flujos de operador W01-W06 ejecutado (30 corridas verificadas).
    - [x] Validación de cobertura P1 completa con Telegram, Grafana y dashboard HTML estático.
    - [x] Decisión formal `no_build` adoptada, preservando la superficie mínima y cero impacto en recursos.

12. **Spec 029 — Estabilización Final y Candidato de Release V2**:
    - [x] Congelamiento determinista de payload SHA-256 (`58d451f1...`, 43 archivos).
    - [x] Validación de matriz completa R001-R025 (416 tests PASS).
    - [x] Período de observación continua de 267.2 horas en producción y aprobación formal del Release Candidate V2 (`v2.0.0`).

---

### 🚀 Programa V3: Maximización de Telegram & Capacidades Avanzadas

1. **Spec 031 — Botones Interactivos y Callbacks Telegram (`031-telegram-interactive-callbacks`)**:
   - [x] Inline Keyboards en alertas de episodios para diagnósticos y gráficos en 1 toque.
   - [x] Flujo interactivo seguro de reinicio en 2 toques (`[ 🔄 Reiniciar ]` -> `[ ✅ Confirmar ]` / `[ ❌ Cancelar ]`) con token de 60s.
   - [x] 14 tests PASS en `tests/test_telegram_callbacks.py`, 430 tests globales PASS, cero impacto en estabilidad.

2. **Spec 032 — Gráficos Nativos Visuales en Telegram (`032-telegram-visual-charts`)**:
   - [x] Envío directo de imágenes PNG con la curva de hashrate, temperaturas y RPM al chat vía `/chart <id>` y `/chart fleet`.
   - [x] Renderizado en RAM en 219ms sobre 23.2 MB sin archivos temporales en disco.
   - [x] 6 tests PASS en `tests/test_telegram_charts.py`.

3. **Spec 033 — Mantenimiento y Silenciamiento Temporal (`033-miner-maintenance-snooze`)**:
   - [x] Comandos `/snooze <miner|all> [minutos]` y botón táctil `[ 🔕 Silenciar 1h ]`.
   - [x] Supresión temporal de alertas, recordatorios y bloqueo de autorreinicios durante intervenciones físicas.
   - [x] 12 tests PASS en `tests/test_telegram_snooze.py` y persistencia en `state.json`.

4. **Spec 034 — Reporte Ejecutivo Diario (`034-daily-executive-digest`)**:
   - [x] Resumen programado diario matutino (08:00 AM) y on-demand `/digest`.
   - [x] Métricas de flota agregadas: uptime, TH/s promedio, J/TH, shares %, anomalías e integridad de backups SQLite.
   - [x] 10 tests PASS en `tests/test_daily_digest.py` con rendimiento real medido de 27.2ms.

5. **Spec 035 — Inteligencia Térmica y de Ventiladores (`035-cooling-fan-health`)**:
   - [x] Supervisión analítica de ventiladores (`/fans [miner]`).
   - [x] Cálculo de margen térmico hacia el umbral de corte (85.0°C).
   - [x] Alertas preventivas de saturación térmica (`COOLING_WARNING`) para anticipar limpieza de filtros.
   - [x] 14 tests PASS en `tests/test_fan_health.py` y monitoreo en vivo continuo.

6. **Spec 036 — Eficiencia Energética Continua (`036-efficiency-energy-tracking`)**:
   - [x] Seguimiento en tiempo real del ratio Joules por Terahash (J/TH) y potencia en Watts/kW vía `/efficiency`.
   - [x] Alertas tempranas de degradación energética (`EFFICIENCY_WARNING`).
   - [x] 12 tests PASS en `tests/test_energy_efficiency.py`.

7. **Spec 037 — Seguimiento de Presets y Autotuning Dinámico (`037-vnish-presets-autotuning`)**:
   - [x] Monitoreo de frecuencias (MHz), tensión de cadena (V), potencia y autotune Vnish vía `/presets`.
   - [x] Alerta preventiva `PROFILE_CHANGE_ALERT` ante reducciones de frecuencia ($\ge 25\text{ MHz}$).
   - [x] 11 tests PASS en `tests/test_vnish_presets.py`.

8. **Spec 038 — Auditoría de Concurrencia y Estabilización Release V3 (`038-v3-release-stabilization`)**:
   - [x] Auditoría profunda de concurrencia multihilo, cerrojos `state_lock` y sockets SQLite con `?mode=ro`.
   - [x] Prevención de condiciones de carrera en `CallbackTokenRegistry` y 19 tests de estrés (`tests/test_v3_concurrency.py`).
   - [x] Certificación formal del Release V3.0.0 (514 tests globales PASS).

---

### ⚡ Programa V3.1: Control y Gobernanza de Hardware (Activación Plena en Producción)

9. **Spec 039 — Gobernador Térmico y Acústico de Ventiladores Vnish (`039-vnish-fan-governor`)**:
   - [x] Detección de modo en `/fans` (`manual`/`auto`) y cliente REST seguro (`app/vnish/client.py`).
   - [x] Modulación determinista de lazo cerrado hacia target de 82.0°C (banda muerta [81.0, 82.5]°C).
   - [x] Despacho concurrente desacoplado con `ThreadPoolExecutor` (timeout 2.5s por minero, 5.0s flota).
   - [x] Protección de emergencia `EMERGENCY_SPIKE` a 83.5°C con forzado inmediato a 100% PWM.
   - [x] Fail-safe ante caídas de comunicación o excepciones consecutivas.
   - [x] Control interactivo en caliente vía Telegram (`/gov on`, `/gov off`, `/gov set`).
   - [x] 12 tests de concurrencia y estrés (`tests/test_fan_governor_concurrency.py`).

10. **Spec 040 — Calibración Dinámica de Presets y Elevadores de Tensión (`040-dynamic-voltage-presets`)**:
    - [x] Algoritmo de optimización de potencia y presets (1600W a 2800W) por grupo eléctrico.
    - [x] Desescalado térmico progresivo (`ACTION_STEP_DOWN_THERMAL`) ante saturación térmica.
    - [x] Protección individual y grupal de elevadores ante caídas de tensión y reinicios en ventana.
    - [x] Subida conservadora tras 72h continuas de soak con margen térmico $\ge 4.0^\circ\text{C}$.
    - [x] Comandos interactivos en caliente `/balancer on`, `/balancer off`, `/balancer setmax`, `/balancer run`.
    - [x] 23 tests unitarios e integración (`tests/test_preset_balancer.py`, `tests/test_preset_balancer_integration.py`).

---

### 🧹 Programa V3.2: Reorganización Modular y Purga Limpia de Shims

11. **Spec 041 — Arquitectura Modular y Reorganización de Dominios en `app/` (`041-app-modular-architecture`)**:
    - [x] Reorganización de 22 archivos planos en 4 subpaquetes canónicos: `app/core/`, `app/vnish/`, `app/governance/`, `app/telegram/`.
    - [x] Capa inicial de shims de retrocompatibilidad con module aliasing (`sys.modules[__name__] = _impl`).
    - [x] 587 tests globales PASS manteniendo retrocompatibilidad total.

12. **Spec 042 — Purga Limpia de Shims y Modernización de Tests en `app/` (`042-purge-shims-test-modernization`)**:
    - [x] Modernización canónica directa de todas las importaciones en la suite de pruebas `tests/`.
    - [x] Purga definitiva mediante `git rm` de los 22 archivos shims de la raíz de `app/`.
    - [x] Validación de estructura mínima en `app/` (`miner_monitor.py` y `__init__.py`).
    - [x] 587/587 tests globales PASS y auditoría de release verificada con 60 payload files limpios.

---

### 🎮 Programa V3.3: Centro de Comando Táctil y Modo Silencio

13. **Spec 043 — Telegram Interactive Command Center & Rich UI (`043-telegram-interactive-command-center`)**:
    - [x] Módulo puro desacoplado `app/telegram/command_center.py` con layouts y builders de InlineKeyboardMarkup.
    - [x] Dashboard táctil `/menu` (alias `/start`, `/panel`) con semáforos, potencia de flota y barras Unicode `[██████░░]`.
    - [x] Submenús in-place vía `editMessageText`: Métricas, Reinicios guiados, Presets y Alertas.
    - [x] Confirmación de reinicio en dos toques con token criptográfico efímero de 60 segundos.
    - [x] Botones de acción rápida de 4 funciones embebidos en alertas de episodios (`diag`, `chart`, `rb_req`, `snz`).
    - [x] Guardián de seguridad RBAC (`from_id == chat_id`) y ACK inmediato `answerCallbackQuery` (< 500ms).
    - [x] 17 tests unitarios en `tests/test_command_center.py` y 602 tests globales PASS.

14. **Spec 044 — Modo Silencio Inteligente con Temporizador Persistente y Thermal Guard (`044-silent-mode-thermal-guard`)**:
    - [x] Condición C1: Despacho asíncrono no bloqueante en el worker de Telegram polling.
    - [x] Condición C2: Campos dedicados `silent_mode_*` en `MinerState` y reconciliación en arranque `first_tick`.
    - [x] Condición C3: Techos acústicos dinámicos (`max_fan_duty_percent`) inyectados en Fan Governor (40%-70% PWM).
    - [x] Condición C4: Desactivación atómica en `state.json` bajo pico térmico (83.5°C) o falla, ventiladores forzados al 100% y alerta Telegram.
    - [x] Temporizadores de cuenta regresiva configurables (30m, 1h, 2h, 4h, 6h, indef) con reversión automática a régimen normal.
    - [x] Selector táctil integrado al Command Center (`cc:nav:silent`, `cc:act:silent:*`) y comando `/silent`.
    - [x] 17 tests unitarios en `tests/test_silent_mode.py`, 621/621 tests globales PASS y activo en producción bajo PID 58344.

---

### 🎯 Resumen de Valor Aportado por Especificación

1. **Spec 023 — Fusión de Evidencia de Incidentes**:
   - [x] *Objetivo*: Correlacionar datos de telemetría SQLite, decisiones de reinicio y logs Vnish.
   - [x] *Valor y Beneficio*: Permite identificar la causa raíz exacta de caídas (red, energía o firmware) eliminando falsos diagnósticos.

2. **Spec 024 — Descubrimiento de Telemetría Eléctrica**:
   - [x] *Objetivo*: Integrar telemetría de PDUs / UPS inteligentes o monitoreo de energía AC real.
   - [x] *Valor y Beneficio*: Evita confundir caídas de tensión de placas con cortes de energía del Data Center.

3. **Spec 025 — Observabilidad Local (Prometheus y Grafana)**:
   - [x] *Objetivo*: Exportar métricas locales Prometheus y proveer tableros Grafana de solo lectura.
   - [x] *Valor y Beneficio*: Otorga visibilidad gráfica en tiempo real del rendimiento de la flota sin sobrecargar el monitor.

4. **Spec 026 — Inventario de Capacidades Hashcore**:
   - [x] *Objetivo*: Mapear de forma conservadora los comandos del Toolkit Hashcore sin ampliar permisos de escritura.
   - [x] *Valor y Beneficio*: Permite auditar el alcance operativo garantizando que no se ejecuten comandos destructivos.

5. **Spec 028 — Respaldo y Restauración de Base de Datos**:
   - [x] *Objetivo*: Programar respaldos en caliente de SQLite y ensayar la restauración en ambiente staging.
   - [x] *Valor y Beneficio*: Asegura la continuidad operativa y la preservación del historial de eventos ante fallos de disco.

6. **Spec 027 — Evaluación de Interfaz de Operación**:
   - [x] *Objetivo*: Determinar si Grafana/HTML estático bastan o si requiere una API local mínima en FastAPI.
   - [x] *Valor y Beneficio*: Minimiza el consumo de recursos e hiper-superficie de ataque (decisión `no_build`).

7. **Spec 029 — Estabilización Final y Candidato de Release V2**:
   - [x] *Objetivo*: Pruebas de regresión cruzadas, auditoría documental y período de observación de 168 horas.
   - [x] *Valor y Beneficio*: Garantiza la entrega de un producto robusto, libre de deudas técnicas y verificado (`v2.0.0`).

8. **Spec 039 — Gobernador Térmico y Acústico de Ventiladores Vnish**:
   - [x] *Objetivo*: Lazo cerrado de control térmico a 82°C con fail-safe al 100% PWM.
   - [x] *Valor y Beneficio*: Prolonga la vida útil de los ventiladores, reduce el ruido y previene disparos térmicos.

9. **Spec 040 — Calibración Dinámica de Presets y Elevadores de Tensión**:
   - [x] *Objetivo*: Balanceo de potencia inteligente por grupo eléctrico y desescalado por inestabilidad.
   - [x] *Valor y Beneficio*: Evita reinicios en cascada por caídas de tensión y maximiza la producción estable de TH/s.

10. **Specs 041-042 — Arquitectura Modular y Purga Limpia de Shims**:
    - [x] *Objetivo*: Reorganización de `app/` en subpaquetes de dominio y purga de 22 archivos planos.
    - [x] *Valor y Beneficio*: Base de código limpia, modular, de alta mantenibilidad y 100% canónica.

11. **Spec 043 — Telegram Interactive Command Center & Rich UI**:
    - [x] *Objetivo*: Centro de mando ejecutivo con menús interactivos táctiles y botones de acción rápida.
    - [x] *Valor y Beneficio*: Gestión y toma de decisiones remota en 1-2 toques táctiles sin necesidad de tipear comandos.

12. **Spec 044 — Modo Silencio / Visitas Inteligente con Thermal Guard**:
    - [x] *Objetivo*: Límite acústico temporal a 40%-70% PWM con temporizadores de cuenta regresiva y protección a 83.5°C.
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
| 18 | Spec 039 vnish-fan-governor | COMPLETE (`active`) | P1 | MEDIUM | Closed 2026-09-08 (calibrado 82.0°C) |
| 19 | Spec 040 dynamic-voltage-presets | COMPLETE (`active`) | P1 | HIGH | Closed 2026-09-08 (autodescubrimiento & elevadores) |
| 20 | Spec 041 modular-architecture | COMPLETE | P2 | MEDIUM | Closed 2026-09-08 (app/ reorganizado) |
| 21 | Spec 042 purge-shims-test-modernization | COMPLETE | P2 | LOW | Closed 2026-09-08 (22 shims purgados) |
| 22 | Spec 043 telegram-command-center | COMPLETE | P1 | LOW | Closed 2026-09-08 (Command Center táctil /menu) |
| 23 | Spec 044 silent-mode-thermal-guard | COMPLETE (`active`) | P0 | HIGH | Closed 2026-09-08 (PID 58344 activo en producción) |

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

- [x] Spec 031: Botones interactivos Telegram inline (1-tap) y flujo de confirmación en 2 pasos para reinicios seguros (`app/telegram/callbacks.py`).
- [x] Spec 032: Gráficos nativos de telemetría en formato PNG generados en RAM sin almacenamiento en disco (`app/telegram/charts.py`).
- [x] Spec 033: Modo mantenimiento y silenciamiento temporal con bloqueo de autoreinicios (`app/telegram/snooze.py`).
- [x] Spec 034: Reporte ejecutivo diario programado (08:00 AM) y on-demand (`app/telegram/digest.py`).
- [x] Spec 035: Inteligencia térmica, cálculo de headroom a 85°C y alertas predictivas de saturación de ventiladores (`app/governance/fan_health.py`).
- [x] Spec 036: Seguimiento en tiempo real de eficiencia energética ($J/\text{TH}$) y alertas de degradación (`app/governance/energy_efficiency.py`).
- [x] Spec 037: Auditoría dinámica de presets Vnish y alertas de downclocking ($\ge 25\text{ MHz}$) (`app/vnish/presets.py`).
- [x] Spec 038: Endurecimiento de concurrencia multihilo, mitigación de condiciones de carrera, 19 tests de estrés (`tests/test_v3_concurrency.py`), 514 tests globales PASS y certificación del Release V3.0.0.

**Invariant**: cero impacto sobre la máquina de estados, aislamiento estricto de hilos lectores SQLite con `?mode=ro`.

---

### R11 - Fan Governor & Dynamic Presets Governance (COMPLETE / ACTIVE, P0)

**Specs**: `specs/039-vnish-fan-governor` y `specs/040-dynamic-voltage-presets`

- [x] Modulación de lazo cerrado térmico en `app/governance/fan_governor.py` hacia temperatura óptima de 82.0°C.
- [x] Protección de emergencia ante picos térmicos `EMERGENCY_SPIKE` a 83.5°C con forzado inmediato a 100% PWM.
- [x] Algoritmo de balanceo por elevador de tensión (`app/governance/preset_balancer.py`) mitigando caídas en cascada.
- [x] Desescalado térmico individual ante saturación y desescalado grupal por inestabilidad de red.
- [x] Control manual y comandos en caliente `/gov` y `/balancer` vía Telegram.
- [x] 35 tests unitarios e integración pasando (`tests/test_fan_governor_concurrency.py`, `tests/test_preset_balancer.py`).
- [x] Activado y verificado en producción con telemetría continua.

---

### R12 - Modular Domain Architecture & Shim Purge (COMPLETE, P2)

**Specs**: `specs/041-app-modular-architecture` y `specs/042-purge-shims-test-modernization`

- [x] Reorganización de los 22 archivos planos en 4 subpaquetes de dominio desacoplados (`app/core/`, `app/vnish/`, `app/governance/`, `app/telegram/`).
- [x] Implementación inicial de shims de retrocompatibilidad con module aliasing.
- [x] Modernización canónica de todas las rutas de importación en la suite de pruebas `tests/`.
- [x] Purga definitiva mediante `git rm` de los 22 archivos shims en la raíz de `app/`.
- [x] Estructura de `app/` reducida estrictamente al orquestador `miner_monitor.py` y el inicializador `__init__.py`.
- [x] 587/587 tests globales PASS y auditoría de release verificada (60 payload files).

---

### R13 - Telegram Interactive Command Center (COMPLETE, P1)

**Spec**: `specs/043-telegram-interactive-command-center`

- [x] Módulo puro desacoplado `app/telegram/command_center.py` con layouts y builders de InlineKeyboardMarkup.
- [x] Dashboard táctil `/menu` (alias `/start`, `/panel`) con semáforos, barras de progreso Unicode `[██████░░]` y métricas de flota.
- [x] Submenús in-place vía `editMessageText`: Métricas, Reinicios guiados, Presets y Alertas.
- [x] Flujo de confirmación de reinicio en dos toques con token criptográfico efímero de 60 segundos.
- [x] Acciones rápidas de 4 botones embebidas en alertas de incidentes (`diag`, `chart`, `rb_req`, `snz`).
- [x] Guardián de seguridad RBAC (`from_id == chat_id`) y acuse inmediato `answerCallbackQuery` (< 500ms).
- [x] 17 tests unitarios en `tests/test_command_center.py` y 602 tests globales PASS.

---

### R14 - Modo Silencio Inteligente & Safety Thermal Guard (COMPLETE / ACTIVE, P0)

**Spec**: `specs/044-silent-mode-thermal-guard`

- [x] Cumplimiento de Condición C1: Despacho asíncrono no bloqueante en el worker de Telegram polling.
- [x] Cumplimiento de Condición C2: Campos `silent_mode_*` independientes en `MinerState` y reconciliación en arranque `first_tick`.
- [x] Cumplimiento de Condición C3: Inyección dinámica de techos acústicos (`max_fan_duty_percent`) al Fan Governor.
- [x] Cumplimiento de Condición C4: Desactivación atómica en `state.json` bajo pico térmico (83.5°C) o falla con ventiladores al 100% y alerta Telegram.
- [x] Temporizadores de cuenta regresiva configurables (30m, 1h, 2h, 4h, 6h, indef) con reversión automática a régimen normal.
- [x] Integración de selector táctil en el Command Center (`cc:nav:silent`, `cc:act:silent:*`) y comando `/silent`.
- [x] 17 tests unitarios en `tests/test_silent_mode.py` y 17 tests en `tests/test_command_center.py`.
- [x] 621/621 tests globales PASS, release audit verificado y activo en producción bajo PID 58344.

### Spec 045: Telegram Mobile Help Center & Categorized Navigation (Completado)
- [x] Cumplimiento de Condición C1: Tarjetas y vistas interactivas con líneas de datos <= 32 caracteres visibles sin tags Markdown.
- [x] Cumplimiento de Condición C2: Catálogo canónico único `HELP_COMMANDS` y `HELP_CATEGORIES` en `app/telegram/help_center.py` con 28 comandos e inclusión de `/menu` y `/silent` con todos sus aliases reales.
- [x] Cumplimiento de Condición C3: Parser `parse_help_callback` con gramática cerrada (`help:nav:home`, `help:cat:<id>`, `help:cmd:<name>`) y validación estricta de longitud <= 64 bytes UTF-8. ACK temprano (<50ms) en `_handle_help_callback`.
- [x] Cumplimiento de Condición C4: Vistas interactivas < 1,500 caracteres (muy por debajo de 3,600 caracteres) evitando particionado con pérdida de tags Markdown.
- [x] Cumplimiento de Condición C5: Sanitización con `escape_markdown` y medición con `strip_markdown`.
- [x] Cumplimiento de Condición C6: Fallback directo de entrega preserva `reply_markup` ante `queue=None` o saturación de cola.
- [x] Cumplimiento de Condición C7: Cero alteraciones en la máquina de estados, bucle de monitoreo, auto-reboot ni workers concurrentes.
- [x] Conexión de router `help:` en `_handle_callback_query`, ACK temprano, in-place editing y botón en Command Center (`cc:nav:main` <-> `help:nav:home`).
- [x] 35 tests específicos (29 puros + 5 integración + 1 fallback) y 660/660 tests globales PASS (0 fallos, 0 regresiones).

### Spec 046: Mobile-First Card Layout & UX Harmonization across Fleet Reports (Completado)
- [x] Cumplimiento de Condición C1: Tarjetas verticales con viñetas `•` y ancho estricto <= 32 columnas visibles para `/status`, `/fans`, `/efficiency` y `/presets`.
- [x] Cumplimiento de Condición C2: Renderizadores puros desacoplados y deterministas (`render_fleet_status_card`, `build_fans_table_text`, `build_efficiency_table_text`, `build_presets_table_text`) sin I/O ni sockets.
- [x] Cumplimiento de Condición C3: Callbacks `diag:ref:*` (`status`, `fans`, `eff`, `presets`) con validación <= 64 bytes UTF-8 y ACK inmediato (< 50ms).
- [x] Cumplimiento de Condición C4: Longitud total acotada (< 1,500 caracteres), previniendo desbordes o particionado roto de Markdown.
- [x] Cumplimiento de Condición C5: Sanitización Markdown robusta en todos los renderizadores.
- [x] Cumplimiento de Condición C6: Fallback táctil completo y legibilidad garantizada sin markups.
- [x] Cumplimiento de Condición C7: Cero modificaciones en FSM, auto-reboot, límites del Fan Governor ni adquisición de telemetría.
- [x] Teclado inline universal de 1 toque: `[ 🔄 Actualizar ] [ 📱 Menú ]` (con `[ 📊 Métricas ]` en `/status`).
- [x] Router de callbacks en `miner_monitor.py` con edición in-place y RBAC.
- [x] 15 tests específicos (9 unitarios en `test_fleet_cards.py` + 6 integración en `test_telegram_callbacks.py`) y 675/675 tests globales PASS (0 fallos, 0 regresiones).

### Spec 047: Mobile-First Card Layout for Balancer, Digest & Operational Events (Completado)
- [x] Cumplimiento de Condición C1: Tarjetas verticales con viñetas `•` y ancho estricto <= 32 columnas visibles para `/balancer`, `/elevadores`, `/digest`, `/snoozed`, `/events`, `/event <id>` y `/why`.
- [x] Cumplimiento de Condición C2: Renderizadores puros desacoplados y deterministas sin I/O ni sockets (`build_balancer_table_text`, `build_miner_balancer_detail_text`, `build_elevator_sensitivity_text`, `format_daily_digest`, `build_snooze_status_text`, `render_event_list`, `render_event_detail`, `render_reboot_decision`).
- [x] Cumplimiento de Condición C3: Callbacks `diag:ref:*` (`balancer`, `elev`, `digest`, `events`) con validación <= 64 bytes UTF-8 y ACK inmediato (< 50ms).
- [x] Cumplimiento de Condición C4: Longitud total acotada (< 2,000 caracteres) y wrapping estricto con `wrap_mobile_lines`.
- [x] Cumplimiento de Condición C5: Sanitización y separación móvil estándar con viñetas `•` y separador `─` * 28.
- [x] Cumplimiento de Condición C6: Fallback táctil completo y legibilidad garantizada sin markups.
- [x] Cumplimiento de Condición C7: Cero modificaciones en FSM, auto-reboot, límites del Fan Governor ni adquisición de telemetría.
- [x] Teclados inline de refresco en 1 toque en dispatcher para `/balancer`, `/elevadores`, `/digest` y `/events`.
- [x] Router de callbacks en `miner_monitor.py` con edición in-place, RBAC y pase de `event_store`.
- [x] 12 tests específicos (8 unitarios en `test_mobile_diagnostics.py` + 4 integración en `test_telegram_callbacks.py`) y 687/687 tests globales PASS (0 fallos, 0 regresiones).

### Spec 048: Safe Fleet Shutdown & Multi-Select Maintenance Mode (Completado)
- [x] Condición C1 (Límite Estricto Mobile-First <= 32 Columnas): 100% de las tarjetas y líneas cumplen ancho de 32 columnas visibles.
- [x] Condición C2 (Parada y Reanudación Segura Vnish): Wrappers transaccionales `safe_stop_mining` y `safe_resume_mining` contra `POST /api/v1/mining/stop` y `resume`.
- [x] Condición C3 (Purga Térmica Activa 45s): Desconexión de carga hash (0W), barrido forzado con coolers por 45s y confirmación "ÁREA ELÉCTRICA SEGURA".
- [x] Condición C4 (Selector Táctil Multiselección): Matriz interactiva de casillas `⬜`/`☑️` con bitmask compacta (`0000` $\leftrightarrow$ `1010`) en callbacks <= 21 bytes.
- [x] Condición C5 (Confirmación en 2 Pasos con Token Criptográfico): Ephemeral 60s token en `CallbackTokenRegistry`.
- [x] Condición C6 (Auto-Snooze de Mantenimiento 4h): Supresión de falsas alarmas y autorreinicios; auto-unsnooze en `/resume`.
- [x] Condición C7 (Interlocks y Armonización): Bloqueo de reboots manuales y automáticos; omitir mineros detenidos en Fan Governor y Balancer; insignias `⏸️ DETENIDO`; comandos `/shutdown` y `/resume` registrados en `/help`.
- [x] 34 tests específicos (17 unitarios en `test_fleet_shutdown.py` + 4 en `test_command_center.py` + 13 integración en `test_safe_fleet_shutdown_integration.py`) y 721/721 tests globales PASS (0 fallos, 0 regresiones).
- [x] Servicio Windows `MinerAlerts` reiniciado y verificado operativo en producción bajo PID 32436.

### Spec 049: Active Thermal Purge Ramp & Acoustic Contrast on Safe Shutdown (Completado)
- [x] Condición C1 (Mobile-First <= 32 Columnas): Tarjetas `render_shutdown_in_progress` y `render_safe_area_card` adaptadas con `visible_line_width <= 32`.
- [x] Condición C2 (Rampa Forzada 100% PWM): Modulación concurrente inmediata al 100% de PWM en todos los mineros detenidos con `execute_parallel_fan_duty(miners, 100)`.
- [x] Condición C3 (Enfriamiento Ultra-Rápido 45s): Evacuación masiva de calor latente con 0W en hashboards, derrumbando chips a <35°C.
- [x] Condición C4 (Contraste Acústico al Segundo 45): Caída brusca al piso de reposo (40% PWM / ~2.400 RPM, ~720 RPM sin carga) sincronizada exactamente con la notificación `ÁREA ELÉCTRICA SEGURA`.
- [x] Condición C5 (Seguridad en Reanudación): `/resume` reactiva la ventilación preventiva (100% PWM) antes del arranque de placas, asegurando flujo térmico seguro.
- [x] Condición C6 (Trazabilidad): Eventos `purge_fan_ramp` y `purge_idle_drop` registrados en SQLite `event_store`.
- [x] 4 nuevos tests (2 unitarios en `test_fleet_shutdown.py` + 2 integración en `test_safe_fleet_shutdown_integration.py`) y 727/727 tests globales PASS (0 fallos, 0 regresiones).


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
- [x] Botones interactivos Telegram inline (1-tap) y flujo de confirmación en 2 pasos (Spec 031).
- [x] Envío de gráficos nativos de telemetría en PNG sin archivos en disco (Spec 032).
- [x] Silenciamiento temporal y bloqueo de reinicios por mantenimiento programado (Spec 033).
- [x] Reporte ejecutivo diario programado y bajo demanda (Spec 034).
- [x] Diagnóstico predictivo de saturación térmica y degradación de ventiladores (Spec 035).
- [x] Métrica en tiempo real de Joules por Terahash y alertas de consumo (Spec 036).
- [x] Auditoría dinámica de perfiles de autotuning Vnish y caídas de frecuencia (Spec 037).
- [x] Blindaje de concurrencia en memoria y sockets SQLite para consultas analíticas (Spec 038).
- [x] Gobernador de lazo cerrado térmico y acústico Vnish a 82.0°C (Spec 039).
- [x] Calibración y balanceo dinámico de potencia y presets por elevador de tensión (Spec 040).
- [x] Arquitectura modular de 4 dominios desacoplados en `app/` (Spec 041).
- [x] Purga definitiva de shims y modernización canónica de tests (Spec 042).
- [x] Centro de Comando táctil interactivo `/menu` con submenús in-place y seguridad RBAC (Spec 043).
- [x] Modo Silencio / Visitas acotado al 30%–50% PWM a 82.0°C con elevadores independientes, temporizadores y Thermal Guard a 83.5°C (Spec 044 - Recalibrado).
- [x] Centro de Ayuda táctil interactivo `/help` con navegación por categorías y tarjetas Mobile-First <= 32 cols (Spec 045).
- [x] Formato Mobile-First vertical con tarjetas <= 32 cols y refresco en 1 toque para /status, /fans, /efficiency, /presets (Spec 046).
- [x] Formato Mobile-First vertical con tarjetas <= 32 cols y refresco en 1 toque para /balancer, /elevadores, /digest, /snoozed, /events (Spec 047).
- [x] Apagado Seguro de Flota y Selector Multiselección de Mantenimiento Eléctrico con Purga Térmica (Spec 048).
- [x] Rampa de Purga Térmica Activa y Contraste Acústico en Parada Segura (Spec 049).
- [x] Guardián de Recuperación Post-Blackout con Botón 1-Tap y Auto-Reanudación (Spec 050).
- [x] Discriminador Rápido de Corte de Fase vs Caída de Conectividad (Spec 051).
- [x] Refuerzo de Concurrencia de Gobernanza y Estabilización Release V4 (Spec 053).
- [x] Resiliencia de Persistencia Post-Blackout y Ámbito Global en Ciclo Principal (Release Hotfix V4.0.1, 797 tests PASS).
- [x] Recalibración de Modo Silencio 30%–50% PWM, Regulación a 82°C y Autonomía por Elevador (Spec 044 Update, 800 tests PASS).
- [x] Calibración de Piso Dinámico a 30% PWM en Fan Governor para Modulación Autónoma a 82°C (Hotfix V4.0.3, 802 tests PASS).
- [x] Telemetría Profunda por Cadena y Diagnóstico Predictivo de Hashboard (Spec 054, 835 tests PASS).


---

## Future Strategic Initiatives (V4 / Next Horizon)

Las propuestas técnicas detalladas de mejora para el sistema se encuentran documentadas en [`docs/proposals/SYSTEM_IMPROVEMENT_PROPOSALS.md`](../proposals/SYSTEM_IMPROVEMENT_PROPOSALS.md).

### Iniciativa 1 — Integración PDU/UPS Inteligente (Continuación Spec 024)
- [ ] Relevar especificación técnica de fabricantes y protocolos soportados (SNMPv3 / Modbus TCP).
- [ ] Diseñar adaptador de lectura de tensión AC real sin inferencias desde DC.
- [ ] Validar con período de sombra de 72 horas antes de incorporar a métricas de flota.

### Iniciativa 2 — Telemetría Avanzada Externa (Prometheus Pushgateway / OTLP)
- [ ] Evaluar exportador remoto seguro hacia Grafana Cloud o stack centralizado.
- [ ] Diseñar autenticación mutua TLS y buffer offline ante cortes de Internet.

### Iniciativa 3 — Perfiles de Eficiencia Estacional (Verano/Invierno)
- [ ] Modelar calibración programática de targets térmicos (80°C verano / 83°C invierno).
- [ ] Automatizar conmutación estacional según temperatura ambiente exterior.

### Iniciativa 4 — Rampa de Purga Térmica Activa y Contraste Acústico en Parada Segura (Spec 049 - Completado)
- [x] Forzar ventiladores al 100% durante los 45s de purga tras `stop_mining` para expulsar activamente el calor residual de los disipadores.
- [x] Caída instantánea a reposo (40% PWM / ~2.400 RPM, ~720 RPM sin carga) en el segundo 45 simultáneo al envío de la notificación "ÁREA ELÉCTRICA SEGURA".
- [x] Contraste acústico evidente para el operador (del rugido de purga al susurro de reposo) y enfriamiento acelerado de chips de 65°C a <35°C antes del corte de energía.
- [x] Tarjeta de Telegram con indicación explícita del piso de reposo (40% PWM) previo a la apertura de la llave termomagnética.

### Iniciativa 5 — Guardián de Recuperación Post-Blackout (Spec 050 - Completado)
- [x] Detección proactiva de mineros que inician en `miner_state: stopped` tras el retorno de tensión de un corte de red.
- [x] Notificación ejecutiva con botón táctil 1-tap `[ ▶️ Reanudar Flota ]` y auto-reanudación configurable con ventana de gracia.
- [x] Respeto estricto de interlocks de mantenimiento (Spec 048) y silenciamiento temporal (Spec 033).
- [x] Restauración automática de ventiladores al 100% PWM al reanudar el minado.

### Iniciativa 6 — Discriminador Rápido de Corte de Fase vs Caída de Conectividad (Spec 051 - Completado)
- [x] Clasificación instantánea (<3s): si el host local/switch sigue activo y los mineros de un elevador o la flota caen al unísono, clasificar de inmediato como disparo de térmica o corte general.
- [x] Supresión de reintentos lentos e histeresis de 3 ticks habitual, encolando tarjeta ejecutiva Mobile-First en Telegram con prioridad máxima.
- [x] Autochequeo de enlace de red del host para suprimir falsas alarmas si el host quedó aislado.
- [x] Exclusión de mineros en mantenimiento deliberado (Spec 048) o silenciamiento activo (Spec 033).
- [x] Cooldown antispam de 300s y trazabilidad completa en EventStore (`electrical_phase_drop`).

### Iniciativa 7 — Programador de Ventanas de Mantenimiento Eléctrico (Spec 052 - Completado)
- [x] Programación diferida de maniobras eléctricas (ej. `/schedule_maintenance in 2h 3h`, `14:30 2h`).
- [x] Desescalado suave y progresivo de presets de potencia antes de la ventana fijada (Pre-Ramp T-10m a 2300W, T-5m a 2100W) y parada segura en T-0 con purga térmica de 45s a 100% y reposo a 40% PWM.
- [x] Cancelación en caliente mediante botón 1-tap `[ ❌ Cancelar Ventana ]` y persistencia en `state.json`.

### Iniciativa 8 — Telemetría Profunda por Cadena y Diagnóstico Predictivo de Hashboard (Spec 054 - Completado)
- [x] Ingesta y normalización periódica de telemetría de cadenas `/api/v1/chains` (sensores de temperatura por chip, chips funcionales/esperados, voltajes y estado I2C).
- [x] Detección temprana de anomalías físicas de sensor y bus (`state: error`, `chip: 54`, `loc: 28`) para predecir `chain_break` antes del reinicio abrupto.
- [x] Acumulación estructurada de telemetría en SQLite (`chain_telemetry_samples`) para análisis forense, correlación de fallas y minería de datos.
- [x] Tarjeta de alerta preventiva y comando interactivo `/chains` en Telegram con visualización ejecutiva del estado por hashboard.
- [x] Herramienta analítica de línea de comandos `tools/analyze_chain_breaks.py` para cruce de fallas y predicción de fin de vida de placas.

### Iniciativa 9 — Auto-Reboot ante Falla de Placa y Recuperación Automática de Hashboard (Spec 055 - Completado)
- [x] Extensión de la puerta pura `auto_reboot_signal_allows_evaluation` para admitir `STATE_HASHBOARD` (0/3 placas con temporizador activo) manteniendo compatibilidad 100% con `STATE_LOW`.
- [x] Temporizador monótono `hashboard_since_ts` en `MinerState` inicializado al entrar en falla y reseteado al recuperar 3/3 placas o ante reinicio.
- [x] Canalización completa a través de los 6 interlocks constitucionales (Startup Guard, ventana sostenida 600s, Thermal Guard 85°C, Fleet Incident Guard >= 2, Firmware Transition Guard, Cooldown 1800s, Límite de ventana 3/24h).
- [x] Ejecución controlada vía Hashcore CLI (`run_hashcore_cli`), reseteo de temporizadores y tarjeta ejecutiva especializada en Telegram.
- [x] Registro determinista en `reboot_decisions` del `EventStore` con `trigger="hashboard_failure"`.
- [x] Certificación global con 854/854 tests unitarios y de regresión PASS.

### Iniciativa 10 — Recuperación Escalonada de Dos Niveles (Spec 056 - Completado)
- [x] Discriminación segura entre Auto-Restart de software (Nivel 1, `/api/v1/mining/restart` en 15-20s) y Auto-Reboot completo de hardware (Nivel 2, Hashcore CLI en 3-4m).
- [x] `evaluate_auto_restart_candidate` con filtros transitorios, cooldown de 300s y límite de reintentos (2 intentos antes de ceder a Nivel 2).
- [x] Worker asíncrono no bloqueante `_async_execute_mining_restart` y notificaciones Telegram de Nivel 1.
- [x] Certificación con 881 tests PASS.

### Iniciativa 11 — Gobernanza de Intervenciones & Contingencia Asimétrica Adaptativa (Spec 057 - Completado)
- [x] Modo global "Vnish Libre" (solo lectura/supervisión) con interlocking de 100% de los actuadores mutantes (Reinicios L1/L2, Fan Governor, Preset Balancer y Contingencia) preservando telemetría, SQLite y alertas.
- [x] Menú táctil e interactivo en Telegram Command Center (`[ 🛡️ Intervenciones: 🟢 ON / 🔴 LIBRE ]`) con selectores individuales y temporizadores de cuenta regresiva (30m, 1h, 2h, 4h, Indef) para reactivación segura automática.
- [x] Contingencia eléctrica asimétrica por elevador relativa al estado actual: reducción exclusiva del minero canario (S19JPRO-24 en Elevador 1, S19JPRO-25 en Elevador 2) ante perturbación matutina de red, manteniendo intacto al compañero.
- [x] Prueba en los límites: descenso escalonado si el canario vuelve a reiniciar, y reducción del compañero solo ante perturbación severa.
- [x] Rampa de Step-Up Soak: tras 2 horas continuas sin reinicios, recuperación progresiva hacia los presets nominales.
- [x] Comandos rápidos `/interventions` y `/contingency` y persistencia atómica en `state.json`.
- [x] Certificación global con 902/902 tests unitarios y de regresión PASS.

### Iniciativa 12 — Desacoplamiento y Modularización Arquitectónica del Monolito (Horizonte V5.0)
- Documento de Plan de Acción: [`docs/speckit/archive/plans/ACTION_PLAN_V5_MODULARIZATION.md`](archive/plans/ACTION_PLAN_V5_MODULARIZATION.md)
- **Fase 0 — Quick Wins Inmediatos**:
  - [x] **QW-01**: Extracción de teclados y menús táctiles (integrada en Spec 058).
  - [x] **QW-02**: Rotación automática de registros con `RotatingFileHandler` en `logs/out.log` para prevenir saturación de disco bajo el servicio Windows.
  - [x] **QW-03**: Saneamiento y purga de funciones y wrappers legados de ayuda (`render_legacy_help_index()`) obsoletos tras Spec 045.
  - [x] **QW-04**: Extracción de `_build_state_payload()` fuera de `state_lock` reduciendo a 0ms la retención del lock de memoria durante `os.fsync()` en Windows NTFS (902 tests PASS).
- **Fase 1 — Spec 058: Desacoplamiento de Telegram Command Center & Dispatcher (MT-01)**:
  - [x] Desacoplamiento del bucle procedural de `telegram_polling_worker` (-2,669 LOC extraídas de `miner_monitor.py`).
  - [x] Arquitectura orientada a handlers desacoplados: `app/telegram/router.py`, `app/telegram/poller.py` y `app/telegram/commands/` (`status`, `fans`, `reboot`, `interventions`, `diagnostics`, `maintenance`, `help`).
  - [x] Suite de pruebas unitarias aisladas (`tests/test_telegram_dispatcher.py` con 8 tests nuevos), con 910/910 tests globales PASS.
- **Fase 2 — Spec 059: Protocolos de Red y Clientes de Hardware (MT-02)**:
  - [x] Extracción del protocolo TCP Socket 4028 (`query_cgminer`, parsers de summary, pools, version, stats, conteo de placas hashboard y temperaturas) a `app/network/cgminer_client.py`.
  - [x] Extracción del actuador de hardware Hashcore Toolkit CLI a `app/network/hashcore_client.py` con guardarraíles QA y flags windowless en Windows (`CREATE_NO_WINDOW`).
  - [x] Cliente formal y tipado para la API REST de Vnish a `app/network/vnish_client.py` (`VnishClient`) con context manager, timeouts acotados de 2.5s y manejo de excepciones.
  - [x] Suite de 18 pruebas unitarias en `tests/test_network_clients.py` con 928/928 tests globales PASS (cero regresiones).
- **Fase 3 — Spec 060: Core Daemon & Contenedor de Estado (ST-01 & ST-02 - Milestone V5.0)**:
  - [x] Formalización de `app/core/state_manager.py` con jerarquía estricta anti-deadlock (`state_lock` Nivel 1 -> `_SAVE_STATE_LOCK` Nivel 2, con fsync fuera de `state_lock`).
  - [x] Motor de supervisión declarativo con arquitectura de hooks por tick en `app/core/engine.py` (`CoreSupervisoryEngine`, `TickResult`).
  - [x] Inyección de dependencias `MonitorContext` y factoría `build_monitor_context` en `app/core/context.py`.
  - [x] Conexión aditiva de `StateManager` y `MonitorContext` en `main()` de `miner_monitor.py` preservando el 100% de contratos `inspect.getsource(main)`.
  - [x] Suite de 7 pruebas unitarias en `tests/test_core_daemon.py` con **935/935 tests globales PASS** (cero fallos, cero regresiones). Milestone V5.0 certificado.

### Iniciativa 13 — Resiliencia de Almacenamiento SQLite WAL Mode & Integrity Check (Spec 061 - Completada)
- Documento de Plan de Evolución: [`docs/speckit/archive/plans/ACTION_PLAN_POST_V5_EVOLUTION.md`](archive/plans/ACTION_PLAN_POST_V5_EVOLUTION.md)
- Especificación: [`specs/061-sqlite-wal-integrity/spec.md`](../../specs/061-sqlite-wal-integrity/spec.md)
- Evidencia: [`specs/061-sqlite-wal-integrity/evidence.md`](../../specs/061-sqlite-wal-integrity/evidence.md)
- [x] Verificación de integridad asíncrona (`_integrity_check_worker`) en arranque sin retrasar el booteo ni el Startup Guard.
- [x] Aislamiento automático de base corrupta a `data/miner_alerts_corrupt_<epoch>.db` y auto-recreación limpia del esquema v7 ante fallo de sectores tras apagón.
- [x] Checkpointing determinista en Windows NTFS: `PRAGMA wal_checkpoint(PASSIVE)` horario y `PRAGMA wal_checkpoint(TRUNCATE)` diario fuera de horas pico.
- [x] Techo blando de tamaño con `PRAGMA max_page_count = 262144` (~1 GB) para evitar saturación de disco.
- [x] Pool de lectura multi-lector `create_readonly_connection` con manejo defensivo de `SQLITE_BUSY_SNAPSHOT` y reintentos con backoff exponencial (11 tests en `tests/test_event_store_wal_resilience.py`, 946/946 tests PASS).

### Iniciativa 14 — HW Error Tripwire & Rollback Automático de Overclock (Spec 062 - Completado)
- Documento de Plan de Evolución: [`docs/speckit/archive/plans/ACTION_PLAN_POST_V5_EVOLUTION.md`](archive/plans/ACTION_PLAN_POST_V5_EVOLUTION.md)
- Especificación: [`specs/062-hw-error-tripwire/spec.md`](../../specs/062-hw-error-tripwire/spec.md) | Evidencia: [`specs/062-hw-error-tripwire/evidence.md`](../../specs/062-hw-error-tripwire/evidence.md)
- [x] Métrica de errores de hardware no volátil en `StabilityMetrics` (`hw_errors_delta_10m`, `hw_error_rate_pct`) calculada vía `EventStore`.
- [x] Regla de disparo `ACTION_STEP_DOWN_HW_ERRORS` en `evaluate_balancer_step()` con umbral combinado (`hw_error_rate_pct >= 0.5%` AND `hw_errors_delta_10m >= 200`).
- [x] Candado de 48 horas (`hw_error_lock_until_ts`, `hw_error_locked_preset`) persistido en `state.json` bloqueando re-escalado optimista.
- [x] Interlock anti-cascada post-reboot L1/L2 impidiendo que el firmware restablezca 2700W por defecto.
- [x] Tarjeta de notificación móvil en Telegram `<= 32` columnas (`render_hw_error_tripwire_card()`).
### Iniciativa 15 — Gobernador Térmico con Conciencia Estacional (Spec 063 - Completado)
- Documento de Plan de Evolución: [`docs/speckit/archive/plans/ACTION_PLAN_POST_V5_EVOLUTION.md`](archive/plans/ACTION_PLAN_POST_V5_EVOLUTION.md)
- Especificación: [`specs/063-ambient-thermal-pid/spec.md`](../../specs/063-ambient-thermal-pid/spec.md) | Evidencia: [`specs/063-ambient-thermal-pid/evidence.md`](../../specs/063-ambient-thermal-pid/evidence.md)
- [x] Extracción de `inlet_temp_c` en `VnishTelemetry` y `normalize_vnish_stats()` desde `stats_response` existente sin requests HTTP adicionales.
- [x] Extensión de `GovernorConfig` con parámetros estacionales (`winter_target_temp_c`, `summer_min_duty_percent`, etc.).
- [x] Función pura `resolve_seasonal_parameters()` en `app/governance/fan_governor.py` con 3 guardarraíles inviolables.
- [x] Adaptación dinámica de curvas en `compute_governor_step(..., ambient_temp_c=...)`.
- [x] Agregación grupal de $T_{\text{amb}}$ y orquestación en `execute_governor_cycle()`.
- [x] Suite completa de tests en `tests/test_fan_governor_seasonal.py`.
### Iniciativa 16 — Telemetría Visual y Gráficos Multi-Miner en Telegram (Spec 064 - Completado)
- Documento de Plan de Evolución: [`docs/speckit/archive/plans/ACTION_PLAN_POST_V5_EVOLUTION.md`](archive/plans/ACTION_PLAN_POST_V5_EVOLUTION.md)
- Especificación Activa: [`specs/064-multi-miner-charts/spec.md`](../../specs/064-multi-miner-charts/spec.md) | Evidencia: [`specs/064-multi-miner-charts/evidence.md`](../../specs/064-multi-miner-charts/evidence.md)
- [x] Consultas y renderizado de gráficos por grupo eléctrico (`fetch_group_chart_data`, `render_group_chart_png`) en `charts.py`.
- [x] Soporte para comandos `/chart elevator_1`, `/chart elevator_2`, `/chart fleet` en `ChartCommand`.
- [x] Selector interactivo de rango con teclado inline `[ 1h ] [ 6h ] [ 24h ] [ 7d ]` (`build_chart_range_keyboard`).
- [x] Acción `chart_range` en `parse_callback_data()` y dispatcher en `_handle_callback_query()`.
- [x] Actualización in-place mediante `edit_telegram_photo()` con `editMessageMedia` y `attach://file_0`.
- [x] Gestión estricta de memoria `matplotlib` (`Agg`, `plt.close(fig)`) y suite de pruebas de estrés (11 tests en `tests/test_multi_miner_charts.py`, 996/996 tests PASS).

### Iniciativa 17 — Pipeline Declarativo de Hooks en CoreSupervisoryEngine (Spec 065 - ST-04 - Completado)
- Especificación: [`specs/065-supervisory-hooks/spec.md`](../../specs/065-supervisory-hooks/spec.md) | Evidencia: [`specs/065-supervisory-hooks/evidence.md`](../../specs/065-supervisory-hooks/evidence.md)
- [x] `HookStage` (enum `IntEnum` con 7 etapas ordenadas: PRE_TICK < ACQUISITION < DETECTION < GOVERNANCE < ACTUATOR < PERSISTENCE < POST_TICK).
- [x] Clase base `SupervisoryHook` y dataclass `HookResult` (ok, duration_seconds, error).
- [x] `CoreSupervisoryEngine.register_hook()` con ordenamiento determinista y `execute_tick()` con contención defensiva por hook individual.
- [x] Garantía invariante: etapa `PERSISTENCE` siempre se ejecuta incluso si todas las etapas previas fallan.
- [x] Hooks canónicos: `PersistenceHook` (PERSISTENCE), `GovernanceInterlockHook` (GOVERNANCE), `TimingGuardHook` (PRE_TICK).
- [x] Integración aditiva en `main()` de `miner_monitor.py` con `_poll_interval_seconds` y modelo monotónico `poll_seconds = max(0.0, interval - elapsed); time.sleep(poll_seconds)`.
- [x] Suite `tests/test_supervisory_hooks.py` con 47 tests (13 clases) cubriendo orden de etapas, contención, timing monotónico y hooks canónicos. **1043/1043 tests PASS** (0 regresiones).

### Iniciativa 18 — Cold-Boot Fleet Grace Period Post-Arranque (Spec 066 - PROP-001 - Completado)
- Documento de Propuestas: [`docs/proposals/SYSTEM_IMPROVEMENT_PROPOSALS.md`](../proposals/SYSTEM_IMPROVEMENT_PROPOSALS.md)
- Especificación: [`specs/066-cold-boot-grace/spec.md`](../../specs/066-cold-boot-grace/spec.md) | Evidencia: [`specs/066-cold-boot-grace/evidence.md`](../../specs/066-cold-boot-grace/evidence.md)
- [x] Configuración `"startup_fleet_grace_period_seconds": 180` y `"startup_fleet_grace_threshold_ths": 50.0`.
- [x] Supresión activa de streaks de falla (`offline_streak = 0`, `low_streak = 0`) y reseteo de timers sostenidos durante la fase `WARMING_UP`.
- [x] Inhibición de alertas de episodios irregulares (`EPISODE_ALERT`) a Telegram durante la ventana de calentamiento de 180 segundos.
- [x] Consolidación temprana de arranque con tarjeta limpia `🟢 FLOTA RESTABLECIDA` al alcanzar $\ge 50$ TH/s en toda la flota.
- [x] Consolidación por timeout tras 180s con tarjeta `STARTUP [FIN PERÍODO DE GRACIA]` y reconocimiento de iniciales (`acknowledge_active_initials()`).
- [x] Sincronización continua de `monitor_ctx.governance = _GLOBAL_INTERVENTION_GOV` en cada tick e inyección en `extra_tick_data` para hooks.
- [x] Suite de 15 pruebas unitarias en `tests/test_startup_grace_period.py`. **1062/1062 tests globales PASS** (0 regresiones).

### Iniciativa 19 — Latido de Gateway y Supresión de Tormentas de Red Local (Spec 067 - PROP-005 - Completado)
- Documento de Propuestas: [`docs/proposals/SYSTEM_IMPROVEMENT_PROPOSALS.md`](../proposals/SYSTEM_IMPROVEMENT_PROPOSALS.md)
- Especificación: [`specs/067-gateway-heartbeat/spec.md`](../../specs/067-gateway-heartbeat/spec.md) | Evidencia: [`specs/067-gateway-heartbeat/evidence.md`](../../specs/067-gateway-heartbeat/evidence.md)
- [x] Worker daemon ultraliviano de latido `GatewayHeartbeatWorker` en `app/network/gateway_heartbeat.py` (TCP connect 50ms, fallback puerto 53, cierre explícito de sockets).
- [x] Supresión de falsos conatos de desconexión masiva (`STATE_OFFLINE`) durante parpadeos de switch Ethernet o microcortes de router local (ventana default 15s).
- [x] Suite de 7 pruebas unitarias en `tests/test_gateway_heartbeat.py`. **1072/1072 tests globales PASS** (0 fallos, 0 regresiones).

### Iniciativa 20 — Canal IPC de Alta Frecuencia Monitor ↔ Watchdog vía Named Pipes (Spec 068 - PROP-007 - Completada & Certificada)
- Documento de Plan y Especificación: [`specs/068-watchdog-ipc-pipe/spec.md`](../../specs/068-watchdog-ipc-pipe/spec.md) | Evidencia: [`specs/068-watchdog-ipc-pipe/evidence.md`](../../specs/068-watchdog-ipc-pipe/evidence.md)
- **Estado**: Completada & Certificada. Servidor y cliente IPC nativo en Windows NT con SDDL `D:(A;;GRGW;;;WD)` y fallback a socket loopback `127.0.0.1:4029`. Total **1176 tests PASS**.
- [x] Servidor Named Pipe nativo en Windows (`\\.\pipe\MinerAlertsWatchdog`) vía `ctypes` (sin dependencias `pywin32`) con fallback a Loopback TCP (`127.0.0.1:4029`).
- [x] Protocolo Ping-Pong (`PING <nonce>` -> `PONG <nonce> <seq> <uptime>`) con timeout de 100ms y detección de deadlocks en el bucle principal (`tick_sequence` congelado).
- [x] Máquina de estados de 3 etapas y volcado forense automático de trazas de hilos (`sys._current_frames()`) antes de `Restart-Service`.

### Iniciativa 21 — Telemetría Profunda por Cadena & Diagnóstico Predictivo Chain Break (Spec 069 - PROP-008 - Completada & Certificada)
- Documento de Plan y Especificación: [`specs/069-chain-telemetry-break-prediction/spec.md`](../../specs/069-chain-telemetry-break-prediction/spec.md) | Evidencia: [`specs/069-chain-telemetry-break-prediction/evidence.md`](../../specs/069-chain-telemetry-break-prediction/evidence.md)
- **Estado**: Completada & Certificada tras auditoría QA especialista y hardening de robustez. Motor predictivo `PredictiveChainEngine` implementado, índice compuesto WAL creado, reglas I2C/déficit/eléctricas certificadas con 23 nuevas pruebas y 1204 tests globales PASS.
- [x] Índice compuesto optimizado `ix_chain_telemetry_miner_chain_time` en SQLite WAL para consultas de evaluación en $< 15\text{ ms}$ (medido $< 1\text{ ms}$).
- [x] Helper resiliente `fetch_chain_samples_window` con reintentos ante `SQLITE_BUSY_SNAPSHOT` y `_cursor_rows_to_dicts` universal.
- [x] Regla de alerta preventiva de bus I2C: notificación proactiva en Telegram si `sensors_error_count > 0` persiste por $> 12\text{ h}$ con significancia $N \ge 24$ (cubriendo el caso del Minero 24 Cadena 2).
- [x] Discriminador de perturbación eléctrica de grupo (`elevator_1` vs `elevator_2`) vs degradación física de silicio suprimiendo alertas falsas individuales ante caídas simultáneas con soporte de claves compuestas.
- [x] Formateador de alertas móviles Telegram ($\le 32$ columnas), soporte explícito de Cadena 0 (Board 0) y deduplicación con cooldown de 24h (`state.chain_warnings_ts`).
- [x] Suite de pruebas unitarias (`tests/test_chain_predictive_rules.py`, 20 tests) y benchmark de rendimiento (`tests/test_chain_query_performance.py`, 3 tests). Total 1204 tests PASS.

### Iniciativa 22 — Modularización del Core Fase B — Desacoplamiento Seguro de `inspect.getsource(main)` (Spec 070 - ST-05 - Completada & Certificada)
- Documento de Plan y Especificación: [`specs/070-core-modularization-decoupling/spec.md`](../../specs/070-core-modularization-decoupling/spec.md)
- **Estado**: Completada & Certificada. Fases A, B, C y D finalizadas. Desacoplamiento total de introspección de código fuente en tests legados y extracción funcional a `DetectionHook` y `ActuatorHook`. Total 1160 tests PASS.
- [x] Construcción del arnés de comportamiento funcional `tests/test_supervisory_core_behavioral.py` reproduciendo los 37 tests de invariantes mediante caja negra sobre `SupervisoryBehavioralHarness`.
- [x] Certificación de paridad dual: validación de 37 tests legados + 37 tests de comportamiento (total **1156/1156 tests PASS**).
- [x] Extracción segura del bucle procedural de `main()` hacia `DetectionHook` y `ActuatorHook` (Fase C) eliminando introspección de código fuente en los 4 archivos de tests legados.
- [x] Certificación global de la suite: **1160/1160 tests PASS** sin regresiones y servicio Windows `MinerAlerts` en ejecución continua (Fase D).

### Iniciativa 23 — Consolidación de Pool SQLite Resiliente & Barrera de Hilos Daemon (Spec 071 - P0/P1 - Completada)
- Plan de Acción y Saneamiento: [`docs/speckit/archive/plans/ACTION_PLAN_REPO_CLEANUP_AND_ROADMAP.md`](archive/plans/ACTION_PLAN_REPO_CLEANUP_AND_ROADMAP.md)
- Especificación: [`specs/071-sqlite-pool-and-thread-hardening/spec.md`](../../specs/071-sqlite-pool-and-thread-hardening/spec.md) | Evidencia: [`specs/071-sqlite-pool-and-thread-hardening/evidence.md`](../../specs/071-sqlite-pool-and-thread-hardening/evidence.md)
- [x] Función defensiva `_async_restore_locked_preset_tripwire` en `miner_monitor.py` para blindar el hilo `RestoreLock_{name}` con captura total de excepciones y logging estructurado (P0).
- [x] Exposición formal de `open_readonly_connection(db_path)` en `app/core/event_store.py` con fallback y pragmas resilientes (P1).
- [x] Migración de las 7 conexiones directas ad-hoc a SQLite (`energy_efficiency`, `fan_health`, `preset_balancer`, `charts`, `daily_digest`, `presets`) hacia el pool resiliente con reintento automático ante `SQLITE_BUSY_SNAPSHOT`.
- [x] Barrera defensiva en `ShutdownPurgeNotify` y nombres descriptivos en hilos de mensajería (`TelegramSender`, `TelegramPolling`).
- [x] Suites de pruebas en `tests/test_sqlite_readonly_consolidation.py` y `tests/test_tripwire_thread_hardening.py`. **1079/1079 tests globales PASS** (+7 nuevos, 0 regresiones).

### Iniciativa 24 — Unificación de Serialización de Estado & Desacoplamiento de Shims (Spec 072 - P2 - Completada & Certificada)
- Plan de Acción y Saneamiento: [`docs/speckit/archive/plans/ACTION_PLAN_REPO_CLEANUP_AND_ROADMAP.md`](archive/plans/ACTION_PLAN_REPO_CLEANUP_AND_ROADMAP.md)
- [x] Delegación de `_build_state_payload()` en `StateManager.serialize_miner_state()` unificando la fuente de verdad de `MinerState`.
- [x] Extracción del helper compartido `find_assessment_by_target()` y `format_miner_key()` eliminando copy-paste en comandos de Telegram (`diagnostics`, `fans`, `reboot`, `maintenance`).
- [x] Centralización de `_dicts()` en `app/core/mining_quality.py`.
- [x] Retiro y saneamiento de shims procedurales preservando contratos de `inspect.getsource(main)`.
- [x] Suite de pruebas en `tests/test_state_serialization_parity.py` y `tests/test_find_assessment_by_target.py`. **1113/1113 tests globales PASS** (0 fallos, 0 regresiones).

### Iniciativa 25 — Reutilización de Clientes en Tools & Alineación de Configuración (Spec 073 - P3 - Completada)
- Plan de Acción y Saneamiento: [`docs/speckit/archive/plans/ACTION_PLAN_REPO_CLEANUP_AND_ROADMAP.md`](archive/plans/ACTION_PLAN_REPO_CLEANUP_AND_ROADMAP.md)
- [x] Migración de `tools/miner_diagnostics.py` y `debug_4028.py` a `app.network.cgminer_client`.
- [x] Script auditor de configuración `tools/audit_config.py` validando paridad entre `config.example.json` y `config.json`.
- [x] Consolidación de fixtures duplicadas en tests compactos de Telegram (`tests/fixtures_compact_ux.py`).
- [x] Suite de pruebas en `tests/test_miner_diagnostics_client.py` y `tests/test_audit_config.py`. **1119/1119 tests globales PASS** (0 fallos, 0 regresiones).

### Iniciativa 26 — Amortiguador de Inrush Pareado de Elevador (Spec 074 - PROP-009 - Laboratorio & Validación Completada)
- Especificación: [`specs/074-paired-elevator-contingency/spec.md`](../../specs/074-paired-elevator-contingency/spec.md) | Evidencia: [`specs/074-paired-elevator-contingency/evidence.md`](../../specs/074-paired-elevator-contingency/evidence.md) | Propuesta: [`docs/proposals/PROP-009-contingency-stabilization-hypotheses.md`](../proposals/PROP-009-contingency-stabilization-hypotheses.md)
- **Estado**: Laboratorio & Validación Completada (1219 tests PASS). Preparado para auditoría de concurrencia y subprocesos con Claude Sonnet 4.6 (Thinking) antes de despliegue a producción.
- [x] Normalización canónica de identificadores de mineros (`normalize_miner_name`) en búsquedas y disparadores de contingencia (H1).
- [x] Clampeo de `preset_switcher.top_preset` (`clamp_top_preset=True`) en `app/vnish/client.py` para anular interferencia del demonio térmico de Vnish (H2).
- [x] Desescalada preventiva transitoria del compañero robusto (-1 peldaño / 300s) durante inrush inductivo y auto-restauración en `soak_tick` (H3).
- [x] Supresión de `ACTION_RECOVERY_MAX_COOLING` durante ventana de arranque (`is_warming_up`) y umbral de potencia de hashboard ($< 500\text{W}$) en `fan_governor.py` (H4).
- [x] Suite dedicada `tests/test_paired_elevator_contingency.py` (15 tests PASS). Suite global del proyecto: **1219/1219 tests PASS** (0 regresiones).
- [x] Despliegue en producción certificado (1221 tests PASS, Servicio Windows PID 19204).

### Iniciativa 27 — Recuperación Suave de Hasheo, Headroom Chilling y Blindaje Anticolapso de Fuentes APW12 (Spec 075 - PROP-010)
- Especificación: [`specs/075-soft-landing-recovery/spec.md`](../../specs/075-soft-landing-recovery/spec.md) | Plan: [`specs/075-soft-landing-recovery/plan.md`](../../specs/075-soft-landing-recovery/plan.md) | Propuesta: [`docs/proposals/PROP-010-soft-landing-recovery-psu-protection.md`](../proposals/PROP-010-soft-landing-recovery-psu-protection.md)
- **Estado**: Implementación y Auditoría de Concurrencia Completadas (T001-T007). Lista para Certificación en Producción (T008).
- [x] Ventana de normalización pasiva de 120s (`settle_window`) ante detención de hasheo.
- [x] Desescalada preventiva pre-reinicio (`soft_landing_clamp` a 1800W con `clamp_top_preset=True`) para suprimir picos $di/dt$ y evitar el Latch-Off de la fuente APW12.
- [x] Inhibición de reintentos agresivos ante falla física persistente (`CHAIN_FAULT` / `stock_firmware_fallback`) para evitar someter a la fuente a ciclos destructivos inútiles.
- [x] Protocolo de enfriamiento proactivo (*Headroom Chilling*): Balancer solicita 100% PWM temporal al Governor para enfriar minero de 2500W a $\le 78.5^\circ\text{C}$ y desbloquear el salto a 2700W (+6 TH/s).
- [x] Calibración de emergencia de Governor a 83.0°C.
- [x] Suite completa de regresión: **1236/1236 tests PASS** (0 fallos, 0 regresiones).

### Iniciativa 28 — Reinstalación Autónoma de Firmware VNish en NAND y Calibración de Escalera de Hardware S19j Pro (Spec 076 - PROP-011 - Completada & Certificada)
- Especificación: [`specs/076-firmware-reflash-and-ladder/spec.md`](../../specs/076-firmware-reflash-and-ladder/spec.md) | Plan: [`specs/076-firmware-reflash-and-ladder/plan.md`](../../specs/076-firmware-reflash-and-ladder/plan.md) | Evidencia: [`specs/076-firmware-reflash-and-ladder/evidence.md`](../../specs/076-firmware-reflash-and-ladder/evidence.md) | Propuesta: [`docs/proposals/PROP-011-autonomous-firmware-reflash-and-hardware-ladder.md`](../proposals/PROP-011-autonomous-firmware-reflash-and-hardware-ladder.md)
- **Estado**: Implementación, Auditoría QA y Certificación en Producción Completadas (T001-T008). 1262/1262 tests PASS.
- [x] Calibración 1:1 de `DEFAULT_PRESET_LADDER` con los 9 peldaños reales de VNish 1.2.6 (`1740W`, `1800W`, `1850W`, `2000W`, `2150W`, `2300W`, `2500W`, `2700W`, `2970W`) y piso mínimo de contingencia en `2150W` (eliminando rechazos HTTP 400 y atrapamiento en 1800W).
- [x] Módulo `app/network/firmware_flasher.py` con verificación de stock Bitmain (`is_stock_bitmain`) y carga multipart HTTP Digest `/cgi-bin/upgrade.cgi` (`flash_bitmain_nand`).
- [x] Aprovisionamiento post-flasheo (`app/governance/miner_provisioner.py`) inyectando pools de Binance, preset 2300W/2700W y matriz de 378 chips afinados desde perfiles guardados.
- [x] Comando Telegram `/flash_vnish <miner>` con confirmación interactiva de 2 pasos (`flash_cfm`/`flash_ccl` o `CONFIRM`) y ejecución en worker desacoplado `FlashWorker_{miner}`.
- [x] Suite de pruebas dedicadas (`test_firmware_flasher.py`, `test_miner_provisioner.py`, `test_telegram_flash_command.py`) y validación de regresión completa (**1262/1262 tests PASS**).
- [x] Servicio Windows `MinerAlerts` reiniciado y certificado en producción.

### Iniciativa 29 — Gobernanza Escalonada de Elevadores, Bajada Compartida y Soft-Contingencia Horaria (Spec 077 - PROP-012 - Completada & Certificada)
- Especificación: [`specs/077-staggered-elevator-governance/spec.md`](../../specs/077-staggered-elevator-governance/spec.md) | Plan: [`specs/077-staggered-elevator-governance/plan.md`](../../specs/077-staggered-elevator-governance/plan.md) | Evidencia: [`specs/077-staggered-elevator-governance/evidence.md`](../../specs/077-staggered-elevator-governance/evidence.md) | Propuesta: [`docs/proposals/PROP-012-staggered-elevator-governance-and-soft-contingency.md`](../proposals/PROP-012-staggered-elevator-governance-and-soft-contingency.md)
- **Estado**: Implementación, Auditoría QA y Certificación en Producción Completadas (T001-T007). 1288/1288 tests PASS.
- [x] Cola global de transición escalonada para la instalación (*Facility-Wide Staggered Queue*): 1 minero a la vez ejecuta cambios de preset por ciclo con ventana de reposo obligatoria de 180s (*Facility Settle Window*) en la bajada compartida.
- [x] Presupuesto dinámico por transformador elevador ($\le 5000\text{W}$ en horario pico, $\le 5400\text{W}$ en horario valle) y preferencia de equilibrio simétrico (priorizar parejas 2x 2500W antes de combinaciones asimétricas 2700W/2300W).
- [x] Soft-Contingencia Horaria quirúrgica: en días hábiles (Lunes a Viernes), desescalada paulatina (1 minero cada 180s) hacia 2500W en pico matutino (08:30-10:30 hs) y nocturno (19:30-22:30 hs). 19 horas libres y 100% de fines de semana habilitan plena potencia (2700W x4).
- [x] Co-gobernanza con VNish: fijación de macro-envolvente en el monitor con clampeo estricto de `top_preset` para evitar desbalanceos por el daemon térmico en frío, respetando el micro-tuneado de chips.
- [x] Módulos dedicados `app/governance/elevator_budget.py`, tests `test_elevator_budget.py` (21 tests PASS) y validación de regresión global (**1288/1288 tests PASS**).
- [x] Servicio Windows `MinerAlerts` reiniciado y certificado en producción.

---

## Governance

- All 77 specifications in the program (Specs 001 through 077) are tracked and maintained.
- Version 5.1.0 + State Unification + Predictive Chain Break Diagnostics (Spec 069) + Paired Elevator Contingency (Spec 074) + Soft-Landing Recovery & APW12 Defense (Spec 075) + Autonomous Firmware Reflash & Hardware Ladder Calibration (Spec 076) + Staggered Elevator Governance & Soft-Contingency (Spec 077) is verified with 1288/1288 tests PASS (0 failures, 0 regressions).
- Production action authority remains strictly centralized in the Windows monitor.
- External read-only surfaces (Grafana, static dashboard, backup CLI, analyze_chain_breaks CLI) operate decoupled from the monitor.

