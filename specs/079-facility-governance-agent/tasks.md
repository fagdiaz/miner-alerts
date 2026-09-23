# Tasks: Spec 079 — Agente Autónomo de Gobernanza de Planta (FGA) y Optimizador Asimétrico de Potencia

- [x] T001: Crear `app/governance/facility_agent.py` implementando:
  - Fórmulas determinísticas de resistencia térmica ($R_{th} = \Delta T / P$) y predicción de temperatura ($T_{pred}$).
  - Lógica de asignación asimétrica inter-elevador basada en margen térmico ($T_{target\_safe} \le 82.5^\circ\text{C}$) y estrategias (`balanced`, `max_power`, `efficiency`, `cool_quiet`).
  - Generador de diagnósticos explicativos para humanos (`explain_miner_state`).
- [x] T002: Crear suite de pruebas unitarias `tests/test_facility_agent.py` validando $R_{th}$, predicciones térmicas, optimización asimétrica y modos estratégicos.
- [x] T003: Extender la persistencia en `app/core/event_store.py` con la tabla y métodos para `facility_agent_knowledge`.
- [x] T004: Implementar comandos de Telegram `/agent`, `/why` y `/strategy` en `app/telegram/commands/` y registrarlos en el router de comandos.
- [x] T005: Integrar el motor del Agente en el bucle principal de `app/miner_monitor.py` para recalibración continua y toma de decisiones asimétricas en tiempo real.
- [x] T006: Ejecutar validación de compilación (`py_compile`) y suite de regresión completa ($\ge 1335$ tests PASS, 0 fallos, 0 regresiones).
- [x] T007: Documentar evidencia en `specs/079-facility-governance-agent/evidence.md`, actualizar `docs/audit/DEVELOPMENT_LOG.md` y `docs/speckit/ROADMAP.md`.
- [x] T008: Presentar el resumen de certificación y habilitación del Agente FGA al usuario.
