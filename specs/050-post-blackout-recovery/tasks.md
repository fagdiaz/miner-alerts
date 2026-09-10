# Tareas: Spec 050 - Post-Blackout Recovery Guard

## Estado General
- **Total Tareas**: 6
- **Completadas**: 6
- **Pendientes**: 0

---

## Tareas de Fase 1 (Dominio Puro, Modelos y Tarjetas Móviles)

- [x] **T1: Implementar `app/governance/post_blackout_guard.py`**:
  - Definir estructuras de datos: `PostBlackoutTarget`, `PostBlackoutDecision`.
  - Implementar lógica pura de evaluación: `evaluate_miner_post_blackout(...)` e interlocks de seguridad (mantenimiento Spec 048, snooze Spec 033, guardia de inicio, interlock térmico).
  - Implementar renderizadores Mobile-First strictly <= 32 columnas visibles:
    * `render_post_blackout_alert(stopped_miners, auto_resume_seconds=None)`
    * `render_recovery_action_card(resumed_miners, automated=False)`
  - Generar teclados inline: `[ ▶️ Reanudar Flota ]` (o individual) y `[ 🔕 Silenciar 1h ]`.
  - Exportar en `app/governance/__init__.py`.

- [x] **T2: Suite de Pruebas Unitarias de Dominio en `tests/test_post_blackout_guard.py`**:
  - Tests para detección de estado `stopped` vs estados normales/transitorios (`mining`, `starting`).
  - Tests para interlocks: exclusión de mineros en mantenimiento o con snooze activo.
  - Tests para histeresis (requerimiento de $\ge 2$ ticks consecutivos).
  - Validación de ancho de líneas de las tarjetas con `visible_line_width() <= 32`.

---

## Tareas de Fase 2 (Integración en Monitor, Callbacks y Auto-Reanudación)

- [x] **T3: Integrar Hook de Supervisión en Bucle de `app/miner_monitor.py`**:
  - Rastreo en memoria de mineros con `stopped` sostenido (`consecutive_stopped_ticks`, `first_stopped_ts`).
  - Evaluación en cada ciclo del monitor tras adquisición de telemetría.
  - Despacho desacoplado de la alerta Telegram una única vez por episodio o tras histeresis.

- [x] **T4: Conectar Callbacks Telegram y Despacho de Reanudación**:
  - Enrutamiento de callback `pbr:resume:all` y `pbr:resume:<id>` en el dispatcher de callbacks del monitor.
  - Invocación de `execute_parallel_resume` y `execute_parallel_fan_duty(100)` para salir de modo reposo e iniciar hash seguro.
  - Notificación de confirmación `render_recovery_action_card`.

- [x] **T5: Soporte de Auto-Reanudación y Registro de Eventos**:
  - Lógica de auto-reanudación si `config["post_blackout_guard"]["auto_resume"] == True` tras expirar `grace_period_seconds`.
  - Persistencia de eventos en `event_store` (`post_blackout_alert`, `post_blackout_resume_manual`, `post_blackout_resume_auto`).
  - Documentar opciones de configuración en `app/config.example.json`.

---

## Tareas de Fase 3 (Pruebas de Integración, Validación y Cierre)

- [x] **T6: Pruebas de Integración y Certificación Global**:
  - Desarrollar `tests/test_post_blackout_integration.py` cubriendo el flujo completo con mocks (detección -> alerta -> callback / auto-resume -> event store).
  - Validación de compilación `py_compile` en todos los archivos modificados.
  - Ejecutar suite global completa de pruebas (749 tests PASS).
  - Documentar evidencia en `specs/050-post-blackout-recovery/evidence.md`.
  - Registrar en `docs/audit/DEVELOPMENT_LOG.md` y actualizar `docs/speckit/ROADMAP.md`.
