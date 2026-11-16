> HISTÓRICO: la observación terminó a01:26. Los fallos posteriores invalidaron
> la estabilidad extendida. El16/11 a09:45–09:47 se restauró79/84/check300;
> ver specs/096-native-switcher-restart-safety/evidence.md para el estado vigente.

# Ajuste individual de powerup — 16/11/2026 01:26 UTC-3

El operador autorizó aplicar individualmente en los cuatro mineros una regla que
permita subir de potencia a 79 °C, conservando el código del sistema. Se realizó
como ajuste operativo del firmware, sin activar otra spec ni modificar el monitor.

## Restricción encontrada y política aplicada

VNish rechazó HTTP 400 al intentar rise_temp=80 con decrease_temp=84. La lectura
posterior confirmó que el intento rechazado dejó los ajustes originales intactos.
La combinación admitida para incluir 79 °C es **subida 80 / bajada 85**, con al menos
5 °C de separación. Se informó esa diferencia antes de continuar.

En los cuatro mineros quedó verificado:

- rise_temp=80 °C: subida cuando la temperatura sea inferior a 80 °C.
- decrease_temp=85 °C: umbral nativo de bajada, elevado 1 °C respecto de la política anterior.
- check_time=300 s; no representa una promesa de subir exactamente cada cinco minutos.
- Switcher habilitado, min_preset=1740, ignore_fan_speed=true y power_delta=0.
- Techos conservados: M23 2700 W; M24/M25/M26 2500 W.

Las protecciones independientes del monitor permanecen habilitadas e intactas:
reducción de emergencia a 85.5 °C y pausa a 87 °C. Antes de cada ajuste se comprobó
heartbeat reciente, minero produciendo, tres placas activas, ausencia de pausa y
restart_required=false. El balanceador continúa en dry-run; VNish sigue decidiendo
los cambios de potencia.

## Aplicación escalonada

| Minero | Aplicación UTC-3 | Umbrales anteriores | Resultado observado |
|---|---|---|---|
| M24 | 00:59:40 | 79/84 | 2000 → 2150 → 2300 W, sin reinicio |
| M25 | 01:07:54 | 79/84 | 2300 → 2500 W, sin reinicio |
| M26 | 01:14:13 | 79/84 | Ya operaba en 2500 W; ajuste confirmado |
| M23 | 01:20:23 | 78/84 | Continúa en 2500 W a 82 °C; aún sin condición de subida |

Se completaron cuatro ventanas de observación de 330 segundos, una antes de pasar
al siguiente equipo. Se observaron los cuatro mineros simultáneamente mediante
consultas de lectura cada 30 segundos. Las 48 capturas de flota abarcan 01:00:00 a
01:26:02, con 192 observaciones individuales y ninguna caída de uptime.

M26 había subido por sí mismo a 2500 W antes de su ajuste, tras registrar 78 °C con
la regla anterior; esa subida no se atribuye al cambio aplicado a M26. M24 fue visto
en 2150 W a las 01:08:03 y en 2300 W a las 01:12:34. M25 fue visto en 2500 W a
las 01:15:52. Los cambios fueron decisiones del switcher, no órdenes de potencia máxima.

## Protocolo y persistencia

La API exige incluir un preset al guardar el switcher. Se envió el tier inferido de
la potencia real de cada minero, en lugar del preset JSON antiguo que podía diferir
de la potencia activa. Se conservó el objeto completo del switcher y se modificaron
sus umbrales. No se ejecutaron Apply/restart_mining, reboot ni reinicios del servicio.

Se guardaron copias locales previas y lecturas posteriores. Los perfiles dorados de
recuperación quedaron alineados en 80/85. La comparación de sus estructuras confirmó
que todos los demás campos permanecieron iguales. No se editaron app/state.json ni
app/config.json; el hash de configuración del monitor sigue siendo 39c2afee.

Se verificaron hashes de **246 archivos Python de app/, tools/ y tests/**: ninguno
cambió durante la operación. Solo se usó una herramienta operativa temporal dentro
de diagnostics/, que no forma parte del código desplegado ni se incorpora a Git.

## Captura de cierre

Lectura autenticada del firmware a las **01:26:12 UTC-3**:

| Minero | Potencia reportada | Máxima de chips | Placas |
|---|---:|---:|---:|
| M23 | 2499 W | 82 °C | 3/3 |
| M24 | 2298 W | 83 °C | 3/3 |
| M25 | 2499 W | 82 °C | 3/3 |
| M26 | 2498 W | 82 °C | 3/3 |

Total instantáneo 366.27 TH/s y 9794 W reportados por ASIC. Ambos grupos permanecen
dentro de los techos configurados (5200/5000 W); esos valores no son mediciones AC.
Cuatro mineros minando, doce placas activas y ningún restart_required. EventStore
registra cero restart_detected desde el primer ajuste exitoso. Heartbeat fresco,
PID 28020, cola Telegram 0. No se cambió la política de notificaciones.

## Evidencia y límites

Artefactos locales ignorados: diagnostics/powerup-20261116/ (antes/después, perfiles
previos, observations.jsonl, observation-summary.json, integrity.json y verification.json).
Los cuatro perfiles están en data/miner_profiles/ y también quedan fuera de Git.
No hubo commit, push, cambios de aplicación ni nueva ejecución de la suite: se verificó
el ajuste con readbacks del firmware, hashes y observación física de la producción.

La prueba cubre esta ventana nocturna. No certifica el comportamiento bajo calor
diurno ni el funcionamiento futuro de M23 a 2700 W con la regla nueva; M23 no estaba
frío para probar esa subida. La perturbación física histórica de la rama 2 sigue sin
identificación AC. Este ajuste no constituye reparación eléctrica ni prueba de máximo
beneficio monetario. La spec 094 y su observación de respaldo a las 03:00 siguen aparte.
