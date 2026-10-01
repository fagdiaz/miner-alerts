# Briefing de Auditoría Arquitectónica y Gobernanza de Flota

**Fecha**: 2026-10-01  
**Destinatario**: Claude Sonnet 4.6 (Thinking)  
**Objetivo**: Realizar una auditoría minuciosa de todas las directivas, gobernanzas, automatizaciones y contratos entre subsistemas del proyecto `miner-alerts`, identificando fricciones, bloqueos latentes y solapamientos, y diseñando un plan de resolución integral sin colisión de directivas ni riesgos para la producción.

---

## 1. Contexto Operativo y Estado Actual de Producción

- **Runtime**: Windows Server / Windows Desktop, NSSM Service `MinerAlerts` (`SERVICE_RUNNING`), Python 3.12 venv, SQLite WAL (`data/miner_alerts.db`).
- **Flota Activa**: 4x Antminer S19j Pro (firmware VNish 1.2.6):
  * **Elevador 1**: S19JPRO-23 (192.168.100.23) y S19JPRO-24 (192.168.100.24).
  * **Elevador 2**: S19JPRO-25 (192.168.100.25) y S19JPRO-26 (192.168.100.26).
- **Estado de Hasheo (Snapshot 2026-10-01 10:14 hs)**:
  * **M23**: 100.0 TH/s | Preset ejecutado: **2700W** (cadenas: 2698W) | Fan: 92% | Uptime: **49.1 horas**.
  * **M24**: 92.4 TH/s | Preset ejecutado: **2500W** (cadenas: 2498W) | Fan: **100%** | Uptime: **32.7 horas** (desde Spec 080).
  * **M25**: 101.5 TH/s | Preset ejecutado: **2700W** (cadenas: 2699W) | Fan: 92% | Uptime: **22.3 horas** (estable >12.5h).
  * **M26**: 99.5 TH/s | Preset ejecutado: **2700W** (cadenas: 2699W) | Fan: 92% | Uptime: **22.3 horas** (estable >12.5h).
  * **Hashrate Total**: ~393.5 TH/s (3 equipos a 2700W, 1 equipo a 2500W).

---

## 2. Inventario de Subsistemas y Directivas Clave

1. **Gobernanza de Elevadores y Soft-Contingencia (`app/governance/elevator_budget.py`)**:
   - *Ventana de reposo global*: `settle_window_seconds = 180s` entre cambios de preset.
   - *Ventana de reposo post-incidente*: `incident_quiet_window_s = 300s` tras reinicios inesperados en un grupo.
   - *Presupuestos dinámicos*: 5000W pico (2500W/minero), 5400W valle (2700W/minero).
   - *Envolvente Térmica Solar*: Techo a 2500W si $T_{chip} \ge 82.0^\circ\text{C}$ durante la franja solar diurna.
   - *Headroom Chilling*: Modulación a 100% PWM previa al ascenso de 2500W a 2700W para enfriar a $\le 78.5^\circ\text{C}$.

2. **Gobernador de Ventiladores (`app/governance/fan_governor.py`)**:
   - *Lazo cerrado de temperatura*: Target $81.0^\circ\text{C} - 82.5^\circ\text{C}$ en chips BM1362.
   - *Pisos físicos de ventilador (`resolve_power_fan_floor`)*: 2700W -> $\ge 70\%$ PWM; 2500W -> $\ge 60\%$ PWM.
   - *Directiva `ACTION_RECOVERY_MAX_COOLING`*: Si `current_power_w < (target_power_w - 120W)`, fuerza incondicionalmente 100% PWM (~6000 RPM) para asistir en el arranque y prevenir colapso térmico.

3. **Agente Autónomo de Gobernanza de Planta FGA (`app/governance/facility_agent.py`)**:
   - Modelo físico de resistencia térmica de silicio ($R_{th} = (T_{chip} - T_{inlet}) / P$).
   - Clasificación en cohortes (`COOL`, `STANDARD`, `HOT`).
   - Asignación asimétrica de potencia y persistencia en tabla SQLite `facility_agent_knowledge`.

4. **Cliente VNish REST y Conectores de Firmware (`app/vnish/client.py`)**:
   - `safe_get_overclock_settings` / `set_miner_preset`: escribe `/config/cgminer.conf` vía `/api/v1/settings`.
   - `auto_restart_mining = False` por defecto para evitar bucles de flapping.
   - `check_miner_settings_health`: detecta HTTP 500 (campos Serde duplicados) y fallo 1002 (Spec 080).
   - `safe_restart_mining`: `POST /api/v1/mining/restart` para recargar proceso cgminer sin reiniciar Linux.

5. **Monitor Central y Máquina de Estados (`app/miner_monitor.py`)**:
   - Ciclo continuo de adquisición de telemetría (API 4028 cada 30s, REST VNish cada 300s).
   - Máquina de 5 estados: `OK`, `LOW`, `OFFLINE`, `HASHBOARD`, `INITIALIZING`.
   - `evaluate_auto_restart_candidate`: evalúa si reiniciar minado ante estados degradados.
   - Cola de Telegram y Centro de Ayuda interactivo con límite estricto de $\le 32$ columnas para UI móvil.

