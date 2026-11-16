# Respaldo de EventStore — operación local

Spec094; tarea MinerAlerts_EventStore_Backup. Copia diaria03:00 UTC-3 bajo SYSTEM,
con ejecución oculta, sin superposición y límite5min. Wrapper independiente del monitor.

## Datos y evidencia

- Base activa: data/miner_alerts.db. Nunca restaurar sobre ella con este procedimiento.
- Copias: backups/verified/<id>/miner_alerts.db y manifest.json.
- Resultado de la última corrida: backups/last_run.json, publicado atómicamente.
- Ensayo de restauración: backup-staging/<nombre-nuevo>/.
- Configuración: bloque backup de app/config.json, local y excluido de Git.
- Tanto backups/ como backup-staging/ están ignorados por Git. MismaunidadF: no cubre
  una pérdida física de esa unidad; una copia externa requiere destino autorizado.

El motor valida integridad de la copia y crea SHA256, versión de esquema y conteos.
El digest consulta solo metadatos pequeños, tamaño, fecha y resultado del job. No vuelve
a hashear toda la copia bajo el lock del monitor ni garantiza detección de bitrot silencioso
posterior si no cambian sus metadatos. Restore vuelve a validar checksum e integridad.

## Consulta y corrida manual

Desde el directorio del proyecto, en PowerShell elevado para consultar la tarea:

```powershell
& .\tools\install_backup_task.ps1 -Action Status
Get-Content .\backups\last_run.json
```

NotVisibleOrNotRegistered indica que una consulta sin privilegios puede no verla;
no demuestra que la tarea esté ausente. La primera ejecución15/11 fue observada como
Ready y LastTaskResult0 desde sesión elevada.

```powershell
& .\tools\install_backup_task.ps1 -Action Plan -ConfigPath app/config.json
& .\tools\install_backup_task.ps1 -Action RunNow
```

Plan no registra ni ejecuta copias. RunNow solicita ejecución al Programador;
confirmar después resultado0, jobverified y started_ts nuevo. El wrapper también puede
invocarse directamente con Python del virtualenv y --config app/config.json; no constituye
por sí solo prueba de permisos del scheduler. No ejecutar copias superpuestas.

## Interpretación del digest

- Deshabilitado: backup.enabled=false; no inventa una copia saludable.
- Sin copias verificadas: no hay generación válida disponible.
- Respaldo en curso: job reciente activo; si queda sin terminar por más330s, informa fallo.
- Copia vencida: completed_ts excede max_age_hours (30h de margen para tarea diaria).
- Falló la verificación o tarea: resultado fallido, JSON inválido, archivos incompletos,
  marker ausente, tamaño/fecha incompatibles o archivo modificado.
- OK: manifest válido y fresco del productor, archivo presente coherente y sin fallo
  posterior de job. No reemplaza una restauración de ensayo.

Ante falta de espacio o fallo, conservar última copia válida y diagnóstico. Un proceso
terminado abruptamente puede dejar .backup.lock: verificar propietario/PID y que ninguna
copia esté en curso antes de cualquier limpieza. No borrar locks ni copias a ciegas.

## Restore y retención

Usar solo un target nuevo dentro de backup-staging y un id existente sin componentes
de ruta. El comando tools/event_store_backup.py --action restore-staging requiere
--source-db, --backup-root, --staging-root, --backup-id y --restore-target apropiados.
Debe devolver checksum_ok/integrity_ok/schema_ok/counts_ok=true; nunca usar la ruta activa.

La retención destructiva automática no se activó para preservar las evidencias iniciales.
Revisar retention-dry-run y capacidad como parte de D+1 antes de habilitar eliminación.
No considerar la política14diarias/8semanales/12mensuales aplicada solo por estar en config.
La corrida diaria crecerá aproximadamente una copia del tamañoactual por día mientras
no se aplique retención. A15/11 hay~114GiB libres antes de las copias, cada una~367MiB.

## Observación pendiente

Próxima ejecución natural:16/11/2026 03:00 UTC-3. Revisar job nuevo y resultadoWindows,
integridad de generación, frescura en digest y continuidad del monitor. Esa ejecución
no se declara aprobada por los tests ni por la corrida manual de activación.
