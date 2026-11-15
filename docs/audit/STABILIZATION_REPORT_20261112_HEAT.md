> Actualización14/11/2026: este documento conserva el registro histórico del incidente.
> El bloqueo administrativo y la reconciliación quedaron superados; el estado operativo
> vigente está en STABILIZATION_REPORT_20261114_POWERUP.md (PASS8/8,18:16:33).
> No se certifica retroactivamente una observación del día12 que no quedó registrada.

# Estabilización térmica — 12 de noviembre de 2026

Estado actual: arreglo final desplegado a las 17:12:30 (UTC-3), observación en curso.
El bloqueo administrativo inicial quedó superado. No se hizo commit ni push.

| Validación | Resultado |
|---|---|
| Suite completa | 1557 pruebas y 75 subpruebas PASS |
| Regresión térmica con Telegram simulado | 41 PASS |
| Compilación | PASS |
| Activación | Servicio RUNNING; configuración sha 810b32c6 |
| Firmware | Sin ajustes pendientes en los cuatro equipos |
| Pools | ViaBTC activa en los cuatro; perfiles de recuperación también migrados |
| Observación de estabilidad | En curso; ver evidence.md y captura local |

## Causa confirmada y corrección

M24 repetía pausas a 87–88 °C. El monitor intentaba el preset inexistente 2100 W,
registraba objetivos aunque la API rechazaba el ajuste y reanudaba sin comprobarlo.
Además, un piso igual al techo impedía bajar potencia mediante el regulador de VNish.

El hotfix usa la escalera validada, conserva el piso de 1740 W, prioriza el preset
observado y comprueba el resultado de cada intervención. La recuperación carga el
preset mediante un reinicio del proceso de minado detenido: resume/start por sí solo
podía dejar settings pendientes. Las pruebas cubren fallos de escritura, recuperación,
parada, guardas QA y deduplicación independiente de la primera alerta crítica.

Los avisos térmicos repetidos tienen un cooldown de 900 segundos por minero y tipo.
Las protecciones de temperatura y la primera alerta crítica permanecen activas.

## Contención operativa

| Minero | Techo temporal | Piso nativo |
|---|---:|---:|
| M23 | 2300 W | 1740 W |
| M24 | 2000 W | 1740 W |
| M25 | 2150 W | 1740 W |
| M26 | 2000 W | 1740 W |

Techos alineados en firmware y configuración local. Ventilación mínima al 100 %;
pre-clamp de recuperación de 1800 W. M24 calibra el nuevo preset mientras produce.
La potencia de las APIs es la reportada por los ASIC; no constituye medición AC del tablero.
No se confirmó saturación de la red eléctrica ni una falla física de los elevadores.

## Cierre pendiente

- [x] Diagnóstico, corrección, pruebas y despliegue final.
- [x] Verificación de settings, pools y tres cadenas produciendo por minero.
- [ ] Completar al menos 15 minutos de observación tras la activación final.
- [ ] Actualizar H004 y ejecutar el preflight final de estabilización.
- [ ] Verificar finalización de la calibración de M24 y observación D+1.

Los estados de chips durante la calibración de M24 todavía no constituyen una
certificación de salud a largo plazo; revalidar una vez que termine el autotuning.
No restaurar automáticamente la potencia nominal mientras persista el calor.
Backups locales ignorados: diagnostics/heat-20261112. No editar state con el servicio vivo.
