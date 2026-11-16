# Operación

> Tipo: índice operativo · Revisión: 2026-11-16.

| Documento | Uso |
|---|---|
| [RUNBOOK](RUNBOOK.md) | Consultas iniciales, tratamiento de incidentes y recarga del monitor |
| [Instalación](INSTALLATION.md) | Preparación de un entorno nuevo y ejecución controlada |
| [Configuración](CONFIGURATION.md) | Archivos, precedencia, secretos y grupos de parámetros |
| [Telegram](TELEGRAM.md) | Catálogo y separación entre consultas y controles |
| [Política térmica y de potencia](THERMAL_AND_POWER.md) | VNish, guardas, techos y recuperación |
| [Diagnóstico](DIAGNOSTICS.md) | Evidencia por capas y herramientas de consulta |
| [Respaldo y restauración](BACKUP_AND_RESTORE.md) | Scheduler, validación, staging y retención |
| [Observabilidad](OBSERVABILITY.md) | Heartbeat, watchdog, métricas y dashboards |
| [Corte de producción](PRODUCTION_BASELINE.md) | Último resultado fechado y pendientes reales |

Para una falla nueva, comenzar por consultas y conservar la línea temporal. Una
lectura aislada, una tensión DC o un descenso de temperatura no prueban por sí solos
una falla de la red eléctrica ni justifican un reinicio.
