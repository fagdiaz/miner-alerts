# PROP-016: Motor Autónomo de Autopsia de Incidentes (Post-Mortem Analyzer) y Supervisor Conversacional Q&A en Telegram

- **Fecha de Creación**: 2026-09-25 17:05 hs
- **Autor**: Antigravity Engineering (Gemini 3.8 Flash High)
- **Estado**: Propuesta de Arquitectura y Especificación Técnica (Listo para Auditoría Multi-Agente)
- **Componentes Afectados**: [app/miner_monitor.py](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py), [tools/vnish_log_collector.py](file:///F:/02-ASIC%20-%20mineros/miner-alerts/tools/vnish_log_collector.py), [app/telegram/dispatcher.py](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/telegram/dispatcher.py), [data/miner_alerts.db](file:///F:/02-ASIC%20-%20mineros/miner-alerts/data/miner_alerts.db)
- **Marco de Referencia**: [PROP-015 (Agente Autónomo de Gobernanza)](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/proposals/PROP-015-autonomous-facility-agent-and-interactive-supervisor.md), [Spec 016 (Vnish Log Intelligence)](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/016-vnish-log-intelligence/spec.md), [Spec 079 (Facility Governance Agent)](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/079-facility-governance-agent/spec.md)

---

## 1. Contexto & Evidencia Empírica de Producción

### 1.1 El Problema Operativo Detectado
Durante la operación del 25 de Septiembre de 2026 a las 15:45 hs, la máquina **S19JPRO-25 (`192.168.100.25`)** sufrió un reinicio de su proceso de minado `cgminer`.

- **Comportamiento del Monitor Actual**:
  1. Detectó el síntoma: `[INCIDENT] type=restart_detected miner=25 elapsed=12507->10 classification=unexpected`.
  2. Aplicó guardas pasivas correctas: no bajó potencia a 1800W, no forzó reboots automáticos y esperó 120s de recuperación.
  3. **Brecha de Inteligencia**: El monitor emitió una alerta básica de tiempo transcurrido, pero **no investigó ni comunicó la causa real del reinicio**. El operador tuvo que recurrir manualmente al asistente de desarrollo en el IDE para pedir una auditoría forense profunda.

### 1.2 Hallazgos de la Autopsia Manual
Al conectarse a los registros internos de VNish (`status`) y al kernel Linux (`system` / `dmesg`), se descubrió:
1. **Watchdog de VNish**: Disparó el reinicio por caída de hashrate al 17.4% (`WARN: Low hashrate (cur=17.40% min=30%)` $\rightarrow$ `INFO: Restarting (3 of 3) - Hashrate is too low`).
2. **Causa Raíz Física en Kernel**: La interfaz de red Ethernet sufrió más de 100 caídas de enlace (`libphy: Link is Down / Link is Up`) en el día por un falso contacto o cable dañado. Al caer el enlace repetidamente durante 5 minutos, se cortó la sesión Stratum TCP con el pool, el hashrate colapsó y VNish forzó el reinicio.

### 1.3 Visión y Solicitud del Operador
> *"¿Nuestro sistema no iba a tener un analizador de estas problemáticas y a informarlas? ¿También funcionar como un chatbot con preguntas y respuestas? Porque la causa de ese reinicio te la tuve que preguntar a vos... pero la idea es que sea capaz de encontrarla y notificarme. Me parece bien empezar a cranearlo, auditarlo con distintos agentes e implementarlo sin apuros."*

---

## 2. Arquitectura del Motor Autónomo de Autopsia (`IncidentAutopsyEngine`)

El motor de autopsia opera como un trabajador desacoplado asíncrono en segundo plano (`async / thread pool`) para **no bloquear jamás el bucle de monitoreo de 30 segundos**.

```
                           ┌────────────────────────────────────────┐
                           │      REINICIO O CAÍDA DETECTADA        │
                           │       elapsed: 12507 -> 10s            │
                           └──────────────────┬─────────────────────┘
                                              │
                       ┌──────────────────────▼─────────────────────┐
                       │   Background Incident Autopsy Task         │
                       │   (Timeout estricto: 2.5s, Read-Only)      │
                       └──────────────────────┬─────────────────────┘
                                              │
             ┌────────────────────────────────┼────────────────────────────────┐
             │                                │                                │
  ┌──────────▼──────────┐          ┌──────────▼──────────┐          ┌──────────▼──────────┐
  │  VNish Status Tab   │          │   VNish Miner Tab   │          │  Linux Kernel dmesg │
  │  ws://host/status   │          │   ws://host/miner   │          │  ws://host/system   │
  └──────────┬──────────┘          └──────────┬──────────┘          └──────────┬──────────┘
             │                                │                                │
             └────────────────────────────────┼────────────────────────────────┘
                                              │
                                   ┌──────────▼──────────┐
                                   │  Clasificador FSM   │
                                   │  de Causa Raíz      │
                                   └──────────┬──────────┘
                                              │
        ┌─────────────────────────────────────┴─────────────────────────────────────┐
        │                                                                           │
┌───────▼────────────────────────────┐                     ┌────────────────────────▼───────────────────┐
│     Notificación Enriquecida       │                     │       Persistencia de Hechos               │
│     Telegram en Tiempo Real        │                     │       data/miner_alerts.db                 │
│  "🚨 Reinicio en S19JPRO-25        │                     │  Tabla: incident_assessments               │
│   • Causa: Watchdog Low Hashrate   │                     │  Permite al Chatbot responder              │
│   • Origen: 8 Link Drops en 5m     │                     │  ¿Por qué reinició la 25?                  │
│   • Sugerencia: Revisar cable RJ45"│                     │  sin re-consultar a la máquina             │
└────────────────────────────────────┘                     └────────────────────────────────────────────┘
```

### 2.1 Matriz de Clasificación de Causas Raíz
El clasificador evalúa los patrones estructurados mediante expresiones regulares determinísticas:

| Categoría | Patrón en Logs VNish / Kernel | Severidad | Acción Preventiva Automatizada |
| :--- | :--- | :---: | :--- |
| **RED / ENLACE FÍSICO** | `Link is Down` frecuente en `system` + `Low hashrate (cur < min)` | `WARNING` | Diagnóstico de cable/switch; suspender reboots automáticos destructivos. |
| **SILICIO / ROTURA DE CADENA** | `Chain break detected` / `chip_addr 0xXX` / `Chain faulted` | `CRITICAL` | Disparo de soft-recovery / notificación de revisión de hashboard. |
| **DISPARO TÉRMICO** | `Overheating` / `chip temp >= 85°C` / `Shutdown due to high temp` | `CRITICAL` | Fan Governor al 100%; bloqueo de escalamiento de preset. |
| **FALLA ELÉCTRICA / PSU** | `PSU error` / `voltage check fail` / `Power off` espontáneo | `CRITICAL` | Congelamiento de elevador; protección contra oscilación. |
| **AUTOTUNE / PLL STALL** | `Auto-tune timeout` / `PLL failed` / cgminer freeze sin drop de enlace | `WARNING` | Reajuste de perfil conservador / fijación de cerrojo de preset. |

---

## 3. Arquitectura del Supervisor Conversacional en Telegram (Chatbot Q&A)

Para transformar el bot de Telegram de un despachador rígido de comandos (`/cmd`) en un asistente interactivo capaz de responder consultas directas del operador, se implementa una arquitectura híbrida de **2 niveles**:

```
                       Mensaje de Texto Libre del Operador
                     "¿Por qué se reinició la 25 recién?"
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │  Telegram Text Dispatcher     │
                       └───────────────┬───────────────┘
                                       │
                         ¿Es una intención conocida?
                                       │
                    ┌──────────────────┴──────────────────┐
               [SÍ: 90% Casos]                       [NO: Pregunta Abierta]
                    │                                     │
       ┌────────────▼─────────────┐             ┌─────────▼──────────────┐
       │ Motor RAG Determinístico │             │ Agente LLM Function-   │
       │ (Zero Cost / Offline)    │             │ Calling (Gemini Flash) │
       │ Consulta SQLite:         │             │ Herramientas:          │
       │ • incident_assessments   │             │ • query_telemetry()    │
       │ • telemetry_samples      │             │ • query_incidents()    │
       │ • facility_knowledge     │             │ • query_network_logs() │
       └────────────┬─────────────┘             └─────────┬──────────────┘
                    │                                     │
                    └──────────────────┬──────────────────┘
                                       │
                                       ▼
                          Respuesta Concisa y Factual
                   "S19JPRO-25 reinició a las 15:45 hs por
                    watchdog de VNish tras 8 caídas de cable
                    de red Ethernet. Silicio 100% sano."
```

### 3.1 Nivel 1: Motor RAG Determinístico (Zero API Cost, 100% Offline)
- **Reconocimiento de Intenciones Rápidas**:
  - `reinicio / cayó / por qué`: Consulta la última fila en `incident_assessments` para el minero indicado.
  - `red / cable / enlace / desconexión`: Consulta eventos `Link is Down` en los últimos 60 minutos.
  - `temperatura / caliente / coolers`: Devuelve el ranking de temperaturas de chips y RPM de ventiladores.
  - `producción / estado / cómo viene`: Resume el hashrate combinado, chips activos (1512/1512) y J/TH.
- **Ventaja**: Respuesta instantánea (<50 ms), funciona aunque no haya conexión a internet externa y es 100% inmune a alucinaciones.

### 3.2 Nivel 2: Capa LLM On-Demand con Function Calling (Opcional / Configurable)
- Si el operador hace una pregunta compleja o no tipificada (ej. *"¿Notás alguna relación entre el calor del mediodía y las caídas del elevador 2 en la última semana?"*):
  - El despachador invoca a la API de `Gemini 3.8 Flash High` proveyéndole acceso a funciones de sólo lectura para consultar la base de datos local SQLite.
  - El modelo sintetiza la respuesta con los datos empíricos de silicio en 2 o 3 oraciones claras.
  - **Cero costo en reposo**: Sólo se consume API cuando el operador envía un mensaje manual.

---

## 4. Invariantes Constitucionales y Reglas de Seguridad

1. **Invariante P0 - Lectura Estrictamente Pasiva**:
   El motor de autopsia **NUNCA** ejecuta escrituras (`POST`/`PUT` a settings, reinicios por hardware, toggles de relé). Se conecta en modo lectura a WebSockets o endpoints de telemetría y cierra el socket inmediatamente.
2. **Invariante P0 - No Bloqueo del Bucle Principal**:
   La recolección de logs corre en un hilo de trabajo aislado con un timeout duro de **2.5 segundos**. Si un minero tarda en responder, la autopsia se cancela de forma limpia sin afectar el monitor principal.
3. **Invariante P0 - Anti-Spam y Resumen Ejecutivo**:
   La autopsia enriquecida solo se notifica en Telegram ante **incidentes reales confirmados**, utilizando tarjetas limpias de 3 a 5 líneas para no saturar la bandeja del operador.

---

## 5. Plan de Maduración y Auditoría Multi-Agente

Siguiendo la instrucción del operador de *"cranearlo, auditarlo con distintos agentes e implementarlo sin apuros"*:

### Fase A: Auditoría de Concurrencia y Arquitectura (Próximo Turno)
- **Revisión por Claude Sonnet 4.6 (Thinking)**:
  - Auditar el diseño de hilos asíncronos para la autopsia en `app/miner_monitor.py` (evitar deadlocks con `state_lock` y asegurar recolección segura de WebSockets bajo desconexiones de red).
  - Validar el esquema de persistencia en SQLite (`incident_assessments`).

### Fase B: Especificación Formal SpecKit (`specs/080-incident-autopsy-and-conversational-qa`)
- Creación de `spec.md`, `plan.md` y `tasks.md` siguiendo el flujo formal de SpecKit.
- Banco de pruebas unitarias con logs simulados de VNish (caída de link, pico térmico, fallo de PLL, PSU).

### Fase C: Implementación Modular y Puesta en Producción
- Implementación del `IncidentAutopsyEngine`.
- Enriquecimiento de alertas de Telegram.
- Integración del despachador conversacional en Telegram.
- Certificación final con la compuerta `speckit-stabilize`.
