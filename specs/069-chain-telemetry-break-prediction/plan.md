# Plan de Implementación — Spec 069: Telemetría Profunda por Cadena & Diagnóstico Predictivo Chain Break (PROP-008)

**ID**: 069  
**Rama**: `codex/022-adaptive-acquisition`  
**Estado**: Planificado  

---

## 1. Arquitectura Técnica y Estructura de Clases

### 1.1 Optimización de Esquema en `app/core/event_store.py`

En la función de migración de esquema de `EventStore`, agregar el índice compuesto:
```sql
CREATE INDEX IF NOT EXISTS ix_chain_telemetry_miner_chain_time
    ON chain_telemetry_samples(miner_key, chain_id, observed_ts DESC);
```

Método de consulta optimizado:
```python
def fetch_chain_samples_window(
    self,
    miner_key: str,
    chain_id: int,
    since_ts: float,
) -> List[Dict[str, Any]]:
    """Consulta de solo lectura acotada en <15ms con reintento ante busy."""
    query = """
        SELECT observed_ts, sensors_error_count, sensors_json, hr_deficit_pct, chips_error_count
        FROM chain_telemetry_samples
        WHERE miner_key = ? AND chain_id = ? AND observed_ts >= ?
        ORDER BY observed_ts ASC
    """
    return self.execute_readonly_with_retry(...)
```

### 1.2 Módulo `app/governance/chain_health.py`

```python
@dataclass(frozen=True)
class PredictiveChainRisk:
    miner_name: str
    chain_id: int
    risk_type: str  # "I2C_PERSISTENT_ERROR", "CHIP_DEGRADATION", "ELECTRICAL_SAG"
    severity: str   # "WARNING", "CRITICAL"
    persistence_hours: float
    error_sample_pct: float
    faulty_locs: Tuple[int, ...]
    message: str

class PredictiveChainEngine:
    """Motor de evaluación predictiva de salud de cadenas y placas ASIC."""
    def evaluate_chain_history(
        self,
        samples: List[Dict[str, Any]],
        now_ts: float,
        config: Dict[str, Any],
    ) -> Optional[PredictiveChainRisk]: ...

    def correlate_electrical_group(
        self,
        risks: List[PredictiveChainRisk],
        miners_config: List[Dict[str, Any]],
    ) -> List[PredictiveChainRisk]:
        """Correlaciona perturbaciones eléctricas por elevador con fallback seguro si no está configurado."""
```

---

## 2. Puntos de Integración

1. **`app/miner_monitor.py`**:
   - Evaluación periódica cada 1 hora (o cada 120 ticks) en el bucle principal o mediante un hook en `CoreSupervisoryEngine`.
   - Si se detecta un `PredictiveChainRisk`, verificar si transcurrieron $> 24\text{ h}$ desde la última alerta para esa cadena.
   - Enviar alerta enriquecida a Telegram y persistir timestamp en `state.chain_warnings_ts`.
   - Preservar invariantes textuales de `main()`.

2. **Renderizado de Notificación**:
   - Generar tarjeta móvil formateada ($\le 32$ columnas) respetando las pautas de formato de Telegram del proyecto.

---

## 3. Plan de Verificación & Testing

1. **Pruebas de Índices y Latencia (`tests/test_chain_query_performance.py`)**:
   - Insertar 10.000 registros sintéticos en una base de datos en memoria o temporal.
   - Medir el tiempo de consulta de ventana: debe ejecutar en $< 15\text{ ms}$.
2. **Pruebas de Reglas Predictivas (`tests/test_chain_predictive_rules.py`)**:
   - Simular 95% de muestras con fallo I2C en `loc 28` durante 12h con $N \ge 24$ muestras $\rightarrow$ emite `PredictiveChainRisk`.
   - Simular muestra insuficiente ($N = 3$) $\rightarrow$ descarta sin emitir alerta (anti-falsas alarmas en arranque).
   - Simular fallo intermitente (30% de muestras) $\rightarrow$ descarta sin emitir alerta.
   - Simular 2 mineros en `elevator_1` cayendo al unísono $\rightarrow$ clasifica como `ELECTRICAL_SAG` y suprime alerta de silicio.
   - Simular minero sin elevador configurado $\rightarrow$ procesa evaluación individual con degradación suave.
3. **Validación Global**:
   - `unittest discover tests`: $\ge 1110$ tests PASS (0 fallos, 0 regresiones).
