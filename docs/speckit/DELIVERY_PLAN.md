# Miner Alerts Delivery Plan

**Planning baseline**: 2026-09-15
**Planning horizon**: 2026-09-15 to 2026-12-20
**Source program**: `docs/speckit/SPEC_PROGRAM.md`
**Source backlog**: `docs/speckit/ROADMAP.md`

## Purpose

This is the estimated implementation, observation and bug-fix calendar. It is
not evidence of completion. Dates move when runtime findings require more time;
safety gates are not compressed to recover an estimate.

## Scheduling Rules

1. Only one monitor-runtime or action-adjacent spec may be active in production.
2. Read-only discovery may overlap only when it does not change the monitor or
   consume the same operator maintenance window.
3. Every production-affecting release has implementation, controlled activation,
   D+1/D+3 review and a documented fix window.
4. High-risk work starts with red contracts and QA no-action proof.
5. P0/P1 incidents stop roadmap work. Containment and focused regression take
   precedence over calendar dates.
6. Friday after 16:00 local time is documentation/read-only work only, except an
   explicitly approved emergency containment.
7. A code change during soak resets affected validation and observation clocks.

## Active Delivery & Operational Window

> [!NOTE]
> **Trazabilidad de Paquetes Históricos**: Para la trazabilidad detallada de todos los paquetes y especificaciones completadas (Specs 001 a 086), consultar [`docs/speckit/SPEC_PROGRAM.md`](SPEC_PROGRAM.md) y la bitácora inmutable [`docs/audit/DEVELOPMENT_LOG.md`](../audit/DEVELOPMENT_LOG.md).

| Paquete / Ventana Activa | Ventana de Implementación / Estado | Ventana de Activación y Observación | Criterio de Salida y Certificación |
| :--- | :--- | :--- | :--- |
| **Observación Continua y Estabilización de Planta (Horizonte V5.2 Cerrado)** | Completado y Certificado 2026-10-02 (`a483899`) | Observación continua 24/7 en producción activa | 4/4 mineros en hash nominal (~387.5 TH/s), Elevador 1 a 2500W (~5000W, margen 400W), Elevador 2 a 2700W (5397W), 0 deadlocks, modulación cerrada de fans, 1511 tests PASS. |
| **Spec 087: Monolith Decoupling Phase 3 (Balancer & Watchdog)** | Planificada (Post-observación V5.2) | Ventana controlada con dry-run y sombra | Desacoplamiento de `execute_balancer_cycle` y `check_autotune_watchdog` de `miner_monitor.py` a módulos puros de gobernanza, 0 regresiones. |

## Milestones

