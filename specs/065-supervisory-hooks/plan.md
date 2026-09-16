# Implementation Plan: Spec 065 — Pipeline Declarativo de Hooks en CoreSupervisoryEngine (ST-04)

**Branch**: `codex/022-adaptive-acquisition` | **Date**: 2026-09-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/065-supervisory-hooks/spec.md`

---

## Summary

Evolucionar `CoreSupervisoryEngine` hacia un pipeline declarativo de hooks estructurado por etapas, con contención defensiva de fallos, verificación de modelo de tiempo monotónico y preservación del 100% de los tests de introspección:
- **Fase A (Modelado de Etapas & Contrato de Hooks en `app/core/engine.py`)**:
  * Definir `HookStage` con enum/constantes ordenadas (`PRE_TICK`, `ACQUISITION`, `DETECTION`, `GOVERNANCE`, `ACTUATOR`, `PERSISTENCE`, `POST_TICK`).
  * Implementar clase base `SupervisoryHook` y contenedor `HookResult`.
  * Diseñar `register_hook()` con ordenamiento determinista por etapa.
- **Fase B (Implementación de Hooks Canónicos & Aislamiento de Errores)**:
  * Implementar `PersistenceHook` utilizando `context.state_manager.save()` fuera de locks.
  * Implementar `GovernanceInterlockHook` y `TimingGuardHook`.
  * Integrar contención de excepciones por hook en el despachador central del engine, asegurando que un fallo en un hook no impida la ejecución de los hooks restantes de la etapa o posteriores.
- **Fase C (Integración Aditiva en `miner_monitor.py` & Suite de Tests)**:
  * Conectar el pipeline en `main()` de `miner_monitor.py` de forma aditiva y segura, sin tocar las líneas examinadas por `inspect.getsource(main)`.
  * Desarrollar suite completa en `tests/test_supervisory_hooks.py`.
  * Verificar 996+ tests globales PASS y servicio Windows `MinerAlerts` activo.

---

## Technical Context

**Language/Version**: Python 3.12 (virtualenv en Windows 11)
**Modules**:
- `app/core/engine.py` (`HookStage`, `SupervisoryHook`, `CoreSupervisoryEngine`, `PersistenceHook`, `GovernanceInterlockHook`, `TimingGuardHook`).
- `app/core/context.py` (Extensiones de conveniencia si aplican).
- `app/miner_monitor.py` (Conexión aditiva y transparente del pipeline).
- `tests/test_supervisory_hooks.py` (Suite dedicada de pruebas de pipeline y timing).
**Target Platform**: Windows 11 Pro / Servicio Windows `MinerAlerts`.

---

## Constitution Check

1. **Principio 1 (Monitoreo Continuo & Seguridad de Hardware)**: ✅ La estructuración en hooks garantiza que la persistencia atómica y el latido se ejecuten incluso si un actuador falla o demora.
2. **Principio 2 (Zero Peticiones HTTP Extras a Mineros)**: ✅ Los hooks operan sobre el flujo de datos en memoria y telemetría ya existente sin añadir peticiones HTTP no planificadas.
3. **Principio 3 (Preservación de Invariantes y Tests de Inspección)**: ✅ Se mantiene estricta compatibilidad con los 4 tests existentes de `inspect.getsource(main)`, asegurando que `len(tests_pass) >= 996`.
4. **Principio 4 (Determinismo Monotónico en Windows)**: ✅ El cálculo de reposo entre ciclos utiliza `time.monotonic()` descontando el tiempo de ejecución de todos los hooks para evitar derivas en la cadencia de 30s.
