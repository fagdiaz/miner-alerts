# Feature Specification: Spec 078 — Supresión de Ruido Eléctrico en Elevadores, Watchdog Anti-Autotune Stall y Gobernanza Térmica Solar (PROP-013)
## (Elevator Inductive Noise Suppression, Autotune Stall Watchdog & Solar Thermal Governance)

## Status
- **Date**: 2026-09-19
- **Priority**: P0 (Crítica Operativa) | **Risk**: Medio
- **Modules**: `app/miner_monitor.py`, `app/governance/elevator_budget.py`, `app/governance/preset_balancer.py`, `app/vnish/client.py`, `app/config.example.json`
- **Baseline**: 1293 tests PASS, Windows Service `MinerAlerts` Running.
- **Incidentes de Origen**:
  1. Atrapamiento del Minero 25 en `auto-tuning` durante 2708 segundos (45.1 minutos) a 2700W con 0.0 TH/s, culminando en reinicio inesperado (`event_id=1873`).
  2. Ruido eléctrico inductivo transitorio ($V = -L \frac{di}{dt}$) en la bajada común compartida por ambos transformadores elevadores que provocó brownout / reinicio colateral en Minero 26 a las 11:20 hs.
  3. Límite térmico del firmware VNish (`decrease_temp: 84°C`) alcanzado en horas de insolación (11:00-17:00 hs) a 2700W x4, generando recargas no programadas de minado.

---

## 1. Problem Statement & Motivation

En la operación continua a máxima potencia de la flota Antminer S19j Pro bajo transformadores elevadores de tensión acoplados a una acometida monofásica compartida desde la red pública, la telemetría empírica de laboratorio (`data/miner_alerts.db`) y la observación física revelaron tres fallas sistémicas interconectadas:

1. **La Trampa de Silicio del Minero 25 (*The 2700W Autotune Stall*)**:
   - Cada minero tiene características de silicio particulares. A diferencia de los mineros 23, 24 y 26, el **S19JPRO-25 no puede sincronizar sus dominios de voltaje ni fijar las frecuencias PLL a 2700W** (503 MHz, 12.8V).
   - Al ser promovido a 2700W, el equipo quedó congelado en `miner_state: 'auto-tuning'` durante **2708 segundos consecutivos (45.1 minutos)**. Durante este período consumió **2700W de potencia reactiva/resistiva continua de la red sin producir un solo hash (0.0 TH/s)**.
   - Tras 45 minutos de estrés térmico infructuoso, el firmware VNish colapsó y ejecutó un reinicio inesperado (`elapsed=2708->10`).
   - En contraste, configurado a **2500W**, el Minero 25 completa el autotuning en menos de 60 segundos, estabiliza a 78°C y entrega ~95 TH/s con 100% de disponibilidad.
   - **Causa Raíz**: Falta de un watchdog que detecte autotunings congelados en tiempo acotado, y falta de un techo de hardware individual por equipo (`max_hardware_preset`).

2. **Ruido Eléctrico Inductivo por Acoplamiento en la Bajada Compartida**:
   - Ambos transformadores elevadores toman corriente de una única bajada de línea ($I_{total} \approx 45-50\text{A}$).
   - Cuando un minero se reinicia o recarga el proceso de minado a 2700W, la corriente cae de 12.3A a 0A en milisegundos y luego repunta con picos inductivos durante el arranque de ventiladores y fuentes APW12.
   - Esta variación genera una fuerza electromotriz inducida $V = -L \frac{di}{dt}$ que distorsiona la onda sinusoidal y provoca caídas de tensión bruscas reflejadas en los núcleos magnéticos de los dos elevadores.
   - Si la ventana de reposo tras un incidente es de solo 180s o si se intentan escalamientos mientras un equipo vecino está inestable, el ruido tumba al equipo compañero (como ocurrió con el Minero 26).
   - Se requiere una **ventana de reposo extendida de 300 segundos (5 minutos)** específicamente tras cualquier incidente o reinicio en el grupo eléctrico.

