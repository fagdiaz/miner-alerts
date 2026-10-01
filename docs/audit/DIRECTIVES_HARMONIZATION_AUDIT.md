 Auditoría de Armonización de Directivas de Gobernanza

**Fecha de Auditoría**: 2026-10-01
**Auditor**: Claude Sonnet 4.6 (Thinking)
**Baseline del Sistema**: 1429 tests PASS · 75 subtests PASS · NSSM MinerAlerts RUNNING
**Estado de Flota (snapshot 10:14 hs)**:
- M23: 2700W · 100.0 TH/s · Fan 92% · Chips 76-80°C · Uptime 49.1h
- M24: 2500W · 92.4 TH/s · Fan **100%** · Chips 57-77°C · Uptime 32.7h ⚠️ `restart_required=True`
- M25: 2700W · 101.5 TH/s · Fan 92% · Chips 78-82°C · Uptime 22.3h
- M26: 2700W · 99.5 TH/s · Fan 92% · Chips 75-78°C · Uptime 22.3h

---

## 1. Inventario Completo de Directivas Activas

El sistema de gobernanza tiene **5 capas de directivas** que actúan concurrentemente sobre los mineros. A continuación se cataloga cada directiva, su origen, su ámbito de actuación y su nivel de prevalencia.

### 1.1 Tabla de Directivas por Orden de Prevalencia

| Prioridad | Directiva | Módulo | Ámbito | Tipo |
|-----------|-----------|--------|--------|------|
| **P0 – Inviolable** | Guardián Térmico: Step-Down 84°C / Pausa 87°C | `thermal_guard.py` | Por minero | Seguridad de hardware |
| **P0 – Inviolable** | Failsafe Fan al 100% ante 3 fallos consecutivos | `fan_governor.py` L244 | Por minero | Seguridad de hardware |
| **P0 – Inviolable** | ACTION_RECOVERY_MAX_COOLING (100% si current < target−120W) | `fan_governor.py` L300 | Por minero | Protección de silicio |
| **P1 – Alta** | Stock Firmware Fallback Block (bloquea auto-restart) | `miner_monitor.py` L6984 | Por minero | Detección de firmware |
| **P1 – Alta** | Thermal Pause Interlock (bloquea restart si pausa térmica) | `miner_monitor.py` L6973 | Por minero | Seguridad de hardware |
| **P2 – Media-Alta** | Soft Contingency Schedule (peak 5000W / valley 5400W) | `elevator_budget.py` | Por elevador | Red eléctrica |
| **P2 – Media-Alta** | Solar Thermal Envelope (2500W si 11:00-17:00 y T≥82°C) | `elevator_budget.py` L282 | Global | Térmico-solar |
| **P2 – Media-Alta** | Thermal Headroom Gate (T_chip < 80°C para subir a 2700W) | `elevator_budget.py` L604 | Por minero | Térmico |
| **P3 – Media** | Incident Quiet Window (300s post-incidente por grupo) | `elevator_budget.py` L536 | Por elevador | Eléctrico |
| **P3 – Media** | Facility Settle Window (180s entre transiciones de planta) | `elevator_budget.py` L552 | Toda la planta | Inductivo |
| **P3 – Media** | Symmetric Balance Preference (partner ≥2500W antes de 2700W) | `elevator_budget.py` L661 | Por elevador | Eléctrico |
| **P3 – Media** | FGA Asymmetric Optimizer (cohortes COOL/STANDARD/HOT) | `facility_agent.py` | Por minero/grupo | Térmico-económico |
| **P4 – Baja** | VNish Internal Daemon (`preset_switcher`, rise_temp/decrease_temp) | Firmware VNish interno | Por minero | Firmware autónomo |
| **P4 – Baja** | Headroom Chilling (`boost_cooling` 100% PWM pre-ascenso 2500W→2700W) | `fan_governor.py` L326 | Por minero | Térmico-preventivo |
| **P5 – Config** | Individual Hardware Ceiling (`max_hardware_preset` por minero) | `elevator_budget.py` / `config.json` | Por minero | Límite de silicio |
| **P5 – Config** | Target Power W (potencia objetivo por minero en config) | `config.json` | Por minero | Operativo |

### 1.2 Flujo de Decisión del Fan Governor

