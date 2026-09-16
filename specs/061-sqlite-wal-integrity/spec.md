# Feature Specification: Spec 061 — Resiliencia SQLite WAL Mode & Integrity Check (ST-03)

**Feature Directory**: `specs/061-sqlite-wal-integrity`
**Created**: 2026-09-15
**Status**: In Planning
**Initiative**: ST-03 (Almacenamiento Concurrente & Integridad ante Apagones)
**Audited by**: Claude Sonnet 4.6 Thinking (2026-09-15 — Correcciones incorporadas)
**Input**: Blindar el motor de base de datos SQLite (`EventStore`) contra fallos abruptos de alimentación (blackouts en galpón), evitar bloqueos en el arranque mediante verificación de integridad asíncrona, garantizar el truncamiento determinista del archivo WAL en Windows NTFS y habilitar un pool de lectura multi-lector protegido contra `SQLITE_BUSY_SNAPSHOT` para Grafana, exportadores y scripts CLI sin riesgo de contención.

---

## User Scenarios & Testing

### User Story 1 - Verificación de Integridad Asíncrona y Auto-Sanación en Arranque (Priority: P1)

Como operador del centro de minería, deseo que si el host Windows o el servicio `MinerAlerts` sufre un apagón eléctrico intempestivo y se reinicia, el monitor arranque de forma instantánea sin retrasos en la supervisión de los ASICs ni en la activación del Startup Guard, mientras un hilo en segundo plano valida la integridad estructural de la base de datos (`PRAGMA quick_check;`) y, si detecta corrupción de sectores, aísle automáticamente el archivo dañado y recree una base de datos limpia sin interrumpir la operación.

**Why this priority**: Evita que un archivo SQLite dañado por corte eléctrico bloquee el inicio del servicio o genere excepciones no controladas durante la escritura de métricas de telemetría.

**Independent Test**: Corromper intencionalmente encabezados de páginas en un archivo `.db` en staging y verificar que `_integrity_check_worker` aísla el archivo en `data/miner_alerts_corrupt_<epoch>.db`, recrea el esquema v7 y el monitor continúa operando de forma continua.

---

### User Story 2 - Checkpointing Determinista en Windows NTFS y Control de Espacio (Priority: P1)

Como administrador de infraestructura, deseo que el archivo `miner_alerts.db-wal` no crezca indefinidamente en el sistema de archivos NTFS de Windows debido a lectores persistentes (Grafana, dashboards o herramientas de diagnóstico), asegurando que el espacio en disco sea reciclado periódicamente.

**Why this priority**: En Windows NTFS, el modo WAL no reduce su tamaño físico con checkpoints `PASSIVE` si hay lectores concurrentes con snapshots abiertos.

**Independent Test**: Ejecutar `EventStore.checkpoint_wal("TRUNCATE")` y verificar que el archivo `-wal` se reduce a 0 bytes sin arrojar errores de bloqueo de archivo de Windows.

---

### User Story 3 - Lectura Concurrente Externa sin Contención ni Errores de Snapshot (Priority: P2)

Como desarrollador de herramientas de observabilidad, deseo poder conectar herramientas externas (`tools/operations_dashboard.py`, `tools/metrics_exporter.py` o Grafana) a `miner_alerts.db` en modo de solo lectura estricto, disponiendo de un mecanismo defensivo que capture `SQLITE_BUSY_SNAPSHOT` (código 5) y reintente con backoff exponencial cuando coincide con un checkpoint de truncamiento del monitor.

**Why this priority**: Previene bloqueos `database is locked` o cierres inesperados de exportadores de telemetría durante escrituras concurrentes.

**Independent Test**: Simular 10 hilos lectores concurrentes ejecutando consultas de agregación mientras el hilo principal escribe muestras de telemetría y ejecuta un checkpoint `TRUNCATE`, verificando cero fallos gracias al reintento con backoff.

---

## Functional Requirements

1. **FR-01 (Quick-Check Asíncrono en Arranque)**:
   - En `EventStore._initialize()`, conectar con `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000` y lanzar un hilo daemon dedicado `_integrity_check_worker`.
   - El worker ejecuta `PRAGMA quick_check;` en una conexión aislada. Si el resultado es distinto de `"ok"`:
     * Renombrar atómicamente la base de datos corrupta a `miner_alerts_corrupt_<epoch>.db`.
     * Recrear la base de datos limpia con esquema vigente (v7).
     * Fijar bandera `self._integrity_failed = True` y registrar advertencia crítica en log y Telegram.
   - El arranque del servicio y el Startup Guard de 10 minutos **no deben retrasarse** (0 ms de bloqueo sincrónico).

2. **FR-02 (Checkpointing Determinista PASSIVE y TRUNCATE)**:
   - Implementar método público `EventStore.checkpoint_wal(mode: str = "PASSIVE") -> Tuple[int, int, int]` que ejecute `PRAGMA wal_checkpoint(<mode>);` bajo lock de conexión.
   - Ciclo Horario: Ejecutar checkpoint en modo `"PASSIVE"` en el ciclo de mantenimiento para checkpointing incremental seguro.
   - Ciclo Diario: Ejecutar checkpoint en modo `"TRUNCATE"` en horas valle (03:00 - 05:00 UTC) para liberar espacio físico en disco.
   - Configurar `PRAGMA max_page_count = 262144;` (~1 GB de techo blando) en la inicialización para prevenir saturación de disco.

3. **FR-03 (Factoría de Conexión de Solo Lectura y Manejo de BUSY_SNAPSHOT)**:
   - Implementar función pública `create_readonly_connection(db_path: Path, timeout: float = 3.0) -> sqlite3.Connection` abriendo en modo URI `file:<path>?mode=ro`.
   - Implementar wrapper o decorador `execute_readonly_with_retry(cursor, query, params, max_retries=3)` que capture `sqlite3.OperationalError` con código de snapshot ocupado (`SQLITE_BUSY_SNAPSHOT`) y reintente con retroceso exponencial de 100ms, 200ms y 400ms.

4. **FR-04 (Integración en Monitor y Ciclo de Mantenimiento)**:
   - Conectar las llamadas de checkpointing en los ciclos de mantenimiento existentes en `app/miner_monitor.py`.

5. **FR-05 (Batería de Pruebas Automatizadas)**:
   - Crear `tests/test_event_store_wal_resilience.py` cubriendo integridad en arranque, auto-cuarentena, checkpoints PASSIVE/TRUNCATE y concurrencia multi-lector bajo estrés.
