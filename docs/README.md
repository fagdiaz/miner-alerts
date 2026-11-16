# Documentación de Miner Alerts

> Tipo: índice principal · Revisión: 2026-11-16 · Alcance: documentación fuera de `specs/`.

## Elegir una ruta de lectura

| Necesidad | Punto de entrada |
|---|---|
| Operar o diagnosticar la planta | [Operación](operations/README.md) |
| Instalar o configurar una instancia | [Instalación](operations/INSTALLATION.md) y [configuración](operations/CONFIGURATION.md) |
| Entender procesos, datos y límites | [Arquitectura](architecture/README.md) |
| Desarrollar, probar y preparar una entrega | [Desarrollo](development/README.md) |
| Conocer prioridades y dependencias | [Planificación](speckit/README.md) |
| Revisar evidencias y cambios | [Auditoría](audit/README.md) |
| Consultar decisiones anteriores | [Archivo histórico](archive/README.md) |
| Mantener la documentación | [Política documental](governance/DOCUMENTATION_POLICY.md) |

## Estructura

```text
docs/
  operations/     Procedimientos y referencia de operación
  architecture/   Diseño actual y decisiones tecnológicas
  development/    Flujo de trabajo, validación y releases
  governance/     Reglas de mantenimiento documental
  speckit/        Backlog, programa y ventanas; rutas contractuales estables
  audit/          Bitácora, índices, inventarios e informes fechados
  proposals/      Registro de propuestas; no equivale al backlog vigente
  archive/        Antecedentes y cortes históricos identificados
```

## Autoridad de las fuentes

| Tema | Fuente |
|---|---|
| Reglas del agente y principios del proyecto | [AGENTS.md](../AGENTS.md) y [constitución](../.specify/memory/constitution.md) |
| Feature activa | [.specify/feature.json](../.specify/feature.json) |
| Prioridad pendiente | [ROADMAP](speckit/ROADMAP.md) |
| Secuencia, dependencias y gates | [SPEC_PROGRAM](speckit/SPEC_PROGRAM.md) |
| Ventanas de implementación y observación | [DELIVERY_PLAN](speckit/DELIVERY_PLAN.md) |
| Salud y resultados de producción | Evidencia fechada y logs; [último corte documentado](operations/PRODUCTION_BASELINE.md) |
| Historial completo | [DEVELOPMENT_LOG](audit/DEVELOPMENT_LOG.md), preservado íntegramente |

El estado de un informe fechado se interpreta en su ventana. Un índice no sustituye
una lectura en vivo ni convierte un seguimiento pendiente en un resultado aprobado.
Las rutas antiguas que conservan enlaces de compatibilidad indican su destino actual.

## Trazabilidad de esta organización

- [Inventario previo](audit/DOCUMENTATION_INVENTORY_20261116.md) y su CSV: corte anterior a la reorganización.
- [Registro de migración y validación](audit/DOCUMENTATION_NORMALIZATION_20261116.md).
- [Copia histórica de documentos sustituidos](archive/documentation-20261116/README.md).
- [Índice de la bitácora](audit/DEVELOPMENT_LOG_INDEX.md): navegación sin alterar el original.
