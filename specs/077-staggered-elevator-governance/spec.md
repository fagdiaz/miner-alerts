# Spec 077: Gobernanza Escalonada de Elevadores, Bajada Compartida y Soft-Contingencia Horaria (PROP-012)

## 1. Resumen Ejecutivo
- **Feature Directory**: `specs/077-staggered-elevator-governance`
- **Propuesta Base**: [`PROP-012`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/proposals/PROP-012-staggered-elevator-governance-and-soft-contingency.md)
- **Línea Base Operativa**: 1262 tests PASS en 41.7s, Servicio Windows `MinerAlerts` RUNNING.
- **Objetivo**: Proteger la bajada eléctrica compartida de la instalación y los transformadores elevadores eliminando sobrecargas combinadas bruscas y variaciones de tensión, priorizando el equilibrio simétrico de potencia (2x 2500W) y habilitando la máxima potencia saludable (2700W x4) en ventanas de red estable.

---

## 2. Requisitos y Especificaciones Técnicas

### REQ-001: Presupuesto Dinámico de Elevadores y Preferencia Simétrica
- **Prioridad de Balance Simétrico**: Dos mineros a 2500W ($5000\text{W}$, ~186 TH/s) tienen prioridad sobre asimetrías extremas (2700W + 2300W), garantizando menor estrés térmico y mayor margen de estabilidad en las fuentes APW12.
- **Modo Soft-Contingencia (Horario Pico)**: Límite de potencia por elevador en **5000W** (2500W + 2500W).
- **Modo Valle / Fin de Semana**: Se autoriza la exploración escalonada hacia el techo máximo individual de 2700W (hasta 5400W por elevador y 10.8 kW en la bajada), siempre que la red no registre perturbaciones.

### REQ-002: Cola Global de Transición Escalonada (*Facility-Wide Staggered Queue*)
- Debido a que ambos elevadores **comparten la misma bajada de cable desde la calle**:
  - En toda la instalación, solo **1 minero a la vez** puede ejecutar una orden de cambio de preset.
  - Se impone una **ventana de estabilización de 180 segundos (*Facility Settle Window*)** tras el cambio de cualquier minero antes de que el siguiente pueda iniciar su rampa.
  - Se previene así el calentamiento acumulativo en el cable de acometida y se suprimen picos inductivos $L \frac{di}{dt}$ en la entrada común de los elevadores.

### REQ-003: Soft-Contingencia Quirúrgica por Horario y Día
- Ventanas compactas y precisas (días hábiles Lunes a Viernes, horario local UTC-3):
  - **Pico Mañana**: **08:30 a 10:30 hs** (2 horas de protección).
  - **Pico Tarde/Noche**: **19:30 a 22:30 hs** (3 horas de protección).
  - **Ventanas Libres (19 horas en días de semana y 100% de Sábados y Domingos)**: Fuera de los picos, la flota opera en Modo Plena Potencia con ascenso escalonado permitido.
- Desescalada paulatina: Al entrar en la franja, los mineros por encima de 2500W bajan a 2500W de a uno por vez, espaciados por 180 segundos.
- Auditoría de eficacia: Registro de métricas para evaluar si la franja previno el 100% de los reinicios.

### REQ-004: Co-Gobernanza con el Firmware VNish
- El monitor fija la envolvente autorizada mediante `preset = X` y `top_preset = X`.
- VNish ejecuta su algoritmo de sintonización y micro-balanceo por chip dentro de los límites impuestos.
- Se respetan las capacidades intrínsecas del firmware VNish sin permitir que sobrepase los límites de la infraestructura física compartida.

---

## 3. Criterios de Aceptación (Garantías de Calidad)

1. **CA-001 (Secuencialidad Global)**: Dos mineros cualesquiera de la instalación nunca ejecutan órdenes de preset con menos de 180s de diferencia.
2. **CA-002 (Preferencia Simétrica)**: El Preset Balancer prefiere promover parejas a 2500W/2500W antes de intentar combinaciones 2700W/2300W.
3. **CA-003 (Soft-Contingencia Puntual)**: Durante días de semana a las 08:30 hs y 19:30 hs, los mineros en 2700W desescalan a 2500W de a uno a la vez.
4. **CA-004 (Tests Unitarios)**: Cobertura completa en `tests/test_elevator_budget.py` ($\ge 1285$ tests globales PASS, 0 fallos, 0 regresiones).
