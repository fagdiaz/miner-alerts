# Implementation Plan: Spec 086 — Autopsia Autónoma de Incidentes y Supervisor Conversacional (PROP-016)

**Branch**: `codex/022-adaptive-acquisition` | **Date**: 2026-10-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/086-incident-autopsy-engine/spec.md` (basado en PROP-016).

---

## Summary

Implementar un motor forense desacoplado (`IncidentAutopsyEngine`) que se ejecute en un hilo aislado ante reinicios de minado inesperados (`elapsed: N -> 10s`), consulte logs de VNish (`system`, `status`, `miner`) con timeout duro de 2.5s en modo read-only, clasifique determinísticamente la causa raíz (red/enlace, térmico, silicio, PSU, autotune, etc.), persista la evaluación en la tabla SQLite `incident_assessments` y emita tarjetas Mobile-First ($\le 32$ cols) en Telegram. Además, dotar al bot de Telegram de comandos on-demand (`/autopsia`) y un router de intenciones en lenguaje natural offline para responder consultas directas del operador sin costo de API.

---

## Technical Context

**Language/Version**: Python 3.14.2  
**Primary Dependencies**: `sqlite3`, `threading`, `concurrent.futures`, `re`, `dataclasses`, `tools.vnish_log_collector` (`collect_vnish_tab`), `app.telegram.router`  
**Storage**: SQLite (`data/miner_alerts.db` / `EventStore`) tabla `incident_assessments` y `assessment_fact_refs`  
**Testing**: `pytest tests/test_incident_autopsy.py -v`  
**Target Platform**: Windows 11, NSSM service `MinerAlerts`, Telegram Bot API  
**Project Type**: Daemon de monitoreo con worker asíncrono forense y dispatcher de Telegram  
**Performance Goals**:
- Autopsia completada y notificada en $\le 3.5$ segundos
- Cero latencia o bloqueo en el tick principal de adquisición (0 ms de impacto)
- Consultas offline de Telegram resueltas en $<50$ ms
**Constraints**:
- Lectura estrictamente pasiva (`read-only`) en WebSockets y endpoints de mineros
- Timeout duro de 2.5s en recolección de logs remotos
- Formato móvil estricto: $\le 32$ caracteres por línea en todas las salidas
- Respeto total al aislamiento de secretos (`config.json` y `state.json` protegidos)

---

## Constitution Check

- [x] **P0 Safety**: Cero reinicios destructivos involuntarios ni alteraciones no autorizadas de hardware.
- [x] **P0 Non-Blocking Loop**: El motor forense corre en `ThreadPoolExecutor` aislado; el tick loop principal no espera ni sufre demoras.
- [x] **P1 Mobile-First**: Tarjetas de autopsia diseñadas con cuadrícula monoespaciada $\le 32$ columnas.
- [x] **P1 Determinismo Offline**: Clasificación por reglas regex y búsqueda en SQLite sin dependencia de conectividad a LLM externo.
- [x] **P2 Backward Compatibility**: El esquema SQLite existente (`incident_assessments` de `EventStore`) se utiliza sin migraciones destructivas.

---

## Project Structure & Deliverables

### Documentation (`specs/086-incident-autopsy-engine/`)
- `spec.md`: Especificación funcional y criterios de aceptación.
- `plan.md`: Plan de implementación técnico (este archivo).
- `research.md`: Patrones de clasificación forense y mapeo de WebSockets.
- `data-model.md`: Modelado de `AutopsyReport`, `AutopsyEvidence` y persistencia.
- `quickstart.md`: Guía rápida de uso del comando `/autopsia` y consultas conversacionales.
- `tasks.md`: Lista desglosada y ordenada de tareas de implementación.

### Source Code (`app/`)
- `app/forensics/autopsy_engine.py` (NUEVO):
  - Dataclasses `AutopsyEvidence`, `AutopsyReport`.
  - `IncidentAutopsyEngine`: worker con timeout 2.5s, recolección de tabs VNish y clasificación determinística de causa raíz.
- `app/forensics/autopsy_card.py` (NUEVO):
  - Formateador Mobile-First ($\le 32$ cols) para reportes de autopsia y resúmenes ejecutivos.
- `app/forensics/conversational_qa.py` (NUEVO):
  - Router RAG determinístico offline para procesar consultas en lenguaje natural ("¿por qué reinició la 25?", "¿cómo está el cable?").
- `app/telegram/commands/autopsy.py` (NUEVO):
  - `AutopsyCommand` registrado con aliases `/autopsia`, `/autopsy`, `/causa_raiz`, `/investigar`.
- `app/core/event_store.py` (MODIFICADO — aditivo):
  - Método `record_autopsy_assessment()` y `get_latest_autopsy_assessment()`.
- `app/miner_monitor.py` (MODIFICADO — integración mínima):
  - Disparo no bloqueante del worker ante `classification == "unexpected"`.

### Tests (`tests/`)
- `tests/test_incident_autopsy.py` (NUEVO):
  - Tests unitarios del clasificador (patrones `Link is Down`, `Overheating`, `Chain break`, `PSU error`, `PLL stall`).
  - Tests de timeout duro de 2.5s.
  - Tests de ancho de tarjeta $\le 32$ columnas.
  - Tests de persistencia y recuperación en `EventStore`.
  - Tests de despachador conversacional offline.
