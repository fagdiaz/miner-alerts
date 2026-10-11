# Feature Specification: Armonización Térmica y Estabilidad VNish (Spec 092)

**Feature Name**: VNish Firmware Harmonization & Silicon Asymmetry Stability
**Feature Code**: `092-vnish-harmonization-and-stability`
**Tracking Issue / Incident**: Diagnóstico de Reinicios Inesperados en M24 y M26 (Octubre 2026)
**Status**: IN IMPLEMENTATION
**Author**: Antigravity Assistant & Production Engineering
**Baseline**: V6.0 Hookified Architecture (1530 tests PASS, NSSM Service RUNNING)
**Target Outcome**: Eliminación total de reinicios espurios en M24 y M26 eliminando la colisión térmica entre el Fan Governor (objetivo 82°C) y el Preset Switcher de VNish (`decrease_temp: 84°C`), desacoplando perfiles térmicos asimétricos de silicio y reconectando la telemetría periódica de cadenas SQLite en el pipeline de hooks.

---

## 1. Problem Statement & Root Cause Forensic Summary

A partir del 9-11 de octubre de 2026, la planta experimentó una serie de reinicios a deshoras concentrados exclusivamente en los mineros `S19JPRO-24` (3 reinicios en 24h) y `S19JPRO-26` (5 reinicios en 24h), mientras que `S19JPRO-23` se mantuvo con 60+ horas de uptime continuo ininterrumpido (0 reinicios) y `S19JPRO-25` con más de 10 horas continuas.

La auditoría forense profunda de `logs/out.log`, `data/miner_alerts.db` y las APIs REST de VNish (`/api/v1/summary`, `/api/v1/settings`) identificó la **causa raíz**:

1. **Colisión de Consignas Térmicas (Fan Governor vs VNish Preset Switcher)**:
   - Los mineros tienen configurado internamente en VNish el `preset_switcher`:
     `{enabled: true, top_preset: "2700", decrease_temp: 84, rise_temp: 79, check_time: 300}`.
   - Nuestro Fan Governor buscaba estabilizar a **82.0°C** (`deadband_high_c: 82.5°C`), relajando ventiladores al piso mínimo de 92% en 2700W.
   - En 2700W (~900W por placa disipada), los chips de la Cadena 1 oscilaban entre 82°C y 84°C.
   - En cuanto cualquier chip de la Cadena 1 roza los **84.0°C**, el watchdog interno de VNish ejecuta un desescalado forzado en caliente (`decrease_temp: 84`). La modulación instantánea de voltaje bajo 2700W induce pérdidas de sincronización de PLL y errores CRC en el bus SPI/I2C de Cadena 1.
   - VNish desconecta la placa marcándola en `failure` (0 chips / 0 TH/s).
   - Nuestro supervisor detecta `active_boards < 3` -> Clasifica `HASHBOARD` -> Ejecuta reinicio automático (`AUTO_RESTART`).

2. **Bucle de Caza de Recuperación (Autoswitch Hunting Loop)**:
   - Al reiniciar, el minero arranca en 2300W.
   - El Fan Governor detecta potencia inferior al objetivo y activa la Regla 5 (`ACTION_RECOVERY_MAX_COOLING`), forzando ventiladores al 100% PWM.
   - Al enfriar a $\le 79^\circ\text{C}$ durante 300 segundos, el `preset_switcher` de VNish (`rise_temp: 79`) escala automáticamente a 2500W y luego a 2700W.
   - Al llegar a 2700W, el Fan Governor reduce los ventiladores hacia 92% buscando 82°C.
   - La Cadena 1 de M24 o M26 vuelve a superar los 82°C, roza los 84°C, VNish corta la Cadena 1, y el ciclo de reinicio se repite cada 1.5 a 3 horas indefinidamente.

3. **Asimetría de Silicio Obligatoria**:
   - M23 y M25 poseen excelente calidad de juntura térmica y sostienen 2700W de forma continua sin exceder 81°C.
   - M24 y M26 presentan impedancia térmica más alta en Cadena 1 y NO toleran 2700W a bajas revoluciones; sin embargo, a **2500W** operan a 74-76°C con margen térmico holgado, rindiendo 95-97 TH/s sostenidos con cero reinicios.

4. **Omisión de Telemetría Periódica en Hook Pipeline**:
   - En la refactorización a hooks de Spec 091, `_async_collect_chain_telemetry` quedó desconectada del ciclo periódico (faltaba invocación periódica cada 300s en `PostTickHook`), deteniendo la recolección periódica en SQLite desde el 9 de octubre.

