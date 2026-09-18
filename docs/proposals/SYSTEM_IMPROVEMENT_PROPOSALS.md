# Propuestas de Mejora y Evolución del Sistema — Miner Alerts

- **Fecha de Creación**: 2026-09-10
- **Línea Base**: Release V4.0.1 (Post-Blackout Persistence Hardening & Concurrency Stabilization)
- **Autor**: Antigravity Assistant & Engineering Team
- **Estado**: Documentado / Para Evaluación en Futuros Ciclos Speckit

---

## 📋 Resumen Ejecutivo

Tras el completamiento de las 53 especificaciones del ciclo V1 a V4 y la reciente resolución del incidente post-corte de luz (Release Hotfix V4.0.1), el sistema **Miner Alerts** cuenta con una arquitectura de gobernanza madura, lazo cerrado de control de ventiladores, balanceo dinámico de elevadores, interfaz Mobile-First en Telegram y persistencia atómica en disco.

Este documento consolida y prioriza **7 propuestas técnicas de mejora** derivadas de observaciones en producción, casos de borde operativos reales y auditorías de rendimiento, orientadas a maximizar la resiliencia física, reducir el ruido de alertas y optimizar el rendimiento energético de la flota ASIC.

---

| ID | Propuesta | Prioridad | Riesgo | Estado / Spec | Impacto Principal |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **PROP-001** | Período de Gracia y Calentamiento Post-Arranque (`Cold-Boot Grace Period`) | **P1 (Alta)** | Bajo | **Completado (Spec 066)** | Cero falsas alarmas tras retorno de energía o reinicio del host. |
| **PROP-002** | Resiliencia SQLite WAL Mode & Integridad ante Apagones | **P1 (Alta)** | Bajo | **Completado (Spec 061)** | Blindaje transaccional de EventStore contra cierres abruptos. |
| **PROP-003** | Rollback Automático por Tasa de Errores de Hardware (`HW Error Tripwire`) | **P2 (Media)** | Medio | **Completado (Spec 062)** | Protección de silicio y eliminación de shares desperdiciados. |
| **PROP-004** | Gobernador Térmico con Conciencia Estacional (`Ambient-Aware Thermal PID`) | **P2 (Media)** | Medio | **Completado (Spec 063)** | Ahorro energético en invierno y máxima disipación en verano. |
| **PROP-005** | Latido de Gateway y Supresión de Tormentas por Fallo de Red Local | **P2 (Media)** | Bajo | **Planificado (Spec 067)** | Supresión de alarmas espurias ante parpadeos del switch Ethernet. |
| **PROP-006** | Tarjetas de Gráficos Comparativos Multi-Miner en Telegram (`/chart` Overlays) | **P3 (Baja)** | Bajo | **Completado (Spec 064)** | Visibilidad operativa inmediata de divergencias entre elevadores. |
| **PROP-007** | Canal IPC de Alta Frecuencia Monitor ↔ Watchdog (Named Pipes) | **P3 (Baja)** | Medio | **Completado (Spec 068)** | Detección de bloqueos del GIL y diagnóstico forense en <15s. |
| **PROP-008** | Telemetría Profunda por Cadena & Diagnóstico Predictivo Chain Break | **P1 (Alta)** | Medio | **Completado (Spec 069)** | Diagnóstico predictivo de fallas de bus I2C y degradación de placas. |
| **PROP-009** | Contingencia Coordinada de Pares y Estabilización de Elevadores | **P1 (Alta)** | Medio | **En Recopilación / Hipótesis Activa** | Eliminación de reinicios múltiples y cascadas de elevador durante arranques. |
| **PROP-010** | Recuperación Suave de Hasheo y Blindaje Anticolapso de Fuentes APW12 | **P1 (Alta)** | Medio | **Documentado / Base de Futura Spec** | Supresión de bloqueos de fuentes APW12 (Latch-Off) mediante desescalada pre-reinicio. |

---

## 🛠️ Detalle Técnico de las Propuestas

### PROP-001: Período de Gracia y Calentamiento Post-Arranque (`Cold-Boot Grace Period`)

#### 1. Contexto y Problema
En el incidente post-blackout del 10/09/2026, el host Windows tardó ~30 segundos en bootear e iniciar el servicio `MinerAlerts`. Sin embargo, los mineros ASIC (Antminer S19j Pro con firmware Vnish) tardan habitualmente entre **120 y 240 segundos** en:
1. Cargar el kernel Linux desde la memoria NAND.
2. Iniciar el demonio de red y sincronizar fecha por NTP.
3. Ejecutar la calibración de autotuning de voltajes y frecuencias en las 3 placas.
4. Establecer conexión con el pool de minería y comenzar a emitir hashrate real.

