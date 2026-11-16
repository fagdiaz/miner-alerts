# Estabilización 096 — reinicios durante cambios nativos

Estado al16/11/2026 11:18 UTC-3: **desplegada y verificada en una ventana de660.1s**.
Gate de código y controles directos PASS. D+1, diagnóstico físico y releaseGit096 pendientes.
El script automático de PowerShell no pudo iniciar; no se certifica su ejecución.

## Diagnóstico y corrección

M24 alcanzó86°C a02:12:06. El monitor inició un downstep a2300W y, un segundo
más tarde, el L1 tomó restart_required como fallo pese a que producía. Aplicó1800W
y reinició, interfiriendo con el cambio nativo. Además, engine infería mining desde
la respuestaTCP y no veía auto-tuning. El flag sano ahora se deriva al watchdog de
presets, que conserva soak, temperatura y cooldown. Se consulta estado fresco y se
respetan autotune, mantenimiento, snooze, pausa y asentamiento térmico. L1 yL2
quedan excluidos durante recuperación. El preclamp conserva el techo nativo;
workers verifican QA/gobernanza y el watchdog revalida estado, flag y temperatura.
HTTP fuera de state_lock, timeouts2.5s, sin nuevos hilos ni campos persistentes.

El ajuste anterior80/85 fue restituido a79/84/check300 en4/4. Su observación hasta
01:26 no cubría los fallos posteriores. VNish deM24 confirma una bajada nativa a
2150W a09:51:19 con84°C, sin reinicio. No se asegura una inclusión exacta del
79°C mostrado porUI a partir de esta prueba.

M23 tuvo chainbreak tras2700W: techo contenido en2500W. M26 repitió chainbreak
nativo a10:07:47, con fallos de inicialización10:10:44 y10:13:17; recuperó10:17:15.
Fue anterior a la recarga y sin orden de restart del monitor. Se contuvo soloM26
en2300W a11:04:01, sin reiniciar; potencia2299W confirmada11:06:49. Firmware,
perfiles yconfiglocal coinciden. No se activó el balanceador: sigue enDRY.

## Despliegue y evidencia

Primera recarga11:00:01/PID34524; recarga final11:06:28/PID17364. UAC aceptado,
NSSM exit0 ySERVICE_RUNNING. CONFIGsha8e9c20b5 cargada, posterior al ajusteM26.
No reinicios de mineros enviados para probar. El primer UAC cancelado1223 quedó
resuelto por estas recargas; no hay aviso ni despliegue pendiente.

Observación11:06:49–11:17:49:23 capturas de flota,660.1s,4/4mining y12placas en
todas. Cero caídas de uptime, cero restart_detected, cero flags pendientes.
Temperaturas80–83°C. Media354.03TH/s y cierre354.08TH/s,9244W reportados porASIC.
Estos watts no son medicionesAC. PID17364 único, heartbeat máximo22.2s ycola0.

| Minero | Potencia al cierre | Máxima de chips | Techo configurado |
|---|---:|---:|---:|
| S19JPRO-23 | 2499W | 83°C | 2500W |
| S19JPRO-24 | 2148W | 82°C | 2500W |
| S19JPRO-25 | 2298W | 80°C | 2500W |
| S19JPRO-26 | 2299W | 81°C | 2300W |

ViaBTC btc.viabtc.io Alive/StratumActive en4/4 y shares aceptados. Watchdog externo
healthy=true, aviso recovery entregado11:07:56. Sin cambios de políticaTelegram ni
mensajes de prueba. No hay errores de hooks/restart en logs posteriores a recarga.

## Validación

Pruebas rojas4FAIL/2PASS reprodujeron el incidente. Focalización final131PASS;
suite final1667PASS+75subpruebas,108.28s conDBG_TELEGRAM=1 y
DBG_TELEGRAM_COMMANDS_ONLY=1. Sintaxis del monitor y módulos PASS. Gate final
porPython/git/nssm:diff,secretos,configuración,4028,servicio yDoD PASS a11:18:03.
PowerShell.exe/pwsh no iniciaban: controles equivalentes directos conservados en
 gate096-final.json; sin declarar corrida automática8/8. Cleanupdry-run24candidatos,
0eliminados; evidencias/config/state/bitácora/logs preservados. Código no modificado
después de la suite. Solo se ajustaron el techo individualM26 y documentos.

094 cerrada antes de activar096: a8ce841 publicado con autorización; respaldo03:00
verified,389083136bytes,7.797s. 095 sigue solo planificada y espera cierre096.
Commit/push096 manuales, no ejecutados; autorizaciónGit recibida cubría094.

## Límites y seguimiento

Los chainbreaks no identifican por sí solos red de calle, elevador, PSU, cableado
o placa. Falta mediciónAC y revisión física.2300W es contención revisable deM26,
no reparación ni óptimo económico demostrado. Históricos72h muestran~87.73TH/s
a2300W y~93.02TH/s a2500W; no controlan ambiente ni atribuyen todo el tiempo de
recuperación. D+1 y comparación neta con costos/pool quedan abiertos. Esta ventana
certifica su duración observada, sin prometer funcionamiento futuro sin fallas.

Artefactos privados ignorados: diagnostics/stability-20261116. Config/state/perfiles
nunca incorporados aGit. prompt.txt contiene el estado actual y los comandos.
