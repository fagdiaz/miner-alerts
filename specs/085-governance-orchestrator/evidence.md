# Evidence: Spec 085 — Extracción del Orquestador de Gobernanza (PROP-021)

**Fecha**: 2026-10-02
**Modelos**: Claude Sonnet 4.6 (Thinking), Gemini Flash (cierre Fase 1)
**Estado**: IMPLEMENTADO Y VERIFICADO — Fase 1, Fase 2, Fase 5 completas; Fases 3–4 descartadas por análisis de riesgo

---

## Resumen de Entregables

### Archivos Creados

| Archivo | Descripción | Líneas |
|---|---|---|
| `app/governance/_orchestrator_state.py` | Módulo de estado compartido thread-safe para globals de gobernanza | ~145 |
| `app/governance/governor_cycle.py` | Ciclo Fan Governor extraído de miner_monitor.py | ~370 |
| `tests/test_governance_orchestrator.py` | Suite de 15 tests de contrato del orquestador | ~180 |

### Archivos Modificados

| Archivo | Cambio | Resultado |
|---|---|---|
| `app/miner_monitor.py` | Eliminadas execute_governor_cycle + refresh_vnish (~572 L), añadido import | 9406 → 8834 líneas |
| `app/telegram/commands/fans.py` | mm._GOVERNOR_RUNTIME_ENABLED → get/set_governor_enabled() | Desacoplado |
| `app/telegram/commands/interventions.py` | mm._BALANCER_RUNTIME_ENABLED → get/set_balancer_enabled() | Desacoplado |
| `tests/test_fan_governor_concurrency.py` | Patches: app.miner_monitor.safe_set_fan_duty → governor_cycle | Actualizados |
| `tests/test_silent_mode.py` | Patches: app.miner_monitor.safe_set_fan_duty → governor_cycle | Actualizados |
| `tests/test_tripwire_thread_hardening.py` | Patches: monitor.safe_get_overclock/safe_set_miner → gov_cycle | Actualizados |

---

## Comandos de Validación Ejecutados

### Compilación (py_compile)
```
& ".\.venv\Scripts\python.exe" -m py_compile app\governance\_orchestrator_state.py
→ exit 0

& ".\.venv\Scripts\python.exe" -m py_compile app\governance\governor_cycle.py
→ exit 0

& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py
→ exit 0

& ".\.venv\Scripts\python.exe" -m py_compile app\telegram\commands\fans.py
→ exit 0

& ".\.venv\Scripts\python.exe" -m py_compile app\telegram\commands\interventions.py
→ exit 0
```

### Tests Específicos
```
& ".\.venv\Scripts\python.exe" -m pytest tests\test_governance_orchestrator.py -v
→ 15 passed in 0.55s

& ".\.venv\Scripts\python.exe" -m pytest tests\test_fan_governor_concurrency.py tests\test_silent_mode.py tests\test_governance_context_contracts.py -v
→ 62 passed in 2.65s

& ".\.venv\Scripts\python.exe" -m pytest tests\test_tripwire_thread_hardening.py tests\test_hw_error_tripwire.py -v
→ 16 passed in 0.65s
```

### Suite Global Pre-Fase-2
```
& ".\.venv\Scripts\python.exe" -m pytest -q
→ 1483 passed, 75 subtests passed in 45.36s
```

### Suite Global Post-Fase-2 + Tests Nuevos
```
& ".\.venv\Scripts\python.exe" -m pytest -q
→ 1498 passed, 75 subtests passed in 42.56s (0 fallos, 0 errores)
```
- Baseline previo: 1483 passed, 75 subtests passed.
- Ganancia neta: +15 tests automáticos en `tests/test_governance_orchestrator.py` verificando importabilidad, preservación de firmas, accesos thread-safe y desacoplamiento de handlers Telegram.

---

## Incidentes Durante Implementación

### Incidente 1: BOM UTF-8 en miner_monitor.py
- **Causa**: PowerShell `Set-Content -Encoding UTF8` introduce BOM (0xEF 0xBB 0xBF)
- **Síntoma**: `SyntaxError: invalid non-printable character U+FEFF` en test_state_resilience.py
- **Solución**: `[System.IO.File]::WriteAllText(..., New-Object System.Text.UTF8Encoding($false))`
- **Lección**: NUNCA usar PowerShell `Set-Content` para editar miner_monitor.py

### Incidente 2: Stale patch targets en tests
- **Causa**: Al mover `safe_set_fan_duty`, `safe_get_overclock_settings` a `governor_cycle.py`,
  los tests que parchean `app.miner_monitor.safe_set_fan_duty` dejaron de interceptar las llamadas
- **Tests afectados**: test_fan_governor_concurrency.py (4), test_silent_mode.py (6), test_tripwire_thread_hardening.py (3)
- **Solución**: Actualizar patches a `app.governance.governor_cycle.safe_set_fan_duty` etc.
- **Lección**: Al extraer funciones, siempre auditar `Select-String -Path "tests\*.py" -Pattern "miner_monitor\.<función>"` antes de declarar completada la fase

---

## Decisiones de Alcance

### Fases 3–4 Descartadas (execute_balancer_cycle, check_autotune_watchdog)

**Razón**: execute_balancer_cycle tiene 10 globals de módulo que son usados simultáneamente en el tick loop main() de miner_monitor.py en ~25 sitios distintos. Extraerlos requeriría:
- Añadir 10 más a _orchestrator_state (triplicando su complejidad)
- Modificar el tick loop principal en múltiples puntos
- Riesgo de producción desproporcionado al beneficio de reducción de líneas

**Documentado como**: Fuera del alcance de Spec 085. Candidato para Spec 086+ con análisis dedicado.

---

## Recuento de Líneas

| Etapa | Líneas miner_monitor.py |
|---|---|
| Pre-Spec 085 (post-084) | 9.406 |
| Post-Fase 2 (extracción governor_cycle) | 8.834 |
| Reducción | -572 líneas (-6.1%) |
| Target ROADMAP ≤6.000 | Aplazado a Spec 086+ |

---

## Estado de Producción

- Servicio NSSM MinerAlerts: RUNNING (sin interrupción)
- Flota: 4/4 mineros a 2700W (~395 TH/s)
- Chips: 69–80°C, sin alertas
- Commit base: 43d6d41 (Spec 084 cert)
