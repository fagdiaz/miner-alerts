# Tasks: Spec 084 — Governance Dashboard (`/directivas`) (PROP-020)

**Feature**: `084-governance-dashboard`
**Fecha**: 2026-10-01
**Prioridad**: P2 — Observabilidad y Confiabilidad
**Riesgo**: BAJO (observabilidad en tiempo real, persistencia aditiva y watchdog de alertas)
**Modelo recomendado**: Gemini 3.8 Flash High (Primary Engine)

---

## Fase 0 — Reconocimiento y Mapeo Previo

- [x] **T0.1** Revisar la definición de `MinerGovernanceContext` en `app/governance/governance_context.py` y `app/governance/elevator_budget.py`.
- [x] **T0.2** Revisar la estructura de comandos desacoplados en `app/telegram/commands/base.py` y `app/telegram/router.py`.
- [x] **T0.3** Mapear el ciclo de evaluación del Fan Governor en `app/miner_monitor.py` (L3470-3620) para ubicar el hook de snapshot y el deadlock watchdog.
- [x] **T0.4** Revisar el DDL y métodos de `EventStore` en `app/core/event_store.py`.

## Fase 1 — Persistencia de `governance_snapshots` en SQLite (EventStore)

- [x] **T1.1** Agregar DDL de la tabla `governance_snapshots` e índices (`ix_gov_snapshots_created`, `ix_gov_snapshots_miner`) en `app/core/event_store.py`.
- [x] **T1.2** Implementar método `record_governance_snapshot()` con soporte para campos opcionales, JSON details y transacciones WAL.
- [x] **T1.3** Implementar método `get_recent_governance_snapshots()` con filtrado opcional por minero y limitador de resultados.
- [x] **T1.4** Integrar depuración periódica de `governance_snapshots` en `cleanup_retention()` de `EventStore`.
- [x] **T1.5** Validar sintaxis: `py_compile app/core/event_store.py`.

## Fase 2 — Módulo Formateador de Directivas (`app/governance/directives_dashboard.py`)

- [x] **T2.1** Crear dataclass `GovernanceSnapshot` para modelado inmutable de instantáneas.
- [x] **T2.2** Implementar función pura `build_fleet_directives_card()` para resumen compacto de flota en $\le 32$ columnas.
- [x] **T2.3** Implementar función pura `build_miner_directive_card()` con desglose exhaustivo de las 5 capas de directivas (P0–P4) en $\le 32$ columnas.
- [x] **T2.4** Validar sintaxis: `py_compile app/governance/directives_dashboard.py`.

## Fase 3 — Watchdog Proactivo de Deadlocks de Enfriamiento

- [x] **T3.1** Definir función pura de detección `evaluate_recovery_deadlock(action, recovery_since_ts, now_ts, is_warming_up) -> bool`.
- [x] **T3.2** Implementar lógica de dispatch de alerta proactiva con cooldown de 1800s por minero para evitar spam.
- [x] **T3.3** Formatear mensaje de alerta de deadlock con ancho móvil $\le 32$ columnas.

## Fase 4 — Handler de Telegram (`app/telegram/commands/directives.py`)

- [x] **T4.1** Crear clase `DirectivesCommand` heredando de `BaseCommandHandler` con nombres y aliases (`/directivas`, `/gov_status`, `/gov`, `/directives`).
- [x] **T4.2** Implementar enrutamiento para vista global `/directivas` o detallada `/directivas <minero>`.
- [x] **T4.3** Registrar `DirectivesCommand` en `create_default_command_router()` de `app/telegram/router.py`.
- [x] **T4.4** Validar sintaxis: `py_compile app/telegram/commands/directives.py` y `py_compile app/telegram/router.py`.

## Fase 5 — Integración en el Loop de Monitoreo (`app/miner_monitor.py`)

- [x] **T5.1** Integrar en `_evaluate_fan_governor_fleet()` o tick principal la llamada a `record_governance_snapshot()` para cada minero.
- [x] **T5.2** Integrar la evaluación del deadlock watchdog y el envío seguro de la alerta proactiva.
- [x] **T5.3** Validar sintaxis: `py_compile app/miner_monitor.py`.

## Fase 6 — Suite de Pruebas Automatizadas

- [x] **T6.1** Crear archivo de pruebas `tests/test_governance_dashboard.py`.
- [x] **T6.2** Test de DDL, inserción y recuperación en `EventStore`.
- [x] **T6.3** Test de verificación estricta de ancho de columnas ($\le 32$ chars/línea) en tarjetas de flota y minero individual.
- [x] **T6.4** Test de detección de deadlock en `evaluate_recovery_deadlock()` y comportamiento de cooldown de alerta.
- [x] **T6.5** Test de ejecución del comando `/directivas` a través de `TelegramCommandRouter`.
- [x] **T6.6** Ejecutar `pytest tests/test_governance_dashboard.py -v` → 100% PASS.

## Fase 7 — Control de Calidad y Preflight (`speckit-qa`)

- [x] **T7.1** Ejecutar `speckit-qa` (verificación de compuertas de seguridad, sintaxis y consistencia).
- [x] **T7.2** Ejecutar suite global: `pytest -x -q` (1477+ tests PASS, 0 fallos).

## Fase 8 — Evidencia, Documentación y Cierre

- [x] **T8.1** Generar `specs/084-governance-dashboard/evidence.md` con comandos ejecutados y resultados de pruebas.
- [x] **T8.2** Registrar entrada newest-first en `docs/audit/DEVELOPMENT_LOG.md`.
- [x] **T8.3** Actualizar `docs/speckit/ROADMAP.md` y `docs/speckit/SPEC_PROGRAM.md`.
- [x] **T8.4** Ejecutar `speckit-stabilize` (8 gates).
- [x] **T8.5** Reiniciar servicio NSSM `MinerAlerts` y verificar logs en producción.
- [x] **T8.6** Actualizar `prompt.txt` con el nuevo baseline para la siguiente sesión.
