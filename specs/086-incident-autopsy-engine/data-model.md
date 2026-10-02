# Data Model: Spec 086 — Autopsia Autónoma de Incidentes y Supervisor Conversacional (PROP-016)

**Fecha**: 2026-10-02  
**Autor**: Antigravity Engineering (Gemini 3.8 Flash High)  

---

## 1. Dataclasses del Dominio Forense (`app/forensics/autopsy_engine.py`)

### 1.1 `AutopsyEvidence`
Representa los hechos objetivos recolectados durante la ventana del incidente.
```python
@dataclass(frozen=True)
class AutopsyEvidence:
    miner_name: str
    host: str
    detected_ts: float
    elapsed_before: int
    elapsed_after: int
    system_log_lines: list[str]     # Kernel dmesg / libphy link drops
    status_log_lines: list[str]     # VNish watchdog warnings
    miner_log_lines: list[str]      # Stratum / cgminer error lines
    last_power_w: Optional[float]
    last_chip_temp_c: Optional[float]
    active_chains: int              # Cantidad de cadenas activas detectadas
```

### 1.2 `AutopsyReport`
Representa el resultado final sintetizado del análisis post-mortem.
```python
@dataclass(frozen=True)
class AutopsyReport:
    miner_name: str
    timestamp: float
    root_cause_category: str        # LINK_DROP, CHAIN_BREAK, THERMAL_SHUTDOWN, PSU_FAULT, etc.
    confidence: str                 # HIGH, MEDIUM, LOW
    headline: str                   # Título breve (ej. "Caída de Enlace Ethernet")
    summary_bullets: list[str]      # Lista de hechos clave formateados
    remediation_suggestion: str     # Sugerencia técnica para el operador
    is_silicon_healthy: bool        # True si los chips/cadenas no reportan falla de hardware
    raw_evidence_digest: str        # Hash SHA-256 para idempotencia y deduplicación
```

---

## 2. Esquema de Persistencia SQLite (`incident_assessments`)

Mapeo de `AutopsyReport` a la tabla `incident_assessments` en `data/miner_alerts.db`:

| Campo en DB | Tipo | Origen en AutopsyReport | Descripción |
|---|---|---|---|
| `created_ts` | REAL | `report.timestamp` | Epoch time del incidente |
| `subject_type` | TEXT | `"miner"` | Tipo de sujeto auditado |
| `subject_ref` | TEXT | `report.miner_name` | Nombre canónico (ej. "S19JPRO-25") |
| `miner_key` | TEXT | `f"{name}|{host}:4028"` | Clave única del minero |
| `ruleset_version` | TEXT | `"autopsy_v1"` | Versión de las reglas forenses |
| `window_start_ts`| REAL | `report.timestamp - 300`| Ventana de evidencia (5 min) |
| `window_end_ts`  | REAL | `report.timestamp` | Fin de ventana |
| `assessment_now_ts`| REAL | `report.timestamp` | Momento de evaluación |
| `status` | TEXT | `report.root_cause_category`| Categoría de causa raíz |
| `evidence_digest`| TEXT | `report.raw_evidence_digest`| Hash de deduplicación |
| `findings_json`  | TEXT | `json.dumps(report.summary_bullets)` | Hechos en formato JSON |
| `hypotheses_json`| TEXT | `json.dumps([{cause, confidence, remediation}])` | Diagnóstico final |
| `contradictions_json` | TEXT | `"[]"` | Contradicciones detectadas |
| `missing_evidence_json`| TEXT | `"[]"` | Evidencia no disponible |

---

## 3. Formato Mobile-First de Salida Telegram ($\le 32$ columnas)

Ejemplo de tarjeta renderizada por `build_autopsy_card(report)`:

```text
🔬 AUTOPSIA: S19JPRO-25
────────────────────────────────
Hora: 15:45:12 | Certeza: ALTA
Causa: ⚠️ ENLACE ETHERNET
────────────────────────────────
Evidencia Forense:
• 8x 'Link is Down' en 5m
• Watchdog: Low hashrate (17%)
• cgminer reiniciado x watchdog
────────────────────────────────
Silicio: ✅ 100% SANO (126 chips)
Acción recomendada:
Revisar patchcord RJ45 o switch
────────────────────────────────
```
*Cada línea de la tarjeta está estrictamente validada a $\le 32$ caracteres.*