| Date | Milestone | Evidence required |
| --- | --- | --- |
| 2026-08-13 | Spec 020 release gate closed | Spec 020 T020, runtime logs and observed Telegram behavior. |
| 2026-08-14 | Spec 021 D+1 review | Scheduled liveness observation artifact and no open P0/P1. |
| 2026-08-16 | Spec 021 D+3 decision | Repeated liveness evidence and close/extend decision. |
| 2026-09-10 | Acquisition contract stable | Authoritative envelope and shadow comparison. |
| 2026-09-24 | Incident assessment available | Deterministic replay and confidence audit. |
| 2026-10-05 | Electrical decision made | Supported source or explicit blocked dependency. |
| 2026-10-19 | Local observability available | Prometheus/Grafana isolation and resource evidence. |
| 2026-10-29 | Hashcore surface known | Complete conservative inventory. |
| 2026-11-12 | Recoverability proven | Verified backup plus staging restore. |
| 2026-08-30 | Interface scope closed | Scorecard completed; no-build formal decision recorded with zero missing fields. |
| 2026-09-07 | V2 release decision | Complete matrix, 267.2h soak, docs audit and approve record. |
| 2026-09-07 | V3 Telegram Max & Intelligence (Specs 031-037) | All 7 modules implemented, tested and verified. |
| 2026-09-07 | V3 Release Decision (Spec 038) | 514 tests PASS, 267.3h soak, concurrency hardened, v3.0.0 approve record. |
| 2026-09-08 | V3.1 Governance & Autotuning (Specs 039-040) | Fan Governor and Dynamic Preset Balancer active in production. |
| 2026-09-08 | V3.2 Domain Reorganization & Shim Purge (Specs 041-042) | 22 shims purged, clean app/ structure, 587 tests PASS. |
| 2026-09-08 | V3.3 Interactive Control & Silent Mode (Specs 043-044) | RFC approved, 621 tests PASS, release audit verified, active in production under PID 58344. |
| 2026-09-09 | V3.4 Telegram Mobile UX Harmonization (Specs 045-047) | Centro de ayuda, navegación por categorías y todas las tarjetas adaptadas a <= 32 columnas, 687 tests PASS. |
| 2026-09-09 | V3.5 Safe Fleet Shutdown & Electrical Maintenance (Spec 048) | Selector táctil multiselección, purga térmica de 45s, maniobra física real validada en caliente, 721 tests PASS. |
| 2026-09-10 | V4 Governance & Safety Release (Specs 048-053) | Parada segura, purga térmica activa, post-blackout, corte de fase, scheduler y cerrojos reentrantes, 792 tests PASS. |
| 2026-09-10 | V4.0.1 Post-Blackout Persistence Hotfix | Blindaje físico de disco `fsync`, fallback `.bak`, scope de ciclo de mantenimiento y 797 tests PASS. |
| 2026-09-12 | V4.0.2 Silent Mode 30%-50% PWM & 82°C Autonomy (Spec 044) | Recalibración acústica 30%-50%, lazo cerrado a 82°C, elevadores independientes y 800 tests PASS. |
| 2026-09-12 | V4.0.3 Fan Governor Floor 30% Hotfix | Piso mínimo de 30% PWM en gobernador, independencia total por minero hacia 82.0°C y 802 tests PASS. |
| 2026-09-12 | Spec 054 Predictive Chain Diagnostics Closed | Colector asíncrono, SQLite v7, diagnóstico predictivo, UX /chains y CLI analítica certificados con 835 tests PASS. |
| 2026-09-12 | V4.1.1 Uptime Persistence & Sensor Accuracy Hotfix | Persistencia de last_elapsed, discriminación de sensores inactivos, purga DB y 837 tests PASS. |
| 2026-09-12 | V4.1.2 Gradient-Adaptive Fan Step-Down & Dwell Fix | Desescalado térmico adaptativo (-5%/-3%/-2%), dwell ágil de 60s en frío y 840 tests PASS. |
| 2026-09-13 | V4.1.3 Hashboard Failure Auto-Reboot (Spec 055) | Recuperación automática ante falla total de placas, 6 interlocks y 854 tests PASS. |
| 2026-09-13 | V4.1.4 Two-Tier Mining Recovery (Spec 056) | Soft Auto-Restart vs Hard Auto-Reboot y 881 tests PASS. |
| 2026-09-15 | V4.1.5 Intervention Governance & Contingency (Spec 057) | Modo Vnish Libre, toggle unificado en /menu y 902 tests PASS. |
| 2026-09-15 | V5.0 Modular Architecture & Foundation (Specs 058-060) | Desacoplamiento de Telegram, clientes de red y StateManager L1/L2, 958 tests PASS. |
| 2026-09-15 | V5.0.1 Hardware Resilience & Seasonality (Specs 061-063) | SQLite WAL mode, HW Error Tripwire y gobernador estacional, 993 tests PASS. |
| 2026-09-15 | V5.0.2 Supervisory Hooks & Multi-Miner UX (Specs 064-065) | Pipeline declarativo de hooks en CoreSupervisoryEngine y gráficos comparativos multi-miner, 1047 tests PASS. |
| 2026-09-15 | V5.0.3 Cold-Boot Fleet Grace Period Release (Spec 066) | Supresión de streaks de arranque, tarjeta 🟢 FLOTA RESTABLECIDA y 1062 tests PASS certificados en producción. |
| 2026-10-02 | Horizon V5.2 Closed & Operational Observation | All 16 directives harmonized, 4 miners hashing stable, 1511 tests PASS, zero deadlocks. |

