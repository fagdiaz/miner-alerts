# Spec 079: Agente Autónomo de Gobernanza de Planta (Facility Governance Agent - FGA) y Optimizador Asimétrico de Potencia

## 1. Contexto y Objetivos

### 1.1 El Problema Operativo y la Evidencia Empírica en Producción
A lo largo de la operación continua de la flota Antminer S19j Pro (4 mineros distribuidos en 2 elevadores de tensión), la telemetría en vivo ha demostrado de manera inequívoca:
1. **Divergencia Térmica Fuerte e Invariable entre Elevadores**:
   - **Elevador 2 (S19JPRO-25 y S19JPRO-26)**: Excelente ventilación y menor resistencia térmica ($R_{th} \approx 0.019^\circ\text{C/W}$). A 2500W operan a **77.0°C**, y a 2700W se estabilizan en **75.0°C - 81.0°C** con ventiladores en 70%-90%.
   - **Elevador 1 (S19JPRO-23 y S19JPRO-24)**: Mayor resistencia térmica ($R_{th} \approx 0.024^\circ\text{C/W}$) debido a recirculación local o posición en rack. A 2500W operan a **85.0°C - 86.0°C** con ventiladores al 100%. Intentar correr ambos a 2700W satura el disipador térmico (`status=SATURATED`), disparando picos térmicos o autotune stalls.
2. **Limitación de las Políticas Simétricas Rígidas**:
   - Imponer un preset uniforme a toda la flota (por ejemplo, "todos a 2700W" o "todos a 2500W") desperdicia hashrate valioso en las máquinas frías (Elevador 2) o sobrecalienta las máquinas calientes (Elevador 1).
3. **Requerimiento del Operador de un Agente Autónomo**:
   - El operador solicita un **Agente interno** dentro de la aplicación que tome decisiones correctas de forma automatizada, profesional e independiente, basado en refinamiento continuo de datos de telemetría.
   - **Definición Constitucional**: No un LLM conectado 24/7 consumiendo tokens de API innecesariamente, sino un **algoritmo determinístico robusto de lazo cerrado**, complementado con una interfaz conversacional/supervisora en Telegram (`/agent`, `/strategy`, `/why`) capaz de razonar y explicar el porqué de cada decisión con datos empíricos de silicio.

---

## 2. Arquitectura del Agente Autónomo de Planta (FGA)

El FGA opera bajo un modelo desacoplado de 3 capas:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   CAPA 3: INTERFAZ CONVERSACIONAL TELEGRAM                  │
│       Comandos: /agent (Dashboard) | /why <miner> | /strategy <mode>       │
│               Generación de diagnósticos e insights factuales               │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Lee estado y explicaciones
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                  CAPA 2: MEMORIA EMPÍRICA Y MODELO DE SILICIO               │
│       Tabla SQLite 'facility_agent_knowledge' + Estado en Memoria           │
│   • Rth = ΔT / P por minero           • Hashrate real sostenido             │
│   • Eficiencia J/TH por preset        • Historial de estabilidad eléctrica  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Consulta métricas aprendidas
┌──────────────────────────────────────▼──────────────────────────────────────┐
│               CAPA 1: MOTOR DETERMINÍSTICO DE GOBERNANZA 24/7               │
│  app/governance/facility_agent.py (Zero Token Cost, Invariantes P0)         │
│   • Balanceador Asimétrico Inter-Elevador (C4/C5/C6)                        │
│   • Headroom Chilling coordinado (100% PWM pre-subida)                      │
│   • Cuarentena de fallas y cerrojo de preset anti-oscilación               │
│   • Límites duros: P <= 5400W/elevador, I <= 50A acometida, T < 82.5°C      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Especificación Detallada de Módulos

### 3.1 Capa 1: Motor Determinístico (`app/governance/facility_agent.py`)
- **Cálculo de Resistencia Térmica ($R_{th}$)**:
  $$R_{th} = \frac{T_{chip} - T_{inlet}}{P_{active}} \quad [^\circ\text{C/W}]$$
  Permite predecir la temperatura resultante $T_{pred}$ antes de autorizar un escalamiento:
  $$T_{pred} = T_{inlet} + R_{th} \cdot P_{target}$$
  Si $T_{pred} > 82.5^\circ\text{C}$, el escalamiento queda **bloqueado por física térmica**, impidiendo disparar protecciones.
