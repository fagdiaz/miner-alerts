# Tareas: Spec 051 - Fast Phase Drop vs Connectivity Discriminator

## Estado General
- **Total Tareas**: 6
- **Completadas**: 6
- **Pendientes**: 0

---

## Tareas de Fase 1 (Dominio Puro, Evaluador y Tarjetas Móviles)

- [x] **T1: Implementar `app/governance/phase_drop_discriminator.py`**:
  - Definir enumeraciones y modelos: `PhaseDropVerdict`, `PhaseDropAssessment`, `PhaseDropConfig`.
  - Implementar lógica pura de evaluación: `evaluate_phase_drop(...)` correlacionando fallos por grupo eléctrico (`elevator_1`, `elevator_2`).
  - Implementar chequeo no bloqueante de conectividad de host `check_host_gateway_reachability(...)`.
  - Implementar renderizador Mobile-First strictly <= 32 columnas: `render_phase_drop_alert(...)`.
  - Exportar en `app/governance/__init__.py`.

- [x] **T2: Suite de Pruebas Unitarias en `tests/test_phase_drop_discriminator.py`**:
  - Tests para veredictos: `NORMAL`, `PHASE_DROP_ELEVATOR`, `PHASE_DROP_FLEET`, `NETWORK_ISOLATION`.
  - Tests para supresión en equipos bajo mantenimiento deliberado (Spec 048).
  - Verificación estricta de ancho de columnas de las tarjetas con `visible_line_width() <= 32`.

---

## Tareas de Fase 2 (Integración en Monitor y Despacho Inmediato)

- [x] **T3: Integrar Hook en Bucle de Adquisición de `app/miner_monitor.py`**:
  - Tras completar el epoch de adquisición, evaluar fallos concurrentes con `evaluate_phase_drop`.
  - Si el veredicto es `PHASE_DROP_*`, marcar bandera de bypass de histeresis.

- [x] **T4: Despacho Inmediato Telegram y Registro en EventStore**:
  - Despacho inmediato de tarjeta `render_phase_drop_alert` con prioridad `HIGH` (sin esperar 3 ticks consecutivos).
  - Persistencia de eventos en `event_store` con acción `electrical_phase_drop`.
  - Documentar configuración en `app/config.example.json`.

---

## Tareas de Fase 3 (Pruebas de Integración, Validación y Cierre)

- [x] **T5: Pruebas de Integración en `tests/test_phase_drop_integration.py`**:
  - Simular desconexión unísona mockeada de elevadores y validar emisión de alerta en $< 3$s.
  - Simular desconexión del host y verificar supresión de falsa alarma de fase.
  - Bypass de histeresis a `OFFLINE` y deduplicación en `episode_batch`.

- [x] **T6: Validación Global, Documentación y Cierre**:
  - Compilación de sintaxis con `py_compile`.
  - Ejecutar suite global completa de pruebas ($\ge 749$ tests PASS -> 767 tests PASS).
  - Documentar evidencia en `specs/051-phase-drop-discriminator/evidence.md`.
  - Actualizar `docs/audit/DEVELOPMENT_LOG.md` y `docs/speckit/ROADMAP.md`.
