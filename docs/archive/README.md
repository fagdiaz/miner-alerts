# Repositorio de Archivo Histórico — Miner Alerts

Este directorio centraliza los registros, propuestas cerradas, diagnósticos tempranos, solicitudes de comentarios (RFCs) y planes de fases previas ya completadas y certificadas en producción. Su propósito es preservar la trazabilidad histórica completa sin contaminar el backlog activo ni confundir a los operadores y agentes de IA.

---

## Estructura del Archivo Histórico

```
docs/archive/
├── proposals/               <-- Propuestas históricas completadas (PROP-001 a PROP-021)
├── historical_rfcs/         <-- RFCs de Telegram y UX móvil implementadas (V3.x)
├── historical_plans/        <-- Planes de acción de fases cerradas (V3, V4, V5, V5.1)
├── historical_audits/       <-- Auditorías previas de directivas y QA consolidadas
├── historical_diagnostics/  <-- Capturas y baselines de telemetría de julio/agosto 2026
└── historical_artifacts/    <-- Artefactos de pruebas de recuperación y fases previas
```

---

## Política de Inmutabilidad y Trazabilidad

1. Los archivos bajo este directorio son de **solo lectura histórica**. No deben modificarse a menos que se requiera corregir enlaces rotos o normalizar codificaciones.
2. Para consultar la bitácora canónica inmutable de desarrollo, remitirse a [`docs/audit/DEVELOPMENT_LOG.md`](../audit/DEVELOPMENT_LOG.md).
3. Para consultar el estado vivo y la planificación activa, remitirse a [`docs/speckit/ROADMAP.md`](../speckit/ROADMAP.md) y [`docs/speckit/SPEC_PROGRAM.md`](../speckit/SPEC_PROGRAM.md).
