# Plan 094 — implementación acotada

Base publicada: 0695385 (093). Riesgo HIGH por datos y programación de procesos.

1. Corregir tools/event_store_backup.py: staging hermano por defecto, URI escapada,
   límite temporal de copia, errores explícitos y lock liberado. Restore solo dentro
   de staging, con backup_id validado, checksum, esquema y tablas allowlisted.
2. app/backup/health.py: contrato de settings, rutas absolutas y salud de respaldo.
   Solo lecturas acotadas de manifest/resultado y stat; sin sockets, hashes grandes,
   SQLite ni nuevos hilos. Integrar en daily_digest.py y sus tres callers (comando,
   callback y pipeline). Respetar configuración nested; mantener firma compatible.
3. tools/run_event_store_backup.py: wrapper CLI separado que usa motor existente,
   valida configuración y marca previa, guarda resultado atómico. Sin retención apply.
4. tools/install_backup_task.ps1: acción exacta al wrapper y config absoluto, pythonw
   del virtualenv obligatorio, SYSTEM sin fallback, tarea oculta y ejecución acotada.
5. Pruebas de motor, fallos, URI, restore traversal/rutas, salud/frescura, concurrencia,
   wrapper y contrato del scheduler. QA antes de implementar; DBG_TELEGRAM en tests.
6. Crear roots/marker locales; backup real y restauración a staging con verificación.
   Instalar y ejecutar tarea; verificar resultadoWindows y resultado del job. Recargar
   solo el monitor para alinear config/digest, sin reinicios de mineros.
7. Suite completa, sintaxisPython/PowerShell, speckit-stabilize, evidencia y revisión D+1.
   Commit/push094 siguen manuales; autorización de Git de este turno solo cubre093.

Concurrencia: backup usa conexiones propias de lectura, no state_lock. Digest obtiene
settings de config inmutable y lee metadatos pequeños bajo el contrato existente.
El job publica resultado con replace; el lector no observa JSON parcial. SQLite.backup
permite escrituras del monitor. La restauración nunca abre ni modifica la base activa.

No activar095 durante esta implementación. Ventana prevista: una iteración más24h
para observar la siguiente ejecución programada; no certificar esa observación ahora.