Como resultado, el monitor ejecutó su primer tick inmediatamente tras bootear, encontrando a los mineros en estado `OFFLINE` o con `0.00 TH/s [LOW]`. El mensaje de `STARTUP` emitido a Telegram reportó un estado alarmante que no reflejaba un fallo real, sino simplemente la inicialización normal del hardware.

#### 2. Solución Propuesta
Introducir un estado transitorio de arranque controlado:
* **Parámetro de Configuración**: `"startup_fleet_grace_period_seconds": 180` (por defecto: 180s, configurable en `app/config.json`).
* **Heurística de Detección**:
  - Si el uptime del sistema operativo o el tiempo de inicio del servicio indica un arranque fresco (`process_start_ts - boot_ts < 300s` o estado local limpio), el monitor ingresa a la fase `WARMING_UP`.
* **Comportamiento durante la Gracia**:
  - Sondeo pasivo en segundo plano cada tick (30s) sin disparar alertas de `OFFLINE` ni contabilizar streaks de `LOW`.
  - La tarjeta de `STARTUP` en Telegram se aplaza hasta que:
    a) Todos los mineros reporten $\ge 50\text{ TH/s}$ (flota activa y estable).
    b) Expire la ventana de gracia de 180 segundos.
  - Al consolidarse, se emite una tarjeta limpia:
    ```text
    🟢 FLOTA RESTABLECIDA (21:44:15)
    Supervisión activa tras retorno de energía:
    - 23: 89.1 TH/s [OK] 72°C
    - 24: 98.9 TH/s [OK] 79°C
    - 25: 86.4 TH/s [OK] 70°C
    - 26: 86.6 TH/s [OK] 68°C
    ```

#### 3. Beneficios
* Cero falsas alarmas o pánico del operador tras cortes de luz.
* Coherencia total con la realidad física del tiempo de booteo de los ASICs.

---

### PROP-002: Resiliencia SQLite WAL Mode & Integridad ante Apagones

#### 1. Contexto y Problema
El motor `EventStore` utiliza SQLite para almacenar métricas de telemetría, decisiones del gobernador, auditorías de reinicios y logs de firmware. Tras un corte de energía intempestivo, una base de datos SQLite en modo journal clásico (`DELETE` o `ROLLBACK`) corre el riesgo de sufrir bloqueos de escritura si el archivo de rollback quedó a medio escribir o si el disco no sincronizó los sectores.

#### 2. Solución Propuesta
Blindar la inicialización y operación de SQLite en `app/core/event_store.py`:
1. **Modo WAL Forzado**:
   ```python
   cursor.execute("PRAGMA journal_mode = WAL;")
   cursor.execute("PRAGMA synchronous = NORMAL;")
   cursor.execute("PRAGMA wal_autocheckpoint = 1000;")
   ```
   * En modo WAL (Write-Ahead Logging), las escrituras nunca modifican las páginas existentes de la base de datos principal, sino que se anexan secuencialmente a un archivo `.db-wal`. Un corte de energía en mitad de una escritura jamás corrompe la estructura de la base de datos.
2. **Chequeo de Integridad en Arranque**:
   - En el constructor de `EventStore`, ejecutar `PRAGMA quick_check;`.
   - Si la verificación falla (código de error o corrupción física), mover automáticamente el archivo corrupto a `data/miner_alerts_corrupt_<ts>.db` y crear una base de datos nueva con el esquema vigente (v6), registrando un aviso de advertencia en los logs.

---

### PROP-003: Rollback Automático por Tasa de Errores de Hardware (`HW Error Tripwire`)

#### 1. Contexto y Problema
En el balanceador de elevadores (Spec 040), cuando un minero escala a presets agresivos (2500W o 2700W), chips individuales pueden volverse inestables debido a envejecimiento del silicio, degradación de pasta térmica o caída de tensión. Si un minero produce un número elevado de *Hardware Errors* en CGMiner, continúa consumiendo energía al máximo pero enviando trabajo inválido al pool, reduciendo el hashrate efectivo y la rentabilidad.

