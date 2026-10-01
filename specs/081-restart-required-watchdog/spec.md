# Spec 081: Watchdog de Reinicio de Minado Pendiente y Armonización Térmica (PROP-017)

## 1. Contexto y Objetivos

### 1.1 El Problema Operativo y la Evidencia Empírica de Auditoría
En la auditoría exhaustiva de directivas (`docs/audit/DIRECTIVES_HARMONIZATION_AUDIT.md`), se catalogaron 16 directivas en 5 capas de prevalencia y se descubrieron 3 fricciones operacionales activas derivadas de la interacción entre VNish y el monitor central:

1. **Fricción F-01 / F-07 (Nudo de Preset No Aplicado)**:
   - Al configurar un nuevo preset en `/api/v1/settings` de VNish, el firmware escribe el JSON en `/config/cgminer.conf` y levanta la bandera `restart_required = True`.
   - Sin embargo, el motor de hasheo (`cgminer`) no conmuta en caliente los reguladores de voltaje ni las tablas PLL de frecuencia sin un reinicio de minado (`POST /api/v1/mining/restart`).
   - El monitor central (`app/miner_monitor.py` L6966-7025) solo evaluaba auto-reinicios si `is_hash_degraded` era `True` (`rate_ths < 60 TH/s` o placas caídas).
   - Por tanto, un minero con preset pendiente pero hasheando a nivel nominal previo (ej. Minero 24 hasheando sano a 92.4 TH/s en 2500W con target en 2700W) nunca era reiniciado, quedando atrapado de forma permanente en el preset inferior.

2. **Fricción F-02 (Trampa de RECOVERY_MAX_COOLING en el Fan Governor)**:
   - El Fan Governor (`app/governance/fan_governor.py`) evalúa `current_power_w < (target_power_w - 120W)`.
   - Al no tener visibilidad de que el preset estaba pendiente de restart, evaluaba `2498W < 2580W` (`True`), forzando de forma incondicional `ACTION_RECOVERY_MAX_COOLING` (100% PWM / ~6000 RPM).
   - Esto provocaba ruido ensordecedor continuo, desgaste de rodamientos y ~180W parasitarios de consumo en ventiladores, aun cuando los chips operaban a temperaturas muy frías (57°C - 77°C).

3. **Fricción F-04 (Imprecisión en Telemetría FGA)**:
   - El Facility Governance Agent calculaba la resistencia térmica de silicio $R_{th}$ usando la potencia configurada en lugar de la potencia medida real cuando existía un preset pendiente de restart.

### 1.2 Directiva del Operador
*"hagamos lo que sea conveniente segun las directivas que nos dio sonnet"*

### 1.3 Objetivos de la Especificación
1. **Watchdog Autónomo de `restart_required`**: Implementar en `app/miner_monitor.py` un evaluador dedicado desacoplado de `is_hash_degraded`, que ejecute `safe_restart_mining` de forma segura tras una ventana de estabilización (`soak_window = 300s`) con verificación de temperatura ($T_{chip} < 80^\circ\text{C}$).
2. **Armonización del Fan Governor**: Fijar `effective_target_pwr = current_power_w` en el ciclo de gobernador cuando `restart_required = True`, liberando a los ventiladores de la trampa del 100% PWM y permitiendo modulación adaptativa en lazo cerrado mientras se espera la ventana de reinicio.
3. **Telemetría FGA Real**: Inyectar la potencia real consumida y la bandera de restart pendiente en la evaluación asimétrica de cohortes.
4. **Validación y Certificación**: Crear suite de pruebas unitarias dedicada y pasar el 100% de la regresión global (1429+ tests PASS).

---

## 2. Requerimientos Funcionales

- **FR-001**: El monitor DEBE registrar el estado `vnish_restart_required: bool` en el objeto de estado del minero (`MinerState`) a partir de la consulta periódica de telemetría de firmware (`/api/v1/status`).
- **FR-002**: El monitor DEBE incorporar el Watchdog de `restart_required` que evalúa:
  - `vnish_restart_required == True`
  - `is_hash_degraded == False` (el minero está hasheando saludablemente)
  - Sin pausa térmica activa (`thermal_pause_until_ts is None`)
  - Tiempo transcurrido en el preset actual $\ge soak\_window$ (300 segundos)
  - Temperatura de chips segura ($T_{chip} < 80.0^\circ\text{C}$)
  - Fuera de cooldown de reinicios de minado
- **FR-003**: Al cumplirse las condiciones del FR-002, el Watchdog DEBE invocar `safe_restart_mining(host, password)`, registrar el evento operacional `preset_restart_applied` (severidad `info`) en `data/miner_alerts.db` y despachar una notificación informativa a Telegram.
- **FR-004**: En `execute_governor_cycle` (`app/miner_monitor.py`), si `getattr(state, "vnish_restart_required", False)` es `True` y `gov_curr_pwr >= 500.0`, el gobernador DEBE usar `gov_target_pwr = gov_curr_pwr` como potencia objetivo efectiva, suprimiendo la activación permanente de `ACTION_RECOVERY_MAX_COOLING`.
- **FR-005**: La interfaz móvil de Telegram DEBE respetar estrictamente el límite de ancho $\le 32$ columnas.
- **FR-006**: La resolución empírica en producción de Minero 24 (escalamiento exitoso a 2700W, 2699W en cadenas, 97.5+ TH/s y erradicación de `RECOVERY_MAX_COOLING`) DEBE quedar documentada en `evidence.md`.

---

## 3. Historias de Usuario y Casos de Aceptación

### Historia 1: Destrabe Autónomo de Preset Pendiente (P1)
**Dado** un minero cuyo archivo `/config/cgminer.conf` fue actualizado con un nuevo preset y reporta `restart_required = True`,
**Cuando** el minero hashea de forma sana pero en el preset antiguo durante más de 300 segundos y sus chips están a temperatura segura (<80°C),
**Entonces** el Watchdog ejecuta automáticamente un reinicio suave de minado, recargando el nuevo preset sin interrumpir indebidamente la operación ni requerir intervención manual.

### Historia 2: Normalización Térmica y Acústica de Coolers (P1)
**Dado** un minero con `restart_required = True` esperando su ventana de reinicio,
**Cuando** el Fan Governor evalúa la potencia consumida frente al objetivo,
**Entonces** toma la potencia real en ejecución como meta efectiva, modula los ventiladores en lazo cerrado por temperatura y evita dejar los ventiladores clavados al 100% PWM.
