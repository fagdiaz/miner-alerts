# Temperatura, potencia y recuperación

> Tipo: referencia operativa · Revisión: 2026-11-16.

## Responsabilidades

| Componente | Responsabilidad |
|---|---|
| Switcher VNish | Subidas y bajadas nativas dentro de su banda, intervalo y techo |
| Fan governor | Control de ventiladores según telemetría, permisos y modo |
| Protección térmica de emergencia | Downstep, pausa, reanudación y límites de seguridad |
| Recuperación L1 | Reinicio suave ante evidencia de detención, con guardas |
| Recuperación L2 | Reboot condicionado a fallas sostenidas e interlocks |
| Balanceador | Propuestas o cambios según permisos y dry-run; no asumir que está activo |

Para la configuración local documentada, ver el [corte de producción](PRODUCTION_BASELINE.md).
No convertir sus valores en defaults universales ni elevar techos solo porque una
lectura de chips esté por debajo de la banda.

## Banda y cinco minutos

En el corte del 16/11 se alinearon `rise_temp=79`, `decrease_temp=84` y
`check_time=300`. El intervalo no garantiza un aumento exactamente cinco minutos
después de una única lectura de 79 °C. Intervienen la condición térmica nativa, el
techo, el tier disponible y el estado del firmware. El redondeo de laUI tampoco
prueba por sí solo cómo evalúa internamente la igualdad.

El ajuste 80/85 de una ventana anterior fue reemplazado. No restaurarlo a partir de
un informe histórico. Verificar settings y logs del minero antes de explicar un powerup.

## Seguridad de los reinicios

Con 096, una marca `restart_required` en un minero que produce no dispara por sí sola
L1: corresponde al watchdog de presets con soak, temperatura y cooldown. Antes de
actuar se consulta estado nativo; no se interrumpe autotune con L1/L2 genéricos.
Mantenimiento, snooze, pausa térmica y asentamiento posterior a una bajada quedan
protegidos. L2 no se despacha junto con L1 durante su ventana de recuperación.

El preclamp conserva el techo nativo. Una recuperación no debe reabrir el máximo de
hardware sobre una contención térmica o eléctrica. Los workers revalidan permisos QA
y gobernanza; el watchdog de presets comprueba estado y temperatura recientes.

## Cambios individuales

Cuando una política autorizada requiera cambios, conservar lectura previa, payload
acotado, readback, potencia medida, flags y uptimes. Alinear perfil de recuperación y
config cargada. La API puede exigir incluir un preset; no reenviar un preset guardado
que ya no representa el tier activo. Un HTTP200 no prueba por sí solo aplicación física.

No resolver una incertidumbre deshabilitando protecciones, forzando máximos o creando
un segundo controlador de potencia que compita con VNish. Comparar rendimiento efectivo
y disponibilidad durante una ventana suficiente.

## Causa física y economía

La tensión de cadena esDC; no mide la entradaAC del elevador. Un chainbreak puede
orientar a fuente, conexiones o placa, sin identificar por sí solo el origen. Para
comparar beneficio se necesitan tiempo total, energíaAC, tarifa y retribución real de
pool. La contención de M26 a 2300 W es revisable y no constituye reparación física.
