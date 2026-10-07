# Feature Specification: Modernización de Contratos de Test Invariantes (Spec 090)

**Feature Name**: Test Invariants Modernization & Source-Inspection Decoupling  
**Feature Code**: `090-test-invariants-modernization`  
**Tracking Issue / Proposal**: ST-05 (Continuación) / Spec 090  
**Status**: DESIGNED / PLANNING ONLY (DO NOT IMPLEMENT UNTIL SPEC 089 IS CLOSED)  
**Author**: Antigravity Assistant & Technical Architecture  
**Baseline**: Requiere cierre exitoso de Spec 089  
**Target Outcome**: Reemplazar la inspección estricta de código fuente de `main()` en `tests/test_startup_grace_period.py:222` por aserciones de comportamiento funcional black-box mediante `SupervisoryBehavioralHarness`, eliminando el bloqueo que impedía refactorizar `main()`.

---

## 1. Problem Statement & Motivation

En [`tests/test_startup_grace_period.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/tests/test_startup_grace_period.py#L218-L250), la clase de prueba `TestStartupGraceInvariantContracts` contiene:
```python
source = inspect.getsource(main)
startup = source.index("elif startup_guard_active")
sustained = source.index("elif (now_ts - state.low_since_ts) < low_sustained_seconds")
interlock = source.index("elif not interlock_decision.allowed")
cooldown = source.index("last_reboot_ts = None")
hashcore = source.index('run_hashcore_cli(hashcore_cfg, miner, "reboot"')
self.assertLess(startup, sustained)
self.assertLess(sustained, interlock)
self.assertLess(interlock, cooldown)
self.assertLess(cooldown, hashcore)
```

Este tipo de prueba es un **anti-patrón de acoplamiento de pruebas**:
- No evalúa el comportamiento en tiempo de ejecución del sistema, sino que analiza la posición exacta de cadenas de texto en el archivo fuente de `main()`.
- Cualquier intento legítimo de mover la lógica de interlocks a un Hook en `app/core/engine.py` hace que este test falle inmediatamente.
- La Spec 070 ya introdujo el [`SupervisoryBehavioralHarness`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/tests/test_supervisory_core_behavioral.py) para evaluar estas precedencias de forma funcional y black-box.

---

## 2. User Stories & Value Proposition

### User Story 1: Desbloqueo Arquitectónico
> **Como** arquitecto de software,  
> **Quiero** que los tests unitarios verifiquen contratos funcionales y no la sintaxis rígida de un archivo,  
> **Para que** `main()` pueda ser transformado en un orquestador limpio y modular sin falsos positivos de prueba.

---

## 3. Scope & Boundaries

### Included (In Scope)
* Refactorizar `TestStartupGraceInvariantContracts` en `tests/test_startup_grace_period.py`.
* Validar que todas las invariantes de precedencia (Startup Guard > Sustained LOW > Interlocks > Cooldown > Hashcore) sigan verificadas al 100% mediante el harness conductual.
* Auditar toda la suite `tests/` para certificar que ningún otro test inspeccione el AST o strings de `main()`.

### Excluded (Out of Scope)
* NO modificar el código de producción de `miner_monitor.py` (esta spec es 100% de tests).
* NO relajar los criterios de seguridad de auto-reboot.

---

## 4. Invariants & Safety Gates

1. **Invariante Single-Spec**: Esta spec NO debe ser implementada mientras Spec 089 esté abierta.
2. **Invariante de Test Suite**: $\ge 1522$ tests PASS.
