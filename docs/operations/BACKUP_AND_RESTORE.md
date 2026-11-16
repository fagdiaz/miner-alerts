# Respaldo y restauración de EventStore

> Tipo: procedimiento · Revisión: 2026-11-16 · Productor vigente: implementación 094.

## Contrato y archivos

| Elemento local | Función |
|---|---|
| `data/miner_alerts.db` | Base activa; nunca es target de restore-staging |
| `backups/verified/<id>/` | Generación verificada: base y manifest |
| `backups/last_run.json` | Resultado del job publicado atómicamente |
| `backup-staging/<nombre-nuevo>/` | Destino separado para ensayo de restauración |
| `backup` en app/config.json | Paths y límites de la instancia |

Los roots deben estar marcados, ser disjuntos de la base activa y entre sí. El motor
usa laAPI de backup SQLite, no una copia ciega del archivo abierto. Genera checksum,
integridad, esquema y conteos. El wrapper [run_event_store_backup.py](../../tools/run_event_store_backup.py)
publica el resultado del job y aplica su presupuesto temporal.

En el corte registrado, la tarea `MinerAlerts_EventStore_Backup` corre diariamente
03:00 UTC-3 como SYSTEM, oculta, IgnoreNew y límite 5min. Una copia en la misma unidad
protege frente a algunos fallos lógicos, no frente a pérdida física de ese disco.

## Consultar y planificar

Desde la raíz, con privilegios suficientes para ver una tareaSYSTEM:

```powershell
& .\tools\install_backup_task.ps1 -Action Status -ConfigPath app\config.json
& .\tools\install_backup_task.ps1 -Action Plan -ConfigPath app\config.json
Get-Content -LiteralPath .\backups\last_run.json
```

Plan no instala ni ejecuta la copia. NotVisibleOrNotRegistered puede indicar falta de
visibilidad; no demuestra que la tarea esté ausente. El último backup automático de
este corte, 16/11 a 03:00, terminó verified; no se mantiene como una prueba perpetua.

## Ejecutar una copia o registrar la tarea

Son escrituras y cambios de scheduler; aplicar solo dentro del alcance autorizado.
No correr jobs superpuestos.

```powershell
& .\tools\install_backup_task.ps1 -Action RunNow -ConfigPath app\config.json
```

Para instalación nueva, revisar Plan antes de `-Action Register`. Verificar identidad,
acción, intérprete y config absolutos. El wrapper puede ejecutarse manualmente con
`python tools/run_event_store_backup.py --config app/config.json`; esa corrida no
prueba los permisos de la tarea programada.

Confirmar started_ts nuevo, resultadoWindows0 y job verified. No considerar el éxito
de lanzar una tarea como éxito de su backup.

## Interpretación de salud

- Deshabilitado y sin copia son estados distintos.
- En curso requiere marca reciente; un job que vence su presupuesto no quedaOK.
- Vencido depende de completed_ts y max_age_hours de la instancia.
- Un fallo posterior del job prevalece aunque exista una copia anterior válida.
- El digest comprueba metadatos acotados; no recalcula un hash grande bajo state_lock.
  Una verificación de metadatos no equivale a detectar todo bitrot silencioso posterior.

Ante fallo, conservar última copia válida y evidencia. Un proceso abortado puede dejar
un lock: verificar propietario y ausencia de job activo antes de limpiarlo.

## Ensayo de restauración

Escribe únicamente en un target nuevo dentro del staging configurado. Reemplazar los
placeholders y revisar rutas antes de ejecutar; no usar la base activa como destino.

```powershell
& .\.venv\Scripts\python.exe tools\event_store_backup.py --source-db data\miner_alerts.db --backup-root backups --staging-root backup-staging --action restore-staging --backup-id '<ID_VERIFICADO>' --restore-target 'backup-staging\<ENSAYO_NUEVO>'
```

Comprobar checksum_ok, integrity_ok, schema_ok y counts_ok. No ejecutar una sustitución
de la base viva como continuación automática. Una recuperación real requiere parada,
preservación de la base dañada y sus sidecars, restore validado y una maniobra específica;
no borrar WAL/SHM ni copiar una base encima de un proceso activo.

## Retención y capacidad

La política del motor puede calcular generaciones diarias, semanales y mensuales. Su
existencia no prueba que la eliminación esté habilitada o se haya aplicado. Primero:

```powershell
& .\.venv\Scripts\python.exe tools\event_store_backup.py --source-db data\miner_alerts.db --backup-root backups --staging-root backup-staging --action retention-dry-run
```

La activación inicial no habilitó retención destructiva automática. Revisar espacio,
conservación y restaurabilidad antes de una eliminación explícita. El procedimiento
anterior se conserva como [corte histórico](../archive/documentation-20261116/docs/audit/BACKUP_RUNBOOK.md).
