# Miner Alerts — Speckit Archive

Este directorio almacena documentos estratégicos, evaluaciones técnicas y planes de expansión que alcanzaron su **disposición terminal** o fueron **completamente implementados y certificados** en producción.

Se conservan aquí para trazabilidad histórica, auditoría de arquitectura y contexto forense, evitando saturar la raíz de `docs/speckit/` con documentos que ya no representan guías operativas vivas.

---

## Índice de Documentos Archivados

| Documento | Contexto Original | Disposición Terminal / Estado | Ubicación de la Solución Viva |
|---|---|---|---|
| [`HASHCORE_TOOLKIT_STRATEGY.md`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/speckit/archive/HASHCORE_TOOLKIT_STRATEGY.md) | Estrategia de inventario de capacidades e integración con Hashcore Toolkit CLI (Spec 026). | **`accepted`**: Conexión CLI de solo lectura y acciones click-safe (`reboot`/`restart`) implementadas y congeladas. | [`RUNBOOK.md`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/speckit/RUNBOOK.md) y [`app/miner_monitor.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py) |
| [`INTERFACE_STRATEGY.md`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/speckit/archive/INTERFACE_STRATEGY.md) | Evaluación de interfaces de operador y viabilidad de servidor FastAPI/web (Spec 027). | **`no_build`**: Scorecard operativo confirmó cobertura 100% con Telegram, Grafana y dashboard HTML estático sin añadir superficie de ataque. | [`docs/speckit/TECHNOLOGY_STRATEGY.md`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/speckit/TECHNOLOGY_STRATEGY.md) |
| [`V3_EXPANSION_PLAN.md`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/speckit/archive/V3_EXPANSION_PLAN.md) | Plan estratégico inicial para la iniciativa Telegram Max y Monitor Engine V3 (Specs 031 a 038). | **`certified`**: El 100% de las capacidades planificadas (Inline Keyboards, `/chart`, `/snooze`, `/digest`, Fan Health `/fans`, Eficiencia `/efficiency`, Autotuning `/presets`, y V3 Release) fueron implementadas y certificadas en producción. | [`docs/speckit/ROADMAP.md`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/speckit/ROADMAP.md) y [`docs/audit/DEVELOPMENT_LOG.md`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/audit/DEVELOPMENT_LOG.md) |

---

## Documentación Activa y de Referencia Viva

Para la operación actual, desarrollo de nuevas specs y registro de cambios, referirse a:

- **Backlog y Cola de Entregas Activa**: [`../ROADMAP.md`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/speckit/ROADMAP.md)
- **Manual Operativo y Comandos Telegram**: [`../RUNBOOK.md`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/speckit/RUNBOOK.md)
- **Marco Programático de Specs y Gates**: [`../SPEC_PROGRAM.md`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/speckit/SPEC_PROGRAM.md)
- **Calendario y Ventanas de Estabilización**: [`../DELIVERY_PLAN.md`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/speckit/DELIVERY_PLAN.md)
- **Estrategia Tecnológica y Principios de Arquitectura**: [`../TECHNOLOGY_STRATEGY.md`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/speckit/TECHNOLOGY_STRATEGY.md)
- **Historial Completo de Specs y Decisiones**: [`../../audit/DEVELOPMENT_LOG.md`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/audit/DEVELOPMENT_LOG.md)
