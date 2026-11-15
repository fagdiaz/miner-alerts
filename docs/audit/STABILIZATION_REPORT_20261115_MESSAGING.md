# Estabilización de mensajería — 15/11/2026

**Resultado de software: PASS, 8/8 compuertas a las 15:17:59 UTC-3.**
Suite completa: 1604 pruebas y 75 subpruebas PASS en 95.59 s.
Observación inmediata de producción aprobada; D+1 y diagnóstico físico pendientes.

Spec activa: 093. Alcance: hallazgos confirmados en Telegram Desktop y registros
de producción. No se activó otra spec. GPT 6.1 Sol, razonamiento alto, por elección
del operador. Commit y push siguen manuales.

## Cambios y contratos

- Status solo muestra snooze cuando su vencimiento está en el futuro. No se
  borró ni reescribió el estado de producción para corregir la presentación.
- El digest cuenta `restart_detected` por separado de las acciones de reboot.
  Conserva `reboots_24h` para consumidores existentes e incluye eventos de éxito
  de reboot manual/automático. Un soft restart enviado no se suma como reboot.
- Transporte común de `sendMessage` para cola y fallback directo: hasta tres
  intentos ante desconexión, timeout, HTTP 5xx o 429. Respeta Retry-After hasta
  30 segundos; si es mayor, registra el fallo sin adelantar otro intento.
  Conserva timeouts de comandos directos (1.5/4 s) y cola (2/6 s).
- Solo HTTP 200 con `ok=true` confirma entrega y actualiza dedupe. Los fallos
  permanentes y el agotamiento de intentos quedan en logs sin payload ni token.
  El heartbeat se actualiza durante esperas; no hay nuevos threads ni locks
  durante red o sleep. Cola, multipartes, comandos y markup conservan su contrato.
- Compuerta de avisos por minero y tipo: primer LOW y primer HASHBOARD del episodio
  pasan; repetición del mismo tipo dentro de 300 s se suprime. OFFLINE conserva
  su alerta y la histéresis existente. OK limpia la compuerta y notifica recuperación.
  Snooze y mantenimiento bloquean avisos de transición. Todos los cambios de estado
  siguen registrados; el limiter no altera streaks ni políticas de actuación.
- Soft restart se atribuye solo a un evento `auto_restart_mining_success` reciente,
  compatible con el uptime observado y sin una detección posterior ya asociada.
  Ventana de 120 s, tolerancia de reloj de 10 s. Lectura bajo el lock propio del
  EventStore, fuera de state_lock. No se usa un timestamp de intento como éxito.

## Validación

- QA previo: PASS; compilación y diff limpios.
- Suite final previa a recarga: **1604 PASS y 75 subpruebas PASS**, 47.19 s.
- 21 pruebas específicas: transporte recuperable/permanente/rate limit,
  dedupe tras fallo, fallback directo, snooze vencido, replay de transiciones
  con QA/snooze, conteo SQLite y atribución de éxito/fallo/consumo/otro minero.
- Replay del chat: cinco avisos LOW/HASHBOARD pasan a dos avisos distintos más
  recuperación. Se conservan las seis transiciones en EventStore.
- Pruebas con `DBG_TELEGRAM=1`, `DBG_TELEGRAM_COMMANDS_ONLY=1`, red simulada y
  bases temporales locales. No se provocaron fallas ni reinicios de ASIC.
- Resultado del gate final y captura posterior: ver evidence.md de la spec 093.

## Activación observada

Servicio recargado a las **15:13:46–47 UTC-3**. Captura de las 15:14:51:
cuatro mineros y doce cadenas minando, ViaBTC activa, ningún restart_required.
Potencias 2298/2148/2298/2299 W reportados; temperaturas 80/83/81/81 °C.
Hash instantáneo 344.93 TH/s. Uptime de todos aumentó entre capturas; la recarga
del monitor no reinició los mineros. Cola Telegram 0; tick/sender de ~5 s.
Render con datos reales: sin falso Silenciado, seis reinicios detectados en 24 h,
cero órdenes de reboot contadas. Artefactos ignorados en diagnostics/messaging-20261115/.

## Límites y trabajos siguientes

La entrega tiene semántica de al menos una vez: una respuesta perdida puede
producir un duplicado al reintentar. Tras tres fallos no hay outbox persistente;
el fallo queda explícito. No se garantiza entrega durante una caída prolongada
de Telegram ni se repone automáticamente el historial de mensajes perdidos.
Los errores de transporte se ensayaron con mocks, no cortando la red de producción.

La atribución exige EventStore disponible; si faltan datos, no inventa evidencia.
No se reclasificaron eventos históricos. La observación inmediata del despliegue
no reemplaza la revisión D+1 ni resuelve la causa física del chain break de M26.

Se diseñaron, sin activar ni implementar, las specs 094 (respaldo verificable) y
095 (rendimiento sostenible basado en evidencia). El backup de Miner Alerts no
está configurado; no existe la carpeta backups ni se identificó una tarea específica
de respaldo. El mensaje de backup pendiente permanece como evidencia real.
094 debe validar integridad, frescura y restauración en staging antes de programar
la copia. 095 requiere atribución fiable y mediciones AC para conclusiones físicas;
la rentabilidad monetaria depende además de costos y retribución de pool.


Captura de cierre 15:19:11: 345.04 TH/s, cuatro mineros y doce cadenas minando,
80/83/81/81 °C, ViaBTC activa y sin reinicios ni ajustes pendientes tras la recarga.
Heartbeat actualizado, cola 0; watchdog real saludable a las 15:18:54. Se observaron
unos cinco minutos y medio de la versión nueva. Esto no certifica estabilidad D+1.
La limpieza se ejecutó en modo dry-run para preservar la evidencia forense.