---

## 3. Puntos de Fricción y Tensiones Detectadas en la Auditoría

### ⚡ Tensión 1: El Bloqueo del "Preset No Aplicado" (`restart_required: True`)
- **Síntoma**: S19JPRO-24 tiene configurado `2700W` en `/config/cgminer.conf`, pero corre a `2500W` (2498W en cadenas, 482 MHz, 92.4 TH/s).
- **Mecanismo**: VNish actualiza el archivo JSON al recibir el POST a `/api/v1/settings`, pero **no conmuta las frecuencias de los chips ni los voltajes** hasta que cgminer se reinicia. Levanta la bandera `restart_required = True`.
- **Fricción**:
  * `safe_set_miner_preset` tiene `auto_restart_mining = False` por diseño (para que el balanceador de presets no reinicie cgminer en caliente durante ajustes rutinarios).
  * El monitor central en `miner_monitor.py` (L6966-6974) **solo** evalúa reiniciar si `is_hash_degraded` es `True` (`rate_ths < 60 TH/s` o placas caídas). Como M24 está hasheando perfectamente a 92.4 TH/s, el monitor nunca lo reinicia.
  * Resultado: El equipo queda atrapado indefinidamente en 2500W.

### ❄️ Tensión 2: La Trampa de `RECOVERY_MAX_COOLING` en el Fan Governor
- **Síntoma**: Los ventiladores de S19JPRO-24 están clavados al 100% PWM (~6000 RPM), generando ruido ensordecedor y consumiendo ~180W adicionales de fan, a pesar de que los chips están súper fríos (57°C - 77°C).
- **Mecanismo**: El Fan Governor compara `current_power_w` (2498W) con `target_power_w` (2700W). Al ver que `2498W < (2700W - 120W = 2580W)`, asume que el minero está en rampa de arranque y fuerza incondicionalmente `ACTION_RECOVERY_MAX_COOLING` (100% PWM).
- **Fricción**: Como el minero no puede ascender a 2700W sin un reinicio de minado, la condición `current_power_w < 2580W` es permanente. El Fan Governor queda congelado en 100% PWM para siempre.

### 🔌 Tensión 3: Asimetría de Estabilidad Eléctrica (Elevador 1 vs Elevador 2)
- **Datos Empíricos**:
  * Elevador 1 (M23 y M24): 49h / 33h con 0 reinicios, 0 micro-cortes, 0 errores de hardware.
  * Elevador 2 (M25 y M26): 3 micro-eventos el 2026-09-30 (reinicios simultáneos y caída de fase detectada a las 21:37 hs).
- **Hipótesis del Operador**: Los relés o el transformador del Elevador 2 presentan rebote o fatiga bajo cargas altas continuas (~5400W).
- **Fricción**: Si M24 pasa a 2700W, el Elevador 1 alcanzará ~5400W (M23 2700W + M24 2700W). ¿Está el Elevador 1 preparado para sostener 5400W continuos sin inducir los mismos problemas que el Elevador 2? ¿Debería existir una estrategia de balance dinámico (ej. alternar cargas o escalonar con mayor margen)?

### 📜 Tensión 4: Prevalencia de Directivas y Jerarquía de Decisión
- Actualmente coexisten múltiples entidades que influyen en presets y potencia:
  1. `app/config.json` (`target_power_w`, `max_hardware_preset`).
  2. `elevator_budget.py` (`evaluate_soft_contingency_schedule`, `evaluate_solar_thermal_envelope`, `StaggeredDecision`).
  3. `facility_agent.py` (`facility_agent_knowledge`, cohortes térmicas).
  4. `fan_governor.py` (`ACTION_RECOVERY_MAX_COOLING`, `pwr_floor`, lazo cerrado de $T_{chip}$).
  5. VNish interno (`preset_switcher`, `rise_temp`, `decrease_temp: 84°C`).
- Es imperativo auditar cómo interactúan estas directivas cuando:
  * Hay una bandera `restart_required` activa.
  * Entra una ventana solar o un horario pico.
  * El operador ajusta manualmente un preset desde Telegram.

---

## 4. Invariantes Críticos y Reglas de Seguridad (No Negociables)

1. **Protección de Producción**: NUNCA ejecutar comandos destructivos o reinicios no solicitados sobre la flota sin validación previa.
2. **Formato Móvil Telegram**: Ancho máximo $\le 32$ columnas en todos los reportes, tarjetas y mensajes de Telegram.
3. **No-Spam y Rate Limiting**: Fails-before-alert = 3, cooldown de alertas = 900s, token de confirmación de 2 pasos en callbacks interactivos.
4. **Protección de Secretos**: `app/config.json` y `app/state.json` NUNCA deben commitearse ni exponer credenciales en logs o markdown.
5. **Calidad de Código**: 100% de la suite de pruebas (1429+ tests) debe pasar sin regresiones.
