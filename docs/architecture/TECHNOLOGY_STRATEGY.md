# Decisiones tecnológicas

> Tipo: referencia de arquitectura · Revisión: 2026-11-16.

## Criterio de adopción

Introducir tecnología cuando reduzca un riesgo o resuelva una necesidad demostrada.
Conservar límites de lectura, frescura y autorización; no agregar un nuevo servicio
para duplicar datos que ya están disponibles localmente.

| Tecnología | Papel actual | Restricción o estado |
|---|---|---|
| Python en Windows | Monitor, bot, clientes y herramientas | Compatibilidad Windows y entorno probado; no inferir soporte de toda versión |
| API 4028 | Señal autoritativa de salud y producción | Pull con procedencia y frescura explícitas |
| HTTP VNish | Configuración/estado y actuaciones acotadas | Autenticación, timeouts, readback y permisos |
| WebSocket VNish | Colección de logs de firmware | Proceso separado, límites por stream; no sustituye salud actual |
| SQLite esquema 7 | Telemetría, incidentes, auditoría y decisiones | WAL y backup online; no sobrescritura automática de la base activa |
| Telegram | Consulta y control del operador | Confirmaciones, cola y semántica de entrega explícita |
| NSSM/SCM y tareas Windows | Vida del monitor y jobs independientes | Identidad, scheduler, límites y resultado verificables |
| Prometheus/Grafana | Superficie auxiliar de observabilidad | Contrato de snapshot; stack Docker pendiente de revalidación actual |
| Dashboard HTML | Visualización local de histórico | Solo lectura de fuentes, salida local y antigüedad visible |

## Decisiones y alternativas

- Mantener el monitor nativo mientras dependa de SCM y de Hashcore local. Docker se
  limita a herramientas auxiliares y no desplaza automáticamente ese proceso.
- La decisión histórica sobre una APIweb adicional fue no_build. Telegram, reportes
  y métricas cubren el alcance documentado; una necesidad nueva debe reevaluarse con
  evidencia antes de introducir FastAPI, React u otro frontend.
- MQTT/SNMP/Modbus solo se consideran después de identificar una fuente PDU/UPS/medidor
  y su contrato. No elegir protocolo sin un publicador real ni inferir medición AC.
- OpenTelemetry permanece como alternativa cuando la distribución de procesos y
  destinos justifique su costo operativo. No se declara desplegado por esta guía.
- Las imágenes, puertos y dependencias concretas se leen de los manifiestos. Su
  existencia no demuestra que el build y los servicios funcionen actualmente.

## Resultado de la revisión documental

La arquitectura usa app/core/metrics_snapshot.py y el contrato de snapshot
`diagnostics/metrics/current.json`. Los ejemplos anteriores que copiaban módulos de
la raíz de app o usaban --config en metrics_exporter ya no describen laCLI actual.
Ver [observabilidad](../operations/OBSERVABILITY.md) para los dos límites concretos
hallados en el Dockerfile y la exposición de Grafana. No se cambiaron esos archivos.

El [documento tecnológico anterior](../archive/documentation-20261116/docs/speckit/TECHNOLOGY_STRATEGY.md)
conserva contexto y referencias primarias de las decisiones históricas. No presenta
sus métricas de una release anterior como un resultado del sistema actual.
