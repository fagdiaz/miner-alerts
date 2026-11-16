# Último corte de producción documentado

> Tipo: evidencia resumida · Corte: 2026-11-16 11:18 UTC-3 · No es un estado en vivo.

## Resultado observado

| Dato | Evidencia del corte |
|---|---|
| Monitor | NSSM MinerAlerts, PID 17364, recarga 11:06:28 |
| Configuración cargada | Hash 8e9c20b5, posterior a los ajustes individuales |
| Ventana | 11:06:49–11:17:49, 660.1 s y 23 capturas |
| Producción | 4/4 mining, 12 placas, cero caídas de uptime o flags pendientes |
| Temperatura | 80–83 °C en esa ventana |
| Rendimiento | Media 354.03 TH/s; cierre 354.08 TH/s |
| Potencia | 9244 W reportados por ASIC al cierre; no medición AC |
| Telegram / liveness | Cola 0, heartbeat máximo 22.2 s, watchdog healthy; entrega recovery 11:07:56 |
| Pool | btc.viabtc.io activa y shares aceptados en 4/4 |

## Política local alineada

| Equipo | Techo |
|---|---:|
| M23 | 2500 W |
| M24 | 2500 W |
| M25 | 2500 W |
| M26 | 2300 W |

Switcher 79/84 °C, check_time=300 s, piso 1740; perfiles de recuperación y configuración local
alineados. Balanceador en DRY. Guardas de emergencia del corte: downstep 85.5 °C y
pausa 87 °C, sin elevarlas para conseguir powerups.

## Validación y publicación

1667 pruebas y 75 subpruebas aprobadas en 108.28 s; focalización 131 PASS. Controles directos
de sintaxis, secretos, configuración, conectividad, servicio y DoD aprobados. PowerShell
no inició en esa sesión: no se certifica ejecución del preflight automático; sus controles
se registraron por otras herramientas. No se hicieron nuevas pruebas de runtime al
normalizar documentación.

093 publicada como 0695385 y 094 como a 8ce841. 096 desplegada y observada en esta ventana;
commit/push 096 siguen manuales y pendientes. Backup automático 16/11 a 03:00 verified,
389083136 bytes/esquema 7/7.797 s. Una copia en la misma unidad no cubre pérdida física del disco.

## Pendientes y límites

- D+1 bajo calor diurno no certificado.
- M26 repitió chainbreak nativo a 10:07:47 antes de cargar el código nuevo y sin orden
  del monitor. El techo 2300 W es contención revisable; causa AC / PSU / conexiones / placa desconocida.
- Una ventana de once minutos no demuestra estabilidad futura ni máximo beneficio económico.
- Retención destructiva de backups no habilitada automáticamente por el cierre 094.

Fuente: [informe 096](../audit/STABILIZATION_REPORT_20261116_RESTART_SAFETY.md),
[bitácora](../audit/DEVELOPMENT_LOG.md) y artefactos privados referidos en la evidencia
local. Los informes anteriores conservan sus resultados y límites temporales.