- **Optimizador Asimétrico de Potencia**:
  - Clasifica a los mineros en dos cohortes según su eficiencia térmica y estabilidad:
    - *Clase Fría/Robusta*: Mineros 25 y 26 (Candidatos primarios para 2700W).
    - *Clase Cálida/Sensible*: Mineros 23 y 24 (Candidatos primarios para 2300W-2500W).
  - Maximiza la función objetivo de Hashrate Global:
    $$\max \sum_{i=1}^4 H_i(P_i) \quad \text{sujeto a:} \begin{cases} P_{elevador\_1} \le 5400\text{W} \\ P_{elevador\_2} \le 5400\text{W} \\ T_{chip\_i} \le 82.5^\circ\text{C} \\ \Delta t_{inter\_miner} \ge 180\text{s} \end{cases}$$

### 3.2 Capa 2: Persistencia y Memoria en SQLite (`facility_agent_knowledge`)
- Tabla `facility_agent_knowledge` en `data/miner_alerts.db`:
  - `miner_id` (TEXT PRIMARY KEY)
  - `thermal_resistance_c_per_w` (REAL)
  - `best_preset` (TEXT)
  - `max_safe_preset` (TEXT)
  - `eff_j_per_th` (REAL)
  - `last_recalibrated_ts` (REAL)
  - `incident_count_24h` (INTEGER)

### 3.3 Capa 3: Comandos de Telegram
- `/agent`: Resumen ejecutivo del Agente (estrategia activa, potencia total, hashrate total, eficiencia global J/TH, asignación por elevador y estado de las 4 máquinas).
- `/why <minero>`: Explicación transparente con telemetría en tiempo real:
  *Ejemplo*: "S19JPRO-23 se mantiene en 2500W porque su chip opera a 85.0°C ($R_{th} = 0.024^\circ\text{C/W}$). Escalar a 2700W predeciría una temperatura de 89.8°C, superando el límite seguro de 82.5°C."
- `/strategy [balanced|max_power|efficiency|cool_quiet]`:
  - `balanced` (Default): 2700W en máquinas frías, 2500W en máquinas cálidas (~385 TH/s, ~10.200W).
  - `max_power`: Explora 2700W en todas las máquinas cuando $T_{inlet} < 20^\circ\text{C}$ de noche.
  - `efficiency`: Optimiza J/TH en 2300W-2500W.
  - `cool_quiet`: Techo 2300W y ventiladores limitados.

---

## 4. Requisitos de Seguridad e Invariantes Constitucionales

1. **Invariante P0 - Respeto al Presupuesto Eléctrico**: Ningún elevador debe exceder 5400W en ningún momento.
2. **Invariante P0 - Ventana de Asentamiento Escalonada**: Mínimo 180 segundos entre cambios de preset de mineros distintos para evitar ruidos parásitos en la línea.
3. **Invariante P0 - Thermal Tripwire**: Todo minero con chip $\ge 84.0^\circ\text{C}$ en 2700W es desescalado de inmediato a 2500W por la soft-contingencia.
4. **Zero-Token Autonomous Loop**: El lazo de control corre en CPU local sin latencias de red ni consumo de tokens de LLM. La síntesis en lenguaje natural solo se activa bajo demanda cuando el usuario escribe `/agent` o `/why`.

---

## 5. Criterios de Aceptación (Definition of Done)
1. Módulo `app/governance/facility_agent.py` implementado con cobertura de pruebas unitarias $\ge 95\%$.
2. Migración/esquema SQLite `facility_agent_knowledge` integrado y persistente.
3. Comandos `/agent`, `/why` y `/strategy` registrados y operativos en Telegram.
4. Suite de pruebas completa en verde ($\ge 1335$ tests PASS, 0 fallos, 0 regresiones).
5. Despliegue en el servicio Windows `MinerAlerts` con evidencia en `evidence.md`.
