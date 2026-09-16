# Spec 071: Consolidación de Pool SQLite Resiliente & Barrera Defensiva de Hilos Daemon (P0/P1)

**ID**: 071  
**Módulos**: `app/core/event_store.py`, `app/miner_monitor.py`, `app/governance/energy_efficiency.py`, `app/governance/fan_health.py`, `app/governance/preset_balancer.py`, `app/telegram/charts.py`, `app/telegram/daily_digest.py`, `app/vnish/presets.py`  
**Riesgo**: Bajo  
**Prioridad**: P0 (Inmediata para Hilos) / P1 (Alta para Conexiones SQLite)  
**Estado**: Especificado  
**Dependencias**: Spec 061 (SQLite WAL Integrity Check & Multi-Reader Pool)  

---

## 1. Contexto y Problema

Durante la auditoría arquitectónica integral del repositorio, se detectaron dos vulnerabilidades de estabilidad y resiliencia:

1. **Vulnerabilidad P0 — Ausencia de Barrera de Excepciones en Hilo Daemon de Restauración**:
   - En [`app/miner_monitor.py:3226`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py#L3226), el monitor detecta si el minero tiene un preset superior al permitido por el candado de errores de hardware y lanza un hilo daemon:
     ```python
     threading.Thread(
         target=safe_set_miner_preset,
         args=(m_host, vnish_pw, st.hw_error_locked_preset),
         kwargs={"timeout": timeout},
         daemon=True,
         name=f"RestoreLock_{m_name}",
     ).start()
     ```
   - Si la red sufre una interrupción o la biblioteca `requests` genera una excepción no capturada en el cuerpo de `safe_set_miner_preset`, el hilo muere silenciosamente en Windows sin registro estructurado en logs ni reintento defensivo.

2. **Vulnerabilidad P1 — Conexiones Directas a SQLite Bypasseando el Pool de `EventStore` (7 Módulos)**:
   - Siete módulos realizan llamadas ad-hoc directas a `sqlite3.connect(uri, uri=True, timeout=2.0)`:
     * `app/governance/energy_efficiency.py:189`
     * `app/governance/fan_health.py:300`
     * `app/governance/preset_balancer.py:389` y `:761`
     * `app/telegram/charts.py:36`
     * `app/telegram/daily_digest.py:168`
     * `app/vnish/presets.py:222`
   - **Riesgo**: Estas conexiones directas no implementan el mecanismo de retroceso exponencial ante `SQLITE_BUSY_SNAPSHOT` que posee `EventStore.execute_readonly_with_retry`. Si coincide una consulta con un checkpoint `TRUNCATE` de WAL en disco, la llamada arroja `sqlite3.OperationalError: database is locked`.

---

## 2. Arquitectura de Solución

### Componente 1: Barrera de Excepciones para `RestoreLock_{name}`
En [`app/miner_monitor.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py), se crea una función envoltorio defensiva `_async_restore_locked_preset_tripwire`:
```python
def _async_restore_locked_preset_tripwire(
    host: str,
    password: str,
    preset: str,
    timeout: float,
    miner_name: str,
) -> None:
    try:
        ok, err = safe_set_miner_preset(host, password, preset, timeout=timeout)
        if ok:
            log(f"[TRIPWIRE_INTERLOCK_RESTORE_OK] miner={miner_name} preset restaurado a {preset}")
        else:
            log(f"[TRIPWIRE_INTERLOCK_RESTORE_FAIL] miner={miner_name} fallo restaurando a {preset}: {err}")
    except Exception as exc:
        log(f"[TRIPWIRE_INTERLOCK_RESTORE_ERR] miner={miner_name} excepcion en hilo: {type(exc).__name__}: {exc}")
```

### Componente 2: Helper Centralizado `open_readonly_connection` en `EventStore`
En [`app/core/event_store.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/core/event_store.py), se expone formalmente la función de nivel de módulo:
```python
def open_readonly_connection(db_path: Path | str, timeout: float = 5.0) -> sqlite3.Connection:
    """Abre conexion de solo lectura con PRAGMA query_only=ON y synchronous=NORMAL."""
```
Y se refactorizan los 7 módulos consumidores para usar `open_readonly_connection` y `execute_readonly_with_retry`, eliminando el bloque de código duplicado de 35 líneas y garantizando tolerancia total a checkpoints WAL.

---

## 3. Requisitos Funcionales y Técnicos

- **RF-01**: Toda excepción en hilos daemon debe quedar registrada en el log con prefijo estructurado.
- **RF-02**: Ningún módulo fuera de `app/core/event_store.py` debe invocar `sqlite3.connect` directamente.
- **RF-03**: Las consultas de solo lectura en los 7 módulos deben beneficiarse automáticamente del mecanismo anti-`SQLITE_BUSY_SNAPSHOT`.
- **RF-04**: Mantener el 100% de los 37 tests de invariantes constitucionales.
- **RF-05**: Mantener $\ge 1072$ tests globales PASS.
