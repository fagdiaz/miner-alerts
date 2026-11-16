# Programa de especificaciones

> Tipo: secuencia y gates · Revisión: 2026-11-16.

## Secuencia vigente

| Orden de ejecución | Paquete | Riesgo | Dependencias | Estado y salida |
|---|---|---|---|---|
| Publicada | 093: estabilidad, watchdog y mensajería | HIGH | Línea previa | `0695385`; conserva causas físicas abiertas cuando falta evidencia |
| Publicada | 094: respaldo verificable de EventStore | HIGH | 093 | `a8ce841`; copia, restore en staging y ejecución programada verificados |
| Activa | 096: seguridad de reinicios y cambios nativos | HIGH | 094 | Publicada como `3028a18`, desplegada y observada 660.1 s; D+1 pendiente |
| Siguiente, no activa | 095: rendimiento sostenible | MEDIUM en fase analítica | Cierre 096 y evidencia 093/094 | Comparación de disponibilidad, TH efectivos y consumo; sin nuevos actuadores |

[feature.json](../../.specify/feature.json) selecciona la feature activa. Sus spec,
plan, tareas y evidencia se consultan en [specs/](../../specs). Un número mayor no
implica ejecución posterior si una corrección urgente se interpone.

## Estados y límites

- **Planificada:** artefactos de diseño; no demuestra implementación ni activación.
- **Implementada:** código existente, todavía sujeto a validación.
- **Validada:** comandos y pruebas registrados con versión identificable.
- **Desplegada:** proceso/configuración cargados y comprobados en el host.
- **Observada:** intervalo y condiciones medidos; declarar su duración.
- **Publicada:** commit y push confirmados dentro de autorización explícita.
- **Bloqueada externamente:** dependencia o medición ausente, con motivo trazable.

Estos estados pueden coexistir. Desplegada no significa publicada y observada
once minutos no significa D+1 ni reparación de la alimentación eléctrica.

## Gates compartidos

1. Mantener una sola spec en implementación y respetar el cierre secuencial de la anterior.
2. Analizar arquitectura, estados compartidos, hilos, locks y contratos antes de código.
3. Preservar QA, startup guard, cooldowns, ventanas y confirmaciones de actuadores.
4. Ejecutar validación proporcional al cambio y registrar comandos y límites reales.
5. Revisar estabilización y documentos antes de publicación manual; ningún defecto
   pendiente se transforma en aprobado para cumplir una fecha.
6. Mantener evidencia y bitácora, config/state fuera de Git y secretos fuera de reportes.
7. Reservar observación posterior; un cambio de código reinicia la ventana afectada.

## Restricciones de 095

Calcular rendimiento sobre tiempo total, incluyendo indisponibilidad. Separar watts
reportados por ASIC de consumo AC. No declarar rentabilidad máxima sin tarifa,
retribución de pool, costo eléctrico y cobertura temporal. Correlación entre mineros
no identifica por sí sola calle, elevador, PSU, cableado o placa.

## Programa histórico

El inventario extenso de paquetes 001–086 y los registros anteriores se preservan
en el [programa previo](../archive/documentation-20261116/docs/speckit/SPEC_PROGRAM.md).
Las fases de desacoplamiento 087–091 tienen su [plan histórico](../archive/historical_plans/MONOLITH_DECOUPLING_MASTER_PLAN.md).
La evidencia específica y la [bitácora](../audit/DEVELOPMENT_LOG.md) prevalecen sobre
porcentajes o declaraciones resumidas de esos documentos.
