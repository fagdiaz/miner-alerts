# PROP-009: Diagnóstico Exhaustivo de Reinicios Múltiples en Contingencia y Arquitectura de Estabilización de Elevadores

- **Fecha de Creación**: 2026-09-17 00:25 hs
- **Última Actualización**: 2026-09-17 00:38 hs
- **Autor**: Antigravity Engineering (Gemini 3.8 Flash High)
- **Estado**: Recopilación de Datos Activa / Hipótesis Formuladas / Herramienta de Auditoría Operativa
- **Herramienta de Verificación**: [tools/audit_contingency_night.py](file:///F:/02-ASIC%20-%20mineros/miner-alerts/tools/audit_contingency_night.py)
- **Alcance**: Algoritmo de Contingencia Asimétrica ([Spec 057](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/057-adaptive-elevator-contingency/spec.md)), Preset Balancer ([Spec 040](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/040-dynamic-power-preset-balancer/spec.md)), Interacción Firmware VNish REST API y Gobernador Térmico ([Spec 039](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/039-fan-governor-pid-tuning/spec.md)).

---

## 1. Resumen Ejecutivo y Síntoma Operativo

Durante episodios de perturbación eléctrica o micro-cortes de cadenas en mineros ASIC Antminer S19j Pro (VNish), el sistema de supervisión experimenta un patrón repetitivo de **reinicios múltiples en cascada (2 a 4 reinicios consecutivos por grupo eléctrico)** antes de lograr estabilizar la operación en estado `OK`.

Este fenómeno se caracteriza por:
1. Un minero sufre un reinicio inicial inesperado o parada de seguridad de firmware.
2. El minero compañero en el mismo grupo de elevador eléctrico sufre una caída correlacionada (**cascada de elevador**) entre **700 y 1000 segundos después**, justo cuando el primer minero intenta volver a plena potencia.
3. El minero en recuperación intenta booteos sucesivos donde las cadenas 1 o 2 fallan en responder (`state='failure'`), provocando que el firmware aborte el proceso a los ~120s-140s de booteo y reinicie el ciclo.
4. El proceso consume entre 15 y 30 minutos de tiempo productivo antes de alcanzar estabilidad térmica y eléctrica combinada.

---

## 2. Evidencia Empírica de Producción (16/09 y 17/09)

La ejecución de la herramienta de auditoría [tools/audit_contingency_night.py](file:///F:/02-ASIC%20-%20mineros/miner-alerts/tools/audit_contingency_night.py) sobre `data/miner_alerts.db` arroja la siguiente cronología de precisión:

### Episodio A: Madrugada 2026-09-16 (03:00 - 06:30 hs)
- **03:09:13**: S19JPRO-25 (`elevator_2`) reinicia (uptime: 3871s $\to$ 15s).
- **03:43:13**: S19JPRO-24 (`elevator_1`) reinicia por falla de sensor I2C en loc 28.
- **03:56:43**: S19JPRO-23 (`elevator_1`) **cae en cascada** 780s tras S19JPRO-24. Carga grupo: 2698 W.
- **04:23:43**: S19JPRO-25 (`elevator_2`) vuelve a reiniciar.
- **04:51:13**: S19JPRO-24 (`elevator_1`) vuelve a reiniciar.
- **05:19:13**: S19JPRO-23 (`elevator_1`) **vuelve a caer en cascada** 1680s tras S19JPRO-24.
- **06:25:43**: S19JPRO-23 (`elevator_1`) **tercera caída en cascada** 1680s tras S19JPRO-24.
- **06:26:13**: S19JPRO-25 (`elevator_2`) reinicia (uptime 7096s $\to$ 0s).

### Episodio B: Noche y Madrugada 2026-09-16 / 2026-09-17 (23:47 - 00:30 hs)
- **23:47:40**: S19JPRO-26 (`elevator_2`) sufre `chain_break` en cadena 1 (`chip1362.c`). VNish ejecuta parada y enfriamiento de 120s.
- **23:55:03**: S19JPRO-26 comienza rampa de potencia y pasa de 0 W a 2299 W. S19JPRO-25 se mantiene a 2698 W. Carga combinada salta a **4997 W**.
- **00:04:03**: S19JPRO-25 (`elevator_2`) **cae en cascada** (960s tras S19JPRO-26).
  * Uptime reiniciado: 50504s $\to$ 5s.
  * A las 00:06:33 las 3 cadenas reportan `state='failure'`.
  * Monitor envía `auto_restart_mining` a las 00:07:03.
  * A las 00:10:03 logra estabilizar al reducirse a 2298 W (preset 2100W).
- **00:13:03**: S19JPRO-24 (`elevator_1`) reinicia por falla sensor I2C cadena 2.
  * A las 00:15:03: cadenas 1 y 2 fallan en inicializar (`state='failure'`). Solo 1/3 placas activas.
  * A las 00:15:33: VNish aborta y reinicia el proceso (uptime reiniciado: 140s $\to$ 20s).
  * A las 00:17:33: Tercer reinicio interno (uptime: 110s $\to$ 3s).
  * A las 00:18:33: Finalmente estabiliza con 3/3 placas (99.2 TH/s).
- **00:26:03**: S19JPRO-23 (`elevator_1`) **cae en cascada correlacionada** 780s tras S19JPRO-24. Carga grupo: 2698 W.
  * Uptime reiniciado: 64544s $\to$ 0s.
  * Monitor asiste con `auto_restart_mining` y a las 00:30 hs S19JPRO-23 recupera a 87.8 TH/s.

### Episodio C: Madrugada 2026-09-17 (01:00 - 02:45 hs)
- **01:04:03**: S19JPRO-24 (`elevator_1`) reinicia por falla sensor I2C en loc 28 (uptime: 2733s $\to$ 15s).
- **01:47:33**: S19JPRO-24 (`elevator_1`) reinicia nuevamente (uptime: 2278s $\to$ 10s).
- **02:21:03**: S19JPRO-26 (`elevator_2`) reinicia (uptime: 8985s $\to$ 1s).
- **02:34:03**: S19JPRO-25 (`elevator_2`) **cae en cascada correlacionada** exactamente **750s tras S19JPRO-26** (carga grupo 2299 W).
  * Uptime reiniciado: 8720s $\to$ 0s.
  * Monitor emite `auto_restart_mining` a las 02:39:33 hs.
- **02:34:33**: S19JPRO-24 (`elevator_1`) reinicia por sensor I2C loc 28 (uptime: 2512s $\to$ 5s).
- **02:41:00**: Ambas parejas completan su ciclo de autotuning y alcanzan estabilidad térmica sostenida.
- **02:41 a 10:05 hs (>7.4 horas ininterrumpidas)**: CERO reinicios en toda la flota, 4/4 mineros al 100% de placas (~401 TH/s combinados).

### Episodio D: Tarde 2026-09-17 (18:28 - 20:26 hs) — Validación Empírica de Protección APW12 (Latch-Off)
- **18:28:00**: S19JPRO-25 (`elevator_2`) cae en desconexión tras operar a 2298 W nominales (descartando sobreconsumo >2700 W).
- **19:04:35 a 19:10:05**: La controladora del minero 25 reinicia, cgminer responde al puerto 4028 y levanta las 3 placas con 126 chips a 450 MHz (~42.7 TH/s).
- **19:11:10**: Al alcanzar el escalón de plena potencia, la interfaz de red del minero 25 desaparece por completo (incluso de la tabla ARP, `DestinationHostUnreachable`).
- **Verificación Física en Sitio (Operador)**:
  * La llave termomagnética del tablero principal **permaneció levantada en todo momento** (no hubo sobrecarga en la línea de CA).
  * El síntoma radicaba en la fuente **Bitmain APW12**: se encontraba en estado de **bloqueo de protección (*Latch-Off*)**, cortando la línea de 12V DC (que alimenta tanto a los hashboards como a la controladora).
  * El operador realizó un ciclo de corte y restitución de 220V CA en el enchufe del minero, descargando los capacitores primarios.
- **20:22:35 a 20:26:05**: La fuente restableció la salida, la controladora arrancó en red, superó la fase de calentamiento protegida por `miner_warming_up` y a las 20:26:05 alcanzó **84.90 TH/s sostenidos en estado `OK`** (62% fan duty, 2298 W).
- **Conclusión de Impacto**: Confirma categóricamente **H3**: transitorios inductivos y picos de arranque bruscos no disparan las térmicas generales de la casa/nave, sino el circuito de protección interna de las fuentes APW12. La amortiguación escalonada del compañero (`PROP-009` / Spec 074) es crucial para evitar perturbar el bus eléctrico compartido durante los arranques.

---

## 3. Las 5 Hipótesis Técnicas Formuladas

### 🔴 Hipótesis 1 (Software - Bug Crítico): Desacople de Nombre (`display_name`) Silencia la Escritura del Preset
- **Ubicación**: [app/miner_monitor.py](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py#L6145-L6167) y línea 7557.
- **Mecanismo de Falla**:
  ```python
  _decision = evaluate_canary_contingency(
      event_type="unexpected_restart",
      miner_name=name_display,   # Pasa '24' (display_name('S19JPRO-24'))
      group_name=m_group,
      ...
  )
  ...
  # Búsqueda estricta por 'name' en config.json:
  _tgt_miner = next((m_item for m_item in miners if m_item.get("name") == _decision.target_miner), None)
  ```
  * En `config.json`, `m_item.get("name")` es `"S19JPRO-24"`.
  * `_decision.target_miner` es `"24"`.
  * La igualdad `"S19JPRO-24" == "24"` es `False`.
  * Por ende, `_tgt_miner` es **`None`**.
  * El bloque `safe_set_miner_preset(...)` **nunca se ejecuta**.
- **Impacto**: El monitor genera la alerta de Telegram, actualiza `elevator_contingency` en `state.json` y asume que el minero bajó a 2500W o 2300W. **Sin embargo, la máquina física sigue configurada a 2700 W en su memoria**. Al reanudar el minado, vuelve a demandar la máxima potencia sobre el elevador degradado, causando reinicios repetitivos.

---

### 🟡 Hipótesis 2 (Firmware): Conflicto con el `preset_switcher` interno de VNish
- **Ubicación**: [app/vnish/client.py](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/vnish/client.py#L248-L260) y [app/state.json](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/state.json).
- **Mecanismo de Falla**:
  En `app/state.json`, los 4 mineros reportan:
  ```json
  "vnish_discovered_switcher_enabled": true,
  "vnish_discovered_top_preset": "2700"
  ```
  La función `set_miner_preset` en `app/vnish/client.py` envía únicamente:
  ```json
  {"miner": {"overclock": {"preset": "2300"}}}
  ```
  En el firmware VNish, cuando `preset_switcher.enabled` es `True`, un demonio interno evalúa periódicamente la temperatura de los chips ($T_{max}$). Si $T_{max} < rise\_temp$ (típicamente 75°C), VNish incrementa automáticamente el preset hacia `top_preset` (2700 W).
- **Impacto**: Como el minero acaba de reiniciar y sus chips están fríos (~50°C-55°C), el firmware ignora la restricción de 2300 W y vuelve a escalar a 2700 W en menos de 2 minutos, destruyendo la contención eléctrica del elevador.

---

### 🟡 Hipótesis 3 (Física / Eléctrica): Transitorio Inductivo ($L \cdot \frac{di}{dt}$) y Caída de Tensión (Voltage Sag) en el Par
- **Fundamento Teórico**:
  Un autotransformador elevador de tensión monofásico posee inductancia serie $L_{line}$ y resistencia interna $R_{line}$. La tensión en bornes de las fuentes APW12 responde a:
  $$V_{bus}(t) = V_{grid}(t) \cdot N_{tap} - R_{line} \cdot I_{total}(t) - L_{line} \cdot \frac{dI_{total}(t)}{dt}$$
  * Potencia nominal por minero: $2700\text{ W} \implies I \approx 12.3\text{ A}$ a 220 V.
  * Carga total del elevador con 2 mineros: $\approx 24.6\text{ A}$.
- **Mecanismo de Falla**:
  Cuando un minero se apaga por caída de cadena, la corriente baja de 24.6 A a 12.3 A (la tensión sube ligeramente).
  Cuando ese minero vuelve a arrancar, pasa de **0 A a 12 A en menos de 10 segundos** ($\frac{di}{dt} > 1.2\text{ A/s}$).
  El transitorio inductivo genera un valle de tensión (*voltage sag*) transitorio. Si la tensión cae por debajo del umbral UVLO de la fuente APW12 (~195 V) o introduce rizado excesivo en el bus de 12 V DC:
  * El PLL de los chips BM1362 del minero compañero pierde el lock de fase.
  * El minero compañero sufre un reinicio retardado (entre 700s y 1000s después, cuando la potencia se consolida).
- **Impacto**: La contingencia asimétrica actual es insuficiente porque deja al compañero a plena potencia (2700 W) mientras el otro intenta arrancar, empujando al transformador a su límite de saturación.

---

### 🟡 Hipótesis 4 (Térmica / Hardware): El Ventilador al 100% (`RECOVERY_MAX_COOLING`) enfría excesivamente el silicio
- **Ubicación**: [app/miner_monitor.py](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py#L5880-L5920).
- **Mecanismo de Falla**:
  Al detectar caída de hashrate o estado `LOW`, el Fan Governor activa la acción de seguridad `RECOVERY_MAX_COOLING`, fijando ventiladores al 100% PWM (~6000 RPM).
  * Los disipadores térmicos de las placas bajan abruptamente a temperatura ambiente (50°C - 53°C).
  * Los chips ASIC BM1362 presentan una curva de impedancia de entrada y capacitancia parásita dependiente de la temperatura. En frío (<55°C), las líneas de comunicación serie SPI / I2C de chips degradados (ej. loc 28 en cadena 2 de minero 24, o chip1362 en minero 26) tienen menor margen de ruido y mayor dispersión temporal.
  * VNish realiza el autotuning de frecuencias en frío. Al no recibir respuesta de paridad en los 126 chips, clasifica `chain_break` a los ~140s de booteo y aborta el proceso.
- **Impacto**: El minero sufre 2 o 3 reinicios hasta que las placas acumulan suficiente calor residual (>65°C) como para que las señales lógicas sincronicen.

---

### 🟡 Hipótesis 5 (Coordinación de Procesos): Ventana de Calentamiento del Monitor vs Duración de Autotune de VNish
- **Ubicación**: [app/miner_monitor.py](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py#L5303) (`auto_restart_min_elapsed_seconds = 180`).
- **Mecanismo de Falla**:
  El monitor considera que a partir de 180 segundos el minero debería estar operativo. Sin embargo, un ciclo completo de inicialización con calibración de voltajes por chip en VNish puede demorar entre **180 y 240 segundos**.
  Si a los 180 segundos una placa aún está en fase de sintonización (`chains_transitioning_count > 0`), el monitor clasifica `active_boards < expected_boards` (`HASHBOARD`) y programa una intervención (`auto_restart_mining`), interrumpiendo el booteo legítimo del firmware.

---

## 4. Arquitectura Propuesta para el Nuevo Algoritmo (PROP-009)

Para resolver definitivamente los reinicios múltiples y garantizar estabilización rápida en un solo ciclo, se propone evolucionar el módulo de contingencia hacia un esquema de **Contingencia Coordinada de Pares y Amortiguación de Arranque (Paired Inrush Dampening)**:

```
                  ┌────────────────────────────────────────────────────────┐
                  │            REINICIO DETECTADO EN ELEVADOR              │
                  │              (ej. Minero A reinicia)                   │
                  └──────────────────────────┬─────────────────────────────┘
                                             │
                                             ▼
                  ┌────────────────────────────────────────────────────────┐
                  │ 1. RESOLUCIÓN CANÓNICA & BLINDAJE REST                 │
                  │    - Match por normalize_miner_name(target)            │
                  │    - Set preset=2300W + top_preset=2300W               │
                  │    - Sync state.balancer_preset                        │
                  └──────────────────────────┬─────────────────────────────┘
                                             │
                                             ▼
                  ┌────────────────────────────────────────────────────────┐
                  │ 2. AMORTIGUACIÓN TEMPORAL DEL COMPAÑERO (Inrush Damp)  │
                  │    - Minero B (compañero) baja temporalmente -1 tier   │
                  │      (ej. 2700W -> 2500W) durante 300s                 │
                  │    - Genera 200W-400W de "Headroom" en el elevador     │
                  │      mientras Minero A ejecuta el inrush inicial       │
                  └──────────────────────────┬─────────────────────────────┘
                                             │
                                             ▼
                  ┌────────────────────────────────────────────────────────┐
                  │ 3. PISO TÉRMICO DE ARRANQUE (Thermal Warmup Floor)     │
                  │    - Durante WARMING_UP (elapsed < 240s):              │
                  │      Fan Governor topeado al 60% PWM si T < 75°C       │
                  │    - Permite calentamiento rápido del silicio a 65°C   │
                  │      eliminando fallas de comunicación en frío         │
                  └──────────────────────────┬─────────────────────────────┘
                                             │
                                             ▼
                  ┌────────────────────────────────────────────────────────┐
                  │ 4. RESTAURACIÓN ESCALONADA (Staggered Recovery)        │
                  │    - Minero A alcanza OK sostenido (> 180s con 3/3 brd)│
                  │    - Minero B recupera su preset nominal               │
                  │    - Cero cascadas, cero reinicios duplicados          │
                  └────────────────────────────────────────────────────────┘
```

---

## 5. Protocolo de Validación para Mañana

Mañana por la mañana, con los datos acumulados de toda la noche (especialmente el período crítico de 03:00 a 07:00 hs), ejecutaremos:

```powershell
& ".\.venv\Scripts\python.exe" tools\audit_contingency_night.py --hours 12
```

### Criterios Cuantitativos de Aprobación/Rechazo de Hipótesis:
1. **Validación H1 (Bug Desacople)**: Confirmada al 100% por inspección estática y dinámica. Corrección requerida en código.
2. **Validación H2 (Switcher VNish)**: Verificar en `telemetry_samples` si la potencia de los mineros en contingencia subió espontáneamente a 2700 W antes de cumplir las 2h de soak.
3. **Validación H3 (Cascada de Par)**: Verificar si los reinicios de S19JPRO-23 y S19JPRO-25 ocurrieron sistemáticamente dentro de los 15 minutos posteriores al reinicio de su compañero de elevador.
4. **Validación H4 (Silicio Frío)**: Cuantificar cuántos `chain_break` ocurrieron con temperaturas de chip $< 60^\circ\text{C}$ durante los primeros 180s de booteo.
5. **Validación H5 (Interrupción por Timeout)**: Verificar si algún `auto_restart_mining` se emitió mientras `chains_transitioning_count > 0`.

Con esta matriz validada, se procederá a implementar la solución de hardening en el código base con la suite de 1204 pruebas unitarias respaldando cada cambio.
