# Spec 094 — Respaldo verificable de EventStore

Estado: VALIDADA, D+1 cumplido; cierre Git autorizado el16/11. 093 cerrada y publicada como 0695385 por autorización expresa.

Evidencia del 15/11: la configuración local no contiene backup, no existe backups/ y
no se identificó una tarea específica de respaldo de Miner Alerts. No atribuir a las
tareas de Windows cobertura de SQLite sin evidencia. La inspección actual también
puede mostrar OK por mera existencia de un archivo sin manifest válido.

Objetivo: copia online de SQLite, checksum, integrity_check y manifest fechado;
restauración comprobada en staging separado. Programación Windows observable por
última ejecución y resultado. Distinguir deshabilitado, vencido, fallido y verificado.
La retención requiere copia verificada y dry-run revisado. Nunca restaurar sobre la
base activa ni eliminar evidencias operativas durante esta implementación.

Aceptación: escritura concurrente, restauración válida, fallas parciales, espacio
insuficiente, rutas solapadas, locks y manifest corrupto. El monitor sigue funcionando
ante cualquier fallo del backup. Riesgo HIGH por datos; sin transmisión de contenidos
o credenciales a terceros ni al chat.


## Contratos de activación

Copia local en backups/ y staging en backup-staging/, disjuntos de data/; ambos
ignorados por Git. Misma unidad: protege ante corrupción lógica, no pérdida del disco.
Config local alineada con backup.enabled/root/staging_root/max_run_seconds (300)
ymax_age_hours (30). Tarea Windows diaria03:00, oculta, SYSTEM, IgnoreNew,
StartWhenAvailable y límite5min. No fallback silencioso de identidad o intérprete.

Manifest autoritativo es elv1 del motor: integrity_result, size_bytes, completed_ts,
source_schema_version, sha256 y table_counts; no campos ficticios integrity_check/start_iso.
El digest no recalcula hashes de cientos deMB bajo state_lock: consulta evidencia
acotada de manifest/tamaño/fecha y resultado del último job. Restore valida SHA e
integridad en copia. No se acepta mera existencia ni manifest inválido como verificado.
Fallo reciente del job prevalece aunque exista copia previa válida (mostrar respaldo previo).
Sin backup habilitado: estado deshabilitado; ausencia, vencimiento y fallo diferenciados.

No se cambia potencia, pools, firmware ni estado de decisiones. El job es proceso
separado, no hilo del monitor. SourceSQLite mode=ro; handles cerrados ante errores.
Lock exclusivo con resultado explícito; progreso acotado por tiempo. No borrado
recursivo de backups ni retención destructiva automática en esta primera activación.
La tarea guarda resultado atómico local y logs sanitizados; nunca imprime config completa.
