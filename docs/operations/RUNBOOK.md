# Manual de operación

> Tipo: procedimiento · Revisión: 2026-11-16 · Ejecutar comandos desde la raíz del repositorio.

## Consulta inicial

Comenzar por `/status`, `/why <id>`, `/presets <id>` y `/fans <id>` en Telegram.
Consultar la edad de las muestras y el estado nativo; una respuestaTCP no implica
que el minero esté minando. El [catálogo](TELEGRAM.md) distingue consultas y controles.

Consultas locales sin actuación sobre mineros:

```powershell
nssm status MinerAlerts
Get-Content -LiteralPath .\data\monitor_heartbeat.json
Get-Content -LiteralPath .\logs\watchdog.log -Tail 10
& .\.venv\Scripts\python.exe tools\monitor_watchdog.py --config app\config.json --no-notify
```

Comprobar tick, poller, sender, cola y proceso. Heartbeat reciente y servicio Running
son necesarios, pero no demuestran salud de placas, temperatura o pool. No difundir
logs crudos: algunas versiones antiguas pudieron registrar tokens en URLs.

## Diagnóstico de un incidente

1. Registrar inicio, mineros afectados, uptime, TH/s, placas, temperaturas y potencia
   reportada. Diferenciar caída de producción de una oscilación puntual de lectura.
2. Correlacionar con eventos SQLite, firmware y acciones realmente enviadas. Una
   intención o marca pendiente no prueba un restart ejecutado.
3. Revisar autotune, cambios nativos de preset y protección térmica antes de intervenir.
4. Comparar los equipos del mismo grupo eléctrico. La simultaneidad orienta el análisis,
   pero no identifica por sí sola la fuente eléctrica.
5. Conservar artefactos y concluir con observado, inferido y desconocido explícitos.

[Diagnósticos](DIAGNOSTICS.md) contiene los comandos de exportación. La política de
[temperatura y potencia](THERMAL_AND_POWER.md) explica las guardas y límites.

## Recarga controlada del monitor

Solo cuando un cambio de código o config ya esté validado y la actuación esté dentro
del alcance autorizado. Una edición documental no requiere recarga.

1. Registrar PID, hash de configuración y uptimes previos de los mineros.
2. Crear un lease acotado del watchdog para la operación planeada:

```powershell
& .\.venv\Scripts\python.exe tools\monitor_watchdog.py --config app\config.json --maintenance-seconds 900 --maintenance-reason "recarga controlada"
```

3. En sesión elevada, recargar únicamente el servicio del monitor:

```powershell
nssm restart MinerAlerts
nssm status MinerAlerts
```

4. Confirmar nuevo bloque de arranque, PID, ruta/hash de config, modo QA y ticks frescos.
   Verificar uptimes crecientes de los mineros, placas, temperatura, pool y ausencia
   de flags pendientes. El reinicio del monitor y el reinicio de un minero son acciones distintas.
5. Cerrar el lease una vez comprobada la salud, o dejar vencer su plazo si corresponde:

```powershell
& .\.venv\Scripts\python.exe tools\monitor_watchdog.py --config app\config.json --clear-maintenance
```

Si Windows esperaUAC, la autorización del trabajo no sustituye la aceptación del sistema
operativo. Un UAC cancelado o un launcher exitoso no equivalen a una recarga completada.
No abrir avisos repetidos sin comprobar el resultado anterior.

## Telegram sin entrega o con avisos repetidos

- Contrastar salud de poller/sender, cola y logs de entrega. Silencio puede significar
  ausencia de eventos, snooze/mantenimiento, supresión o un fallo de transporte.
- Comprobar `ok=true` y confirmación de envío; el dedupe solo debe consolidar mensajes
  entregados. La respuesta perdida puede dejar duplicados; no hay garantía exactly-once.
- No habilitar avisos de prueba continuos ni publicar tokens para diagnosticar conexión.
- Los mensajes de recuperación y de incidentes reales permanecen operativos; controlar
  frecuencia por episodio y por tipo, con evidencia del motivo de supresión.

## Intervenciones y restauración

No usar reboot/restart como test rutinario de documentación o de release. Confirmar
minero, acción, riesgo, QA y ventana antes de cualquier ensayo real. No borrar state.json,
locks o bases activas como una limpieza. Ver [respaldo y staging](BACKUP_AND_RESTORE.md)
antes de una recuperación de datos; no copiar archivos sobre SQLite en vivo.

## Cierre de una comprobación

Registrar comandos, resultado, versión/hash, modo, proceso cargado, periodo observado
y pendientes. Una ventana corta no certifica D+1 ni una reparación física. El último
[corte documentado](PRODUCTION_BASELINE.md) no es un dashboard en tiempo real.
