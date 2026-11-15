# Producción sostenible e incidente de rama 2 — 14 de noviembre de 2026

## Conclusión causal

A las 21:48:47 y 21:48:51, M25 y M26 registraron en su propio firmware una lectura fallida
del registroASIC y `chain#1 - chain break detected`. VNish apagó ordenadamente el minado
y arrancó de nuevo. Ambos estaban en 79°C y 2300 W. M23/M24 conservaron uptime.

La evidencia apunta a una perturbación compartida en la rama del elevador 2. **No prueba
que el elevador esté averiado ni que la calle sea culpable**: falta mediciónAC simultánea.
Tampoco permite afirmar corte total de energía o reinicio del sistemaLinux. Este episodio
no fue precedido por sobretemperatura ni por cambio inmediato de potencia: los últimos
cambios observados fueron 18:07:26(M25) y 18:18:56(M26), más de 3 horas antes.

En 30 d hay 23 cohortes de reinicios clasificados inesperados de 25+26 frente 2 de 23+24
(ventana 45 s). Contando todas las clasificaciones son 40 frente 4; no equivalen a 40 cortes
eléctricos y pueden incluir intervención humana o atribuciones incompletas del monitor.

## Qué se cambió

- M25 limitado a 2500 W; M23 conserva 2700 yM24/M26 hasta 2500, siempre sujetos a temperatura.
- M23 exige 78°C para subir; los otros conservan 79°C. Bajada nativa 84°C y protecciones
  supervisoras 85.5/87°C conservadas. El nuevo margen se basa en respuesta térmica medida.
- Perfiles dorados alineados: evitar que una restauración reinstale caps viejos o bloquee
  promociones por ventiladores 100%. Pools, red y credenciales conservadas.
- El monitor ya no compara datos ausentes contra enteros; tampoco prueba firmwarestock
  solo porque faltó telemetría. QA no crea threads de recuperación; reflash-disabled se respeta.
- Reinicios correlacionados de un grupo generan un evento y un aviso neutral, aunque el
  socket 4028 siga respondiendo. Ventana 45 s y cooldown 900 s, sin nuevo actuador.
- El guardián térmico calcula stepdown con potencia real. Guarda el siguiente tier seguro
  antes de pausar, lo valida contra la escalera y el techo al reanudar y preserva ese dato
  entre reinicios del monitor. Un estado legado sin evidencia usa un valor conservador.
- La simulación del balanceador conserva recomendaciones pero no modifica presets,
  timestamps, locks, presupuesto de transición ni solicita ventilación física o confirma acciones.

## Evidencia de rendimiento (30 días)

Exposición aproximada: muestras válidas×30 s; hashrate promedio mientras ese nivel de
potencia está reportado. Los reinicios se vinculan al último nivel válido de los 180 s previos.
Comparación observacional: clima, sesgo de selección, fallos sin datos y atribuciones
manuales impiden tratarla como experimento causal o máximo económico demostrado.

| Minero | NivelW | Horas observadas | TH/s activo promedio | Reinicios próximos | Reinicios/100 h |
|---|---:|---:|---:|---:|---:|
| M23 | 2500 | 165.8 | 93.64 | 4 | 2.41 |
| M23 | 2700 | 428.4 | 99.86 | 3 | 0.7 |
| M24 | 2300 | 204.7 | 86.95 | 5 | 2.44 |
| M24 | 2500 | 448.1 | 93.36 | 4 | 0.89 |
| M25 | 2500 | 236.7 | 93.86 | 10 | 4.23 |
| M25 | 2700 | 346.3 | 100.26 | 60 | 17.33 |
| M26 | 2300 | 37.1 | 85.66 | 2 | 5.39 |
| M26 | 2500 | 622.2 | 93.07 | 53 | 8.52 |

A 2700 W,M25 ofrece más SHA, incluso descontando aproximadamente el tiempo de recuperación:
98.84 TH/s frente 93.55 a 2500. La diferencia de~5 TH/s NO se oculta. El techo 2500 elige un
compromiso de continuidad y eficiencia frente a 4.1 veces más reinicios por hora observada.
Se renuncia a ese pequeño margen para evitar explotar permanentemente el nivel más inestable.
No se calcula beneficio monetario sin tarifa eléctrica, coste totalAC y rendimiento de pool.
M23 a 2700 tiene mucha mejor tasa histórica y por eso conserva su margen máximo.

## Respuesta térmica medida

Transiciones con 3 muestras estables previas y 7 posteriores (~3 min), sin discontinuidad de
uptime ni hueco mayor 330 s. No se usan arranques desde 0 W para fijar umbrales de subida.

