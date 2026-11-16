# Normalización documental — 16/11/2026

> Tipo: registro de migración y validación · Estado: validación documental aprobada.

## Alcance

Organización de la documentación del proyecto fuera de specs/. Se actualizaron índices, manuales, referencias y texto de instrucciones de herramientas. No se editaron fuentes de producción, configuración, scripts ejecutables, specs ni artefactos privados del runtime. La feature activa continúa siendo 096; no se inició otra implementación.

La petición permite reorganizar documentos y exige conservar el contenido de DEVELOPMENT_LOG. Se eligió preservar el original byte por byte y construir navegación externa. No se ejecutaron mineros, llamadas Telegram, scheduler, reinstalaciones o recargas durante este trabajo.

## Estructura resultante

- [Centro documental](../README.md): rutas de lectura y matriz de autoridad.
- [Operación](../operations/README.md): instalación, configuración, runbook, Telegram, diagnóstico, potencia, respaldo y observabilidad.
- [Arquitectura](../architecture/README.md): componentes, pipeline y decisiones actuales.
- [Desarrollo](../development/README.md): flujo, validación y publicación manual.
- [Gobierno documental](../governance/DOCUMENTATION_POLICY.md): tipos, vigencia, conservación y cambios de rutas.
- [Planificación](../speckit/README.md): backlog, dependencias y ventanas con responsabilidades separadas.
- [Auditoría](README.md): índices, cortes e historial completo.
- [Archivo](../archive/README.md): antecedentes y copias de documentos sustituidos.

## Mapa de migración

Las rutas contractuales de roadmap, programa, calendario y bitácora se mantienen. Cinco rutas antiguas conservan referencias de compatibilidad para specs, bitácora y consumidores no editados. [CSV de migración](DOCUMENTATION_NORMALIZATION_20261116.csv).

| Ruta anterior | Destino actual | Copia histórica |
|---|---|---|
| `README.md` | [README.md](../../README.md) | [Antecedente](../archive/documentation-20261116/ROOT_README.md) |
| `docs/README.md` | [docs/README.md](../README.md) | [Antecedente](../archive/documentation-20261116/docs/README.md) |
| `docs/speckit/README.md` | [docs/speckit/README.md](../speckit/README.md) | [Antecedente](../archive/documentation-20261116/docs/speckit/README.md) |
| `docs/speckit/ROADMAP.md` | [docs/speckit/ROADMAP.md](../speckit/ROADMAP.md) | [Antecedente](../archive/documentation-20261116/docs/speckit/ROADMAP.md) |
| `docs/speckit/SPEC_PROGRAM.md` | [docs/speckit/SPEC_PROGRAM.md](../speckit/SPEC_PROGRAM.md) | [Antecedente](../archive/documentation-20261116/docs/speckit/SPEC_PROGRAM.md) |
| `docs/speckit/DELIVERY_PLAN.md` | [docs/speckit/DELIVERY_PLAN.md](../speckit/DELIVERY_PLAN.md) | [Antecedente](../archive/documentation-20261116/docs/speckit/DELIVERY_PLAN.md) |
| `docs/speckit/RUNBOOK.md` | [docs/operations/RUNBOOK.md](../operations/RUNBOOK.md) | [Antecedente](../archive/documentation-20261116/docs/speckit/RUNBOOK.md) |
| `docs/speckit/MINER_DIAGNOSTICS.md` | [docs/operations/DIAGNOSTICS.md](../operations/DIAGNOSTICS.md) | [Antecedente](../archive/documentation-20261116/docs/speckit/MINER_DIAGNOSTICS.md) |
| `docs/speckit/TECHNOLOGY_STRATEGY.md` | [docs/architecture/TECHNOLOGY_STRATEGY.md](../architecture/TECHNOLOGY_STRATEGY.md) | [Antecedente](../archive/documentation-20261116/docs/speckit/TECHNOLOGY_STRATEGY.md) |
| `docs/audit/BACKUP_RUNBOOK.md` | [docs/operations/BACKUP_AND_RESTORE.md](../operations/BACKUP_AND_RESTORE.md) | [Antecedente](../archive/documentation-20261116/docs/audit/BACKUP_RUNBOOK.md) |
| `docs/proposals/README.md` | [docs/proposals/README.md](../proposals/README.md) | [Antecedente](../archive/documentation-20261116/docs/proposals/README.md) |
| `docs/speckit/MONOLITH_DECOUPLING_MASTER_PLAN.md` | [docs/archive/historical_plans/MONOLITH_DECOUPLING_MASTER_PLAN.md](../archive/historical_plans/MONOLITH_DECOUPLING_MASTER_PLAN.md) | [Antecedente](../archive/historical_plans/MONOLITH_DECOUPLING_MASTER_PLAN.md) |

