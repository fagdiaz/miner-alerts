# Evidencia096 —16/11/2026

Análisispreimplementación: docs/audit/POWERUP_POLICY_20261116.md eshistórico;
ventanacerró01:26ylosfallos posteriores invalidanestabilidadextendida.
Native statuslogs guardados diagnostics/restarts-20261116: M23chainbreak
02:15:50tras2700;M26chainbreak01:50:52;M24cambiando2300a02:12:07
yminingstopped02:12:10despuésdelL1monitor.

Lectura09:43:4/4mining,12placas,82–84C,>7h sin reinicio,
restart_requiredfalse. Operación09:45–09:47 restauró79/84/check300en4/4
sinreinicio. M23top2500/perfilyconfiglocalalineados, recargapendiente.

QA: HIGH; riesgo de interrupción de producción yclampseléctricos.
Locks: engineinvocahooksecuencialmente; estados compartidosbajostate_lock;
workers daemon ysyncVNish actualizancache cada300s. Solorestart_required
cacheado noes evidencia de fallo. LecturasHTTPsiemprefuera dellock.
Conservar guardsarranque/cooldown/reintentos/L2;autotunewatchdogexistente
atiende tuningestancado. Pruebasno deben accionarLAN.

QApreimplementación: testsrojos0964FAIL/2PASSreproducen exactamente flag sano
yauto-tuning/autotuning. PreflightQA PSintentado ybloqueadoenarranque;
contratos/artefactos/manualreviewycompilaciónbasePASS; sinsecretos.
Trasprimerparche:104testsPASS7s(096/two_tier/watchdog/hooks),faltangatesfinales.

Primera suitecompleta1663+75PASS58.18s. Auditoríaposteriordetectóque
L2podíainterferir conventanaL1yconasentamientotérmico:seagregaron
exclusiónL1/L2,pausatérmica,mantenimiento/snooze ycooldowntérmicoexistente.
Validaciónfocalizadafinal131PASS6.97s;suitedefinitivaen ejecución.
Sin nuevoskeysconfig,nilocks,hilosopersistencia. Native HTTPsolo ante
posibleintervención;fallodelecturabloqueaL1, L2conservasusinterlocks.

## Validación final y despliegue aún no realizado

Suite definitiva1667+75PASS108.28s con DBG_TELEGRAM=1 y
DBG_TELEGRAM_COMMANDS_ONLY=1. Controles directos de sintaxis, diff, secretos,
configuración,4028 y NSSM PASS. El preflight PowerShell no inició; no se
declara una corrida automática del script.

ShellExecuteEx solicitó UAC para NSSM restart a10:03; el aviso se cerró con
error1223 a10:10, sin ejecutar reload.cmd. No existe reload-exit.txt ni PID nuevo.
Por eso R005 sigue pendiente y no se declara código desplegado. Se preguntó
al usuario si está frente aPC para abrir otro aviso. No hubo reinicio de mineros.

VNish nativo deM24 confirma09:51:19 Lowering preset to2150 (temp=84,pwm=100),
sinMining stopped posterior. Telegramevidencia: POWER_CHANGE09:54:15 y
DIGEST10:00:15 entregados; cola0. No hay silencio total ni mensajes de prueba.
Observador pasivo de recarga detenido al quedar sin UAC activo; reanudar solo
después de la respuesta del usuario y confirmar PID nuevo.

## Recarga efectiva y nueva evidencia —16/11 11:07

UAC aceptado: primera recarga11:00:01,PID34524,exit0/SERVICE_RUNNING.
Durante la espera anterior, M26 tuvo chainbreak10:07:47 y fallos de inicialización
10:10:44/10:13:17; recuperó minado10:17:15. Sin orden de restart del monitor.
El hecho es anterior al código nuevo y permanece como evidencia física nativa.

Balanceador en DRY recomendaba bajarM26 por4 reinicios/24h; no se activó.
Se aplicó soloM26: preset/top2300 a11:04:01, pareja79/84 intacta, sin restart.
Perfil yconfig local alineados. Segunda recarga11:06:28,PID17364,exit0.
11:06:49: M26reporta2299W/88.66TH/s,80C,3placas,uptimecreciente.
Techos finales2500/2500/2500/2300. La primera observación se cerró antes del
ajuste; ventana final nueva de660s iniciada11:06:49 (observation096.jsonl).

Datos históricosM26 (72h,8639 muestras):2300W~87.73TH/s(n1969);
2500W~93.02TH/s(n2640). Comparación observacional, sin controlar ambiente ni
asignar tiempo de recuperación a cada techo; no prueba rentabilidad neta.
2300W es contención y línea base de observación, no reparación ni óptimo probado.

Alineación11:07:55: firmware y perfiles iguales en switcher79/84/check300;
techos2500/2500/2500/2300. Log CONFIG11:06:28 confirma SHA8e9c20b5,
coincidente con configlocal; PID17364 posterior a todas las modificaciones.
Hash engineffbc3e62672d6e66 yrestart_intelligence5d6c2781c8c2118b.
No cambios de fuente desde la suite1667+75; solo configuración individual deM26
y documentación. Rerun completo no necesario; contratos de límites ya cubiertos.
Solo se alineó el diseño futuro095 con096 y techos nuevos;095 no activada.

## Verificación final de producción —16/11/2026

Ventana 2026-11-16T11:06:49.517727-03:00 a 2026-11-16T11:17:49.514245-03:00: 660.1s, 23 capturas,
4/4mining y12placas en todas. Cero caídas de uptime, cero restart_detected
y cero flags restart_required/reboot_required. Temperaturas 80–83C.
Media instantánea de flota 354.03TH/s; cierre 354.08TH/s y
9244W reportados por ASIC, sin inferir consumoAC. PID17364 único,
heartbeat máximo 22.2s y cola Telegram máxima 0.

Watchdog externo11:07–11:17 reporta healthy=true; aviso recovery entregado11:07:56.
ViaBTC btc.viabtc.io Alive/StratumActive en4/4; shares aceptados observados.
Sin mensajes de prueba ni cambios de política Telegram. Sin errores de hooks trasrecarga.

Comandos de validación: python -m pytest -q mediante validate096.py con
DBG_TELEGRAM=1 yDBG_TELEGRAM_COMMANDS_ONLY=1:1667+75PASS108.28s;
python -m py_compile app/miner_monitor.py app/core/engine.py
app/core/restart_intelligence.py:PASS. NSSM status MinerAlerts:SERVICE_RUNNING.
Gitdiffcheck yescaneo de modificados/nuevos sin secretos:PASS.
Gate final directo: diagnostics/stability-20261116/gate096_final.py;
resultado gate096-final.json. PowerShell no inicia: el script automático de
speckit-stabilize no se certifica ejecutado; controles equivalentes directos.
Cleanup dry-run:24 candidatos,0 eliminados;config/state/logs/bitácora preservados.

D+1, diagnóstico físico M26 y rentabilidad neta quedan sin certificar.2300W es
contención revisable; necesita ventana larga y datosAC/costos para concluir
óptimo.095 sigue planificada;096 sigue activa hasta releaseGit manual.
Commit/push096 no ejecutados; autorizaciónGit anterior cubría094.
