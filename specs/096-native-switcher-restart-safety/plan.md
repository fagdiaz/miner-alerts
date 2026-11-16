# Plan 096

1. QA previo: revisar engine, restart_intelligence, cliente VNish y sus tests;
   reproducir en rojo el incidente M24 y las variantes de auto-tuning.
2. Corregir L1 y usar estado nativo fresco solo ante posibles intervenciones.
   No agregar otro controlador de potencia ni modificar el algoritmo VNish.
3. Mantener los hilos existentes y state_lock. Las lecturas HTTP quedan fuera
   del lock; solo las actualizaciones de caché y contadores lo toman. Sin nuevos
   campos persistentes ni edición manual de state.json.
4. Probar flags transitorios, autotune, QA, gobernanza, mantenimiento, temperatura,
   conservación del techo, exclusión L1/L2 y recuperación real simulada.
5. Suite completa, sintaxis y estabilización; recargar exclusivamente el monitor
   y observar al menos dos intervalos nativos completos de 300 segundos.
6. Registrar evidencia, bitácora, roadmap, prompt y límites. Commit/push de 096
   permanecen manuales; la autorización de cierre recibida corresponde a 094.

Archivos de producción: app/core/engine.py y app/core/restart_intelligence.py.
No cambian pools, ventiladores, esquema SQLite ni políticas de Telegram.