| Minero | EscalónW | Casos | Aumento mediano°C | Percentil 90°C |
|---|---|---:|---:|---:|
| M23 | 2150→2300 | 3 | 1.0 | 1.0 |
| M23 | 2300→2500 | 25 | 3.0 | 4.0 |
| M23 | 2500→2700 | 25 | 3.0 | 4.3 |
| M24 | 2150→2300 | 4 | 2.0 | 2.0 |
| M24 | 2300→2500 | 21 | 3.0 | 4.0 |
| M25 | 2150→2300 | 3 | 2.0 | 2.0 |
| M25 | 2300→2500 | 83 | 2.3 | 3.0 |
| M25 | 2500→2700 | 69 | 3.7 | 4.7 |
| M26 | 2000→2150 | 3 | 2.0 | 2.0 |
| M26 | 2150→2300 | 3 | 1.0 | 1.0 |
| M26 | 2300→2500 | 53 | 2.0 | 2.7 |

En M23, promover con 79°C y una subida térmica de 4–4.3°C deja poco margen frente 84.
Rise 78 reduce ese riesgo sin cancelar el techo 2700 en una sala suficientemente fresca.
No se intenta vencer la limitación térmica elevando cortes ni reduciendo protección.

## Lo que falta para identificar el componente físico

Un técnico debe correlacionar la hora del próximo evento con un registro de tensión y
corriente de entrada/salida de ambos elevadores, además de su temperatura. Un valorDC de
hashboard no permite identificar una caídaAC de calle ni su origen. Las guías de Fluke
explican la necesidad de registrar y correlacionar eventos para localizar perturbaciones:
https://www.fluke.com/en-us/learn/blog/power-quality/power-quality-at-the-service-panel

## Validación y límites del cierre

Suite final 1583 tests+75 subtestsPASS (44.61 s); pruebas de QA, reflash-disabled y simulación
sin efectos físicos incluidas. CompilaciónPASS. Activación final 22:31:50, configsha 997550 ad.
M25 cap 2500 yM23 rise 78 aceptados por firmware, sin ajustes pendientes ni reinicio de mineros.
La observación y el preflight final se registran en evidence.md. Una ventana inmediata sin
fallos no demuestra haber reparado la perturbación física intermitente ni garantiza cerofallos.
El sistema conserva margen dinámico; el próximo evento compartido quedará mejor documentado.

Fuentes locales ignoradas: history-summary.json, exposure-analysis.json, thermal-step-analysis.json,
logs de firmware y capturas de diagnóstico en diagnostics/production-20261114. No contienen
credenciales en este informe; los backups completos permanecen locales y fuera deGit.


## Despliegue final y alcance de la verificación

La última recarga fue a las **22:31:50**, con configuración `997550ad`. El estado
persistido incluye el nuevo campo de reanudación segura; los cuatro mineros permanecen
`OK`. No hubo reinicios de mineros por los ajustes nocturnos. Se observaron las subidas
nativas de M25/M26 y la bajada térmica de M23; la regulación no fue reemplazada por
un segundo controlador. La prueba inmediata verifica operación, no reparación eléctrica.

El hallazgo físico compartido permanece abierto hasta medir tensión/corriente y correlacionar
otro evento. Los escenarios raros de QA, datos ausentes y pausa/recuperación se validaron
con pruebas deterministas, sin provocar fallas de hardware para ensayarlos.


## Cierre técnico nocturno — 14/11/2026 22:37 UTC-3

**Preflight de software PASS, 8/8 compuertas, a las22:35:16.** 1583 pruebas y75 subpruebas
PASS en92.84s. Sintaxis, diff, secretos, config, servicio, flota y DoD automatizadosPASS.
La instalación de código final se verificó a22:31:50, con estado persistido nuevo presente.
Se usaron TEMP/TMP y basetemp locales para no confundir errores del sandbox con regresiones.

Captura final2026-11-14T22:37:44.578494-03:00: cuatro mineros minando, doce cadenas produciendo, ViaBTC
activa4/4, ningún restart_required. Potencia reportada9443W; hashrate360.11TH/s.
Actuales:2298/2148/2499/2498W; temperaturas81/79/82/82°C. M25/M26 sostienen el régimen
pareado de2500W; M23 se reguló de2500a2300W por temperatura, sin reiniciar.
Desde22:11:33 hasta22:37:44: **cero reinicios detectados**. El código final lleva~6min
en vivo; el régimen físico fue observado~26min. Se mantienen separados esos períodos.

Las pruebas cubren None, QA, reflash deshabilitado, simulación sin side-effects y cálculo
correcto de potencia/reanudación térmica. No se provocó otra falla eléctrica para ensayar
la correlación; ese circuito lógico se verificó con replay y pruebas deterministas.

**Incidente físico abierto.** Esta ventana inmediata no demuestra que desapareció la
perturbación compartida de la rama2. Falta registroAC de entrada/salida correlacionado con
un evento para decidir calle, elevador o protección. No se certifica reparación eléctrica
ni máximo monetario global. Se aplicó una política operativa basada en evidencia y límites.

Código/config/perfiles ya activos; no pendientes de UAC o despliegue. Commit y push siguen
manuales. No activar otra spec antes del cierre manual de release y los gates aplicables.
