# Plan de Implementación: Spec 084 — Governance Dashboard (`/directivas`) & Snapshot Persistence (PROP-020)

**Branch**: `codex/022-adaptive-acquisition` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/084-governance-dashboard/spec.md`

---

## Resumen Ejecutivo

Implementar un panel interactivo de observabilidad de directivas de gobernanza para Telegram (`/directivas`, `/gov_status`, `/gov`), permitiendo al operador diagnosticar en tiempo real y en menos de 10 segundos el estado de las 16 directivas en sus 5 capas de prevalencia (P0–P4), el motivo exacto de retención o compuerta bloqueada, y las métricas térmicas/eléctricas de cada minero.
Complementariamente, establecer la persistencia estructurada y periódica de `governance_snapshots` en SQLite (`EventStore`) para auditoría forense (base para Spec 086), y un **Watchdog Proactivo de Deadlocks** que detecte y alerte cuando un minero permanezca atrapado por más de 300 segundos en `ACTION_RECOVERY_MAX_COOLING` sin converger hacia la potencia objetivo.

---

## Technical Context

**Language/Version**: Python 3.10+ (entorno de ejecución virtualenv activo en Windows, compatible con Python 3.14).

**Primary Dependencies**:
- `app.governance.governance_context.MinerGovernanceContext` (Spec 082)
- `app.telegram.commands.base.BaseCommandHandler` (Spec 058)
- `app.telegram.router.TelegramCommandRouter`
- `app.core.event_store.EventStore`
- `app.governance.elevator_budget`
- `app.governance.facility_agent`

**Storage**: SQLite WAL mode (`miner_alerts.db`), tabla aditiva `governance_snapshots` con índices temporales y por minero.

**Testing**: `pytest` con tests unitarios, formateo visual móvil y pruebas de persistencia en `tests/test_governance_dashboard.py`.

**Target Platform**: Windows 11 / Windows Server, servicio NSSM `MinerAlerts`, bot de Telegram con ancho estricto $\le 32$ columnas.

**Performance Goals**:
- Generación de tarjeta de directivas $\le 2\text{ ms}$.
- Persistencia de instantáneas en SQLite $\le 5\text{ ms}$ por tick de monitoreo.
- Respuesta en Telegram $\le 1.5\text{ s}$.

**Constraints**:
- **Mobile-First Estricto**: Todo mensaje o tarjeta debe tener un ancho máximo de 32 columnas.
- **Cero disrupción**: No altera presets ni interrumpe el ciclo de hash.
- **Protección de secretos**: `app/config.json` y `app/state.json` no se exponen ni modifican.
- **Sin falsas alarmas de deadlock**: Cooldown de 1800s para alertas proactivas y supresión durante calentamiento inicial (`is_warming_up=True`).

---

## Constitution Check

| Principio | Estado | Justificación / Salvaguarda |
| :--- | :---: | :--- |
| **P0 – Seguridad de Hardware** | ✅ PASS | Operación de solo lectura y observabilidad; no modifica hardware ni elude protecciones P0. |
| **P1 – Control de Intervención** | ✅ PASS | El panel visualiza directivas sin forzar transiciones involuntarias. |
| **P2 – Telemetría No Bloqueante** | ✅ PASS | Lectura pura desde `MinerGovernanceContext` e inserción en SQLite vía WAL sin locks de larga duración. |
| **P3 – Mobile-First Telegram** | ✅ PASS | Cumple estrictamente la regla de $\le 32$ columnas en tarjetas monoespaciadas. |
| **P4 – Persistencia Atómica** | ✅ PASS | Nueva tabla `governance_snapshots` con índices y migración segura en `EventStore._create_schema()`. |

---

## Arquitectura de la Solución

```
                                  ┌───────────────────────────────┐
                                  │      Ciclo de Monitoreo       │
                                  │       (miner_monitor.py)      │
                                  └───────────────┬───────────────┘
                                                  │
                                                  ▼
                       ┌─────────────────────────────────────────────────────┐
                       │ Construcción de MinerGovernanceContext por minero   │
                       └──────────────────────────┬──────────────────────────┘
                                                  │
               ┌──────────────────────────────────┴──────────────────────────────────┐
               ▼                                                                     ▼
┌──────────────────────────────┐                                      ┌──────────────────────────────┐
│ app/governance/              │                                      │ Deadlock Watchdog            │
│ directives_dashboard.py      │                                      │ (recovery_cooling > 300s)    │
│                              │                                      └──────────────┬───────────────┘
│ - build_fleet_directives_card│                                                     │ Si deadlock detectado:
│ - build_miner_directive_card │                                                     ▼
│ - Formato <= 32 cols         │                                      ┌──────────────────────────────┐
└──────────────┬───────────────┘                                      │ Alerta Proactiva Telegram    │
               │                                                      │ (cooldown 1800s por minero)  │
               ▼                                                      └──────────────────────────────┘
┌──────────────────────────────┐                                                     │
│ Telegram Command Handler     │                                                     │
│ /directivas [minero]         │                                                     │
│ (app/telegram/commands/      │                                                     │
│  directives.py)              │                                                     │
└──────────────┬───────────────┘                                                     │
               │                                                                     │
               ▼                                                                     ▼
┌──────────────────────────────┐                                      ┌──────────────────────────────┐
│ Operador Móvil Telegram      │                                      │ EventStore SQLite            │
│ (Visualización instantánea)  │                                      │ (governance_snapshots)       │
└──────────────────────────────┘                                      └──────────────────────────────┘
```

### Componentes y Módulos

1. **`app/governance/directives_dashboard.py` (NUEVO)**:
   - Funciones puras desacopladas para construir las tarjetas de directivas:
     - `build_fleet_directives_card(contexts: List[MinerGovernanceContext], now_ts: float) -> str`
     - `build_miner_directive_card(ctx: MinerGovernanceContext, elevator_state: Any, now_ts: float) -> str`
   - Formato visual monoespaciado con cajas ASCII y badges legibles ($\le 32$ caracteres).

2. **`app/telegram/commands/directives.py` (NUEVO)**:
   - Handler `DirectivesCommand` heredando de `BaseCommandHandler`.
   - Nombres y aliases: `/directivas`, `/gov_status`, `/gov`, `/directives`.
   - Soporte para invocación global `/directivas` o detallada `/directivas 24`.

3. **`app/core/event_store.py` (ACTUALIZACIÓN ADITIVA)**:
   - DDL para `governance_snapshots`:
     `id, created_ts, miner_name, fan_action, fan_duty, target_power_w, current_power_w, chip_temp_c, fga_cohort, fga_r_th, elevator_group, elevator_gate_status, solar_envelope_active, contingency_mode, restart_required, is_deadlocked, details_json`.
   - Índices: `ix_gov_snapshots_created`, `ix_gov_snapshots_miner`.
   - Métodos: `record_governance_snapshot()`, `get_recent_governance_snapshots()`.
   - Integración con `cleanup_retention()`.

4. **`app/miner_monitor.py` (INTEGRACIÓN SUPERVISADA)**:
   - Inserción periódica de instantánea en cada tick tras el paso del Fan Governor.
   - Detección de `is_deadlocked`: `action == ACTION_RECOVERY_MAX_COOLING` y `recovery_duration > 300.0s`.
   - Envío de alerta proactiva con cooldown de 1800s.

5. **`app/telegram/router.py` (REGISTRO)**:
   - Registro de `DirectivesCommand` en `create_default_command_router()`.
