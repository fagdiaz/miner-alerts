# Tasks — Spec 071: Consolidación de Pool SQLite Resiliente & Barrera Defensiva de Hilos Daemon (P0/P1)

**ID**: 071  
**Rama**: `codex/022-adaptive-acquisition`  
**Estado**: Pendiente  

---

### Fase A: Blindaje de Hilos Daemon (P0)

- [ ] **T001**: Implementar función defensiva `_async_restore_locked_preset_tripwire` en `app/miner_monitor.py` con `try ... except Exception` y logging estructurado.
- [ ] **T002**: Actualizar la instanciación de `RestoreLock_{name}` en `app/miner_monitor.py:3226` para usar la nueva función defensiva.
- [ ] **T003**: Auditar todos los demás hilos daemon en `app/miner_monitor.py` asegurando nombres descriptivos y barreras de excepción completas.

### Fase B: Consolidación de Conexiones SQLite Read-Only (P1)

- [ ] **T004**: Exponer `open_readonly_connection(db_path, timeout=5.0)` en `app/core/event_store.py`.
- [ ] **T005**: Migrar conexión directa en `app/governance/energy_efficiency.py:189` a `open_readonly_connection` y `execute_readonly_with_retry`.
- [ ] **T006**: Migrar conexión directa en `app/governance/fan_health.py:300` a `open_readonly_connection` y `execute_readonly_with_retry`.
- [ ] **T007**: Migrar conexiones directas en `app/governance/preset_balancer.py:389` y `:761` a `open_readonly_connection` y `execute_readonly_with_retry`.
- [ ] **T008**: Migrar conexión directa en `app/telegram/charts.py:36` a `open_readonly_connection` y `execute_readonly_with_retry`.
- [ ] **T009**: Migrar conexión directa en `app/telegram/daily_digest.py:168` a `open_readonly_connection` y `execute_readonly_with_retry`.
- [ ] **T010**: Migrar conexión directa en `app/vnish/presets.py:222` a `open_readonly_connection` y `execute_readonly_with_retry`.

### Fase C: Pruebas y Validación

- [ ] **T011**: Crear pruebas unitarias en `tests/test_sqlite_readonly_consolidation.py` validando conexión, pragmas y reintentos.
- [ ] **T012**: Sintaxis `py_compile` en todos los archivos modificados.
- [ ] **T013**: Ejecución de suite de regresión completa: $\ge 1072$ tests PASS, 0 regresiones.

### Fase D: Documentación y Cierre

- [ ] **T014**: Registrar evidencia en `specs/071-sqlite-pool-and-thread-hardening/evidence.md`.
- [ ] **T015**: Agregar entrada newest-first en `docs/audit/DEVELOPMENT_LOG.md`.
- [ ] **T016**: Actualizar `docs/speckit/ROADMAP.md`.
