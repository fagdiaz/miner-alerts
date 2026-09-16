# Spec 070: Modularización del Core Fase B — Desacoplamiento Seguro de inspect.getsource(main) (ST-05)

**ID**: 070  
**Módulos**: `app/miner_monitor.py`, `app/core/engine.py`, `tests/`  
**Riesgo**: Alto (Regresión potencial de 37 tests de invariantes constitucionales legados)  
**Prioridad**: P2 (Media)  
**Estado**: Especificado  
**Dependencias**: Spec 060 (Core Daemon Architecture), Spec 065 (Supervisory Hooks Pipeline)  

---

## 1. Contexto y Problema

Durante el desarrollo de las versiones V1 a V4 de Miner Alerts, se implementó una técnica de verificación de seguridad basada en inspección estática del código fuente en tiempo de ejecución:
```python
source = inspect.getsource(main)
self.assertIn("state.low_since_ts = None", restart_reset)
self.assertIn("elif (\n            new_state == STATE_HASHBOARD", hashboard_branch)
```

Actualmente, 4 suites de tests validan 37 invariantes utilizando este método:
1. `tests/test_auto_reboot_signal_gate.py`: 8 tests.
2. `tests/test_hashboard_auto_reboot.py`: 8 tests.
3. `tests/test_reboot_safety.py`: 13 tests.
4. `tests/test_vnish_hashboard_detection.py`: 8 tests.

### El Problema de Acoplamiento Rígido:
- Si bien esta técnica impidió regresiones accidentales en el bucle procedural de `main()`, se convirtió en una **barrera arquitectónica infranqueable** que bloquea la modularización del sistema: cualquier intento de extraer la lógica procedural hacia `AcquisitionHook`, `DetectionHook` o `ActuatorHook` hace fallar inmediatamente estos 37 tests por discrepancia de texto plano o indentación.

---

## 2. Estrategia de Solución: Migración en 3 Fases con Paridad Dual

Para eliminar el acoplamiento sin correr el menor riesgo de regresión funcional ni alterar la seguridad del auto-reboot:

### Fase 1: Construcción del Arnés de Comportamiento (`Behavioral Test Harness`)
- Se crea `tests/test_supervisory_core_behavioral.py`.
- Este arnés no analiza texto plano, sino que evalúa el **comportamiento de caja negra** invocando directamente `CoreSupervisoryEngine.execute_tick()` con un `MonitorContext` mockeado.
- Reproduce de manera determinista cada una de las 37 reglas de negocio:
  1. *Compuertas de Señal*: `auto_reboot_signal` clasificado como no elegible resetea `low_since_ts` y cancela el auto-reboot.
  2. *Secuencia de Interlocks*: Orden estricto de los 6 interlocks (startup grace -> sustained timer -> firmware transition -> cooling cooldown -> reboot window -> hashcore execution).
  3. *Invariable Hashboard*: Detección de placas faltantes (`active_boards < expected_boards`) priorizada sobre la caída de hashrate.

### Fase 2: Certificación de Paridad Dual (100% de Tests Activos)
- Ambas suites de pruebas coexisten simultáneamente en el repositorio:
  - 37 tests legados de `inspect.getsource(main)`
  - 37 nuevos tests de comportamiento funcional
- La suite completa debe reportar $\ge 1109$ tests globales PASS (1072 actuales + 37 nuevos).
- Se prohíbe tocar `main()` hasta que la paridad sea total y demostrada.

### Fase 3: Refactorización Hacia Hooks Desacoplados
- Con la suite de comportamiento protegiendo todas las invariantes funcionales, se refactoriza de forma segura el bucle de `main()` delegando la adquisición, detección y actuación a los hooks formales de `CoreSupervisoryEngine`.
- Los 4 archivos de test legados se actualizan para verificar la lógica a través del arnés o de funciones puras, eliminando la inspección textual de `main()`.

---

## 3. Requisitos Inviolables

1. **RI-01 (Invariante de Tests Crecientes)**: `len(tests_pass)` sólo puede aumentar ($\ge 1072 \rightarrow \ge 1109$), jamás decrecer.
2. **RI-02 (Cero Modificaciones a Producción en Fase 1 y 2)**: El archivo `app/miner_monitor.py` no debe modificarse durante la construcción del arnés de comportamiento.
3. **RI-03 (Preservación Absoluta de Seguridad de Auto-Reboot)**: Ningún interlock, tiempo de cooldown o comprobación de Hashcore Toolkit puede ser alterado o flexibilizado.

---

## 4. Configuración

No requiere cambios de configuración en `config.json`.