## Preservación de DEVELOPMENT_LOG

- Original y resultado: **554353 bytes**, sin truncado, reordenamiento ni recodificación.
- SHA-256: `9387431334099110dced2d640674ce409c5fc56b0a698c8c743bce8d223610d5`.
- [Índice cronológico externo](DEVELOPMENT_LOG_INDEX.md):195 encabezados fechados, con destino a las secciones originales.
- Las nuevas entradas futuras siguen siendo aditivas y newest-first; no se reescribió el cuerpo histórico para uniformar sus títulos o estilo.

## Correcciones documentales

1. Los README ya no declaran V2/V5 o cantidades antiguas como un estado actual permanente. El único resumen de runtime es un [corte fechado](../operations/PRODUCTION_BASELINE.md).
2. Los documentos de planificación conservaron su histórico en once copias identificadas y ahora exponen prioridades, secuencia y ventanas sin mezclar estados pasados.
3. Manuales contrastados con paths y opciones reales: módulos bajo app/core, esquema SQLite 7, CLI de métricas sin --config, manifiesto Docker real y backup 094 con wrapper independiente.
4. Diferencia explícita entre los dos dry-run: miner_diagnostics no consulta equipos; vnish_log_collector puede conectar sin persistir.
5. Skills y plantillas dejan de exigir documentos académicos inexistentes de docs/project_docs. Se alinearon con backlog, programa y reglas de preservación del proyecto.
6. Las instrucciones de commit/estabilización explicitan la regla existente de Git manual. Corregida la firma documentada del preflight: booleanos explícitos para parámetros object.
7. Links relativos y portables; se corrigieron rutas locales del host y codificación dañada del roadmap histórico. Tres referencias técnicas retiradas se marcaron como contexto histórico, sin inventar una equivalencia de implementación.
8. El [inventario previo](DOCUMENTATION_INVENTORY_20261116.md) conserva su corte y el CSV original; sus enlaces de navegación ahora contemplan la migración.

## Validación

El control final se ejecuta con el helper local de esta iteración, que solo inspecciona archivos. Comprueba enlaces, anchors, UTF-8, encabezados de documentos vigentes y hashes de preservación. DEVELOPMENT_LOG se compara íntegramente; sus enlaces históricos internos no se reescriben. Los enlaces entrantes de su índice sí se validan.

Los hashes de fuentes y specs se comparan con el inicio de esta tarea. state.json y state.bak son archivos de estado vivo, actualizados autónomamente por el monitor: no se confunde ese cambio natural con una edición del agente. La configuración local sí se compara y permanece intacta.

- Resultado final: **PASS**. 127 archivos Markdown revisados; 958 enlaces locales y 195 anchors comprobados, sin destinos faltantes.
- 829 archivos de código, configuración y specs comparados, sin cambios. DEVELOPMENT_LOG preservado en contenido y bytes.
- UTF-8, encabezados de documentos vigentes y git diff --check aprobados.
- Pruebas de runtime: no ejecutadas, por ser una edición documental.
- Backup documental anterior: archivo local ignorado before-documents.zip; no incorpora configuración ni estado reales.
- Evidencia técnica local: diagnostics/documentation-normalization-20261116/validation.json y reference-repairs.json.

## Hallazgos de infraestructura conservados como pendientes

La inspección encontró Dockerfile.metrics copiando app/metrics_snapshot.py, que no coincide con el módulo actual app/core/metrics_snapshot.py. El manifiesto publica Grafana con 3000:3000 y credenciales inicialesadmin/admin; no corresponde afirmar que toda la pila está limitada a loopback. Estos archivos no se cambiaron ni se ejecutó un build. Ver [observabilidad](../operations/OBSERVABILITY.md) y backlog INFRA-01.

La organización documental no certifica estabilidad futura, reparación de la causa física de M26 o rentabilidad óptima. Permanecen los pendientes de observación y diagnóstico físico del corte de producción.

## Publicación

El usuario autorizó commit/push el16/11/2026. Se separó el código096 de esta reorganización: `3028a18` ya fue publicado en origin/codex/096-native-switcher-restart-safety. La documentación se publica en un commit posterior independiente, identificable en git log.

El checkout ya contenía cambios096 antes de normalizar; la validación de hashes distingue ese trabajo previo. La bitácora permanece idéntica al inicio de la normalización y no se mezclaron actuaciones de planta con publicación documental. D+1 y causa física no se consideran cerrados por el push.
