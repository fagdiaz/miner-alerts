# Backlog y prioridades

> Tipo: planificación vigente · Revisión: 2026-11-16.

La feature activa se determina mediante [.specify/feature.json](../../.specify/feature.json).
La secuencia y los gates están en [SPEC_PROGRAM](SPEC_PROGRAM.md); las ventanas en
[DELIVERY_PLAN](DELIVERY_PLAN.md). Este backlog no sustituye una medición en vivo.

## Estado documentado

| Paquete | Estado al corte 16/11/2026 |
|---|---|
| 093 | Publicada como `0695385` |
| 094 | Publicada como `a8ce841`; respaldo automático de 03:00 verificado |
| 096 | Publicada como `3028a18`, desplegada y observada 660.1 s; D+1 pendiente |
| 095 | Planificada, analítica y sin activación; espera el cierre 096 |

El [corte de producción](../operations/PRODUCTION_BASELINE.md) centraliza números,
techos y límites. La secuencia 096 antes de 095 responde al incidente de planta y
no altera la numeración histórica de las specs.

## Prioridades abiertas

| ID | Prioridad | Trabajo | Evidencia de cierre |
|---|---|---|---|
| OP-01 | P0 | Diagnosticar los chain breaks físicos de M26 y validar su contención a 2300 W | Registro de fuenteAC / PSU / conexiones y ventana sostenida; sin inferirAC desdeDC |
| OP-02 | P0 | Completar observación D+1 del arreglo 096 bajo calor diurno | Historial continuo, temperaturas, placas, intervenciones y TH efectivos |
| DATA-01 | P1 | Definir capacidad y retención de backups | Dry-run revisado y conservación de generaciones verificadas; sin borrado automático habilitado por esta edición |
| PERF-01 | P1 | Ejecutar el análisis 095 después del cierre 096 | Exposición normalizada, downtime, TH efectivos, costos y datos AC; fase de solo lectura |
| INFRA-01 | P2 | Revalidar el stack opcional de observabilidad | Dockerfile y publicación de puertos contrastados; no certificar stack por mera presencia de manifiestos |

Los incidentes P0/P1 interrumpen la expansión de funcionalidades. Mantener las
protecciones, la regulación nativa y la separación de diagnósticos y actuaciones.
Una entrega de Telegram con respuesta perdida todavía puede duplicar un aviso;
no se afirma una garantía exactamente-una-vez ni un outbox persistente.

## Reglas de actualización

Registrar hechos en evidencia y bitácora; actualizar aquí solo cambios de estado y
prioridad. No calcular un porcentaje global sumando tareas de paquetes heterogéneos,
ni considerar cerrado un riesgo físico por tests aprobados.

## Histórico preservado

El catálogo detallado de avances, propuestas y estados anteriores está en el
[roadmap anterior](../archive/documentation-20261116/docs/speckit/ROADMAP.md) y en
la [bitácora](../audit/DEVELOPMENT_LOG.md). No se eliminó contenido de esta última.

## Publicación confirmada

El16/11/2026 se publicó096 como `3028a18` en origin/codex/096-native-switcher-restart-safety, por autorización explícita. Permanecen la observación D+1 y el diagnóstico físico; publicar el código no los certifica.
