# Ventanas de entrega y observación

> Tipo: planificación temporal · Revisión: 2026-11-16 · Zona: America/Argentina/Buenos_Aires (UTC-3).

Las fechas estiman trabajo; no certifican ejecución ni autorizan actuaciones. No
se crearon recordatorios o automatizaciones al normalizar este documento.

## Ventana vigente

| Paquete | Implementación y activación | Observación | Pendiente |
|---|---|---|---|
| 094 | Cerrada y publicada | Backup automático 16/11 a 03:00 verificado | Capacidad y decisión de retención |
| 096 | Código validado; recarga final 16/11 a 11:06:28 | Capturas 11:06:49–11:17:49:660.1 s sin reinicios | D+1 bajo calor diurno; código publicado como `3028a18` |
| 095 | No activa | Inicia tras cierre 096 | Análisis de disponibilidad/rendimiento; medición física cuando exista fuente |

Una revisión D+1 requiere un intervalo completo posterior al cambio efectivo y
comprobar continuidad; llegar al 17/11 no la aprueba automáticamente. Las recargas,
cambios de código o de política que afecten el resultado reinician la ventana pertinente.
Los tiempos de diagnóstico físico no se prometen sin acceso a la medición externa.

## Reglas de planificación

- Los incidentes de planta P0/P1 tienen prioridad sobre el calendario de funcionalidades.
- Implementación, validación, activación y observación son etapas distintas.
- No superponer cambios de actuadores de distintas specs.
- No comprimir soak o gates para alcanzar una fecha estimada.
- Reservar una iteración de corrección si aparecen fallas; registrar la reapertura.
- Mantener las restricciones de ventana operativa y excepciones de emergencia ya
  establecidas por el proyecto. Un documento no concede autorización de despliegue.

## Evidencia y antecedentes

- [Corte documentado](../operations/PRODUCTION_BASELINE.md).
- [Informe 096](../audit/STABILIZATION_REPORT_20261116_RESTART_SAFETY.md).
- [Plan temporal anterior](../archive/documentation-20261116/docs/speckit/DELIVERY_PLAN.md), con hitos y reaperturas históricas preservados.
- [Programa y gates](SPEC_PROGRAM.md).