3. **La Barrera Térmica Solar del Mediodía (11:00 a 17:00 hs)**:
   - Durante las horas centrales del día, la temperatura ambiente en la sala y la radiación solar elevan la temperatura de entrada. A 2700W x4 (10.8 kW totales), los chips tocan entre 84°C y 86°C.
   - El firmware VNish tiene codificado de fábrica un umbral de protección destructiva en `decrease_temp: 84°C`. Al superarlo, el propio VNish fuerza una recarga de minado para bajar de peldaño, disparando transitorios de corriente imprevistos.
   - A **2500W x4**, los chips se mantienen entre 74°C y 80°C con cero reinicios y ventiladores al 75-85%. La explotación de 2700W debe reservarse para horarios nocturnos, madrugadas frescas y mañanas templadas, o limitarse estrictamente por temperatura.

---

## 2. User Stories

- **US-01 (Watchdog Anti-Autotune Stall)**: Como operador, requiero que si cualquier minero permanece en estado `auto-tuning` por más de 10 minutos (600s) generando un hashrate nominal nulo o despreciable ($< 20\text{ TH/s}$), el monitor detecte la condición `AUTOTUNE_STALLED`, envíe una alerta a Telegram, desescale preventivamente al minero a su escalón seguro probado (2500W o 2300W) y active un cerrojo de hardware para no volver a intentar el preset fallido en la sesión actual.
- **US-02 (Matriz de Techo de Hardware por Minero)**: Como operador, requiero poder definir en la configuración de cada minero su techo físico de silicio (`max_hardware_preset`, ej. `"2500W"` para Minero 25 y `"2700W"` para 23, 24 y 26), de modo que el orquestador de valle jamás intente promover un equipo más allá de su capacidad comprobada de hardware.
- **US-03 (Ventana Extendida Post-Incidente de 300s)**: Como operador, requiero que tras un reinicio, incidente o recuperación en un grupo de elevador, la ventana de estabilización para ese grupo se extienda a 300 segundos (5 minutos), suprimiendo cualquier intento de escalamiento hasta que el transformador y la bajada eléctrica compartida se hayan estabilizado térmicamente y magnéticamente.
- **US-04 (Envolvente Térmica Solar / Midday Guard)**: Como operador, requiero que durante la franja de mayor calor solar (11:00 a 17:00 hs), el sistema limite preventivamente el techo máximo de la flota a 2500W, o permita 2700W únicamente si la temperatura máxima de chips es estrictamente $< 80.0^\circ\text{C}$ con ventiladores con margen, evitando tocar los 84°C de corte brusco de VNish.
- **US-05 (Notificaciones Claras de Diagnóstico)**: Como operador en Telegram, requiero recibir notificaciones explicativas cuando un equipo sea retenido por techo de hardware o desescalado por autotune stall, con detalles de potencia, duración y motivo físico.

---

## 3. Requisitos Funcionales y Técnicos

### REQ-001: Watchdog Anti-Autotune Stall
- En cada ciclo de supervisión en `app/miner_monitor.py`:
  - Si `miner_state == 'auto-tuning'` (o el campo `stage` de autotune está activo):
    - Medir el tiempo transcurrido continuo en dicho estado (`autotune_elapsed_s`).
    - Si `autotune_elapsed_s > 600` (10 minutos) y `current_hashrate_ths < 20.0`:
      1. Identificar estado como `AUTOTUNE_STALLED`.
      2. Registrar log de alta severidad: `[AUTOTUNE-WATCHDOG] miner={name} trapped in auto-tuning for {elapsed}s at {preset} with hashrate {th} TH/s. Triggering safe step-down rescue.`
      3. Emitir alerta a Telegram detallando el incidente.
      4. Invocar `safe_set_miner_preset` desescalando un escalón (ej. de 2700W a 2500W o 2300W) con `auto_restart_mining=True`.
      5. Registrar en el estado en memoria `hardware_preset_lock = True` para bloquear escalamientos hacia el preset fallido.

