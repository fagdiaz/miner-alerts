# Política de documentación

> Tipo: guía de mantenimiento · Revisión: 2026-11-16 · Subordinada a AGENTS.md y la constitución.

## Tipos documentales

| Tipo | Contenido | Ubicación |
|---|---|---|
| Procedimiento | Pasos operativos, precondiciones, resultado esperado y límites | `docs/operations/` |
| Arquitectura | Componentes, contratos, decisiones y restricciones | `docs/architecture/` |
| Desarrollo | Validación, flujo de cambios y releases | `docs/development/` |
| Planificación | Trabajo pendiente, dependencias y ventanas | `docs/speckit/` |
| Evidencia fechada | Qué se ejecutó, cuándo, resultado y pendientes | `docs/audit/` |
| Histórico | Documentos superados con procedencia y contexto | `docs/archive/` |

## Reglas editoriales

1. Usar UTF-8, finales LF y un encabezado H1 por documento nuevo. Separar encabezados,
   párrafos, listas y tablas con líneas en blanco.
2. Escribir en español claro; conservar nombres de código, APIs y comandos en su forma original.
3. Indicar tipo, alcance y fecha de revisión. Los valores dinámicos pertenecen a un corte
   fechado, no a todos los README o manuales.
4. Usar enlaces relativos al repositorio. Evitar rutas locales `file:///`, nombres de usuario
   del host y credenciales. Rutas de configuración privadas se documentan sin sus contenidos.
5. Diferenciar implementado, validado en tests, desplegado, observado y publicado. Una
   compilación o checklist no demuestra estabilidad física ni una observación D+1.
6. Marcar comandos de consulta, escritura o actuación. Los ejemplos no conceden autorización
   adicional y no deben ejecutarse automáticamente al leer una página.
7. Mantener una fuente por dato: código y config de ejemplo para contratos; feature.json
   para la spec activa; evidencia fechada para resultados; roadmap para pendientes.

## Bitácora e histórico

[DEVELOPMENT_LOG.md](../audit/DEVELOPMENT_LOG.md) conserva todos sus registros. En esta
normalización se preservó byte por byte y se creó un índice externo. Las entradas nuevas
siguen siendo aditivas y newest-first según las reglas del proyecto. Una futura corrección
se agrega con contexto; no borra ni trunca el relato anterior.

Los informes y artefactos históricos no se interpretan como configuración vigente. Corregir
su navegación o codificación no autoriza a reescribir resultados, transformar una hipótesis
en certeza ni eliminar evidencia. El inventario de un corte permanece fechado aunque cambie
la estructura actual. El registro de migración explica las rutas sustituidas.

## Cambios de rutas y compatibilidad

Antes de mover un documento, buscar consumidores en código, automatizaciones, plantillas,
la bitácora y specs. Mantener un enlace de compatibilidad si el consumidor queda fuera del
alcance de edición. ROADMAP.md, SPEC_PROGRAM.md, DELIVERY_PLAN.md y DEVELOPMENT_LOG.md
conservan sus rutas contractuales actuales.

La carpeta `specs/` quedó fuera de esta reorganización. Los documentos de skills y plantillas
solo se alinearon con las rutas y reglas ya existentes; no activan una spec ni un despliegue.

## Validación de una revisión documental

- Verificar enlaces locales y anchors de documentos vigentes y de compatibilidad.
- Revisar ejemplos contra archivos y opciones reales, sin ejecutar actuaciones.
- Comparar hashes del código, config y specs para comprobar que no cambiaron.
- Comprobar la preservación de la bitácora y ejecutar `git diff --check`.
- Documentar límites y referencias históricas no resolubles; no ocultar errores.
- Una revisión solo documental no requiere recarga del servicio ni pruebas sobre mineros.
