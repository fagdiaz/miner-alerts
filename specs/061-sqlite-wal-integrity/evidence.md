# Evidencia de Validación: Spec 061 — Resiliencia SQLite WAL Mode & Integrity Check (ST-03)

## 1. Validación de Sintaxis Python
```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\core\event_store.py app\core\__init__.py app\miner_monitor.py tests\test_event_store_wal_resilience.py
```
- **Resultado**: 100% OK (cero errores, compilación limpia).

## 2. Validación de Pruebas Unitarias y de Resiliencia WAL
```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests/test_event_store_wal_resilience.py
```
- **Resultado**: **11/11 tests PASS** en 0.900s.
  * `test_async_integrity_check_clean_db`: Verificación asíncrona de integridad en hilo daemon (`EventStoreIntegrityWorker`) sobre base de datos limpia; completa en milisegundos sin bloquear el hilo principal.
  * `test_max_page_count_configured`: `PRAGMA max_page_count = 262144;` (~1 GB techo blando) aplicado y verificado.
  * `test_quarantine_and_recreate_on_corrupt_database`: Aislamiento atómico de base dañada a `miner_alerts_corrupt_<epoch>.db`, auto-recreación con esquema v7 y persistencia inmediata operativa.
  * `test_quarantine_on_corrupt_page_async_worker`: Detección en segundo plano de páginas internas malformadas con `PRAGMA quick_check;`, cuarentena y recreación limpia.
  * `test_checkpoint_wal_modes`: Soporte verificado para modos `PASSIVE`, `FULL`, `RESTART` y `TRUNCATE` (truncamiento de WAL a 0 bytes en Windows NTFS).
  * `test_create_readonly_connection_enforces_read_only`: Apertura en `mode=ro` con `PRAGMA query_only = ON` bloqueando escrituras accidentales.
  * `test_create_readonly_connection_non_existent_file`: `FileNotFoundError` defensivo si el archivo de base de datos no existe.
  * `test_execute_readonly_with_retry_on_busy_snapshot`: Reintento automático con backoff exponencial (100ms, 200ms, 400ms) ante `SQLITE_BUSY_SNAPSHOT`.
  * `test_execute_readonly_with_retry_exceeds_max_retries`: Propagación de error al agotar reintentos configurados.
  * `test_is_busy_or_snapshot_error_detection`: Detección de errores de bloqueo y conflicto de snapshot por código, nombre y texto de excepción.
  * `test_multi_reader_concurrency_with_continuous_writes_and_truncate`: Concurrencia de 4 hilos lectores continuos y 1 hilo escritor con checkpoint `TRUNCATE` en caliente sin bloqueos ni errores no capturados.

## 3. Validación de Regresiones en la Suite Completa del Proyecto
```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
```
- **Resultado**: **946 tests PASS** en 15.427s (0 fallos, 0 errores, 0 regresiones sobre la línea base de 935 tests).

## 4. Estado del Servicio en Producción (Windows Service)
```powershell
Get-Service -Name "MinerAlerts"
```
- **Resultado**: `Running` (`Miner Alerts Monitor`). Supervisión continua sin alteraciones.

## 5. Matriz de Entregables por Fase
- [x] **Fase A: Integridad Asíncrona & Límite de Disco**:
  * Hilo daemon `_integrity_check_worker` en `app/core/event_store.py` corriendo `PRAGMA quick_check;` en conexión aislada read-only sin retrasar el arranque del monitor ni el Startup Guard.
  * Auto-cuarentena atómica a `miner_alerts_corrupt_<epoch>.db` (`.db`, `.db-wal`, `.db-shm`) y recreación limpia con esquema v7.
  * Techo blando de almacenamiento: `PRAGMA max_page_count = 262144;` en `_initialize()`.
- [x] **Fase B: Gestión Determinista de Checkpointing**:
  * Método público `EventStore.checkpoint_wal(mode="PASSIVE") -> Tuple[int, int, int]`.
  * Integración en `app/miner_monitor.py`: checkpoint horario `PASSIVE` y diario `TRUNCATE` durante ventana off-peak (03:00 - 05:00 UTC).
- [x] **Fase C: Concurrencia Multi-Lector & Tolerancia BUSY_SNAPSHOT**:
  * `create_readonly_connection(db_path, timeout=3.0)` y `execute_readonly_with_retry(cursor_or_conn, sql, params)`.
  * Re-exportación en `app/core/__init__.py`.
  * Suite de pruebas dedicada `tests/test_event_store_wal_resilience.py` con 11 tests verdes.
