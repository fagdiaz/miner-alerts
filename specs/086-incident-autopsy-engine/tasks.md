# Tasks: Spec 086 — Autopsia Autónoma de Incidentes y Supervisor Conversacional (PROP-016)

**Feature**: `086-incident-autopsy-engine`  
**Fecha**: 2026-10-02  
**Prioridad**: P2 — Observabilidad y Autonomía Forense  
**Riesgo**: MEDIO (subsistema aditivo, worker no bloqueante)  
**Modelo recomendado**: Gemini 3.8 Flash High (Primary Engine)  
**Baseline**: 1498 tests PASS, 75 subtests PASS  

---

## Fase 1 — Setup y Persistencia en `EventStore`

- [x] **T1.1** [P] Revisar métodos existentes en `app/core/event_store.py` para la tabla `incident_assessments`.
- [x] **T1.2** Implementar en `app/core/event_store.py` los métodos de conveniencia `record_autopsy_assessment()` y `get_latest_autopsy_assessment(miner_name)`.
- [x] **T1.3** Validar sintaxis: `py_compile app/core/event_store.py`.

---

## Fase 2 — Dominio y Clasificador Forense (`app/forensics/autopsy_engine.py`)

- [x] **T2.1** [P] Crear el paquete `app/forensics/` con `__init__.py`.
- [x] **T2.2** Definir dataclasses inmutables `AutopsyEvidence` y `AutopsyReport` en `app/forensics/autopsy_engine.py`.
- [x] **T2.3** Implementar función pura `classify_incident_root_cause(evidence: AutopsyEvidence) -> AutopsyReport` cubriendo:
  - `LINK_DROP` (patrones `libphy: Link is Down`, watchdog de VNish hashrate caído).
  - `CHAIN_BREAK` (`Chain break detected`, `chip_addr 0xXX`).
  - `THERMAL_SHUTDOWN` (`Overheating`, `temp >= 85`).
  - `PSU_FAULT` (`PSU error`, `voltage check fail`).
  - `AUTOTUNE_STALL` (`Auto-tune timeout`, `PLL failed`).
  - `POWER_LOSS` (`elapsed` reiniciado sin registros en buffer).
  - `UNRESOLVED` (evidencia insuficiente).
- [x] **T2.4** Implementar `IncidentAutopsyEngine.run_autopsy(miner_name, host, detected_ts, ...)` con invocación segura a `collect_vnish_tab` bajo timeout duro de 2.5s y sin bloqueos.
- [x] **T2.5** Validar sintaxis: `py_compile app/forensics/autopsy_engine.py`.

---

## Fase 3 — Tarjetas Mobile-First ($\le 32$ columnas) (`app/forensics/autopsy_card.py`)

- [x] **T3.1** [P] [US1] Crear módulo `app/forensics/autopsy_card.py`.
- [x] **T3.2** [US1] Implementar función pura `build_autopsy_card(report: AutopsyReport) -> str` respetando estrictamente $\le 32$ columnas en cada línea.
- [x] **T3.3** [US1] Implementar función pura `build_fleet_autopsy_summary_card(reports: list[AutopsyReport]) -> str` en $\le 32$ columnas.
- [x] **T3.4** [US1] Validar sintaxis: `py_compile app/forensics/autopsy_card.py`.

---

## Fase 4 — Comandos y Router de Telegram (`app/telegram/commands/autopsy.py`)

- [x] **T4.1** [P] [US2] Crear handler `AutopsyCommand` en `app/telegram/commands/autopsy.py` con aliases `/autopsia`, `/causa_raiz`, `/autopsy`, `/investigar`.
- [x] **T4.2** [US2] Registrar `AutopsyCommand` en `create_default_command_router()` de `app/telegram/router.py`.
- [x] **T4.3** [P] [US3] Crear módulo `app/forensics/conversational_qa.py` con router determinístico de intenciones ("¿por qué reinició la 25?", "¿cómo está la red?", etc.).
- [x] **T4.4** [US3] Integrar el fallback de texto libre en `app/telegram/router.py` para canalizar preguntas al supervisor conversacional.
- [x] **T4.5** Validar sintaxis: `py_compile app/telegram/commands/autopsy.py app/forensics/conversational_qa.py app/telegram/router.py`.

---

## Fase 5 — Integración en Detección de Incidentes (`app/miner_monitor.py`)

- [x] **T5.1** Ubicar el punto de detección de reinicios `unexpected` en `app/miner_monitor.py` (L6900-7100).
- [x] **T5.2** Disparar la autopsia en segundo plano (`ThreadPoolExecutor` aislado) y anexar el dictamen a la alerta de Telegram sin retrasar el tick principal.
- [x] **T5.3** Validar sintaxis: `py_compile app/miner_monitor.py`.

---

## Fase 6 — Suite de Pruebas Automatizadas (`tests/test_incident_autopsy.py`)

- [x] **T6.1** [P] Crear `tests/test_incident_autopsy.py`.
- [x] **T6.2** Test de clasificación de causas raíz determinísticas (Link drop, thermal, chain break, PSU, autotune).
- [x] **T6.3** Test de verificación estricta de ancho de columnas ($\le 32$ columnas por línea).
- [x] **T6.4** Test de persistencia y consulta en `EventStore` (`incident_assessments`).
- [x] **T6.5** Test de router conversacional Q&A offline (reconocimiento de intenciones y respuestas instantáneas).
- [x] **T6.6** Test de timeout duro de 2.5s y manejo de errores de red en el worker.
- [x] **T6.7** Ejecutar `pytest tests/test_incident_autopsy.py -v` → 100% PASS.

---

## Fase 7 — Control de Calidad y Preflight (`speckit-qa`)

- [x] **T7.1** Ejecutar `speckit-qa` (verificación de compuertas de seguridad, sintaxis y consistencia).
- [x] **T7.2** Ejecutar suite global: `pytest -x -q` (1510 passed, 75 subtests passed, 0 fallos).

---

## Fase 8 — Evidencia, Estabilización y Cierre

- [x] **T8.1** Generar `specs/086-incident-autopsy-engine/evidence.md` con comandos ejecutados y resultados de pruebas.
- [x] **T8.2** Registrar entrada newest-first en `docs/audit/DEVELOPMENT_LOG.md`.
- [x] **T8.3** Actualizar `docs/speckit/ROADMAP.md` y `docs/speckit/SPEC_PROGRAM.md`.
- [x] **T8.4** Ejecutar `speckit-stabilize` (8 gates).
- [x] **T8.5** Reiniciar servicio NSSM `MinerAlerts` y verificar logs en producción.
- [x] **T8.6** Actualizar `prompt.txt` con el nuevo baseline para la siguiente sesión.
