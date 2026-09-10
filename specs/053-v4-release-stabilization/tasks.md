# Tareas: Spec 053 - V4 Concurrency Hardening & Release Stabilization

## Estado General
- **Total Tareas**: 6
- **Completadas**: 6
- **Pendientes**: 0

---

## Tareas de Fase 1 (Auditoría de Concurrencia y Refuerzo de Cerrojos)

- [x] **T1: Auditoría de Estado Compartido en `app/miner_monitor.py`**:
  - Asegurar copias atómicas en `save_state()` para evitar `RuntimeError: dictionary changed size during iteration` ante mutaciones concurrentes.
  - Proteger y aislar referencias a `_ACTIVE_SCHEDULED_WINDOW` y listas mutables (`auto_reboot_timestamps`).
  - Migrar `state_lock` a `threading.RLock()` para garantizar reentrancia segura en toda la jerarquía de llamadas.
  - Verificar no-bloqueo en callbacks interactivos (`answer_callback_query` inmediato).

---

## Tareas de Fase 2 (Suite de Validación Mobile-First <= 32 Columnas)

- [x] **T2: Implementar Suite de Validación Mobile-First `tests/test_mobile_compliance.py`**:
  - Probar exhaustivamente todas las tarjetas del sistema:
    * Estado, fans, eficiencia, presets (Spec 046).
    * Balancer, elevadores, digest, snoozed, events (Spec 047).
    * Parada en progreso, área segura, reanudación y errores (Specs 048-049).
    * Alerta post-blackout y reanudación (Spec 050).
    * Corte de fase por elevador, corte general y aislamiento de host (Spec 051).
    * Confirmación, estado, pre-rampa y cancelación de mantenimiento (Spec 052).
    * Menús y topics del Centro de Ayuda (Spec 045).
  - Assert estricto de `visible_line_width(line) <= 32` en el 100% de las líneas (7/7 tests PASS).

---

## Tareas de Fase 3 (Suite de Estrés y Concurrencia V4)

- [x] **T3: Implementar Suite de Concurrencia `tests/test_v4_concurrency.py`**:
  - Simular hilos concurrentes llamando a `save_state()` mientras el bucle de adquisición y los comandos Telegram mutan estados simultáneamente.
  - Simular ejecución paralela de callbacks de parada, cancelación y reanudación.
  - Probar reentrancia de `state_lock` anidado.
  - Verificar cero bloqueos mutuos (deadlocks), cero excepciones y consistencia atómica (4/4 tests PASS).

---

## Tareas de Fase 4 (Ejecución de Regresión Completa y Evidencia)

- [x] **T4: Validación de Sintaxis y Suite Global**:
  - Compilación de sintaxis con `py_compile` en todo el proyecto.
  - Ejecución de la suite completa de pruebas unitarias y de integración (792/792 tests PASS en 13.4s).
  - Documentar resultados en `specs/053-v4-release-stabilization/evidence.md`.

---

## Tareas de Fase 5 (Documentación de Release y Cierre)

- [x] **T5: Actualizar Documentación del Proyecto**:
  - Registrar entrada más reciente en `docs/audit/DEVELOPMENT_LOG.md` para Spec 053.
  - Actualizar `docs/speckit/ROADMAP.md` y `docs/speckit/SPEC_PROGRAM.md` certificando el Release V4.0.0.

- [x] **T6: Commit y Push de Estabilización**:
  - Realizar commit de feature `feat(release): V4 Core Governance Concurrency Hardening & Release Stabilization (Spec 053)`.
  - Realizar `git push origin codex/022-adaptive-acquisition` (habilitado explícitamente para specs de estabilización).
  - Actualizar `prompt.txt`.
