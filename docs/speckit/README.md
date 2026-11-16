# Planificación y ejecución con Spec Kit

> Tipo: índice de planificación · Revisión: 2026-11-16.

| Fuente | Responsabilidad |
|---|---|
| [.specify/feature.json](../../.specify/feature.json) | Selección de la única feature activa |
| [ROADMAP](ROADMAP.md) | Prioridades y pendientes de trabajo |
| [SPEC_PROGRAM](SPEC_PROGRAM.md) | Secuencia, dependencias, riesgo y gates |
| [DELIVERY_PLAN](DELIVERY_PLAN.md) | Ventanas y criterios temporales de observación |
| [Constitución](../../.specify/memory/constitution.md) | Principios del proyecto |
| [AGENTS](../../AGENTS.md) | Instrucciones de ejecución |

Las specs se conservan en [specs/](../../specs). Esta reorganización no modifica
sus artefactos ni selecciona una nueva feature. Los manuales se encuentran en
[operación](../operations/README.md); la arquitectura en su [sección propia](../architecture/README.md).

## Flujo

Diseño → plan → tareas → QA aplicable → implementación → validación → estabilización
→ publicación manual → observación sustentada por evidencia. El proyecto limita la
implementación a una spec por vez. Diseñar una futura no la activa.

Los comandos de Spec Kit y sus extensiones quedan subordinados a las reglas de Git
manual y seguridad del proyecto. Ver [desarrollo](../development/WORKFLOW.md).

## Historia

Las anteriores descripciones de versiones, porcentajes y fases están preservadas
como [corte histórico del 16/11](../archive/documentation-20261116/README.md).
Para resultados y fechas exactas, consultar el [índice de la bitácora](../audit/DEVELOPMENT_LOG_INDEX.md).
