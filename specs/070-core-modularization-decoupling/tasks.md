# Tasks — Spec 070: Modularización del Core Fase B — Desacoplamiento Seguro de inspect.getsource(main) (ST-05)

**ID**: 070  
**Rama**: `codex/022-adaptive-acquisition`  
**Estado**: Pendiente  

---

### Fase A: Construcción del Arnés de Comportamiento (`Behavioral Test Harness`)

- [ ] **T001**: Crear `tests/test_supervisory_core_behavioral.py` con el arnés `SupervisoryBehavioralHarness` y fixtures deterministas.
- [ ] **T002**: Implementar los 8 tests de paridad para compuertas de señal y reseteo de temporizadores (reemplazo funcional de `test_auto_reboot_signal_gate.py`).
- [ ] **T003**: Implementar los 8 tests de paridad para detección de `STATE_HASHBOARD` y secuencia de 6 interlocks (reemplazo funcional de `test_hashboard_auto_reboot.py`).
- [ ] **T004**: Implementar los 13 tests de paridad para orden jerárquico de seguridad y cooldowns (reemplazo funcional de `test_reboot_safety.py`).
- [ ] **T005**: Implementar los 8 tests de paridad para precedencia de placas activas sobre tasa de hashrate (reemplazo funcional de `test_vnish_hashboard_detection.py`).

### Fase B: Certificación de Paridad Dual

- [ ] **T006**: Ejecutar suite de comportamiento: `unittest tests.test_supervisory_core_behavioral` (37/37 tests PASS).
- [ ] **T007**: Ejecutar suite completa de regresión con ambas suites activas simultáneamente: verificar $\ge 1109$ tests PASS (1072 + 37 nuevos, 0 fallos).

### Fase C: Refactorización Segura a Hooks

- [ ] **T008**: Extraer `DetectionHook` en `app/core/engine.py` encapsulando la clasificación de estados (`OK`, `LOW`, `OFFLINE`, `HASHBOARD`).
- [ ] **T009**: Extraer `ActuatorHook` en `app/core/engine.py` encapsulando la evaluación de interlocks de auto-reboot.
- [ ] **T010**: Conectar los nuevos hooks en `main()` de `miner_monitor.py`.
- [ ] **T011**: Actualizar los 4 archivos de test legados para reemplazar las aserciones de `inspect.getsource(main)` por aserciones directas sobre funciones puras o el motor de supervisión.

### Fase D: Validación Final y Documentación

- [ ] **T012**: Sintaxis `py_compile app/miner_monitor.py app/core/engine.py`.
- [ ] **T013**: Suite completa de regresión: $\ge 1072$ tests PASS, 0 fallos, 0 regresiones.
- [ ] **T014**: Registrar comandos y evidencia en `specs/070-core-modularization-decoupling/evidence.md`.
- [ ] **T015**: Agregar entrada en `docs/audit/DEVELOPMENT_LOG.md`.
- [ ] **T016**: Actualizar `docs/speckit/ROADMAP.md` y `prompt.txt`.
