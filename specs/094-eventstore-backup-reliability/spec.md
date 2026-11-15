# Spec 094 — Respaldo verificable de EventStore

Estado: PLANIFICADA, sin implementación ni activación. Depende del cierre manual de 093.

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