## Review And Bug-Fix Rhythm

| Frequency | Activity | Output |
| --- | --- | --- |
| After every activation | Verify PID, mutex, config path/hash, QA mode, startup guard, EventStore, worker/heartbeat freshness and no immediate action. | Active spec `evidence.md`. |
| D+1 | Inspect false/missed alerts, command delivery, sample age, service health, database and auxiliary errors. | D+1 evidence plus issue priority. |
| D+3 | Repeat reliability review and close or extend the observation gate. | D+3 decision in evidence. |
| Wednesday | Triage P0/P1/P2 and recalculate later dates/dependencies. | Roadmap/calendar update when needed. |
| Friday | Full regression and documentation sweep; late deployment only for read-only or emergency work. | Test and `git diff --check` evidence. |
| First Monday monthly | Reliability review: missed/false alerts, restarts, actions, liveness, storage and collector health. | SQLite/metrics report and development-log summary. |

## Bug Priority And Response

| Priority | Definition | Response target | Calendar effect |
| --- | --- | --- | --- |
| P0 | Unsafe/duplicate action, missed sustained outage, secrets exposure, monitor unavailable or data-loss risk. | Immediate triage and same-day containment. | Stop all roadmap work; focused hotfix and full safety regression. |
| P1 | False critical alert, command silence, stale/contradictory status, delayed incident evidence or restore failure. | Within one working day. | Resolve in current review window; later dates move. |
| P2 | Wording, non-critical dashboard/log issue or documentation gap. | Weekly triage. | Batch into next read-only/docs window. |

## Definition Of Ready

A package starts only when:

- its predecessor exit gate and required D+1 review are complete;
- requirements, plan, tasks, contracts and checklist have no unresolved critical
  inconsistency;
- hardware/API samples exist or the work is explicitly discovery-only;
- action authority, rollback, validation and observation are written;
- elevated access, Docker or device access required for the package is available;
- no open production P0/P1 invalidates the baseline.

## Definition Of Done

A package closes only when:

- all tasks and acceptance scenarios have exact evidence;
- targeted/full tests and applicable syntax/config/PowerShell checks pass;
- state/action/polling invariants pass where relevant;
- controlled activation is observed when a long-lived component changed;
- backup/restore or rollback proof exists where persistence/runtime changes;
- D+1/D+3 (and longer package-specific soak) has no unresolved P0/P1;
- evidence, roadmap, calendar, strategy docs and development log agree;
- real config, state, backups, logs, credentials and addresses remain outside Git.

## Calendar Change Policy

- Update this file and `ROADMAP.md` in the same documentation change.
- Record the trigger and dependency impact in the active spec evidence.
- Do not backdate missed work or report an expired estimate as completed.
- Re-run the cross-spec dependency sweep when a package is split, added,
  reordered, blocked or deferred.


## Incidente térmico 2026-11-12 — prioridad P0
Hotfix probado (1557 tests y 75 subtests PASS) y activado a las 17:12:30 UTC-3.
Contención: techos de 2300/2000/2150/2000 W, piso nativo de 1740 W, ventilación al 100 %
y deduplicación térmica de 900 s por minero/tipo. ViaBTC activa en toda la flota.
No avanzar a otra spec hasta cierre. Observación inmediata: al menos 15 minutos desde
activación; calibración de M24 y revisión D+1 (13 de noviembre) quedan sujetas a evidencia.
El bloqueo administrativo inicial está resuelto. No hubo commit/push automático.
Ver docs/audit/STABILIZATION_REPORT_20261112_HEAT.md y evidencia de Spec 093.


