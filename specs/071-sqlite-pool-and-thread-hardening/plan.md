# Plan de Implementación — Spec 071: Consolidación de Pool SQLite Resiliente & Barrera Defensiva de Hilos Daemon (P0/P1)

**ID**: 071  
**Rama**: `codex/022-adaptive-acquisition`  
**Estado**: Planificado  

---

## 1. Diseño Técnico

### 1.1 Helper de Conexión en `app/core/event_store.py`
Exponer `open_readonly_connection(db_path: Path | str, timeout: float = 5.0) -> sqlite3.Connection`:
- Abre la URI con `?mode=ro`.
- Aplica `PRAGMA query_only = ON;`.
- Aplica `PRAGMA synchronous = NORMAL;`.
- Configura `conn.row_factory = sqlite3.Row`.
- Maneja excepciones con log descriptivo.

### 1.2 Refactorización de Módulos Consumidores
Sustituir el bloque duplicado en los 7 módulos por:
```python
from app.core.event_store import open_readonly_connection, execute_readonly_with_retry

conn = open_readonly_connection(db_file)
try:
    cursor = execute_readonly_with_retry(conn, query, params)
    rows = cursor.fetchall()
finally:
    conn.close()
```

### 1.3 Barrera de Hilo `RestoreLock_{name}` en `miner_monitor.py`
Envolver la llamada a `safe_set_miner_preset` en `_async_restore_locked_preset_tripwire`.

---

## 2. Plan de Verificación & Testing

1. **Test de Barrera de Hilo (`tests/test_tripwire_thread_hardening.py`)**:
   - Simular excepción en `safe_set_miner_preset` y verificar que el log registra el error sin matar el hilo silenciosamente.
2. **Test de Conexión Centralizada (`tests/test_readonly_pool_consolidation.py`)**:
   - Verificar que `open_readonly_connection` devuelve conexiones con `query_only=ON`.
   - Verificar que los 7 módulos obtienen los mismos datos históricos sin errores de sintaxis.
3. **Validación Global**:
   - $\ge 1072$ tests PASS.
   - `py_compile` en todos los archivos modificados.
