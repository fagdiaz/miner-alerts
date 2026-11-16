# Spec 094 — Respaldo verificable de EventStore

**Software: PASS, 8/8 compuertas a las 15:43:25 UTC-3 del 15/11/2026.**
1634 pruebas y 75 subpruebas PASS en 109.68 s. Implementación activa;
observación D+1 y cierre Git de 094 pendientes.

## Dependencia y cambios

El operador autorizó expresamente el commit y push de 093: `0695385`, publicado
en `origin/codex/022-adaptive-acquisition`. Solo después se activó 094, en la rama
`codex/094-eventstore-backup-reliability`. 095 sigue planificada y sin implementación.

Se corrigieron el staging predeterminado incompatible con la validación de rutas,
la URI SQLite sin escape, los fallos sin resultado estructurado y la restauración
que admitía targets ajenos a staging. La copia conserva lock exclusivo, conexión
de origen de solo lectura, validación de integridad y promoción atómica. Se amplió
el manifest para incluir las tablas del esquema 7. Los fallos parciales no se
promueven; el progreso de copia tiene un presupuesto temporal acotado.

El digest ahora usa los campos reales del manifest y la configuración nested de
backup, compartida por comando, callback y reporte programado. Distingue ausencia,
deshabilitado, copia vencida, job en curso, fallo y copia verificada. Exige marker,
manifest, tamaño y fecha coherentes, y toma en cuenta el último resultado del job.
La consulta lee metadatos pequeños, sin hashear la base bajo el lock del monitor.

El wrapper publica `last_run.json` atómicamente. La tarea Windows usa rutas absolutas,
el `pythonw.exe` del virtualenv, SYSTEM, modo oculto, IgnoreNew, StartWhenAvailable
y límite de cinco minutos. No hay fallback silencioso a otro usuario o intérprete.

## Evidencia real

- Primera copia online: **384983040 bytes**, esquema 7, resultado verified en 7.527 s.
- Restauración de esa copia en staging: checksum, integridad, esquema y conteos PASS.
- Primera ejecución desde el Programador de tareas a las **15:36:40**: resultado **0**,
  Ready, nueva copia verified en 10.385 s. Permisos de SYSTEM comprobados por ejecución.
- Inspección elevada confirmó SYSTEM, Hidden=true, PT5M e IgnoreNew. Una consulta
  sin privilegios devolvía acceso denegado; el comando Status distingue incertidumbre
  de una ausencia confirmada y remite a consulta elevada.
- Próxima ejecución natural: **16/11/2026 a las 03:00 UTC-3**.
- Digest renderizado con datos reales reconoce copia de **367.15 MiB** a las 15:36.
  La consulta de salud tardó aproximadamente 2.6 ms.

Solo se alineó el bloque backup de la configuración local, hash `39c2afee`.
El resto de las claves se comparó sin diferencias. Configuración, estado, copias,
staging y diagnósticos quedan excluidos de Git.

Servicio recargado a las **15:36:56**. Captura final **15:45:58**: cuatro mineros
y doce cadenas minando, ViaBTC activa y ningún restart_required. Temperaturas
79/83/82/80 °C; 9043 W reportados y 339.63 TH/s instantáneos. Uptime creciente en
todos; cero restart_detected desde la recarga. Heartbeat actualizado y cola Telegram 0.
No se cambiaron pools, límites de potencia ni decisiones de actuación.

## Pruebas y operación

Se probaron escrituras concurrentes, rutas con espacios y caracteres reservados,
locks, falta de espacio, fallo parcial, datos corruptos, manifest inválido o ausente,
frescura, archivos modificados, restauración fuera de staging, traversal de backup_id,
configuración inválida y publicación de resultado. La suite final incluye los contratos
de Telegram con DBG_TELEGRAM y DBG_TELEGRAM_COMMANDS_ONLY habilitados.

Artefactos locales: `diagnostics/backup-20261115/`, `backups/` y `backup-staging/`.
El ensayo de limpieza fue dry-run; se preservaron las copias y evidencias iniciales.
[Runbook operativo](../operations/BACKUP_AND_RESTORE.md).

## Límites y seguimiento

El respaldo está en la misma unidad F: protege ante ciertos errores lógicos, pero
no ante pérdida física de esa unidad. La salud del digest se basa en evidencia del
productor y metadatos; una restauración vuelve a comprobar checksum e integridad.
No se garantiza detección continua de corrupción silenciosa posterior sin cambio
de metadatos. Un job terminado abruptamente puede dejar un lock que debe revisarse
antes de limpiar; no se borra un lock de propietario incierto automáticamente.

La retención destructiva automática permanece deshabilitada. El dry-run seleccionó
la segunda copia del día y propuso retirar la primera; no se eliminó ninguna.
Revisar capacidad y retención como parte de D+1. No considerar aplicada la política
de generaciones solo porque figure en la configuración.

La ejecución natural de mañana todavía no ocurrió. La observación inmediata cubre
unos nueve minutos de la nueva versión y no certifica D+1. La causa física del
chain break de M26 continúa abierta. Commit y push de 094 no se ejecutaron;
la autorización de Git recibida cubría el cierre de 093.