## Revisión 2026-11-14 — powerups y avisos
La intención vigente es C3 dinámico (2700/2500/2700/2500), no los caps de calor del día12.
Suite1561+75 PASS; avisos de potencia real y gracia600 preparados. Recarga administrativa
pendiente; M26 sigue limitado a2000 hasta completar activación y observación escalonada.
No activar otra spec ni certificar release mientras R004 siga pendiente. La ventana de
observación se cuenta desde la recarga efectiva; no backdatear D+1 del incidente anterior.
Ver STABILIZATION_REPORT_20261114_POWERUP.md.


## Actualización efectiva — 2026-11-14 18:11 UTC-3
Superado el bloqueo anterior: servicio recargado17:59:24 con shaefa85f7d y nuevos avisos/gracia600.
Techos firmware y config alineados2700/2500/2700/2500; piso1740. M25 subió a2300W sin
reiniciar y generó aviso confirmado a18:08:56. M26 alineado sin reinicio. Cierre de la
observación y preflight final en curso; la política C3 dinámica sustituye caps temporales
del día12. No activar otra spec ni restaurar configuración antigua de contención.


## Cierre de reconciliación — 2026-11-14 18:17 UTC-3
PASS operativo/preflight8/8,1561tests+75subtests. Recarga17:59, observación18min,
powerupsM25/M26 y avisos confirmados. H004/R004 completadas; no quedan activaciones
pendientes. C3 dinámico2700/2500/2700/2500, piso1740; no restaurar caps temporales del día12.
RevisiónD+1 sugerida para15/11, sujeta a evidencia futura. Release/commit/push manuales;
no implementar otra spec antes del cierre de release exigido por la constitución.


## Reapertura por incidente compartido — 14/11/2026 noche
El cierre de18:19fue una verificación inmediata, no garantía de estabilidad prolongada.
A21:48:47/51,M25/M26 sufrieron chainbreak simultáneo a79°C y2300W estables. Se prioriza
estabilización093: correlación, None/QA, aislamiento de dry-run y techo empíricoM25a2500.
M23rise78por respuesta térmica; máximos2700/2500/2500/2500, ambos elevadores conprotecciones.
La identidad calle/elevador/protección queda pendiente de registroAC externo; no especular.
Ventana inmediata desde activación final22:11:33; revisiónD+1el15/11sujeta a evidencia futura.
No iniciar otra spec mientras haya implementación/release actual sin cerrar manualmente.
Ver docs/audit/PRODUCTION_STABILITY_20261114.md.


### Actualización nocturna — 14/11/2026 22:32 UTC-3
Despliegue final22:31:50 incluye potencia medida y tier persistido de recuperación segura.
Regresión1583+75PASS, preflight final en curso. La observación física de la tarde no cerró
el incidente compartido: sigue pendiente mediciónAC, fuera de la evidencia disponible.
Operación actual: máximos2700/2500/2500/2500, M23rise78 y resto79. Mantener regulación
nativa y protecciones; no forzar nominal ni deshabilitar guardas para subir rendimiento.


### Cierre técnico nocturno — 14/11/2026 22:37 UTC-3
SoftwarepreflightPASS8/8,1583+75PASS. Config997550ad y código final activos22:31:50.
Régimen físico observado~26min sin reinicios; cuatro mineros produciendo, M25/M26a2500W.
La causa física compartida sigue ABIERTA hasta mediciónAC. RevisiónD+1el15/11sujeta a
nueva evidencia; no declarar problema eléctrico resuelto por una prueba inmediata exitosa.
Sin commit/push automático; no ampliar límites antes de revisar estabilidad y evidencia.


## Ventana revisada — 2026-11-15

093M: una iteración de corrección, regresión y activación; observación inmediata yD+1.
094: siguiente trasrelease093manual;1iteración más observación24h del respaldo.
095: posterior a094;1iteraciónanalítica. Diagnóstico físico condicionadoamedicionesAC,
sinfecha prometida. No comprimir observación para cumplir estimaciones.


Cierre de la iteración M,15/11 15:19 UTC-3: software y observación inmediata PASS;
gate8/8 y1604+75 pruebas PASS. Correcciones activas desde15:13:46. D+1 pendiente.
094/095 siguen solo planificadas, dependientes de release093manual. Causa física abierta.