#### 2. Solución Propuesta
Implementar un "Tripwire" de protección en `app/governance/preset_balancer.py`:
* Monitorear la métrica `Hardware Errors` y `Hardware%` retornada por la API 4028 en cada ciclo.
* **Criterio de Disparo**:
  - Si en una ventana de 10 minutos se detectan más de 50 nuevos errores de hardware o `Hardware% > 0.5%`:
    1. Desescalar inmediatamente el preset del minero en 200W (ej. 2700W -> 2500W).
    2. Fijar una bandera `hardware_lock_ts = now + 48h` impidiendo que el Preset Balancer vuelva a subir la potencia durante 48 horas.
    3. Enviar una tarjeta Mobile-First a Telegram alertando de silicio degradado:
       ```text
       ⚠️ HARDWARE ERROR TRIPWIRE
       Minero: S19JPRO-24
       Causa: 78 HW Errors en 10m
       Acción: Desescalado a 2500W
       Bloqueo: 48h en preset seguro
       ```

---

### PROP-004: Gobernador Térmico con Conciencia Estacional (`Ambient-Aware Thermal PID`)

#### 1. Contexto y Problema
Actualmente, el gobernador térmico (Spec 039) utiliza un objetivo estático de 75°C - 82°C.
* En **invierno** (temperatura ambiente de 5°C a 15°C en galpón), los mineros pueden mantenerse a 65°C con los ventiladores al 50%-60% de RPM, ahorrando desgaste mecánico y reduciendo la contaminación acústica.
* En **verano** (temperatura ambiente de 30°C a 38°C), se requiere una rampa anticipatoria mucho más agresiva para que los ventiladores alcancen el 100% antes de que la masa térmica de los disipadores toque los 80°C.

#### 2. Solución Propuesta
* **Inferencia de Temperatura Ambiente**:
  - Los mineros Antminer S19j Pro disponen de sensores en los ventiladores de entrada (`temp_in` en telemetría Vnish).
  - Promediar `temp_in` para estimar la temperatura ambiente del recinto minero.
* **Ajuste Dinámico de Rampas**:
  - Si $T_{\text{amb}} < 18^\circ\text{C}$: Modo "Silencio Acústico y Conservación de Fans" (target 78°C, piso de fans 50%).
  - Si $T_{\text{amb}} > 28^\circ\text{C}$: Modo "Disipación Agresiva de Verano" (target 74°C, rampa acelerada hacia 100% PWM).

---

### PROP-005: Latido de Gateway y Supresión de Tormentas por Fallo de Red Local

#### 1. Contexto y Problema
El discriminador de caídas de fase (Spec 051) verifica la conectividad del gateway cuando ocurre una caída unísona. Sin embargo, si un switch de red local o access point hogareño sufre un reinicio rápido (parpadeo de 5 a 10 segundos) o un bucle de STP, las conexiones TCP a los 4 mineros pueden fallar simultáneamente por timeout, generando un falso conato de alerta antes de que el monitor verifique el gateway.

#### 2. Solución Propuesta
* Hilo daemon en segundo plano con sondeo de bajísimo impacto (socket connect no bloqueante de 50ms cada 5 segundos al router/gateway local `192.168.100.1`).
* **Ventana de Supresión de Tormentas**:
  - Si el enlace con el router parpadea, congelar la emisión de alertas de Telegram durante 15 segundos.
  - Si la red se reanuda dentro de esos 15 segundos, descartar la anomalía como "Transitorio de Enlace Ethernet Local" registrándolo en log sin molestar al operador en Telegram.

---

### PROP-006: Tarjetas de Gráficos Comparativos Multi-Miner en Telegram (`/chart` Overlays)

#### 1. Contexto y Problema
Actualmente, `/chart <id>` genera un gráfico PNG para un minero individual. Cuando los operadores sospechan un desbalance térmico o de carga en un elevador (ej. Elevador 1: Mineros 23 y 24), deben pedir `/chart 23` y `/chart 24` por separado, dificultando la comparación visual en pantallas de teléfonos móviles.

