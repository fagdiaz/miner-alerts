# Plan de Implementación: Spec 052 - Scheduled Maintenance Windows & Soft Pre-Ramp

**Feature Directory**: `specs/052-maintenance-scheduler`  
**Fecha**: 2026-09-10  
**Motor Principal**: Gemini 3.8 Flash High  
**Condiciones de Control**: RFC C1-C10 (Mobile-First UX <= 32 cols, precisión temporal, no-bloqueo)  
**Parent Plans**: `specs/048-safe-fleet-shutdown/plan.md`, `specs/049-thermal-purge-ramp/plan.md`, `specs/040-dynamic-voltage-presets/plan.md`

---

## 1. Arquitectura y Desglose de Componentes

### 1.1 Principio de Operación y Máquina de Estados de Ventanas
- **Módulo Puro de Dominio (`app/governance/maintenance_scheduler.py`)**:
  * Funciones desacopladas para parsing y evaluación temporal:
    - `parse_schedule_expression(time_expr, duration_expr, now_ts) -> Tuple[bool, Optional[ScheduledWindow], Optional[str]]`
    - `evaluate_window_stage(window: ScheduledWindow, now_ts: float) -> WindowStageAction`
  * Estados de la Ventana (`ScheduledStage`):
    1. `PENDING`: Ventana programada a la espera de entrar en pre-rampa ($t < T - 10\text{m}$).
    2. `PRE_RAMP_TIER_1`: A T-10m, desescalado a preset intermedio (ej. 2300W).
    3. `PRE_RAMP_TIER_2`: A T-5m, desescalado a preset mínimo de trabajo (2100W).
    4. `EXECUTING`: A T-0, parada suave de hash (0W), rampa 100% (45s) y reposo a 40%.
    5. `SNOOZED`: Ventana en mantenimiento con auto-snooze activo.
    6. `CANCELLED` / `COMPLETED`: Estados terminales limpios.
  * Formateadores Mobile-First strictly $\le 32$ columnas:
    - `render_schedule_confirmation_card(window: ScheduledWindow) -> str`
    - `render_scheduled_list_card(windows: List[ScheduledWindow]) -> Tuple[str, Dict[str, Any]]`
    - `render_pre_ramp_card(stage: int, target_w: int) -> str`

### 1.2 Persistencia Atómica en Estado y Supervisión Periódica
- **Persistencia en `state.json`**:
  * Guardado atómico del objeto serializado `scheduled_maintenance` bajo `state_lock`.
  * Si el servicio se reinicia, la ventana activa se reconstituye sin perder los tiempos objetivo.
- **Módulos Afectados**:
  1. `app/governance/maintenance_scheduler.py` (Nuevo módulo).
  2. `app/governance/__init__.py` (Exportación pública).
  3. `app/miner_monitor.py` (Hook de supervisión periódica y comandos Telegram `/schedule_maintenance`, `/scheduled`, callback `sch:cancel`).
  4. `tests/test_maintenance_scheduler.py` (Pruebas unitarias de parsing, etapas y tarjetas).
  5. `tests/test_maintenance_scheduler_integration.py` (Pruebas de integración del ciclo de pre-rampa y ejecución a T-0).

---

## 2. Fases de Entrega

### Fase 1: Dominio Puro, Parser Temporal y Tarjetas Móviles
- [ ] **P1.1**: Implementar `app/governance/maintenance_scheduler.py` con `ScheduledWindow`, `parse_schedule_expression`, `evaluate_window_stage` y formateadores de tarjetas.
- [ ] **P1.2**: Implementar `tests/test_maintenance_scheduler.py` validando parsing relativo/absoluto, transiciones de etapa y ancho móvil $\le 32$ cols.

### Fase 2: Integración en Monitor, Persistencia y Comandos Telegram
- [ ] **P2.1**: Integrar persistencia de ventanas en `save_state` y `load_state`.
- [ ] **P2.2**: Conectar la supervisión periódica en cada tick del monitor ejecutando desescalado a T-10m/T-5m y parada a T-0.
- [ ] **P2.3**: Registrar comandos Telegram `/schedule_maintenance` y `/scheduled` con callback interactivo de cancelación (`sch:cancel`).

### Fase 3: Pruebas de Integración, Documentación y Cierre
- [ ] **P3.1**: Desarrollar `tests/test_maintenance_scheduler_integration.py` simulando avance de reloj virtual.
- [ ] **P3.2**: Ejecutar suite completa de pruebas ($\ge 749$ PASS).
- [ ] **P3.3**: Registrar evidencia en `evidence.md`, actualizar `DEVELOPMENT_LOG.md` y `ROADMAP.md`.

---

## 3. Matriz de Validación de Calidad

| Condición | Requisito | Mecanismo de Verificación |
|---|---|---|
| **C1** | Formato móvil $\le 32$ cols | Verificación en tests con `visible_line_width()` |
| **C2** | Precisión temporal | Pre-rampa a T-10m y parada a T-0 exactos |
| **C3** | Resiliencia a reinicios | Reconstitución desde `state.json` validada en tests |
| **C4** | Desescalado suave comprobado | Reducción previa de potencia antes de corte de hash |
| **C5** | Cobertura de tests | 100% tests PASS sin regresiones |
