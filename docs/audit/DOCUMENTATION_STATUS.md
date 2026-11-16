# Estado y autoridad documental

> Tipo: matriz de mantenimiento · Revisión: 2026-11-16 · No es un semáforo de salud de planta.

| Familia | Fuente canónica | Estado documental |
|---|---|---|
| Entrada general | [docs/README](../README.md) | Índice normalizado por necesidad de lectura |
| Operación | [operations/README](../operations/README.md) | Procedimientos contrastados con rutas/opciones actuales |
| Configuración pública | [config.example.json](../../app/config.example.json) | Ejemplo; no afirmar que representa la instancia real |
| Arquitectura | [SYSTEM_OVERVIEW](../architecture/SYSTEM_OVERVIEW.md) | Contraste estático; no certifica despliegue auxiliar |
| Planificación | [ROADMAP](../speckit/ROADMAP.md), [programa](../speckit/SPEC_PROGRAM.md), [ventanas](../speckit/DELIVERY_PLAN.md) | Responsabilidades diferenciadas y rutas estables |
| Feature activa | [feature.json](../../.specify/feature.json) | No modificada en la normalización |
| Instrucciones | [AGENTS](../../AGENTS.md), [constitución](../../.specify/memory/constitution.md) | Reglas del proyecto; paths documentales alineados |
| Runtime | [PRODUCTION_BASELINE](../operations/PRODUCTION_BASELINE.md) | Corte 16/11 a 11:18; no lectura nueva de planta |
| Evidencia fechada | [audit/README](README.md) | Contexto y límites conservados |
| Bitácora | [DEVELOPMENT_LOG](DEVELOPMENT_LOG.md) | Preservación byte por byte; índice externo |
| Histórico | [archive/README](../archive/README.md) | Separado de procedimientos vigentes |
| Specs | [specs/](../../specs) | Fuera del alcance de esta organización; sin modificaciones |

## Validación y límites

La [normalización](DOCUMENTATION_NORMALIZATION_20261116.md) registra rutas, comprobaciones,
hashes, enlaces y salvedades. El [inventario previo](DOCUMENTATION_INVENTORY_20261116.md)
continúa siendo un corte fechado y no se presenta como un catálogo posterior a los movimientos.
La revisión documental no ejecutó mineros, scheduler, deployments ni pruebas de runtime.
Los límites del stack opcional se describen en [observabilidad](../operations/OBSERVABILITY.md).