#### 2. Solución Propuesta
Extender [`app/telegram/charts.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/telegram/charts.py):
* Comando `/chart elevator_1` o `/chart fleet`:
  - Renderiza en memoria un gráfico multi-línea con matplotlib:
    * Eje Y1: Hashrate (TH/s) de ambos mineros superpuestos.
    * Eje Y2: Temperatura de chip de ambos mineros.
  - Asignación de colores fijos por equipo (azul, naranja, verde, rojo).
* **Teclado Interactivo Inline**:
  - Debajo de la imagen enviada, agregar botones de cambio de rango temporal en 1 toque:
    `[ ⏱️ 1h ] [ ⏱️ 6h ] [ ⏱️ 24h ] [ ⏱️ 7d ]`
  - Al pulsar un botón, la imagen de Telegram se actualiza en el lugar (`editMessageMedia`) sin saturar el historial del chat.

---

### PROP-007: Canal IPC de Alta Frecuencia Monitor ↔ Watchdog (Named Pipes)

#### 1. Contexto y Problema
Actualmente, el watchdog independiente ([`tools/monitor_watchdog.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/tools/monitor_watchdog.py)) se ejecuta mediante el Programador de Tareas de Windows leyendo el archivo `monitor_heartbeat.json` y ejecutando `sc.exe queryex`. Aunque es seguro y desacoplado, tiene una latencia de detección de hasta 2 a 5 minutos. Si el monitor entra en un interbloqueo o bucle cerrado de CPU, la detección tarda más de lo deseable.

#### 2. Solución Propuesta
* Crear un servidor de Named Pipe local en Windows dentro del monitor: `\\.\pipe\MinerAlertsWatchdog`.
* El watchdog envía un paquete de desafío `PING\n` y espera `PONG\n` con un timeout de 2 segundos.
* **Ventajas**:
  - Detección instantánea de bloqueos del GIL de Python o deadlocks de hilos en menos de 10 segundos.
  - Si el pipe no responde pero el proceso existe en Windows, el watchdog sabe con 100% de certeza matemática que el proceso está congelado en kernel o en llamada C bloqueante, procediendo al reinicio automático del servicio.

---

### PROP-008: Telemetría Profunda por Cadena y Diagnóstico Predictivo de Hashboard (Chain Break Analysis)

#### 1. Contexto y Hallazgo en Producción
Durante el incidente del 2026-09-12 (Evento 940), el minero 24 sufrió un reinicio abrupto tras registrar `chain_break` en el firmware Vnish. Una sonda en caliente realizada sobre la API REST (`/api/v1/chains`) reveló que el Minero 24 presenta un fallo persistente en el sensor térmico I2C de la **Cadena 2 (Board 2)**:
```json
{"state": "error", "board": 39, "chip": 54, "loc": 28}
```
mientras que los demás mineros de la granja (23, 25 y 26) mantienen el 100% de sus sensores en estado `measure`.

Actualmente, el monitor captura únicamente métricas consolidadas (hashrate total, promedio de voltaje entre placas y conteo `active_boards: 3/3`), perdiendo la visibilidad granular por cadena que el firmware Vnish expone nativamente.

#### 2. Datos Disponibles en Vnish `/api/v1/chains` para Acumulación
* **Salud de Sensores Térmicos**: Lista de 4 sensores por placa con estado (`measure` vs `error`), temperatura de placa, chip y ubicación física (`loc: 28, 61, 66, 99`).
* **Déficit de Hashrate por Cadena**: Comparativa en tiempo real de `hr_realtime` vs `hr_nominal`.
* **Frecuencia por Cadena**: Desviaciones de autotuning por placa individual.
* **Mapa de Chips (126 chips por placa)**: Chips degradados, chips con errores de hardware (`errs > 0`), chips térmicamente estrangulados (`throttled: true`) y clasificación de silicio (`grade`).

#### 3. Arquitectura de Captura y Análisis de Datos
1. **Esquema de Almacenamiento (`chain_telemetry_samples`)**:
   - Tabla SQLite optimizada para almacenar métricas por placa cada 15–30 minutos y de forma reactiva ante cualquier transición a `HASHBOARD`, `LOW` o `reboot_detected`.
   - Campos: `miner_key`, `chain_id`, `hr_realtime`, `hr_nominal`, `freq_mhz`, `sensors_json`, `err_chips_count`, `throttled_count`.
2. **Herramienta Analítica de Correlación (`tools/analyze_chain_breaks.py`)**:
   - Análisis de series temporales para predecir desconexiones antes de que ocurran:
     - **Regla 1 (Falla de Bus I2C)**: Si un sensor reporta `state: error` por más de 12 horas, alertar preventivamente riesgo de desconexión de bus en placa específica.
     - **Regla 2 (Déficit de Potencia/Hashrate)**: Si una placa rinde $< 92\%$ de su nominal mientras las otras rinden $100\%$, predecir degradación de chips o caída de tensión en dominio.
     - **Regla 3 (Aislamiento de Causas)**: Correlación cruzada entre elevador (fase eléctrica AC), fuente de alimentación (DC general) y placa hash (señal interna SPI/I2C) para determinar con certeza matemática si un reinicio es eléctrico o de silicio.

