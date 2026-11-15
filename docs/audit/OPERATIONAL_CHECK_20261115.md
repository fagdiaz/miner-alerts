# Verificación operativa — 2026-11-15 14:34 UTC-3

Solicitud: comprobar funcionamiento y mensajes de Telegram. Revisión de solo lectura
del servicio, heartbeat, SQLite, logs, API VNish y API Telegram; sin reinicios, cambios
de configuración, envío de mensajes ni consumo paralelo de getUpdates.

## Estado actual

- MinerAlerts RUNNING; proceso activo desde 2026-11-14 22:31:50, aproximadamente 16 h.
- Heartbeat: tick 23 s, poller 37 s, sender 23 s, cola 0. Watchdog saludable.
- Captura directa 14:33: cuatro mineros y doce cadenas minando, ViaBTC activa,
  restart_required=false en todos. 9043 W reportados, 344.92 TH/s instantáneos.
- M23/M24/M25/M26: 2298/2148/2298/2299 W y 80/83/81/81 °C.
- Promedio de los últimos 30 minutos: 345.56 TH/s; 60 muestras por minero.
- Sin pausas térmicas actuales, mantenimiento programado ni snoozes vigentes.

## Incidencias desde la última carga

Cuatro eventos restart_detected: M26 14/11 23:12, 23:25 y 15/11 11:39;
M23 14/11 23:42. M24 y M25 sin reinicios durante esta ventana.
Dos acciones auto_restart_mining_success: M26 23:25:22 y M23 23:41:52.
No equivalen a cuatro fallas espontáneas.

El reinicio M26 23:25:51 está clasificado unexpected pese al éxito de la acción
automática 30 s antes. DetectionHook pasa last_auto_reboot_ts a classify_restart,
pero omite el timestamp de soft restart. No corregido en esta revisión; requiere
atribución de acciones exitosas, sin convertir intentos fallidos en evidencia de éxito.

Hoy el firmware de M26 registra chain_break y watchdog_chain_restart a 11:38:21.
El monitor detecta caída de uptime a 11:39:03; vuelve a OK a 11:47:33. M25 continúa
sin reinicio. Esta incidencia individual no demuestra caída compartida de elevador
ni identifica por sí sola la causa física. Temperatura previa reportada 78 °C.

Anoche hubo downsteps térmicos a 86 °C en M24 y M23. Actualmente la regulación
mantiene las temperaturas indicadas; no se forzó un aumento de potencia.

## Telegram

- getMe, getWebhookInfo y getChat: HTTP 200, ok=true.
- Webhook ausente (polling), pending_update_count=0, chat privado accesible.
- Lectura y envío activos según heartbeat; no silencio global por mantenimiento.
- Logs registran RemoteDisconnected durante sendMessage a 00:18:53 y 12:06:04.
  Coinciden temporalmente con avisos de potencia M23 y M26, respectivamente; el log
  no identifica el contenido exacto del mensaje que falló.
- telegram_sender_worker retira el elemento y, ante esa excepción, registra el
  error y continúa sin reencolarlo. El resultado remoto es incierto: no asumir
  entrega ni ausencia definitiva. Un reintento futuro debe contemplar duplicados
  posibles, límites, prioridad y contabilización de entrega solo confirmada.
- Se observaron 17 POWER_CHANGE desde la carga, con confirmación/cooldown; el log
  de generación no demuestra recepción de cada mensaje.
- No se encontró una ventana Telegram disponible. Se preguntó al operador por la
  ubicación de su sesión. No se pudo leer el historial visible ni certificar entrega
  extremo a extremo. No se envió un mensaje de prueba sin instrucción específica.

## Alcance y pendientes

Sistema produciendo actualmente; no declarar todo resuelto: persiste incidencia de
M26, debilidad de entrega Telegram y atribución incorrecta del soft restart.
No hubo cambios de código ni nuevo despliegue; la suite 1583+75 del cierre anterior
no se volvió a ejecutar para esta revisión de solo lectura.
Captura local ignorada: diagnostics/verification-20261115/fleet.json.
Modelo elegido por el operador: GPT 6.1 Sol con razonamiento alto.


## Contraste posterior con Telegram Desktop abierto por el operador

Se leyó el historial de Miner Alerts mediante la skill computer-use, sin enviar
mensajes ni ejecutar controles del bot. Confirmada recepción de avisos de potencia,
enfriamiento, respuestas Status de07:02/11:44 y recuperación de flota11:47.
El último aviso leído es la bajada M25de2500a2300W a13:53.

Hallazgos adicionales confirmados:
- Las tarjetas Status07:02/11:44 dicen Silenciado para los cuatro mineros aunque
  los snoozes persistidos vencieron. fleet_cards.py comprueba snooze_until is not
  None, sin comparar con la hora. Es un error de presentación, no silencio real.
- Reporte10:00:13 anomalías y0reinicios. daily_digest.py cuenta reboot_action/
  reboot_execute o decisiones executed, pero omite restart_detected. La etiqueta
  mezcla reinicios detectados con acciones de reboot. Deben mostrarse por separado,
  sin sumar acción y observación del mismo episodio.
- M26: cinco alertas alternadas LOW/HASHBOARD11:40–11:44 durante una recuperación,
  después FLOTA RESTABLECIDA11:47. La alternancia está en los eventosSQLite y el
  despachador emite cada transición; hay ruido de un mismo incidente.
- No aparecen en el historial leído la subida M26de1800a2000W12:06 ni la subida
  M23de2000a2300W00:18, coincidentes con los dos errores sendMessage. Esto respalda
  pérdida de esos avisos; no afirmar que todos los demás mensajes están auditados.
- El reporte también muestra Sin backups recientes. No se validó en esta ampliación
  la disponibilidad real de backups; queda por revisar con el sistema de respaldo.

Revisión concluida: recepción de múltiples mensajes confirmada de extremo a extremo;
la mensajería no está totalmente correcta. Hallazgos documentados, aún sin corrección
ni nueva versión aplicada. La ubicación de Telegram ya quedó resuelta.
