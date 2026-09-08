# Spec 040: Dynamic Power & Preset Balancer for Voltage Sensitivity

## Estado y Metadatos
- **ID**: `040-dynamic-voltage-presets`
- **Prioridad**: P1 (Confiabilidad Eléctrica, Prevención de Caídas en Cascada y Optimización Neta de Hashrate)
- **Estado**: PROPUESTA FORMAL (Fase de Especificación y Diseño)
- **Fecha**: 2026-09-08
- **Autor**: Antigravity (Gemini 3.8 Flash High - Pair Programming con Operador)
- **Dependencias**: Specs 020 (State Machine), 035 (`app/fan_health.py`), 037 (`app/vnish_presets.py`), 038 (V3 Core), 039 (Vnish REST Client & Fan Governor).

---

## 1. Contexto Operativo y Problema Raíz

### 1.1 El Problema Eléctrico y Térmico
En la instalación minera del operador:
1. **Sensibilidad Eléctrica Diferencial en Elevadores de Tensión**:
   Los mineros Antminer S19j Pro están alimentados a través de elevadores de tensión / reguladores de línea. Uno de los elevadores presenta una **sensibilidad sustancialmente mayor**: cuando la potencia agregada de los mineros conectados supera cierto umbral o cuando la red externa sufre micro-cortes o subtensiones, el elevador satura, provocando:
   - Caídas bruscas de tensión.
   - Reinicios no programados de las máquinas.
   - Pérdida de cadenas (*hashboards*) o desconexiones repetitivas.
2. **El Elevado Costo Oculto de los Reinicios**:
   Cada reinicio de un Antminer S19j Pro implica:
   - **Downtime significativo**: 5 a 15 minutos con hashrate igual a 0 TH/s mientras carga el sistema operativo, calibra los 3 paneles de chips ASIC, establece conexiones con el pool y converge a la frecuencia de trabajo.
   - **Estrés Térmico y Mecánico**: Transición térmica brusca (los chips caen de 80°C a temperatura ambiente y luego calientan aceleradamente), lo cual desgasta soldaduras y pistas de silicio.
   - **Pico de Corriente de Inrush**: Al arrancar los 4 ventiladores al 100% y alimentar condensadores de la fuente de poder, se produce un pico de corriente que puede desestabilizar aún más el elevador de tensión sensible.
3. **Throttling Forzado por Firmware**:
   Tal como se evidencia en los registros en vivo del monitor:
   ```text
   [COOLING_WARNING] miner=24 status=SATURATED
   [PROFILE_CHANGE_ALERT] miner=24 status=DOWNCLOCKED freq=440.532
   ```
   Cuando un minero opera forzado en un preset alto (ej. 2700W / 2800W) pero sufre saturación de ventilación o inestabilidad eléctrica, el firmware Vnish `preset_switcher` baja automáticamente la frecuencia de 516 MHz a 440 MHz o inferior.

### 1.2 La Necesidad del Operador
El operador requiere un algoritmo inteligente que:
1. Evalúe de forma continua la estabilidad operativa de cada minero y de su grupo eléctrico (elevador).
2. Cuantifique la **relación Costo/Beneficio** entre:
   - **Beneficio**: El hashrate nominal alcanzado al operar en un preset determinado (TH/s).
   - **Costo**: Las horas de hashrate perdidas debido a reinicios, más la penalización por estrés físico y riesgo de caída en cadena.
3. Ajuste de forma autónoma (o sugiera en modo Dry-Run) el **preset de potencia óptimo** de Vnish (ej. 2700W, 2500W, 2300W, 2100W) para que el minero opere al máximo hashrate *sostenible* con la mínima cantidad de reinicios posibles.

---

## 2. Objetivos de la Especificación

1. **Agrupamiento Eléctrico en Configuración**:
   - Permitir asignar cada minero a un elevador o grupo eléctrico en `app/config.json`:
     `"electrical_group": "elevator_sensible"` o `"elevator_estable"`.
2. **Motor Determinista de Optimización Costo/Beneficio (`app/preset_balancer.py`)**:
   - Función matemática que calcule el *Hashrate Efectivo Neto* ($H_{\text{eff}}$):
     $$H_{\text{eff}} = \bar{H} \times (1 - \text{Ratio Downtime}) - \text{Penalización por Reinicio}$$
   - Registro de métricas móviles de estabilidad: reinicios en las últimas 24h, 48h y 72h.
3. **Política de Transición de Presets con Hysteresis**:
   - **Desescalado Rápido ante Inestabilidad (*Step-Down*)**:
     Si un minero sufre $\ge 2$ caídas o reinicios en 24 horas, o si detecta caída en cascada de su elevador, desescalar inmediatamente 1 preset hacia abajo (ej. de 2700W a 2500W).
   - **Escalado Lento y Conservador (*Step-Up*)**:
     Solo si el equipo acumula al menos **72 horas continuas** de operación ininterrumpida sin reinicios y con margen térmico holgado, ensayar subir 1 nivel de preset hasta el límite configurado por el operador (`max_preset`).
4. **Comandos de Telemetría y Control en Telegram**:
   - `/balancer` (o `/power`): Tabla ejecutiva con elevador asignado, preset actual, reinicios 24h/72h, recomendación del algoritmo y modo de operación.
   - `/balancer setmax <miner|all> <preset>`: Límite de seguridad superior definido por el operador.
   - `/balancer on` / `/balancer off`: Habilitación del control automático de presets con modo seguro Dry-Run por defecto.

---

## 3. Historias de Usuario (User Stories)

### US-1: Diagnóstico de Estabilidad por Elevador (Prioridad: P1)
**Como** operador de la granja,  
**Quiero** ver en Telegram qué mineros pertenecen a cada elevador y cuántos reinicios han tenido en 24h y 72h,  
**Para** saber de inmediato si el elevador sensible está sufriendo sobrecarga o inestabilidad.

### US-2: Desescalado Preventivo para Evitar Caídas en Cadena (Prioridad: P1)
**Como** operador,  
**Quiero** que si una máquina se reinicia más de una vez en el día, el monitor baje su preset a un nivel de menor consumo (ej. 2500W a 2300W),  
**Para** aliviar la carga del elevador de tensión sensible y evitar que se apaguen las demás máquinas.

### US-3: Hysteresis de Recuperación a Máximo Hashrate Sostenible (Prioridad: P2)
**Como** operador,  
**Quiero** que las máquinas vuelvan a probar un preset superior únicamente cuando hayan demostrado estabilidad total durante varios días,  
**Para** no entrar en un ciclo vicioso de subir potencia y volver a reiniciar inmediatamente.

---

## 4. Requisitos No Funcionales y Seguridad Constitucional

1. **Cero Comandos Mutantes Inesperados**: El balanceador arrancará siempre con `preset_balancer_dry_run: true`. Registrará en logs y en Telegram la recomendación sin alterar el hardware real hasta que el operador lo autorice.
2. **Respeto Estricto de Techos Fijados por el Usuario**: El algoritmo jamás escalará por encima del preset máximo (`max_preset`) fijado por el operador en la configuración.
3. **Persistencia Transaccional**: El historial de eventos de reinicio se apoya en el almacén duradero de SQLite (`event_store` / `data/miner_alerts.db`) y `state.json`, garantizando supervivencia tras reinicios del monitor.
4. **Independencia de Hilos**: Las consultas a los presets de Vnish se realizan con timeouts acotados y en paralelo sin interferir con el ciclo autoritativo de 30s de la API 4028.