### PROP-009: Contingencia Coordinada de Pares y Estabilización Rápida de Elevadores

#### 1. Contexto y Problema
Durante perturbaciones de red o reinicios en un elevador eléctrico, el sistema experimenta múltiples reinicios en bucle (2 a 4 por equipo) y caídas en cascada del compañero entre 700s y 1000s después. La contingencia asimétrica actual ([Spec 057](../specs/057-adaptive-elevator-contingency/spec.md)) presentaba un desacople de software que silenciaba la llamada REST a la API de VNish y dejaba al minero compañero a plena carga (2700W), induciendo un transitorio inductivo ($L \cdot di/dt$) al reanudar el minado.

#### 2. Hipótesis y Diagnóstico Técnico
Se han formulado y documentado 5 hipótesis analíticas respaldadas por telemetría de producción:
* **H1 (Bug Crítico de Software)**: `display_name` ('24') vs `name` ('S19JPRO-24') silencia la escritura física de preset en hardware.
* **H2 (Conflicto Firmware VNish)**: `preset_switcher` re-acelera a `top_preset: 2700` en frío.
* **H3 (Transitorio Eléctrico)**: Salto de 0A a 12A induce caída de tensión en el autotransformador, desestabilizando al par.
* **H4 (Enfriamiento Excesivo)**: Fan Governor al 100% enfría chips a <53°C provocando fallas SPI/I2C de autotuning.
* **H5 (Ventana de Calentamiento)**: Watchdog de 180s colisiona con el tiempo real de calibración de VNish (210s-240s).

Para el estudio completo, modelos matemáticos, código y plan de validación, consultar el documento específico:
👉 **[PROP-009: Diagnóstico Exhaustivo de Reinicios Múltiples en Contingencia](PROP-009-contingency-stabilization-hypotheses.md)**.

Herramienta de auditoría continua: `tools/audit_contingency_night.py`.

---

## 📅 Estado de Implementación & Hoja de Ruta

1. **Iniciativas Completadas (Fases 4 a 6 - V5.0 Post-Evolution)**:
   - ✅ **PROP-001** (`Cold-Boot Fleet Grace Period`) -> Implementada y certificada en **Spec 066** (1062 tests PASS).
   - ✅ **PROP-002** (`SQLite WAL Mode & Integrity Check`) -> Implementada y certificada en **Spec 061**.
   - ✅ **PROP-003** (`HW Error Tripwire & Overclock Rollback`) -> Implementada y certificada en **Spec 062**.
   - ✅ **PROP-004** (`Ambient-Aware Thermal PID`) -> Implementada y certificada en **Spec 063**.
   - ✅ **PROP-006** (`Multi-Miner Charts & Range Switchers`) -> Implementada y certificada en **Spec 064**.

2. **Horizonte V5.1 (Completado y Certificado)**:
   - ✅ **PROP-005** (`Latido de Gateway y Supresión de Tormentas`) -> Implementada y certificada en **Spec 067**.
   - ✅ **PROP-007** (`Canal IPC Alta Frecuencia Monitor ↔ Watchdog`) -> Implementada y certificada en **Spec 068**.
   - ✅ **PROP-008** (`Telemetría Profunda por Cadena & Diagnóstico Chain Break`) -> Implementada y certificada en **Spec 069**.
   - Ver detalle de ejecución en [`docs/speckit/archive/plans/ACTION_PLAN_V5_1_HORIZON.md`](../speckit/archive/plans/ACTION_PLAN_V5_1_HORIZON.md).

3. **Iniciativas en Evaluación y Recopilación Activa**:
   - 🔬 **PROP-009** (`Contingencia Coordinada de Pares y Estabilización de Elevadores`) -> Documento específico en [`docs/proposals/PROP-009-contingency-stabilization-hypotheses.md`](PROP-009-contingency-stabilization-hypotheses.md). Herramienta de auditoría operativa en [`tools/audit_contingency_night.py`](../../tools/audit_contingency_night.py).

---

*Documento archivado en `docs/proposals/SYSTEM_IMPROVEMENT_PROPOSALS.md` como repositorio formal de iniciativas técnicas del proyecto Miner Alerts.*
