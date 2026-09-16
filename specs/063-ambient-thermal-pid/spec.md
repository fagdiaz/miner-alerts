# Feature Specification: Spec 063 — Gobernador Térmico con Conciencia Estacional (Ambient-Aware Thermal PID) (GOV-02)

## Status
- **Date**: 2026-09-15
- **Priority**: P2 (Media) | **Risk**: Medio
- **Modules**: `app/governance/fan_governor.py`, `app/vnish/telemetry.py`, `app/miner_monitor.py`
- **Baseline**: 959 tests PASS, Windows Service `MinerAlerts` Running.

---

## 1. Problem Statement & Motivation
El gobernador de ventiladores en lazo cerrado (Spec 039) modula la velocidad PWM hacia un objetivo térmico fijo de 82.0°C.
En entornos de minería reales con variaciones climáticas marcadas:
- **Invierno (5°C - 15°C ambiente)**: El aire frío entrante permite mantener los chips holgadamente entre 65°C y 75°C. Forzar a los coolers a desacelerar excesivamente para intentar alcanzar 82°C provoca ciclos de histéresis innecesarios, o por el contrario, no aprovechar el aire frío para preservar rodamientos y reducir el estrés térmico en silicio.
- **Verano (30°C - 38°C ambiente)**: El delta térmico con el exterior es mínimo. Un piso de coolers estándar (30%) o una rampa de aceleración normal (+3%) reacciona tarde cuando la temperatura sube rápidamente, aumentando el riesgo de picos térmicos hacia 83.5°C o 85.0°C. Se requiere un piso elevado (65% PWM) y aceleración anticipatoria.
- **Inferencia de Temperatura Ambiente sin sobrecarga HTTP**: Los mineros Antminer S19j Pro con firmware Vnish reportan la temperatura de entrada en la telemetría `/api/v1/summary` (`temp_in` o `temp_pcb_in`), la cual ya se sondea en el ciclo normal de 30 segundos. **Cero peticiones HTTP adicionales.**

---

## 2. User Stories
- **US-01 (Operación de Invierno Eficiente)**: Como operador de granja en meses fríos ($T_{\text{amb}} < 18^\circ\text{C}$), deseo que el gobernador module con un objetivo conservador de 76°C y un piso de 45% PWM para reducir el ruido acústico y el desgaste de rodamientos manteniendo los chips frescos sin choque térmico.
- **US-02 (Defensa de Verano Proactiva)**: Como operador en meses cálidos ($T_{\text{amb}} > 28^\circ\text{C}$), deseo que el gobernador establezca automáticamente un piso de 65% PWM y rampa de aceleración agresiva para anticipar la inercia térmica antes de alcanzar niveles de alarma.
- **US-03 (Inviolabilidad de Seguridad de Hardware)**: Como responsable de infraestructura, exijo que la adaptación estacional jamás comprometa el Thermal Guard de emergencia (83.5°C / 85.0°C) ni reduzca el piso de PWM por debajo del 30% seguro de hardware.

---

## 3. Functional Requirements

### FR-01: Extracción de Temperatura de Entrada ($T_{\text{inlet}}$) en Telemetría
- Extender `VnishTelemetry` en `app/vnish/telemetry.py` con el campo `inlet_temp_c: Optional[float] = None`.
- En `normalize_vnish_stats()`, detectar claves de entrada de aire (`temp_in`, `temp_pcb_in`, `temp_inlet` o coincidentes con `r"^temp(?:_pcb)?_in(?:let)?(\d+)?$"`) con rango válido `-10.0 <= temp <= 60.0°C`.
- Calcular el promedio de los sensores de entrada encontrados y asignarlo a `inlet_temp_c`.
- En `app/miner_monitor.py`, propagar `inlet_temp_c` a `MinerState.inlet_temp_c`.
- En `execute_governor_cycle()`, calcular la temperatura ambiente efectiva del grupo o flota promediando los `inlet_temp_c` de los mineros activos disponibles.

### FR-02: Modos Estacionales y Adaptación de Curvas en `compute_governor_step()`
Extender `GovernorConfig` con:
- `seasonal_enabled: bool = True` (activación del control estacional).
- `winter_ambient_threshold_c: float = 18.0` (umbral superior de invierno).
- `summer_ambient_threshold_c: float = 28.0` (umbral inferior de verano).
- `winter_target_temp_c: float = 76.0` (objetivo de chip en invierno).
- `winter_min_duty_percent: int = 45` (piso de coolers en invierno).
- `summer_target_temp_c: float = 80.0` (objetivo de chip en verano).
- `summer_min_duty_percent: int = 65` (piso de coolers en verano).
- `summer_step_up_percent: int = 5` (aceleración en verano).

Función pura de resolución estacional:
`resolve_seasonal_parameters(ambient_temp_c: Optional[float], config: GovernorConfig) -> SeasonalGovernorParams`:
1. **Sin telemetría ambiental ($T_{\text{amb}} = \text{None}$) o `seasonal_enabled = False`**:
   - Modo `ESTÁNDAR`: target 82.0°C, banda [81.0, 82.5]°C, min 30% PWM, step_up nominal.
2. **Modo Conservación Invierno ($T_{\text{amb}} < 18.0^\circ\text{C}$)**:
   - Modo `INVIERNO`: target 76.0°C, banda [75.0, 77.0]°C, min 45% PWM, step_up nominal.
3. **Modo Estándar ($18.0^\circ\text{C} \le T_{\text{amb}} \le 28.0^\circ\text{C}$)**:
   - Modo `ESTÁNDAR`: target 82.0°C, banda [81.0, 82.5]°C, min 30% PWM, step_up nominal.
4. **Modo Verano Intenso ($T_{\text{amb}} > 28.0^\circ\text{C}$)**:
   - Modo `VERANO`: target 80.0°C, banda [79.0, 81.0]°C, min 65% PWM, step_up acelerado (+5%).

### FR-03: Guardarraíl Térmico Absoluto (INVARIANTE INVIOLABLE)
Cualquier parámetro generado por el ajuste estacional debe validarse contra las 3 invariantes de seguridad:
1. `effective_target_temp_c <= 82.0°C` (NUNCA elevar el objetivo por encima de 82.0°C).
2. `effective_min_duty_percent >= 30%` (NUNCA reducir el piso por debajo del mínimo absoluto de hardware).
3. `emergency_spike_temp_c` inalterable (83.5°C fuerza 100% PWM inmediato independientemente de la estación).

---

## 4. Boundary Cases & Defensive Behaviors
- **Sensor de entrada desconectado o anómalo (ej. 120°C o -50°C)**: Descartado por el filtro de validez (`-10.0 <= T <= 60.0`), fallback transparente a modo Estándar.
- **Flota mixta donde sólo 1 minero reporta `temp_in`**: Se utiliza la lectura de dicho minero para su grupo; si ningún minero del grupo reporta, fallback a modo Estándar.
- **Interacción con Silent Mode**: Silent Mode establece un techo acústico superior (ej. 50%). Si el modo Verano exige piso de 65%, Silent Mode y la seguridad de temperatura tienen precedencia con clamp defensivo.

---

## 5. Verification Gate
1. `& ".\.venv\Scripts\python.exe" -m py_compile app\governance\fan_governor.py app\vnish\telemetry.py app\miner_monitor.py`
2. Suite dedicada `tests/test_fan_governor_seasonal.py` cubriendo transiciones de temperatura ambiente, límites de banda y los 3 guardarraíles inviolables.
3. Batería completa de 959+ tests PASS (0 regresiones).
4. Servicio Windows `MinerAlerts` en estado `Running`.