### REQ-002: Matriz de Techo de Hardware Individual (`max_hardware_preset`)
- En `app/config.example.json` y en el parser de configuración:
  - Permitir el atributo opcional `max_hardware_preset` por minero en la sección `miners` (ej. `"max_hardware_preset": "2500W"`).
  - Por defecto, si no se especifica, toma el valor global `max_preset` (2700W).
- En `app/governance/elevator_budget.py` y `app/governance/preset_balancer.py`:
  - Al evaluar candidatos para `STEP_UP`, la potencia objetivo de un minero queda acotada por:
    $$P_{target} \le \min(P_{fleet\_ceiling}, P_{group\_budget}, P_{hardware\_limit})$$
  - Para `S19JPRO-25`, con `max_hardware_preset: "2500W"`, el evaluador jamás emitirá `STEP_UP` a 2700W, retornando `ACTION_HOLD_HARDWARE_LIMIT`.

### REQ-003: Ventana de Reposo Extendida Post-Incidente (300s Incident Quiet Window)
- En `FacilityBudgetState` (`app/governance/elevator_budget.py`):
  - Incorporar tracking de incidentes por grupo eléctrico:
    - `last_group_incident_ts: Dict[str, float]`
    - `incident_quiet_window_s: float = 300.0` (5 minutos)
  - Al registrarse un evento de reinicio inesperado, contingencia adaptativa o recuperación suave en un minero:
    - Se actualiza `last_group_incident_ts[group] = now_ts`.
  - La función `can_facility_transition_miner` bloquea cualquier subida de preset en ese grupo si `now_ts - last_group_incident_ts[group] < 300.0`, retornando:
    `can_transition = False`, `reason = "INCIDENT_QUIET_WINDOW"`.

### REQ-004: Envolvente Térmica Solar (Ventana 11:00 a 17:00 hs)
- En `app/governance/elevator_budget.py`:
  - Extender `evaluate_soft_contingency_schedule(now_dt)` o implementar `evaluate_solar_thermal_envelope(now_dt, max_chip_temp_c)`:
    - Ventana solar: Todos los días entre las **11:00 hs y las 17:00 hs**.
    - Regla de Techo: El preset máximo autorizado para la flota durante esta ventana es **2500W**.
    - Excepción condicional: Se autoriza 2700W únicamente si la temperatura máxima de chip en toda la flota es estrictamente $< 79.5^\circ\text{C}$ con ventiladores $< 85\%$.
    - Si la temperatura de cualquier chip alcanza $\ge 82.0^\circ\text{C}$ durante la ventana solar, se fuerza desescalada escalonada a 2500W con anticipación, previniendo el corte violento de VNish en 84°C.

---

## 4. Criterios de Aceptación (Garantías de Calidad)

1. **CA-001 (Watchdog Autotune Stall)**: Un minero en `auto-tuning` por $> 600\text{s}$ con $< 20\text{ TH/s}$ es rescatado a un preset seguro en menos de un ciclo de supervisión, con notificación despachada y cerrojo de subida activado.
2. **CA-002 (Aislamiento de Silicio Minero 25)**: El Minero 25 configurado con `max_hardware_preset: "2500W"` opera a 2500W y nunca es promovido a 2700W por ningún planificador automático.
3. **CA-003 (Ventana Extendida 300s)**: Ocurrido un reinicio o incidente en el Elevador 2, ningún minero del Elevador 2 puede aumentar su consumo durante los siguientes 300 segundos.
4. **CA-004 (Supresión de Ruido en Bajada Compartida)**: Los escalamientos de potencia entre distintos elevadores se mantienen estrictamente espaciados por al menos 180 segundos.
5. **CA-005 (Protección Térmica Solar)**: Durante el rango 11:00-17:00 hs, la potencia de la flota no sobrepasa 2500W por equipo si las temperaturas superan 80.0°C.
6. **CA-006 (Suite de Pruebas y Paridad)**: $\ge 1300$ tests unitarios PASS en total (incluyendo tests dedicados para cada requerimiento en `test_autotune_watchdog.py` y extensiones en `test_elevator_budget.py`).
