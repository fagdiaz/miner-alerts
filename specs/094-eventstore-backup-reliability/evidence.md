# Evidencia — Spec 094, 15/11/2026

## Dependencia y alcance

093 cerrada con autorización expresa, commit0695385 publicado en origin/codex/022-adaptive-acquisition.
094 activada en .specify/feature.json, rama codex/094-eventstore-backup-reliability.
No implementación de095. D+1 y causa físicaM26 de093 siguen abiertos, sin reparaciónAC afirmada.

## Auditoría previa

Motor existente tenía staging predeterminado anidado en backup y rechazado por su propia
validación; URI no escapada; errores SQLite sin resultado estructurado. Restore aceptaba
targets externos a staging y backup_id con traversal. Digest usaba integrity_check/start_iso
pero el productor emite integrity_result/completed_ts y size_bytes. También aceptaba
existencia de archivo sin manifest y no comprobaba frescura. Pipeline/comando/callback
consultaban clave plana backup_root mientras el instalador leía backup.root.

QA: `.agents/skills/speckit-qa/scripts/preflight.ps1 -RunBuilds` PASS antes de código.
Auditoría manual HIGH: datos, locks, scheduler y lectura acotada del digest; sin actuadores.

## Pruebas

- Primeras66 pruebas focalizadas PASS12.53s.
- Suite completa1633+75 PASS76.91s, antes del último contrato de root marker.
- Versión final:53 pruebas de backup/motor/digest PASS13.98s tras agregar marker y estado running.
- `py_compile` de monitor, pipeline, callbacks, help, daily_digest, backup/health,
  tools/event_store_backup y tools/run_event_store_backup: PASS.
- Parser PowerShell de tools/install_backup_task.ps1: sin errores.
- `git diff --check`: PASS. Config/state/backups/staging ignorados.
- Todos los tests de Telegram con DBG_TELEGRAM=1 y DBG_TELEGRAM_COMMANDS_ONLY=1,
  temporales en diagnostics/backup-20261115. Gate final con suite raíz se agrega al cierre.

## Activación real

DiscoF con114GiB libres antes de activar. Backups y staging locales y disjuntos de data.
Copia de configuración previa en diagnostics/backup-20261115/config-before.json.
Solo se agregó backup.enabled/root/staging_root/limits; otras claves comparadas idénticas.
Hash nuevo deconfig39c2afee. Los backups y staging están excluidos de Git.

Primera copia online de producción:20261115T183512Z_326f4461,384983040bytes,
esquema7,7.527s,resultadoverified. Restore en staging de esa copia: checksum,
integridad, esquema yconteos PASS; nunca se restauró sobre la base activa.

Plan del scheduler validado antes de registro, con intérprete/config absolutos.
Tarea MinerAlerts_EventStore_Backup instalada comoSYSTEM, oculta, IgnoreNew,
StartWhenAvailable y límite5min; corrida diaria03:00 local. Primera ejecución real
por Programador de tareas15:36:40 terminóresultado0 yReady. Copia generada
20261115T183641Z_86a542fa,10.385s,384983040bytes,verified. Próxima16/11/2026 03:00 UTC-3.
No retención destructiva automática. El wrapper publica last_run.json atómicamente.

La consulta no elevadaGet-ScheduledTask oculta esta tarea; schtasks confirmaAccesoDenegado.
Inspección elevada separada en task-inspection.json confirma identidad ysettings. El Status
del instalador informaNotVisibleOrNotRegistered cuando no puede verla, sin falso diagnóstico.

MinerAlerts recargado15:36:56. Captura15:38:03:4/4mining,12cadenas,ViaBTCactiva,
ningún restart_required,9043W reportados,341.70TH/s instantáneos,79/83/82/81C.
Uptime de todos creciente respecto de capturas anteriores. PID28020,cola0, tick/sender7s,
poller16s. Digest local reconoce copia367.15MiB de15:36; lectura de salud~2.6ms.
No se enviaron mensajes de prueba ni se cambiaron controles de mineros.

Artefactos ignorados: diagnostics/backup-20261115 (planes, pruebas, resultados, restore,
config-backup yrender), backups/ (copias), backup-staging/ (restauración de ensayo).
SeguimientoD+1 pendiente. Commit/push094 siguen manuales y no fueron ejecutados.


## Cierre de software — 15/11/2026 15:45 UTC-3

`preflight_stabilize.ps1 -RunTests $true -CheckFleet $true`: PASS8/8 a15:43:25,
1634 pruebas+75subpruebas PASS109.68s. TEMP/TMP ybasetemp locales para la suite raíz;
DBG_TELEGRAM=1 yDBG_TELEGRAM_COMMANDS_ONLY=1. No cambios de producción posteriores
al código validado; solo documentación de cierre. ParserPowerShell PASS.
Reporte: docs/audit/STABILIZATION_REPORT_20261115_BACKUP.md.

Captura15:45:58:4/4mining,12cadenas,ViaBTC activa yrestart_required=false;
339.63TH/s instantáneos,9043W reportados,79/83/82/80C. PID28020,cola0,
tick1.6s/poller5.8s/sender5.9s. Cero reinicios desde recarga15:36:56,~9min observados.
Watchdog real15:45:54 saludable. Logs del monitor sin errores de hook/entrega trasrecarga.

Cleanup dry-run ejecutado; ningún archivo de evidencia eliminado. Escaneo adicional de
archivos nuevos ydiff sin patrones de token real. GitdiffcheckPASS. Retentiondryrun propone
retirar copia inicial del mismo día pero NO se aplicó; ambas copias yrestore se conservan.

D+1 pendiente de corrida16/11 03:00 yrevisiónposterior. Respaldo local enmismaunidad,
retención destructiva no habilitada. Commit/push094 manuales ynoejecutados.095noactiva.

## Verificación D+1 — 2026-11-16 09:48 UTC-3

La corrida programada de03:00 terminó verified a03:00:08.999, duración7.797s,
389083136bytes, esquema7, backup20261116T060001Z_305aa41c. Evidencia local
backups/last_run.json. No fue corrida manual ni se aplicó retención destructiva.
La observación del respaldo queda cumplida; los incidentes térmicos/reinicios son
un alcance independiente de estabilización, aún no implementado.

## Gate previo al cierreGit —16/11 09:52

Suite raíz nuevamente:1634+75 PASS57.72s. Pythonpy_compile,gitdiffcheck,escaneo
de secretos en modificados/nuevos,config-example,4028en4/4,NSSM SERVICE_RUNNING
yDoD PASS. ScriptPowerShell de estabilización no inició correctamente enesta sesión;
controles equivalentes ejecutados directamente conPython/nssm/git, sin declarar
una nueva corrida automática8/8. ParserPS previo permanece aplicable: no cambió
el instalador desde elgate15/11. Evidencia diagnostics/stability-20261116/gate094-manual.json.
Sin nuevos cambios de código094; usuario autorizócommit/pushycontinuación.
