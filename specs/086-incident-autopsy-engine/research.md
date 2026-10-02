# Research: Spec 086 — Autopsia Autónoma de Incidentes y Supervisor Conversacional (PROP-016)

**Fecha**: 2026-10-02  
**Autor**: Antigravity Engineering (Gemini 3.8 Flash High)  

---

## 1. Patrones de Recolección de Logs de VNish sin Bloqueo

### Decisión
Reutilizar la lógica probada de `tools/vnish_log_collector.py` (`collect_vnish_tab`) invocada a través de un `ThreadPoolExecutor` acotado (1 a 2 workers) con:
- `connect_timeout = 1.5` segundos.
- `idle_timeout = 0.5` segundos.
- `max_bytes = 65_536` (64 KB, suficiente para los últimos ~300 renglones de eventos).
- Hard deadline total para la tarea: 2.5 segundos.

### Racional
El bucle authoritative de `miner_monitor.py` corre cada 30 segundos. Si un minero reinicia, puede tener su stack TCP o HTTP temporalmente no responsivo. Un timeout duro de 2.5s en un hilo secundario garantiza que el bucle principal jamás perciba degradación ni bloqueos, cumpliendo con la regla constitucional P0 de no disrupción.

---

## 2. Taxonomía y Expresiones Regulares de Causa Raíz

### Decisión
Definir un clasificador determinístico por prioridades de severidad e impacto:

| Categoría | Expresiones Regulares en Logs de VNish / Kernel | Remediatión Sugerida |
| :--- | :--- | :--- |
| `LINK_DROP` | `(?:libphy|eth0).*Link is Down`, `carrier lost`, `network unreachable` + `Low hashrate` | Inspeccionar cable Ethernet RJ45, patchcord o puerto de switch. |
| `CHAIN_BREAK` | `Chain break detected`, `chip_addr\s+0x[0-9a-fA-F]+`, `Chain faulted`, `chain\s+\[?\d+\]?\s+offline` | Revisar conectores ribbon de hashboard o microfisura térmica. |
| `THERMAL_SHUTDOWN` | `Overheating`, `Shutdown due to high temp`, `temp\s*>=?\s*8[5-9]`, `thermal runaway` | Limpieza de disipadores, revisión de flujo de aire o fans. |
| `PSU_FAULT` | `PSU error`, `voltage check fail`, `Power off spontaneously`, `power supply fault` | Verificar fase eléctrica de elevador, bornes y PSU. |
| `AUTOTUNE_STALL` | `Auto-tune timeout`, `PLL failed`, `autotune fail`, `frequency lock lost` | Fijar perfil de autotune más conservador o cerrojo de preset. |
| `POWER_LOSS` | Caída abrupta sin logs previos, tiempo transcurrido reseteado a 0s, socket cerrado | Posible caída de fase o corte de suministro en el elevador. |
| `UNRESOLVED` | Sin coincidencias claras en los logs recolectados | Monitorear telemetría previa y comportamiento en warmup. |

### Alternativas Consideradas
- **Llamar a un LLM en la nube para cada incidente**: Descartado por costo, latencia (3-10s), y riesgo de alucinaciones en diagnósticos críticos de hardware. El clasificador determinístico regex responde en <1ms y es 100% auditable.

---

## 3. Modelo de Persistencia en SQLite (`EventStore`)

### Decisión
Utilizar la tabla existente `incident_assessments` (schema 7 de `data/miner_alerts.db`):
- `subject_type = "miner"`
- `subject_ref = miner_name` (ej. "S19JPRO-25")
- `miner_key = miner_key`
- `ruleset_version = "autopsy_v1"`
- `status = root_cause_category` (ej. "LINK_DROP")
- `evidence_digest = hash de los hechos detectados`
- `findings_json = [lista de hallazgos estructurados]`
- `hypotheses_json = [{"cause": root_cause, "confidence": "HIGH", "remediation": ...}]`

### Racional
La tabla ya fue creada e indexada con `ix_assessment_subject_time` en Spec 023. Su reutilización aditiva no requiere migraciones DDL ni altera la base de datos de producción.

---

## 4. Supervisor Conversacional RAG Determinístico (Zero-Cost Offline)

### Decisión
Implementar un analizador de intenciones léxicas con expresiones regulares para Telegram:
1. **Intención de Autopsia / Causa**: Coincide con `(por qu[eé]|causa|motivo|qu[eé] pas[oó]|cay[oó]|reinici[oó])` + identificador de minero (`23`, `24`, `25`, `26`).
   - *Acción*: Consulta el último assessment en SQLite y devuelve la tarjeta de autopsia.
2. **Intención de Red / Enlace**: Coincide con `(red|cable|enlace|link|desconexi[oó]n|ethernet)`.
   - *Acción*: Resumen de eventos de enlace de red en los últimos 60m.
3. **Intención de Temperatura / Fans**: Coincide con `(temp|calor|cooler|fan|ventilador)`.
   - *Acción*: Resumen de temperaturas máximas y duty actual.

### Racional
Satisface el 95% de las preguntas operativas del usuario con latencia <50ms, cero tokens consumidos y disponibilidad 100% offline.
