# Miner Alerts — Speckit Archive

Este directorio almacena documentos estratégicos, evaluaciones técnicas y planes de expansión que alcanzaron su **disposición terminal** o fueron **completamente implementados y certificados** en producción.

Se conservan aquí para trazabilidad histórica, auditoría de arquitectura y contexto forense, evitando saturar la raíz de `docs/speckit/` con documentos que ya no representan guías operativas vivas.

---

## Índice de Documentos Archivados

| Documento | Contexto Original | Disposición Terminal / Estado | Ubicación de la Solución Viva |
|---|---|---|---|
| [`HASHCORE_TOOLKIT_STRATEGY.md`](HASHCORE_TOOLKIT_STRATEGY.md) | Estrategia de inventario de capacidades e integración con Hashcore Toolkit CLI (Spec 026). | **`accepted`**: Conexión CLI de solo lectura y acciones click-safe (`reboot`/`restart`) implementadas y congeladas. | [`../RUNBOOK.md`](../RUNBOOK.md) y [`app/miner_monitor.py`](../../../app/miner_monitor.py) |
| [`INTERFACE_STRATEGY.md`](INTERFACE_STRATEGY.md) | Evaluación de interfaces de operador y viabilidad de servidor FastAPI/web (Spec 027). | **`no_build`**: Scorecard operativo confirmó cobertura 100% con Telegram, Grafana y dashboard HTML estático sin añadir superficie de ataque. | [`../TECHNOLOGY_STRATEGY.md`](../TECHNOLOGY_STRATEGY.md) |
| [`V3_EXPANSION_PLAN.md`](V3_EXPANSION_PLAN.md) | Plan estratégico inicial para la iniciativa Telegram Max y Monitor Engine V3 (Specs 031 a 038). | **`certified`**: El 100% de las capacidades planificadas fueron implementadas y certificadas en producción. | [`../ROADMAP.md`](../ROADMAP.md) y [`../../audit/DEVELOPMENT_LOG.md`](../../audit/DEVELOPMENT_LOG.md) |
| [`plans/ACTION_PLAN_V5_MODULARIZATION.md`](plans/ACTION_PLAN_V5_MODULARIZATION.md) | Plan de modularización y desacople arquitectónico del núcleo del monitor (Specs 056 a 060). | **`certified`**: Arquitectura Clean Core (`app/core/`, `app/governance/`, `app/interfaces/`) 100% implementada y probada. | [`../ROADMAP.md`](../ROADMAP.md) y [`../../audit/DEVELOPMENT_LOG.md`](../../audit/DEVELOPMENT_LOG.md) |
| [`plans/ACTION_PLAN_POST_V5_EVOLUTION.md`](plans/ACTION_PLAN_POST_V5_EVOLUTION.md) | Plan de evolución post-V5 para blindaje térmico, tripwires y mitigaciones (Specs 061 a 066). | **`certified`**: Todas las mitigaciones de hardware, tripwires y grace periods 100% certificadas. | [`../ROADMAP.md`](../ROADMAP.md) y [`../../audit/DEVELOPMENT_LOG.md`](../../audit/DEVELOPMENT_LOG.md) |
| [`plans/ACTION_PLAN_V5_1_HORIZON.md`](plans/ACTION_PLAN_V5_1_HORIZON.md) | Especificación del horizonte V5.1 de alta disponibilidad, watchdog IPC y telemetría profunda (Specs 067 a 070). | **`certified`**: Named pipe IPC, hooks desacoplados y predicción de fallos 100% completados. | [`../ROADMAP.md`](../ROADMAP.md) y [`../../audit/DEVELOPMENT_LOG.md`](../../audit/DEVELOPMENT_LOG.md) |
| [`plans/ACTION_PLAN_REPO_CLEANUP_AND_ROADMAP.md`](plans/ACTION_PLAN_REPO_CLEANUP_AND_ROADMAP.md) | Plan de saneamiento, consolidación de SQLite pool, unificación de estado y clientes (Specs 071 a 073). | **`certified`**: WAL mode, reuso de clientes de red y auditoría de configuración 100% finalizadas. | [`../ROADMAP.md`](../ROADMAP.md) y [`../../audit/DEVELOPMENT_LOG.md`](../../audit/DEVELOPMENT_LOG.md) |

---

## Documentación Activa y de Referencia Viva

Para la operación actual, desarrollo de nuevas specs y registro de cambios, referirse a:

- **Backlog y Cola de Entregas Activa**: [`../ROADMAP.md`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/speckit/ROADMAP.md)
- **Manual Operativo y Comandos Telegram**: [`../RUNBOOK.md`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/speckit/RUNBOOK.md)
- **Marco Programático de Specs y Gates**: [`../SPEC_PROGRAM.md`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/speckit/SPEC_PROGRAM.md)
- **Calendario y Ventanas de Estabilización**: [`../DELIVERY_PLAN.md`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/speckit/DELIVERY_PLAN.md)
- **Estrategia Tecnológica y Principios de Arquitectura**: [`../TECHNOLOGY_STRATEGY.md`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/speckit/TECHNOLOGY_STRATEGY.md)
- **Historial Completo de Specs y Decisiones**: [`../../audit/DEVELOPMENT_LOG.md`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/audit/DEVELOPMENT_LOG.md)
