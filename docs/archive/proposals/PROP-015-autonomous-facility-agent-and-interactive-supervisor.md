# PROP-015: Agente Autónomo de Gobernanza de Planta y Supervisor Conversacional Interactivo

- **Fecha de Creación**: 2026-09-19 17:25 hs
- **Autor**: Antigravity Engineering (Gemini 3.8 Flash High)
- **Estado**: Propuesta de Arquitectura y Especificación Técnica
- **Componentes Afectados**: [app/miner_monitor.py](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py), [app/governance/elevator_budget.py](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/elevator_budget.py), [app/telegram/dispatcher.py](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/telegram/dispatcher.py), [data/miner_alerts.db](file:///F:/02-ASIC%20-%20mineros/miner-alerts/data/miner_alerts.db)
- **Marco de Referencia**: [PROP-012 (Gobernanza de Elevador)](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/proposals/PROP-012-staggered-elevator-governance-and-soft-contingency.md), [PROP-013 (Watchdog Anti-Stall y Envolvente Solar)](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/proposals/PROP-013-elevator-noise-autotune-stall-and-thermal-protection.md), [PROP-014 (Roadmap de Máxima Potencia)](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/proposals/PROP-014-maximum-power-and-asymmetric-combination-roadmap.md)

---

## 1. Visión y Definición de Agente

El usuario plantea el objetivo estratégico del sistema:
> *"Crear un agente dentro de la misma app que pueda tomar las decisiones correctas y automatizarlo... que con toda la recolección y refinamiento de datos el sistema pueda llegar a ser 100% seguro e independiente. No me refiero a un LLM vinculado 24/7 gastando tokens, sino a un algoritmo robusto, que quizás sea también chatbot o sí crear un LLM, sin alucinarnos."*

Esta definición coincide con la mejor práctica de ingeniería de sistemas autónomos críticos (control aeroespacial, plantas de energía y centros de cómputo de alta densidad):

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                   AGENTE AUTÓNOMO DE GOBERNANZA DE PLANTA (FGA)                 │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   ┌──────────────────────────────────────────────────────────────────────────┐   │
│   │ CAPA 1: MOTOR DETERMINÍSTICO 24/7 (Zero Token Cost / Sub-milisequencial) │   │
│   │ • Algoritmo de control en bucle cerrado (Closed-Loop Governor).          │   │
│   │ • Evaluación continua de invariantes de seguridad (P, I, V, T, Duty).    │   │
│   │ • Transiciones escalonadas (180s settle, 300s quiet) anti-ruido L di/dt. │   │
│   │ • Optimización de potencia autónoma (busca max TH/s sin superar 84°C).   │   │
│   └─────────────────────────────────────┬────────────────────────────────────┘   │
│                                         │                                        │
│   ┌─────────────────────────────────────▼────────────────────────────────────┐   │
│   │ CAPA 2: MEMORIA EMPÍRICA Y APRENDIZAJE (data/miner_alerts.db)            │   │
│   │ • Registro continuo de telemetría de 30s (telemetry_samples).            │   │
│   │ • Perfil de transferencia térmica de silicio por minero (Rth = ΔT / P).  │   │
│   │ • Historial de autotune, límites de PLL comprobados y estabilidad.       │   │
│   └─────────────────────────────────────┬────────────────────────────────────┘   │
│                                         │                                        │
│   ┌─────────────────────────────────────▼────────────────────────────────────┐   │
│   │ CAPA 3: INTERFAZ CONVERSACIONAL Y AUDITORÍA ON-DEMAND (Telegram Bot)     │   │
│   │ • Respuestas inmediatas y determinísticas (/agent, /why, /audit, /plan). │   │
│   │ • Síntesis inteligente on-demand (activada SOLO cuando el usuario habla)│   │
│   │   alimentada 100% con hechos de SQLite: CERO ALUCINACIONES.              │   │
│   └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Los Tres Pilares de la Arquitectura

### Pilar 1: El Motor Autónomo Determinístico (24/7 Zero Cost)
* **Principio de Diseño**: Las decisiones críticas de voltaje, frecuencia, relés y térmicas **NUNCA** deben depender de una llamada de red a un LLM externo que pueda demorar 5 segundos, fallar por timeout o alucinar un valor fuera de rango.
* **Operación**: Se ejecuta cada 30 segundos en el bucle principal de [app/miner_monitor.py](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py).
* **Función Objetivo de Optimización**:
  $$\max \sum_{i=1}^{4} \text{Hashrate}_i(\text{TH/s})$$
  **Sujeta a los Invariantes Físicos**:
  1. $\forall i, \text{TempChip}_i < 84.0^\circ\text{C}$ (Disparo preventivo a 84.0°C desescala inmediatamente al preset inferior).
  2. $\forall i, \text{FanDuty}_i < 92.0\%$ (Margen de disipación para absorber fluctuaciones ambiente).
  3. $P_{\text{Elevador 1}} \le 5400\text{W}$ y $P_{\text{Elevador 2}} \le 5400\text{W}$ (Límite magnético continuo de autotransformadores).
  4. $I_{\text{Acometida}} \le 50.0\text{ A}$ (Límite térmico de conductores de bajada compartida).
  5. $\Delta t_{\text{transición}} \ge 180\text{ s}$ (Ventana de reposo eléctrico entre escalones de potencia).
  6. $\Delta t_{\text{post-incidente}} \ge 300\text{ s}$ (Reposo obligatorio tras reinicios o microcortes).

### Pilar 2: La Memoria Empírica de Silicio (`data/miner_alerts.db`)
El agente no toma decisiones "a ciegas", sino basándose en la experiencia acumulada del laboratorio:
* **Perfil de Silicio de Cada Minero**:
  * **S19JPRO-23**: Silicio A+. Tolera 2500W en siesta (81°C) y 2700W con clima fresco ($<22^\circ\text{C}$).
  * **S19JPRO-24**: Silicio A. Rompe los 100 TH/s a 2700W, pero su cooler satura a 6000 RPM en días calurosos. El agente sabe que a $>24^\circ\text{C}$ ambiente debe operar a 2500W (96 TH/s, 78°C).
  * **S19JPRO-25**: Silicio B. Presenta fallo de PLL en autotune a 2700W. El agente fija un cerrojo en 2500W para garantizar 94 TH/s estables sin colapsos.
  * **S19JPRO-26**: Silicio A++. Opera a 2700W con disipación sobresaliente (79°C chips, 101.8 TH/s).
* **Curvas Térmicas Dinámicas**: A medida que el agente recopila muestras, calcula la inercia térmica de la sala, anticipándose al pico de radiación solar sin necesidad de timers rígidos.

### Pilar 3: El Asistente Conversacional (Chatbot Factual en Telegram)
* **Principio de Cero Alucinación**: El chatbot no "inventa" respuestas ni adivina estados. Consulta directamente el estado de memoria del supervisor y la base SQLite.
* **Comandos Nativos del Agente**:
  * `/agent`: Muestra el estado del agente autónomo, la función objetivo actual, la combinación en curso (ej: C1), el hashrate total y el margen de seguridad de acometida.
  * `/why [minero]`: Explica en lenguaje claro y técnico **por qué** el agente tomó la última decisión (ej: *"S19JPRO-24 se mantiene en 2500W porque sus chips tocaron 84.0°C a las 17:21 hs. El agente aguarda chips < 80.0°C para reintentar 2700W"*).
  * `/strategy [conservadora | agresiva | laboratorio]`: Permite al usuario cambiar el perfil de aversión al riesgo del agente con 1 botón.
* **Capa Opcional de Síntesis LLM On-Demand**:
  * Cuando el usuario escribe una consulta en lenguaje natural en Telegram (ej: *"¿por qué bajó el hashrate a las 3 de la tarde?"*):
  * El sistema extrae los registros exactos de SQLite de esa franja horaria (eventos de reinicio, telemetría, alertas).
  * Construye un prompt compacto con **únicamente datos reales**:
    ```
    Eres el Agente Autónomo de Gobernanza de Miner Alerts.
    Telemetría real de la base de datos:
    - 15:00 hs: Temp máx chip 84°C, Fan duty 100%.
    - 15:02 hs: Desescalada preventiva a 2500W aplicada a S19JPRO-24.
    Responde al operador en 2 líneas de forma técnica y concisa.
    ```
  * Realiza una sola llamada API al modelo ligero (`Gemini 3.8 Flash High` o similar). Costo: fracción de centavo por consulta manual, 0 costo en reposo, y 100% libre de alucinaciones.

---

## 3. Plan de Implementación Progresiva

| Fase | Alcance | Estado Técnico |
| :---: | :--- | :---: |
| **Fase 1** | **Invariantes de Gobernanza y Guardias Físicas**: Gate 0 (margen térmico), Watchdog anti-autotune stall, Reposo de elevador 300s, Desescalada por sobrecalentamiento individual. | **100% COMPLETADA (En Producción)** |
| **Fase 2** | **Optimizador Autónomo de Combinaciones**: El agente explora autónomamente presets intermedios (ej: 2600W), prueba transiciones escalonadas y evalúa el delta de TH/s vs temperatura en SQLite. | **En Diseño (PROP-014 / PROP-015)** |
| **Fase 3** | **Interfaz Conversacional en Telegram**: Implementar el comando `/agent` y `/why` en [app/telegram/commands/](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/telegram/commands/) para que el operador pueda interactuar en tiempo real con las decisiones del agente. | **Siguiente Paso Operativo** |
| **Fase 4** | **Síntesis Inteligente On-Demand**: Hook opcional para preguntas abiertas en Telegram mediante API Gemini Flash sobre el historial factual de SQLite. | **Fase Final** |

---

## 4. Conclusión

Este enfoque satisface integralmente la visión del usuario:
1. **Robusto y Profesional**: El sistema opera como un PLC industrial de misión crítica (seguro, determinístico, sin fallas por desconexión de internet).
2. **Económicamente Inteligente**: No gasta tokens en bucle 24/7.
3. **Completamente Independiente**: Puede gestionar contingencias, caídas de relé, picos solares y autotune stalls de forma 100% autónoma.
4. **Transparente y Comunicativo**: Responde con exactitud matemática a cualquier pregunta del operador a través de Telegram.
