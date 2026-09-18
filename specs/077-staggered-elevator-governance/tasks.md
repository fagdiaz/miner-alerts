# Tasks: Spec 077 — Gobernanza Escalonada de Elevadores, Bajada Compartida y Soft-Contingencia Horaria

- [x] T001: Implementar módulo puro `app/governance/elevator_budget.py` con `FacilityBudgetState`, cálculo de presupuesto por grupo eléctrico ($\le 5000\text{W}$ en pico, $\le 5400\text{W}$ en valle), preferencia de balance simétrico (2x 2500W antes que 2700W+2300W), cerrojo global de transición para la bajada compartida (180s) y evaluador de Soft-Contingencia horaria (Lunes-Viernes 08:30-10:30 y 19:30-22:30).
- [x] T002: Desarrollar suite de pruebas unitarias en `tests/test_elevator_budget.py` cubriendo presupuesto de elevadores, preferencia simétrica, exclusión de 2700W simultáneos en el mismo elevador durante picos, secuenciación global de la bajada compartida (180s settle) y calendario semanal (21 tests PASS).
- [x] T003: Integrar compuertas de presupuesto y cerrojo de bajada compartida en `app/governance/preset_balancer.py` (`ACTION_HOLD_FACILITY_SETTLE`, `ACTION_HOLD_BUDGET_LIMIT`, `ACTION_HOLD_ASYMMETRY_PREFERENCE`, `ACTION_HOLD_SCHEDULE_CEILING`) priorizando parejas a 2500W.
- [x] T004: Integrar evaluador de Soft-Contingencia horaria y orquestador escalonado en el loop principal de `app/miner_monitor.py` manteniendo el clampeo de `top_preset` para gobernar la envolvente de VNish.
- [x] T005: Ejecutar suite de regresión completa (1288 tests PASS, 75 subtests PASS en 43.28s, 0 fallos, 0 regresiones) y validar compilación limpia con `py_compile`.
- [x] T006: Documentar evidencia en `specs/077-staggered-elevator-governance/evidence.md`, actualizar `docs/audit/DEVELOPMENT_LOG.md` y `docs/speckit/ROADMAP.md`.
- [ ] T007: Realizar commit Git feature-scoped, sincronizar con origin y reiniciar el servicio Windows `MinerAlerts` en producción.