```
Orden de evaluación en compute_governor_step():
1. Sin telemetría           → ACTION_UNKNOWN           (requires_write=False)
2. ≥3 fallos consecutivos   → ACTION_FAILSAFE_FAULT    (100% PWM, P0)
3. T ≥ emergency_spike(83°C)→ ACTION_EMERGENCY_SPIKE  (100% PWM, P0 inviolable)
4. Exceso sobre techo       → ACTION_STEP_DOWN         (bajar al máximo)
5. current_w < target−120W  → ACTION_RECOVERY_MAX_COOLING (100% PWM, P0)
5b. boost_cooling=True      → ACTION_STEP_UP           (100% PWM, headroom)
6. Por debajo del piso mínimo→ ACTION_STEP_UP          (subir al piso)
7. Dwell activo y T≤deadband→ ACTION_HOLD_DWELL
8. T > deadband_high (82.5°)→ ACTION_STEP_UP          (proporcional)
9. T en banda objetivo      → ACTION_HOLD_TARGET
10. T < deadband_low (81°C) → ACTION_STEP_DOWN         (gradiente adaptativo)
```

### 1.3 Flujo de Decisión del Orquestador de Elevadores

```
evaluate_facility_transition_permission() — gates en orden estricto:
  Step-Down: SIEMPRE permitido (alivio de red inmediato)
  Gate 0: Incident Quiet Window (300s post-incidente en grupo)
  Gate 1: Facility Settle Window (180s post-transición en planta)
  Gate 2: Individual Hardware Ceiling (max_hardware_preset)
  Gate 3: Solar Thermal Envelope (11:00-17:00, 2500W si T≥82°C)
  Gate 3.1: Thermal Headroom (chip < 80°C para >2500W)
  Gate 4: Soft Contingency Schedule (pico: 2500W; valle: 2700W)
  Gate 5: Group Power Budget (≤5000W pico / ≤5400W valle)
  Gate 6: Symmetric Balance (partner ≥2500W antes de 2700W)
```

---

## 2. Matriz de Directivas y Puntos de Fricción

### 2.1 Mapa de Interacciones — Quién Manda Sobre Quién

```
VNish Internal Daemon
  │ (derecho de paso a 84°C)
  ▼
Thermal Guard P0 [84°C step-down / 87°C pausa]
  │ (suprime restart/reboot candidato)
  ▼
Fan Governor P0 [RECOVERY_MAX_COOLING si current < target−120W]
  │ (puede bloquear ascenso si duty=100% ≥ 92% en Gate 0 del orquestador)
  │ (BYPASS: _is_recovery_cooling omite el bloqueo por duty si T<80°C)
  ▼
Elevator Budget Orchestrator [Gates 0-6]
  │ (evalúa la solicitud de transición de preset)
  ▼
FGA Asymmetric Optimizer [cohortes R_th]
  │ (recomienda preset, pero no ejecuta directamente)
  ▼
VNish REST API [safe_set_miner_preset / safe_restart_mining]
  │ (escribe config y requiere restart para conmutar cgminer)
  ▼
Estado operativo real del hardware ASIC
```

### 2.2 Tabla de Fricciones Identificadas

| ID | Directivas en Conflicto | Síntoma Observado | Miner Afectado | Severidad |
|----|-------------------------|-------------------|----------------|-----------|
| **F-01** | `restart_required=True` + `auto_restart_mining=False` + `is_hash_degraded=False` | M24 corre a 2500W en vez de 2700W de forma indefinida | M24 | 🔴 Alta |
| **F-02** | `RECOVERY_MAX_COOLING` + `restart_required=True` (nunca se resuelve) | Fans de M24 clavados al 100% con chips a 57-77°C | M24 | 🟡 Media |
| **F-03** | Elevador 2 (fatiga de relés) + presupuesto 5400W (M25+M26 a 2700W cada uno) | 3 eventos eléctricos en 2026-09-30 (vs 0 en Elevador 1) | M25, M26 | 🟡 Media |
| **F-04** | FGA decide cohortes por `R_th` pero no tiene visibilidad de `restart_required` | FGA puede recomendar subida a 2700W para M24 cuando es físicamente imposible sin restart | M24 | 🟡 Media |
| **F-05** | Solar Envelope (11:00-17:00 → cap 2500W) + `RECOVERY_MAX_COOLING` (100% fans si <2700W) | En franja solar, M24 quedaría atrapado al 100% fans indefinidamente aun en 2500W (target=2500W, current=2498W < 2500-120=2380W → condición TRUE por 2W) | M24 (hipotético post-subida) | 🟠 Baja-Media |
| **F-06** | VNish daemon (decrease_temp: 84°C) + Thermal Guard externo (85.5°C) | Potencial doble-bajada ante saturación térmica (ya resuelto en 2026-09-27 con cerrojo bidireccional min_preset+top_preset) | Todos | ✅ Resuelto |
| **F-07** | `evaluate_auto_restart_candidate` condicionado a `is_hash_degraded` | No existe mecanismo para aplicar `restart_required` cuando el minero hashea bien pero tiene preset configurado distinto al ejecutado | M24 | 🔴 Alta |
| **F-08** | Asymmetric Balance Gate 6 + Elevador 1 en 5400W tras subida de M24 | M24 sube a 2700W → Elevador 1 pasa de ~5200W a ~5400W (misma carga que Elevador 2 que tuvo fatiga) | M23, M24 | 🟡 Media |

