# Feature Specification: Spec 057 - Intervention Governance & Adaptive Elevator Contingency

**Feature Directory**: `specs/057-intervention-governance-contingency`  
**Created**: 2026-09-15  
**Status**: Ready for Planning  
**Author**: Gemini 3.8 Flash High  
**RFC Reference**: `docs/speckit/ROADMAP.md` (Release V4.2)  
**Parent Specs**: `specs/043-telegram-interactive-command-center`, `specs/044-silent-mode-thermal-guard`, `specs/040-dynamic-voltage-presets`, `specs/056-two-tier-mining-recovery`

---

## 1. Executive Summary & Problem Statement

En una granja minera ASIC supervisada por Miner Alerts, coexisten dos requerimientos operativos críticos para garantizar estabilidad sin fricción humana:

### 1.1 Gobernanza de Intervenciones y Modo "Vnish Libre" (Solo Lectura)
Actualmente, Miner Alerts ejecuta diversos actuadores mutantes automáticos sobre los mineros:
- **Recuperación en Dos Niveles (Spec 056 / Spec 055 / Spec 008)**: Auto-Restart de software (Nivel 1) y Auto-Reboot de hardware (Nivel 2).
- **Gobernador de Ventiladores (Spec 039 / Spec 042)**: Modulación continua de PWM hacia 82.0°C.
- **Balanceador de Presets y Voltaje (Spec 040)**: Desescalado de potencia por reinicios o térmicas.

Cuando el operador necesita realizar pruebas de overclock manuales en la interfaz web de Vnish, ensayar perfiles personalizados o simplemente dejar que el firmware gestione libremente los ventiladores y el autotuning sin interferencias del bot, **no existía un interruptor maestro táctil en Telegram**.  
**Requerimiento Clave**: Crear un menú de **"Gobernanza de Intervenciones"** en Telegram `/menu` que permita con 1 toque desactivar todas las intervenciones sobre los mineros (dejando a Vnish 100% libre) o modularlas selectivamente (apagar solo reinicios, apagar solo fans, o apagar solo presets), con un temporizador de seguridad de reactivación automática (30m, 1h, 2h, 4h, indef) para prevenir descuidos. **La telemetría, el guardado en SQLite, el watchdog y las alertas de Telegram continúan al 100% activas**.

### 1.2 Contingencia Eléctrica Asimétrica y Dinámica por Elevador (Sin Asumir 2700W)
En días hábiles durante las primeras horas de la mañana (05:30 a 11:30), la actividad industrial y comercial de la zona genera oscilaciones y caídas bruscas de tensión (*sags*) en la red eléctrica de entrada hacia los elevadores de tensión.
- **Naturaleza del Incidente**: El análisis forense de telemetría de ayer (14/09) demostró que los mineros hashean de forma perfecta a 101 TH/s hasta el milisegundo exacto en que la fuente APW12 corta por subtensión ante la conmutación de pasos del elevador bajo carga máxima.
- **Ausencia de Perturbación en Días Estables**: Hoy (15/09), la red amaneció estable y hubo **0 reinicios**. Forzar una contingencia horaria ciega todos los días a las 05:30 penalizaría la producción injustificadamente.
- **Referencia Dinámica Basada en el Estado Actual**: No todos los mineros están a 2700W (ej. Minero 23 está a 2500W). La reducción no debe asumir 2700W como punto de partida, sino **el preset activo actual (`current_preset`) de cada máquina**.
- **Enfoque Asimétrico por Minero Canario / Sensible**: En cada elevador existe un minero más sensible a las perturbaciones de tensión (Minero 24 en Elevador 1 por sensibilidad de bus I2C; Minero 25 en Elevador 2). Ante el primer reinicio en un elevador, solo el minero sensible desciende 1 escalón de potencia (ej. de su estado actual de 2700W a 2500W, o de 2500W a 2300W), aliviando inmediatamente la corriente de ese elevador sin castigar al minero robusto.
- **Prueba en los Límites**: Si el minero sensible vuelve a reiniciar en su nivel reducido, desciende al siguiente peldaño. Si el minero robusto reinicia, también reduce su potencia.

---

## 2. User Scenarios & Testing

### User Story 1 - Control Táctil de Intervenciones en Telegram (Priority: P1)
Como operador de la granja,
quiero pulsar un botón en el menú de Telegram para desactivar todas las intervenciones sobre los mineros y dejar a Vnish operar libremente,
para realizar ajustes de firmware sin que el monitor altere mis configuraciones ni dispare reinicios automáticos.

**Acceptance Scenarios**:
1. **Given** el bot en `/menu`, **When** el usuario observa el panel principal, **Then** ve un botón táctil `[ 🛡️ Intervenciones: 🟢 ACTIVAS ]` (o estado correspondiente).
2. **Given** que el usuario pulsa `[ 🛡️ Intervenciones ]`, **When** el mensaje se edita in-place, **Then** se presenta el submenú con el desglose de actuadores (`Reinicios`, `Fans`, `Presets`) y opciones de acción rápida.
3. **Given** que el usuario selecciona `[ 🔴 Desactivar TODAS (Vnish Libre) ]`, **When** se procesa la acción, **Then** el monitor desactiva en memoria y en `state.json` los despachos de Auto-Restart L1, Auto-Reboot L2, Fan Governor y Preset Balancer, y notifica la confirmación.
4. **Given** que las intervenciones están desactivadas, **When** un minero cae a 0.0 TH/s o `STATE_LOW`, **Then** el monitor registra el evento en SQLite y envía la alerta diagnóstica a Telegram, pero **NO despacha ningún reinicio ni comando HTTP POST mutante**.