---

## 2. User Stories & Value Proposition

### User Story 1: Armonización Térmica con Firmware VNish
> **Como** operador de planta minera,
> **Quiero** que el Fan Governor estabilice a una temperatura nominal de 79.5°C con zona muerta hasta 81.0°C y disparo de emergencia a 82.5°C,
> **Para que** exista una barrera de seguridad de al menos 3.0°C respecto al umbral de corte de 84.0°C de VNish, evitando desescalados abruptos y cortes de cadena por calentamiento.

### User Story 2: Clampeo Asimétrico de Silicio para M24 y M26
> **Como** supervisor de infraestructura,
> **Quiero** que los mineros térmicamente restringidos (`S19JPRO-24` y `S19JPRO-26`) tengan su potencia objetivo clampeada a 2500W tanto en la configuración del supervisor como en el firmware VNish (`top_preset: "2500"`),
> **Para que** operen en su punto óptimo continuo de eficiencia y estabilidad sin sufrir el bucle de sobrecalentamiento a 2700W.

### User Story 3: Restauración de Telemetría Periódica de Cadenas
> **Como** ingeniero de confiabilidad,
> **Quiero** que la telemetría detallada de cadenas por ASIC (`/api/v1/chains`), la evaluación predictiva de fallas y el mantenimiento WAL de SQLite se ejecuten periódicamente dentro de `PostTickHook`,
> **Para que** la base de datos `data/miner_alerts.db` mantenga series temporales actualizadas y alertas preventivas sin sobrecargar el bucle principal.

---

## 3. Scope & Technical Specifications

### Included (In Scope)
1. **Calibración de Parámetros del Fan Governor**:
   - `fan_governor_target_temp_c`: `79.5` (antes `82.0`)
   - `fan_governor_deadband_low_c`: `78.0` (antes `81.0`)
   - `fan_governor_deadband_high_c`: `81.0` (antes `82.5`)
   - `fan_governor_emergency_temp_c`: `82.5` (antes `83.0`)
   - Sincronización en `app/config.json` y `app/config.example.json`.

2. **Perfiles Asimétricos de Silicio por Minero**:
   - `S19JPRO-23` y `S19JPRO-25`: `target_power_w: 2700.0`, `max_hardware_preset: "2700W"`.
   - `S19JPRO-24` y `S19JPRO-26`: `target_power_w: 2500.0`, `max_hardware_preset: "2500W"`.
   - Actualización en vivo de configuración VNish en M24 y M26 mediante `safe_set_miner_preset(host, pw, "2500", clamp_top_preset=True, top_preset="2500")`.

3. **Reconexión de Pipeline de Telemetría en `PostTickHook`**:
   - Invocación en segundo plano (`threading.Thread`) de `_async_collect_chain_telemetry` cada `chain_telemetry_interval_s` (300s).
   - Invocación de `_async_evaluate_predictive_chain_break` cada `predictive_chain_eval_interval_s` (300s).
   - Mantenimiento periódico SQLite WAL (`PASSIVE` cada 3600s, `TRUNCATE` en ventana 03:00-05:00 UTC).

4. **Verificación y Certificación Operativa**:
   - Verificación de no-regresión en la suite de pruebas (`pytest` $\ge 1530$ tests PASS).
   - Ejecución de `speckit-qa` y `speckit-stabilize`.
   - Monitoreo en vivo de telemetría con el servicio NSSM reiniciado.

### Excluded (Out of Scope)
- Modificación de los algoritmos de hashing ni flasheo de firmware.
- Desactivación de las alertas de seguridad por placas faltantes (`HASHBOARD`).

---

## 4. Invariants & Safety Gates

1. **Invariante Térmica Headroom $\ge 3^\circ\text{C}$**: Ningún target del Fan Governor operará a más de 81.0°C para garantizar margen absoluto frente al umbral 84.0°C de VNish.
2. **Invariante de Clampeo de Firmware**: Mineros con `max_hardware_preset: "2500W"` deben tener `top_preset: "2500"` en el firmware para que el escalador autónomo de VNish no sobrepase 2500W.
3. **Invariante de Test Suite**: $\ge 1530$ tests unitarios e integrados pasando sin regresiones.
4. **Compuerta de Estabilización**: `speckit-stabilize` 8/8 gates PASS antes del release.