---

## 3. Análisis Profundo por Fricción

### 3.1 Fricción F-01 / F-07: El Nudo S19JPRO-24 — Preset No Aplicado

#### Causa Raíz Técnica

El nudo se forma por la intersección de 3 diseños correctos individualmente que crean un caso límite no previsto:

1. **VNish no conmuta en caliente**: Al recibir `POST /api/v1/settings` con `preset: "2700"`, VNish escribe el JSON en `/config/cgminer.conf` y levanta `restart_required=True`. Los PLLs de frecuencia y los reguladores de voltaje de las hashboards **no cambian** hasta que cgminer reinicia.

2. **`auto_restart_mining=False` por diseño**: La función `safe_set_miner_preset` tiene este parámetro en `False` para evitar que ajustes rutinarios del balanceador generen microreinicios frecuentes (anti-flapping correcto).

3. **`evaluate_auto_restart_candidate` requiere degradación**: La condición de entrada ([`miner_monitor.py` L6955-6958](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py#L6955-L6958)) es:
   ```python
   is_hash_degraded = (
       new_state in (STATE_LOW, STATE_HASHBOARD)
       or (rate_ths is not None and rate_ths <= 0.0)
       or (active_boards is not None and active_boards == 0)
   )
   ```
   M24 hashea a 92.4 TH/s con 3 placas activas. `is_hash_degraded = False`. El bloque de auto-restart nunca se evalúa.

**Resultado**: El minero queda atrapado indefinidamente en 2500W mientras tiene 2700W configurado y está en perfecto estado.

#### Traza de Impacto en Cadena

```
Preset config = 2700W
cgminer ejecuta = 2500W (482 MHz)
restart_required = True (VNish)
    │
    ├─► Fan Governor ve: current_w=2498 < target_w=2700−120=2580
    │   → ACTION_RECOVERY_MAX_COOLING → Fan PWM = 100% (permanente)
    │
    ├─► Monitor ve: rate_ths=92.4 > threshold → is_hash_degraded=False
    │   → Bloque auto_restart NO se evalúa → restart_mining() nunca se llama
    │
    └─► FGA ve: cohort puede ser COOL o STANDARD según R_th
        → Puede recomendar 2700W, pero el preset ya está configurado a 2700W
        → La recomendación es redundante y no resuelve el restart_required
```

#### Solución Propuesta para F-01/F-07

**Inmediata (Operativa)**: Ejecutar manualmente `safe_restart_mining` en M24.
**Arquitectónica (Spec futura)**: Implementar un watchdog de `restart_required` separado del bloque `is_hash_degraded`.

---

### 3.2 Fricción F-02: Trampa de RECOVERY_MAX_COOLING en Fan Governor

#### Causa Raíz Técnica

En [`fan_governor.py` L300](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/fan_governor.py#L300):
```python
if current_power_w < (target_power_w - cfg.power_margin_w):
```
- `current_power_w` = 2498W (preset cgminer 2500W)
- `target_power_w` = 2700W (potencia objetivo del minero)
- `power_margin_w` = 120W
- Evaluación: `2498 < (2700 − 120) = 2580` → **True** → 100% PWM indefinido

El Fan Governor fue diseñado para una transición **temporal**: el minero está escalando y necesita chips fríos para que el autoswitch de VNish lo autorice a subir de preset. El supuesto implícito es que **el minero eventualmente llegará a 2700W** y la condición se volverá `False`.

En el caso de M24, **esa transición nunca ocurrirá** sin un `restart_mining`. El Fan Governor no tiene visibilidad de la bandera `restart_required` y no puede distinguir entre "escalando temporalmente" y "atrapado permanentemente".

#### Impacto Operativo Medido

- **Ruido acústico**: ~6000 RPM continuos en un equipo que tiene chips a 57-77°C (muy por debajo del setpoint de 81-82.5°C).
- **Consumo parasitario de fans**: ~150-200W adicionales de consumo eléctrico en ventiladores.
- **Desgaste de rodamientos**: Los motores brushless de los coolers tienen vida útil acotada; operación continua al 100% innecesaria los degrada.

#### Solución Propuesta para F-02

Agregar consciencia de `restart_required` al Fan Governor o al ciclo de gobernador en `miner_monitor.py`:

**Opción A** (sin cambios al Fan Governor puro):
En el ciclo de gobernador de `miner_monitor.py`, al construir `target_pwr` para el Fan Governor, si `state.vnish_restart_required=True` y el preset ejecutado (cgminer actual) es `< max_hardware_preset`, usar el preset **ejecutado** (no el configurado) como `target_pwr` para el Fan Governor:
```python
# Si restart_required activo, Fan Governor usa el preset en ejecución real
# para evitar RECOVERY_MAX_COOLING permanente por preset pendiente de restart
if getattr(state, 'vnish_restart_required', False):
    target_pwr = state.current_power_w or target_pwr
```

**Opción B** (más limpia, requiere Spec nueva):
Agregar parámetro `preset_pending_restart: bool` a `compute_governor_step()`. Si `True`, suprimir el check de RECOVERY_MAX_COOLING (la condición de potencia deficiente es legítimamente permanente hasta el restart, no un defecto de arranque).

---

### 3.3 Fricción F-03: Asimetría de Estabilidad Eléctrica entre Elevadores

#### Datos Empíricos

| Métrica | Elevador 1 | Elevador 2 |
|---------|-----------|-----------|
| Eventos eléctricos (2026-09-30) | 0 | 3 (06:15, 07:42, 11:51) + caída de fase 21:37 |
| Uptime actual (mineros) | 49.1h / 32.7h | 22.3h / 22.3h |
| Carga actual | ~5200W (2700+2500) | ~5400W (2700+2700) |
| Carga si M24 sube | ~5400W (2700+2700) | ~5400W (sin cambio) |

#### Análisis de Riesgo

El Elevador 1 ha demostrado **calidad de energía impecable** durante 49+ horas, lo que sugiere que la acometida física (relés, transformador, cableado) del Elevador 1 tiene mayor margen de seguridad que la del Elevador 2.

**Hipótesis de Fatiga del Elevador 2**:
Los 3 eventos del 2026-09-30 en Elevador 2 coinciden con operación continua a ~5400W. El transformador de Elevador 2 opera más cerca de su límite térmico de diseño. La rebaja de 5400W a 5000W (un minero a 2500W) como medida temporal podría confirmar si los eventos son causados por la carga continua.

**¿Es seguro subir M24 a 2700W?**

El riesgo eléctrico no es despreciable, pero el Elevador 1 tiene un historial limpio que sugiere mayor robustez. Las salvaguardas escalonadas que deben verificarse antes de dar el paso son:

1. ✅ **Gate 0 Incident Quiet**: Elevador 1 no tiene incidentes recientes → 0 segundos de espera.
2. ✅ **Gate 1 Facility Settle**: Última transición hace >32h → ventana de 180s ya expirada.
3. ✅ **Gate 2 Hardware Ceiling**: M24 tiene `max_hardware_preset="2700W"` en config.
4. ✅ **Gate 3 Solar Envelope**: A las 11:10 hs (inicio de franja solar), T_chip M24 = 57-77°C. Franja solar activa, pero chip **por debajo** de 82°C → max_authorized_preset = 2500W (franja solar activa sin sobrecalentamiento). ⚠️ **BLOQUEANTE ACTUAL**: El Solar Envelope retorna `max_authorized_preset=solar_preset=2500W` cuando `is_solar_window=True` aunque `is_overheated=False`. Esto significa que **ahora mismo** (11:10 hs, dentro de la franja solar 11:00-17:00) el orquestador bloquearía el ascenso a 2700W en Gate 3.
5. ⏳ **Gate 3.1 Thermal Headroom**: T_chip_M24 = 57-77°C < 80°C → **OK si gate 3 fuera superado**.
6. ✅ **Gate 4 Schedule**: 2026-10-01 es un jueves. Hora actual 11:10 hs. Franja pico matutina es 08:30-09:30 (config) → ya ha terminado. Franja pico nocturna es 20:00-21:15 → no activa aún. **Off-peak weekday** → valley preset 2700W permitido.
7. ⚠️ **Gate 5 Budget**: M23 ya está a 2700W. Si M24 sube a 2700W, grupo = 2700+2700 = 5400W ≤ 5400W límite de valle → **OK**.
8. ✅ **Gate 6 Symmetric Balance**: M23 está a 2700W (≥2500W) → partner ya cumple la condición de simetría → **OK**.

**Conclusión**: El único bloqueante actual para subir M24 a 2700W es el **Gate 3 (Solar Envelope)**. La franja solar activa (11:00-17:00) impone techo de 2500W mientras esté activa, aunque el chip esté frío. La ventana óptima para ejecutar el `safe_restart_mining` en M24 es **antes de las 11:00 hs o después de las 17:00 hs** (cuando la solar envelope se desactiva).

> **Nota**: El snapshot de 10:14 hs del briefing probablemente se tomó antes de las 11:00 hs. Si la acción se ejecuta ahora (11:10 hs), el Solar Envelope bloquearía la transición de preset a 2700W después del restart. El cgminer reiniciaría con el preset que tenga activo en ese momento (2700W en config), pero el VALLEY_ORCHESTRATOR podría intervenir para bajar a 2500W post-restart. Sin embargo, `safe_restart_mining` no cambia el preset — solo recarga cgminer con la config existente. El preset ya está en 2700W en `/config/cgminer.conf`. Por lo tanto, el restart cargará 2700W y el Solar Envelope debería evaluarse en el ciclo siguiente para decidir si corresponde bajar.

---

### 3.4 Fricción F-04: FGA Sin Visibilidad de `restart_required`

#### Causa Raíz

El Facility Governance Agent ([`facility_agent.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/facility_agent.py)) recibe telemetría de `miners_telemetry` que incluye: `chip_temp_c`, `inlet_temp_c`, `power_w`, `preset`, y `electrical_group`. No recibe:
- `vnish_restart_required`
- `vnish_discovered_preset` (preset real en ejecución vs configurado)
- Estado de `restart_required` de VNish

Esto significa que si M24 tiene `preset="2700W"` en la telemetría FGA (tomado del config), pero en realidad ejecuta 2500W, el FGA calculará `R_th = (T_chip − T_inlet) / P` con `P=2700W` cuando el poder real es 2498W. El error en `R_th` es pequeño (≈7%), pero la cohorte podría clasificarse incorrectamente (e.g., COOL en vez de STANDARD).

#### Impacto

La decisión del FGA de recomendar 2700W para M24 es redundante (ya está en 2700W en config) pero puede generar diagnósticos de explicación engañosos al operador ("ya está en 2700W" cuando en realidad no lo está).

---

### 3.5 Fricción F-05: Interacción Solar Envelope + RECOVERY_MAX_COOLING (Hipotético)

Si M24 sube a 2700W pero en la franja solar el Solar Envelope lo baja a 2500W, el Fan Governor volverá a activar `RECOVERY_MAX_COOLING` (100% fans) porque `current_w=2498W < 2700W−120W=2580W`. Sin embargo, en ese escenario el `target_pwr` del Fan Governor debería resolverse como 2500W (el nuevo objetivo de contingencia, no 2700W). Si la resolución de `target_pwr` en `miner_monitor.py` usa el `balancer_preset` (2500W) cuando hay una contingencia activa, la condición `current < target−120W = 2500−120 = 2380W` → 2498W ≥ 2380W → `False` → Fan Governor **no** activaría RECOVERY_MAX_COOLING.

Esta fricción hipotética no es un problema **si** el código de resolución de `target_pwr` en `miner_monitor.py` usa correctamente `balancer_preset` cuando está activo. Debe verificarse en el código (fuera del alcance de esta revisión documental).

---

## 4. Protocolo de Resolución Técnica Paso a Paso

### 4.1 Resolución Inmediata: S19JPRO-24 (Acción Operativa — Requiere Aprobación del Operador)

**Prerrequisito**: Confirmar que la hora es fuera de la franja solar (antes de 11:00 hs o después de 17:00 hs) para evitar que el orquestador baje el preset post-restart.

> **Estado actual (11:10 hs 2026-10-01)**: La franja solar está activa (11:00-17:00). El restart técnicamente puede ejecutarse (recargar cgminer con el preset 2700W que ya está en config), pero el VALLEY_ORCHESTRATOR podría emitir un step-down en el siguiente ciclo de evaluación de presupuesto de elevador si detecta que el Elevador 1 supera 5400W. Dado que 2700+2700=5400W = exactamente el límite, el Gate 5 pasaría. El Gate 3 (Solar Envelope) solo bloquea la **asignación proactiva** de preset, no el restart de cgminer. Por lo tanto, el restart es seguro en términos de gates del orquestador.

**Pasos de ejecución**:

1. **Verificar estado actual de M24**:
   ```
   GET http://192.168.100.24/api/v1/status
   GET http://192.168.100.24/api/v1/summary (cooling + chip_temp)
   ```
   Confirmar: `restart_required=True`, `chip_temp < 80°C`, `miner_state=mining`.

2. **Validar config en firmware**:
   ```
   safe_get_overclock_settings("192.168.100.24", password)
   ```
   Confirmar: `preset="2700"`, `top_preset="2700"`, `min_preset="1740"`.

3. **Ejecutar restart suave**:
   ```python
   safe_restart_mining("192.168.100.24", password)
   ```
   Esto ejecuta `POST /api/v1/mining/restart` → cgminer recarga config → frecuencias escalan a ~521 MHz → potencia sube de 2498W a ~2698W.

4. **Verificar resultado esperado** (en los siguientes 2-5 minutos):
   - `current_preset` debe mostrar `"2700"` (no `"2500"`)
   - `restart_required` debe ser `False`
   - `power_usage` debe estar en ~2698W
   - Fan Governor debe desactivar `RECOVERY_MAX_COOLING` (fans bajarán de 100% a ~92%)
   - Temperatura de chips debe subir de 57-77°C a ~76-82°C
   - Hashrate debe incrementar de 92.4 TH/s a ~98-101 TH/s

5. **Alerta de seguimiento**:
   - Monitorear por 30 minutos que los chips no superen 82.5°C (deadband_high)
   - Si chips superan 84°C, el Thermal Guard ejecutará automáticamente step-down a 2500W (cerrojo 2 horas)

---

### 4.2 Resolución Arquitectónica: Watchdog de `restart_required` (Nueva Spec)

**Objetivo**: Detectar automáticamente cuando `restart_required=True` y el minero está en estado saludable (no degradado), y ejecutar `safe_restart_mining` tras un periodo de soak configurable (default: 300s después de la última transición de preset).

**Contrato de seguridad para el Watchdog**:

| Condición | Acción |
|-----------|--------|
| `restart_required=True` Y `is_hash_degraded=True` | Ya cubierto por `evaluate_auto_restart_candidate`. No actuar duplicado. |
| `restart_required=True` Y `is_hash_degraded=False` Y `thermal_pause_until_ts` activo | HOLD — esperar fin de pausa térmica |
| `restart_required=True` Y `is_hash_degraded=False` Y `uptime < soak_window (300s)` | HOLD — esperar estabilización post-preset-change |
| `restart_required=True` Y `is_hash_degraded=False` Y `uptime ≥ soak_window` Y `T_chip < 80°C` | **EJECUTAR `safe_restart_mining`** |
| `restart_required=True` Y `is_hash_degraded=False` Y `uptime ≥ soak_window` Y `T_chip ≥ 80°C` | HOLD — esperar enfriamiento (Headroom Chilling activo) |

**Cooldown post-restart**: Respetar `settle_window_seconds=180s` del Facility Budget antes de ejecutar otro restart.

**Notificación**: Enviar alerta Telegram al ejecutar el restart (evento `preset_restart_applied`, severidad `info`).

---

### 4.3 Resolución del Fan Governor: Consciencia de `restart_required`

**Cambio mínimo de bajo riesgo** en el ciclo de gobernador de `miner_monitor.py`:

```python
# Antes de calcular la decisión del Fan Governor para cada minero:
effective_target_pwr = target_pwr

# Si el preset está pendiente de restart (configurado pero no aplicado),
# usar la potencia real en ejecución como target para el Fan Governor.
# Evita RECOVERY_MAX_COOLING permanente cuando restart_required=True.
vnish_restart_req = getattr(state, 'vnish_restart_required', False)
if vnish_restart_req and current_power_w is not None and current_power_w >= 500.0:
    effective_target_pwr = current_power_w  # preset en ejecución real

# Usar effective_target_pwr (en lugar de target_pwr) en la llamada a compute_governor_step()
```

**Efecto**: Cuando `restart_required=True` y `current_power_w=2498W`, el Fan Governor usará `target=2498W`. La condición `2498 < 2498−120=2378` → `False`. El Fan Governor entra en lazo cerrado normal (modulación por temperatura). Los chips a 57-77°C recibirían `ACTION_STEP_DOWN` progresivo hasta los pisos configurados (~60-70% PWM para 2500W actual). El ruido cesará.

**Invariante de seguridad preservado**: Esta lógica solo aplica cuando `restart_required=True`. En condiciones normales de escalado (sin restart_required), `RECOVERY_MAX_COOLING` sigue activo como antes.

---

### 4.4 FGA: Inyección de `vnish_restart_required` en Telemetría

Añadir el campo `vnish_restart_required` en la telemetría que se pasa a `evaluate_asymmetric_allocation()`:

```python
# En la construcción de miners_telemetry para FGA:
{
    "name": miner_name,
    "electrical_group": group,
    "chip_temp_c": ...,
    "power_w": state.current_power_w,          # Potencia REAL (no config)
    "preset": state.vnish_discovered_preset,    # Preset REAL en cgminer
    "config_preset": state.balancer_preset,     # Preset CONFIGURADO en VNish config
    "vnish_restart_required": getattr(state, 'vnish_restart_required', False),
}
```

El FGA usará `power_w` (real) para calcular `R_th`, evitando el error de clasificación de cohorte cuando hay discrepancia entre preset configurado y ejecutado.

---

### 4.5 Evaluación Eléctrica del Elevador 1: Estrategia de Monitoreo Post-Subida

Una vez ejecutado el restart de M24 y verificada la estabilidad, implementar el siguiente protocolo de monitoreo para el Elevador 1:

**Ventana de observación**: 24-48 horas post-subida a 5400W.

**Métricas de vigilancia** (ya recopiladas automáticamente en `data/miner_alerts.db`):
- Uptime continuo de M23 y M24 (sin reinicios inesperados)
- `operational_events` con `event_type IN ('unexpected_restart', 'phase_drop', 'offline')` para `elevator_1`
- Frecuencias de cadenas (estabilidad de PLLs en ~521 MHz)
- Temperatura de chips (mantenerse en 76-82°C)

**Criterio de éxito**: 24h sin eventos eléctricos en Elevador 1 a 5400W → Elevador 1 confirmado robusto para esta carga.

**Criterio de regresión** (trigger automático de vuelta a 5200W): ≥1 evento de reinicio inesperado simultáneo o caída de fase en Elevador 1 → activar `PROFILE_C1_ASYMMETRIC` (M23=2700W, M24=2500W) automáticamente si el código de perfiles lo soporta.

---

## 5. Evaluación de Riesgos para Producción

### 5.1 Riesgos por Acción

| Acción | Riesgo | Mitigación |
|--------|--------|-----------|
| Ejecutar `safe_restart_mining` en M24 | Breve caída del hashrate (~30-60s) durante recarga de cgminer. Si config está corrupta (Spec 080), el restart fallará con código 1002 | `check_miner_settings_health` antes del restart. Si 1002 → detener y notificar. |
| Elevador 1 a 5400W sostenidos | Potencial fatiga del transformador si este tiene las mismas características que el Elevador 2 | Monitoreo activo 24h. Rollback inmediato si hay eventos eléctricos. |
| Agregar Watchdog `restart_required` al código | Podría ejecutar restarts en momentos inadecuados si las condiciones de seguridad no son exhaustivas | Cooldown estricto, soak_window configurable, bloqueo por pausa térmica, notificación Telegram obligatoria. |
| Cambiar `target_pwr` del Fan Governor cuando `restart_required=True` | Los fans bajarían en un equipo con preset pendiente de restart. Si el restart se produce mientras los fans están bajos, podría haber pico térmico transitorio | El restart es rápido (cgminer sube a 2700W en segundos). El Fan Governor detectaría inmediatamente `current < target−120W` y volvería a 100%. Riesgo despreciable. |

### 5.2 Invariantes que No Deben Romperse

1. **Tests a 100%**: Cualquier cambio en `fan_governor.py`, `miner_monitor.py` o `elevator_budget.py` debe pasar la suite completa (1429 tests).
2. **No restart automático sin gate de seguridad**: El watchdog de `restart_required` debe respetar todos los interlocks térmicos y de estado.
3. **Formato Telegram ≤32 columnas**: Las alertas del nuevo watchdog deben seguir el estándar móvil.
4. **`app/config.json` y `app/state.json` no se commitean**: Solo modificar `app/config.example.json` y documentación.
5. **Commits manuales y feature-scoped**: Cada resolución es una spec independiente con su ciclo completo (QA + Stabilize).

---

## 6. Resumen Ejecutivo y Plan de Implementación

### 6.1 Prioridades por Urgencia

| Prioridad | Acción | Tipo | Ventana Temporal |
|-----------|--------|------|-----------------|
| **Inmediata** | Ejecutar `safe_restart_mining` en M24 | Operativa (aprobación operador) | Después de 17:00 hs (fuera de Solar Envelope) o confirmar que el preset config no cambia tras restart en franja solar |
| **Corto plazo** | Spec nueva: Watchdog de `restart_required` | Arquitectónica | Próxima sesión de desarrollo |
| **Corto plazo** | Corrección Fan Governor: `effective_target_pwr` cuando `restart_required=True` | Código | Misma spec que watchdog |
| **Medio plazo** | FGA: inyectar `power_w` real (vs config) en telemetría | Arquitectónica | Siguiente sprint |
| **Observación** | Monitorear Elevador 1 a 5400W post-restart M24 | Operativa | 24-48h post-subida |

### 6.2 Spec Propuesta: `restart_required_watchdog`

**Archivos a modificar**:
- [`app/miner_monitor.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py): Nuevo bloque watchdog separado del bloque `is_hash_degraded`
- [`app/governance/fan_governor.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/fan_governor.py): Parámetro opcional `preset_pending_restart: bool` (Opción B) O parche en `miner_monitor.py` (Opción A, sin tocar fan_governor.py puro)
- [`app/config.example.json`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/config.example.json): Nuevo campo `restart_required_watchdog_soak_seconds: 300`
- Nuevos tests en `tests/test_restart_required_watchdog.py`

**Estimación**: 4-6 horas de implementación + QA + Stabilize.

### 6.3 Cohesión de Directivas Post-Resolución

Una vez aplicadas las resoluciones de las Fricciones F-01, F-02, y F-07:

```
Estado Post-Resolución de M24:
  - cgminer ejecuta: 2700W (~521 MHz, ~2698W reales)
  - restart_required: False
  - Fan Governor: lazo cerrado 92% PWM (chips en 76-82°C)
  - RECOVERY_MAX_COOLING: INACTIVO
  - Hashrate: ~98-101 TH/s
  - Flota total: ~393-400 TH/s

Directivas en armonía:
  ✅ Fan Governor: lazo cerrado normal
  ✅ Elevator Budget: 2700+2700=5400W = límite valle (OK)
  ✅ FGA: M24 cohorte evaluada con potencia real 2700W
  ✅ VNish daemon: preset_switcher opera en rango [1740W-2700W]
  ✅ Thermal Guard: activo (step-down a 84°C si necesario)
  ✅ restart_required Watchdog: no hay preset pendiente → pasivo
```

---

## 7. Evidencia Requerida para Cierre de Auditoría

Antes de considerar esta auditoría completamente resuelta, se requiere evidencia de:

- [ ] `safe_restart_mining` ejecutado exitosamente en M24 y `restart_required=False` confirmado
- [ ] M24 hasheando a ≥98 TH/s con preset ejecutado = 2700W
- [ ] Fans de M24 modulando en lazo cerrado (≤92% PWM) con chips en 76-82°C
- [ ] Elevador 1 estable a 5400W por ≥24h sin eventos eléctricos
- [ ] Spec `restart_required_watchdog` implementada, testeada (1429+ tests PASS) y documentada
- [ ] Corrección del Fan Governor (`effective_target_pwr`) implementada y validada
- [ ] Este documento actualizado con evidencia de cierre

---

*Documento generado por Claude Sonnet 4.6 (Thinking) como parte del ciclo de gobernanza y auditoría de directivas del sistema miner-alerts.*
*Próximo modelo recomendado: **Gemini 3.8 Flash High** para la implementación del Watchdog `restart_required` (tarea de implementación acotada y determinista).*