### User Story 2 - Selectores Granulares y Temporizador de Reactivación Segura (Priority: P1)
Como operador responsable,
quiero poder desactivar únicamente los reinicios automáticos o únicamente el control de ventiladores, o fijar una desactivación por 1 o 2 horas,
para trabajar tranquilo sin riesgo de olvidar reactivar las protecciones indefinidamente.

**Acceptance Scenarios**:
1. **Given** el submenú de intervenciones, **When** el usuario pulsa `[ 🔄 Reinicios: ON/OFF ]`, **Then** conmuta exclusivamente la política de reinicios (L1 y L2) manteniendo el Fan Governor activo.
2. **Given** el submenú de intervenciones, **When** el usuario pulsa `[ 🌪️ Fans Gov: ON/OFF ]`, **Then** conmuta el gobernador de ventiladores, permitiendo que Vnish vuelva a su modo automático (`auto`) de fábrica.
3. **Given** que el usuario selecciona `[ ⏱️ Desactivar x Tiempo ]` (30m, 1h, 2h, 4h), **When** el temporizador expira, **Then** el monitor reactiva automáticamente todas las intervenciones y envía un mensaje proactivo a Telegram: `🛡️ INTERVENCIONES REACTIVADAS AUTOMÁTICAMENTE: Finalizó la ventana temporal de suspensión.`

### User Story 3 - Contingencia Eléctrica Asimétrica Relativa al Estado Actual (Priority: P1)
Como técnico de la instalación eléctrica,
quiero que ante el primer reinicio matutino de un elevador, solo el minero más sensible de ese elevador reduzca 1 nivel de potencia respecto a su estado actual,
para amortiguar la fluctuación eléctrica sin degradar innecesariamente al resto de la flota.

**Acceptance Scenarios**:
1. **Given** los mineros en régimen nominal (ej. Minero 23 @ 2500W, Minero 24 @ 2700W en `elevator_1`), **When** ocurre un reinicio inesperado en Minero 24 (el canario del grupo), **Then** el sistema NO asume 2700W para todos, sino que reduce exclusivamente al Minero 24 un peldaño en el ladder (`2700W -> 2500W`), mientras el Minero 23 permanece en su estado actual (2500W).
2. **Given** la reducción aplicada, **When** se registra en Telegram, **Then** emite una notificación clara: `⚡ CONTINGENCIA ASIMÉTRICA [elevator_1]: Reinicio en minero canario S19JPRO-24. Reduciendo de 2700W a 2500W. S19JPRO-23 se mantiene en 2500W.`
3. **Given** un día sin fluctuaciones de red (como hoy), **When** no ocurren reinicios matutinos, **Then** el sistema mantiene la potencia nominal al 100% sin entrar en contingencia.

### User Story 4 - Prueba en los Límites y Recuperación Gradual (Step-Up Soak) (Priority: P2)
Como operador que busca máxima resiliencia,
quiero que si el minero sensible vuelve a reiniciar en su potencia reducida el sistema explore el siguiente nivel hacia abajo, y que restaure la potencia cuando la red se calme,
para probar los límites reales de tolerancia de los elevadores sin intervención humana continua.

**Acceptance Scenarios**:
1. **Given** que el minero sensible está en 2500W y sufre un segundo reinicio en la ventana de contingencia, **When** se evalúa el evento, **Then** desescala al siguiente nivel (`2500W -> 2300W`).
2. **Given** que el minero robusto (ej. Minero 23 o Minero 26) sufre un reinicio bajo perturbación severa, **When** se evalúa el evento, **Then** también desciende un nivel respecto a su estado actual.
3. **Given** un período de estabilidad sostenida (ej. 2 horas continuas sin reinicios o transcurrido el mediodía), **When** el orquestador evalúa la flota, **Then** ejecuta una rampa suave de recuperación (Step-Up) restaurando los presets nominales de forma escalonada.

---

## 3. Data Contracts & Architecture Alignment

### 3.1 Modelo de Datos en Memoria y Persistencia (`MinerState` / `InterventionState`)
```python
@dataclass
class InterventionGovernance:
    master_enabled: bool = True          # False = Modo "Vnish Libre" total
    reboots_enabled: bool = True         # Control de Auto-Restart L1 y Auto-Reboot L2
    governor_enabled: bool = True        # Control dinámico PWM Fan Governor
    contingency_enabled: bool = True     # Contingencia asimétrica adaptativa de potencia
    expires_at_ts: Optional[float] = None # Timestamp epoch para reactivación automática
    disabled_reason: str = ""            # "manual_indefinite", "manual_timer_1h", etc.
```

### 3.2 Configuración Declarativa en `config.json`
```json
{
  "intervention_governance": {
    "enabled": true,
    "default_timer_options_minutes": [30, 60, 120, 240]
  },
  "adaptive_contingency": {
    "enabled": true,
    "window_start": "05:00",
    "window_end": "12:00",
    "days": ["mon", "tue", "wed", "thu", "fri"],
    "soak_stability_hours": 2.0,
    "canary_miners": {
      "elevator_1": "S19JPRO-24",
      "elevator_2": "S19JPRO-25"
    },
    "step_down_margin_w": 200,
    "min_preset_floor": "1900W"
  }
}
```

### 3.3 Preservación Constitucional
- **Principio I (Seguridad)**: Las acciones mutantes están bloqueadas cuando `master_enabled=False`.
- **Principio II (Telemetría Intacta)**: El ciclo de polling de la API 4028, SQLite, Watchdog de vida y alertas a Telegram no se ven afectados por la desactivación de intervenciones.
- **Principio III (Control Operativo Telegram)**: Todas las transiciones de botones táctiles responden en < 1s mediante `answerCallbackQuery` y edición in-place.
