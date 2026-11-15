# Plan 094

1. Auditar tools/event_store_backup.py, rutas, manifests, scheduler de Windows,
   inspect_latest_backup en daily_digest.py y configuración de ejemplo. Reutilizar el motor.
2. Definir backup y staging disjuntos dentro del workspace o en un destino autorizado;
   verificar espacio y persistencia. Usar SQLite.backup, sin edición de la base activa.
3. Normalizar frescura y estados del digest; pruebas, restauración en staging y QA.
4. Validar el comando y el entorno antes de programar; observar primera ejecución y fallo.
5. Suite, speckit-stabilize y revisión D+1. No implementar antes del release de 093.

Estimación: una iteración de implementación más 24 horas de observación.
