# Telegram: consulta y control

> Tipo: referencia Â· RevisiÃ³n: 2026-11-16 Â· CatÃ¡logo contrastado con help_center.py.

La ayuda vigente se consulta con `/help` y `/help <comando>`. El registro en
[help_center.py](../../app/telegram/help_center.py) describe el catÃ¡logo; el
[router](../../app/telegram/router.py) y handlers definen su ejecuciÃ³n. Una etiqueta
safe del catÃ¡logo no garantiza que todas las variantes de un comando sean de lectura.

## Consultas frecuentes

`/status`, `/why <id>`, `/presets <id>`, `/fans <id>`, `/events` y `/diagnose` ayudan a distinguir
estado actual, histÃ³rico y evidencia nativa. Ver edad de muestras y modo antes de actuar.
Los grÃ¡ficos/digest consumen historial; no certifican salud instantÃ¡nea por sÃ­ solos.

## Controles y confirmaciones

Reboot/restart solicitan confirmaciÃ³n; los tokens manuales e inline de reinicio tienen
TTL 60 s en el contrato actual. Una selecciÃ³n o preview no equivale a acciÃ³n ejecutada.
Snooze, modo silencioso, permisos, presets y apagado tienen efectos operativos diferentes.
Revisar /help, objetivo, QA y permisos antes de usar variantes de escritura. No usar un
reinicio confirmado como prueba rutinaria de documentaciÃ³n.

## CatÃ¡logo de referencia

La tabla es un corte del registro; los aliases y usos exactos se resuelven con la ayuda.
La columna de efecto es conservadora y no sustituye la revisiÃ³n de subcomandos.

| Nombre del registro | Uso | DescripciÃ³n | Efecto a revisar |
|---|---|---|---|
| status | `/status` | Snapshot actual de la flota. | Consulta o navegaciÃ³n; revisar variantes |
| info | `/info [id\|all\|<comando>]` | TelemetrÃ­a detallada o ayuda. | Consulta o navegaciÃ³n; revisar variantes |
| chart | `/chart [id\|grupo\|fleet] [horas]` | GrÃ¡ficos PNG de telemetrÃ­a. | Consulta o navegaciÃ³n; revisar variantes |
| digest | `/digest  \|  /summary` | Resumen ejecutivo 24 h. | Consulta o navegaciÃ³n; revisar variantes |
| fans | `/fans [id\|all]` | Salud de coolers y margen 85 Â°C. | Consulta o navegaciÃ³n; revisar variantes |
| governor | `/gov [on\|off\|set <temp>]` | Regulador lazo cerrado (82 Â°C). | Puede modificar estado/configuraciÃ³n/hardware |
| silent | `/silent <duraciÃ³n\|off>` | Modo silencio (30-50% PWM). | Puede modificar estado/configuraciÃ³n/hardware |
| efficiency | `/efficiency [id\|all]` | Eficiencia en Joules por TH. | Consulta o navegaciÃ³n; revisar variantes |
| presets | `/presets [id\|all]` | Frecuencias, tensiÃ³n y tuning. | Consulta o navegaciÃ³n; revisar variantes |
| balancer | `/balancer [on\|off\|miner]` | Balanceador para elevadores. | Puede modificar estado/configuraciÃ³n/hardware |
| elevadores | `/elevadores` | DiagnÃ³stico de carga elevador. | Consulta o navegaciÃ³n; revisar variantes |
| menu | `/menu  \|  /start  \|  /panel` | Command Center interactivo. | Consulta o navegaciÃ³n; revisar variantes |
| reboot | `/reboot <id>  \|  /rb<id>` | Reinicio manual de un minero. | Puede modificar estado/configuraciÃ³n/hardware |
| reboot_no_ok | `/reboot_no_ok` | Reinicio agrupado de NO-OK. | Puede modificar estado/configuraciÃ³n/hardware |
| restart | `/restart <id>` | Restart del software minero. | Puede modificar estado/configuraciÃ³n/hardware |
| confirm | `/confirm reboot <id> <code>  \|  /c<code>` | Confirma acciÃ³n pendiente. | Puede modificar estado/configuraciÃ³n/hardware |
| snooze | `/snooze <id\|all> [minutos]` | Pausa alertas por mantenimiento. | Puede modificar estado/configuraciÃ³n/hardware |
| unsnooze | `/unsnooze <id\|all>` | Reactiva supervisiÃ³n normal. | Puede modificar estado/configuraciÃ³n/hardware |
| snoozed | `/snoozed` | Lista mineros en mantenimiento. | Consulta o navegaciÃ³n; revisar variantes |
| shutdown | `/shutdown [id1 id2... \| all]` | Parada segura y purga tÃ©rmica. | Puede modificar estado/configuraciÃ³n/hardware |
| resume | `/resume [id1 id2... \| all]` | Reanudar minado tras parada. | Puede modificar estado/configuraciÃ³n/hardware |
| agent | `/agent [status\|log]` | Estado del agente supervisor. | Puede modificar estado/configuraciÃ³n/hardware |
| events | `/events [id]` | Historial reciente de incidentes. | Consulta o navegaciÃ³n; revisar variantes |
| event | `/event <id>  \|  /e<id>` | Detalle de incidente por ID. | Consulta o navegaciÃ³n; revisar variantes |
| why | `/why [id]` | Explica Ãºltimo auto-reboot. | Consulta o navegaciÃ³n; revisar variantes |
| diagnose | `/diagnose [id\|all]` | DiagnÃ³stico multidisciplinario. | Consulta o navegaciÃ³n; revisar variantes |
| health | `/health [id\|all]` | ComparaciÃ³n con baseline estable. | Consulta o navegaciÃ³n; revisar variantes |
| quality | `/quality [id\|all]` | Calidad de minado y errores HW. | Consulta o navegaciÃ³n; revisar variantes |
| firmware | `/firmware [id\|all]` | Evidencia de firmware Vnish. | Consulta o navegaciÃ³n; revisar variantes |
| selftest | `/selftest  \|  /test` | Chequeo rÃ¡pido de subsistemas. | Consulta o navegaciÃ³n; revisar variantes |
| help | `/help  \|  /help <comando>` | Centro de ayuda y navegaciÃ³n. | Consulta o navegaciÃ³n; revisar variantes |
| chains | `/chains [id\|all]` | Salud y sensores por hashboard. | Consulta o navegaciÃ³n; revisar variantes |
| anomalias | `/anomalias [resumen\|detalle]` | Desglose de anomalÃ­as 24 h. | Consulta o navegaciÃ³n; revisar variantes |
| autopsia | `/autopsia [id\|all]` | Autopsia forense post-mortem. | Consulta o navegaciÃ³n; revisar variantes |
| directivas | `/directivas [watchdog\|grace\|all]` | PolÃ­ticas activas y gobernanza. | Consulta o navegaciÃ³n; revisar variantes |

## Entrega y frecuencia

Las respuestas a comandos y las alertas tienen contratos de entrega distintos. Conservar confirmaciones de envÃ­o, razones de supresiÃ³n y lÃ­mites de cola; no silenciar avisos legÃ­timos para ocultar inestabilidad. La respuesta perdida puede duplicar un aviso: no se afirma exactly-once ni un outbox persistente.

Consultar [RUNBOOK](RUNBOOK.md) para incidentes de entrega y [configuraciÃ³n](CONFIGURATION.md) para las claves de transporte y dedupe.
