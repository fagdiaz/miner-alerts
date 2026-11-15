# Estabilización nocturna — 14 de noviembre de 2026

Estado: **software PASS8/8; diagnóstico físico de rama2 ABIERTO**.
No commit/push automático ni certificación de reparación eléctrica.

| Aspecto | Resultado |
|---|---|
| Regresión final | 1583 pruebas y75 subpruebas PASS |
| Preflight completo | 8/8 PASS,22:35:16 |
| Activación final |22:31:50,config997550ad |
| M25 yM26 |2500W reportados cada uno, sin ajustes pendientes |
| Flota |4/4mining,12cadenas,ViaBTCactiva |
| Incidente físico |Requiere registroAC para separar calle/elevador/protección |

El informe PRODUCTION_STABILITY_20261114.md contiene metodología, exposición histórica,
comparación de rendimiento, causas probables, cambios y limitaciones. La evidencia de
Spec093 conserva intentos y resultados sin inventar certificaciones históricas.

No se atribuye una causa física por el solo hecho de un reinicio. Los dos logs de firmware
muestran chainbreak compartido a79C con potencia estable por más de3h. Los límites nuevos
mitigan el régimen más inestable, pero no reparan ni prueban la salud del componente eléctrico.

Seguimiento: correlacionar futuros eventos con registro de tensión/corriente, revisar
comportamientoD+1 antes de ampliar límites, y conservar una única autoridad de potencia.


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
