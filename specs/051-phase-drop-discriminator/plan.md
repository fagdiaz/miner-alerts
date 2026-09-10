# Plan de Implementación: Spec 051 - Fast Phase Drop vs Connectivity Discriminator

**Feature Directory**: `specs/051-phase-drop-discriminator`  
**Fecha**: 2026-09-10  
**Motor Principal**: Gemini 3.8 Flash High  
**Condiciones de Control**: RFC C1-C10 (Mobile-First UX <= 32 cols, no-bloqueo, evaluación O(1))  
**Parent Plans**: `specs/040-dynamic-voltage-presets/plan.md`, `specs/022-adaptive-acquisition/plan.md`

---

## 1. Arquitectura y Desglose de Componentes

### 1.1 Principio de Operación y Clasificación Heurística
- **Módulo Puro de Dominio (`app/governance/phase_drop_discriminator.py`)**:
  * Funciones desacopladas para evaluación de eventos concurrentes:
    - `evaluate_phase_drop(failed_miners, responded_miners, host_network_ok, maintenance_miner_ids, elevator_groups) -> PhaseDropAssessment`
    - `check_host_gateway_reachability(gateway_host, timeout=0.3) -> bool`
  * Formateadores Mobile-First strictly $\le 32$ columnas visibles:
    - `render_phase_drop_alert(assessment: PhaseDropAssessment) -> str`
- **Lógica de Decisión y Veredictos**:
  1. **`NORMAL`**: Todos los equipos responden o los fallos son aislados e individuales.
  2. **`NETWORK_ISOLATION`**: Fallan todos los mineros Y el host no puede alcanzar el gateway/DNS (problema de cable/switch del host). Se suprime la falsa alarma eléctrica.
  3. **`PHASE_DROP_ELEVATOR`**: El host tiene red, pero el 100% de los mineros de un elevador específico (ej. `elevator_1`: S19JPRO-23 y 24) caen al unísono en el mismo ciclo, mientras el elevador gemelo sigue activo.
  4. **`PHASE_DROP_FLEET`**: El host tiene red, pero el 100% de los mineros de todos los elevadores caen simultáneamente (corte total de la línea de cabecera o disparo de térmica general).

### 1.2 Mecanismo de Supresión de Histeresis e Integración
- **Bypass de Histeresis en Monitor**:
  * Ante un veredicto `PHASE_DROP_*`, el monitor no espera la acumulación de 3 fallos consecutivos (`fails_before_alert`) ni aguarda ciclos adicionales de 30s.
  * Se encola inmediatamente la alerta a Telegram con prioridad `HIGH` (Spec 030).
- **Módulos Afectados**:
  1. `app/governance/phase_drop_discriminator.py` (Nuevo módulo).
  2. `app/governance/__init__.py` (Exportación pública).
  3. `app/miner_monitor.py` (Hook en análisis post-adquisición).
  4. `tests/test_phase_drop_discriminator.py` (Pruebas unitarias de dominio y formato móvil).
  5. `tests/test_phase_drop_integration.py` (Pruebas de integración del bucle de adquisición).

---

## 2. Fases de Entrega

### Fase 1: Dominio Puro, Evaluador y Tarjetas Móviles
- [ ] **P1.1**: Implementar `app/governance/phase_drop_discriminator.py` con `PhaseDropAssessment`, `evaluate_phase_drop` y `render_phase_drop_alert`.
- [ ] **P1.2**: Implementar `tests/test_phase_drop_discriminator.py` validando lógica de veredictos y ancho $\le 32$ columnas.

### Fase 2: Integración en Adquisición y Bypass de Tiempos Muertos
- [ ] **P2.1**: Conectar la verificación de gateway y el evaluador de caídas en el procesador de resultados de adquisición de `app/miner_monitor.py`.
- [ ] **P2.2**: Conectar el despacho inmediato de la alerta Telegram suprimiendo la histeresis lenta.
- [ ] **P2.3**: Registrar eventos en `event_store` con acción `electrical_phase_drop`.

### Fase 3: Pruebas de Integración, Documentación y Cierre
- [ ] **P3.1**: Desarrollar `tests/test_phase_drop_integration.py` simulando caídas por elevador y caídas de red.
- [ ] **P3.2**: Ejecutar suite completa de pruebas ($\ge 749$ PASS).
- [ ] **P3.3**: Registrar evidencia en `evidence.md`, actualizar `DEVELOPMENT_LOG.md` y `ROADMAP.md`.

---

## 3. Matriz de Validación de Calidad

| Condición | Requisito | Mecanismo de Verificación |
|---|---|---|
| **C1** | Formato móvil $\le 32$ cols | Tests unitarios exhaustivos con `visible_line_width()` |
| **C2** | Latencia de alerta $< 3.0$s | Supresión de timeouts sucesivos y despacho en el primer ciclo |
| **C3** | Discriminación de aislamiento de red | Verificación de gateway local impide falsos positivos |
| **C4** | Exclusión de mantenimiento manual | Equipos en `/shutdown` se omiten del cálculo de caída |
| **C5** | Cobertura de tests | 100% tests PASS sin regresiones |
