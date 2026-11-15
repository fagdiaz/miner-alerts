# Miner Alerts — reconciliación verificada el 14 de noviembre de 2026

**Estado: PASS operativo y preflight 8/8 a las 18:16:33 UTC-3.**
Activación confirmada a17:59:24; observación hasta18:17. Cambios sin commit/push automático.

## Problemas corregidos

- La configuración dinámica estaba guardada pero el servicio usaba la del12 de noviembre.
- Los techos residuales de M25/M26 impedían seguir subiendo aun a77°C.
- Los powerups nativos de VNish carecían de avisos de potencia real.
- El fallback de120s podía interrumpir el arranque; se alineó a600s con config y ejemplo.

La recarga está confirmada por hash efa85f7d. Techos C3 alineados en configuración y
firmware:2700/2500/2700/2500W; piso1740W y regulación79/84°C cada300s. Balanceador en
simulación: no se habilitó un segundo controlador de potencia. Protecciones térmicas activas.

## Resultado real

M25 subió de2150 a2300W y M26 de2000 a2150W. La alineación de la tarde no requirió
reiniciar los mineros. Los avisos se registraron tras90s de confirmación a18:08:56 y
18:15:26; el cooldown900s por minero evita repetir cada fluctuación.

| Equipo | Potencia activa reportada | Temperatura | Techo permitido |
|---|---:|---:|---:|
| S19JPRO-23 | 2298W | 80°C | 2700W |
| S19JPRO-24 | 1999W | 80°C | 2500W |
| S19JPRO-25 | 2298W | 80°C | 2700W |
| S19JPRO-26 | 2149W | 78°C | 2500W |

Captura final18:17:31: flota343.16TH/s y8744W reportados por ASIC. Cuatro equipos
minando, doce cadenas produciendo, ViaBTC activa en los cuatro y cero ajustes pendientes.
Desde recarga: no se detectaron reinicios, pausas térmicas ni errores Telegram en out.log.
Los datos de potencia no constituyen medición AC del tablero. El firmware conserva la
capacidad de subir o bajar según margen; techo permitido no significa potencia forzada.

## Validación

- Preflight completo8/8 PASS: regresión, sintaxis, diff, secretos, config, servicio, flota,DoD.
- 1561 pruebas y75 subpruebas PASS en93.88s.
- Pruebas dirigidas con DBG_TELEGRAM=1 y DBG_TELEGRAM_COMMANDS_ONLY=1:15 PASS.
- H004/R004 completadas bajo la política dinámica vigente; sin certificar observaciones
  históricas que no quedaron registradas. No pendientes de activación.

## Verificación de Codex

Paquete principal26.1111.2228.0 en estadoOk, runtime nuevo26.1112.737.0 en estadoOk,
y ejecutable responde codex-cli0.169.0-alpha.11.1. La comprobación TokenElevation confirma
que app, agente y ejecutor no estaban elevados. El runtime anterior figuraNotAvailable;
no basta para diagnosticar corrupción. Existe un reporte público de comportamiento
similar de elevación: https://github.com/openai/codex/issues/46682 (no demuestra misma causa).
No se modificaron instalación, registro, políticas de seguridad ni permisos de WindowsApps.
La operación de Miner Alerts ya quedó completada sin necesidad de otra elevación.

## Trazabilidad y continuidad

Capturas y backups locales ignorados:diagnostics/reconcile-20261114. Comandos, efectos
transitorios e intentos previos se conservan en evidence.md. Config/state sin versionar.
Commit/push manuales; nueva implementación de otra spec exige cierre manual de release.
Una revisiónD+1 puede comparar estabilidad y avisos; no constituye una tarea ya verificada.


### Extensión de observación hasta18:19 UTC-3
M26 efectuó un segundo powerup nativo2150→2300W, a79°C, sin reinicio ni ajustes
pendientes. No se repitió un aviso inmediato dentro del cooldown900s, conforme al
criterio anti-spam. Los cuatro siguenOK; observación completa supera19min desde recarga.
Captura18:19:01:2298/1999/2298/2299W; temperaturas80/80/80/79°C; ~343.5TH/s.
Se detuvo únicamente el lector auxiliar de observación al finalizar; MinerAlerts continúa.
