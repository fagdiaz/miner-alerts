# Plan de Implementación: Spec 050 - Post-Blackout Recovery Guard

**Feature Directory**: `specs/050-post-blackout-recovery`  
**Fecha**: 2026-09-10  
**Motor Principal**: Gemini 3.8 Flash High  
**Condiciones de Control**: RFC C1-C10 (Mobile-First UX <= 32 cols, no-bloqueo, concurrencia segura)  
**Parent Plans**: `specs/048-safe-fleet-shutdown/plan.md`, `specs/049-thermal-purge-ramp/plan.md`

---

## 1. Arquitectura y Desglose de Componentes

### 1.1 Principio de Detección y Supervisión
- **Módulo Puro de Dominio (`app/governance/post_blackout_guard.py`)**:
  * Funciones desacopladas para evaluación de estado:
    - `evaluate_miner_post_blackout(miner_status, uptime, state, in_maintenance, is_snoozed) -> RecoveryAction`
    - `filter_recoverable_miners(miners_telemetry, farm_state, config) -> List[RecoveryTarget]`
  * Formateadores Mobile-First strictly $\le 32$ columnas visibles:
    - `render_post_blackout_alert(stopped_miners, auto_resume_seconds=None)`
    - `render_recovery_action_card(resumed_miners, automated=False)`
- **Interlocks de Seguridad Requeridos**:
  1. **Interlock de Mantenimiento / Snooze**: Si `is_in_maintenance(miner_id)` o `is_snoozed(miner_id)` está activo, el equipo se excluye de plano de la recuperación (apagado intencional).
  2. **Interlock de Transición / Arranque**: Si el minero está en `starting`, `benchmarking` o `uptime < 60s`, se considera en arranque normal y no se emite alerta.
  3. **Interlock de Confirmación (Hysteresis)**: Requiere $\ge 2$ ciclos consecutivos en estado detenido (`consecutive_stopped >= 2`) antes de emitir notificación.
  4. **Interlock Térmico**: Si cualquier sensor reporta $\ge 85.0^\circ\text{C}$, se bloquea la orden de reanudación.

### 1.2 Mecanismo de Reanudación y Botones Telegram
- **Notificación Interactiva con Callback Telegram**:
  * Callback `pbr:resume:all` y `pbr:resume:<id>`: Reutiliza la lógica segura de `execute_parallel_resume` y restauración de coolers (100% PWM) de la Spec 048/049.
  * Botón táctil `[ ▶️ Reanudar Flota ]` (o individual) y botón de descarte `[ 🔕 Silenciar 1h ]`.
- **Auto-Reanudación Autónoma Opcional**:
  * Configurable vía `config.json`:
    ```json
    "post_blackout_guard": {
        "enabled": true,
        "auto_resume": false,
        "grace_period_seconds": 180,
        "confirm_ticks": 2
    }
    ```
  * Si `auto_resume` está habilitado, tras `grace_period_seconds` de estabilidad sin respuesta del operador, el monitor ejecuta la reanudación autónoma y notifica el resultado.

### 1.3 Módulos Involucrados
1. `app/governance/post_blackout_guard.py` (Nuevo módulo de dominio y tarjetas).
2. `app/governance/__init__.py` (Exportación pública).
3. `app/miner_monitor.py` (Tick hook de supervisión, retención de timestamps y callbacks).
4. `app/config.example.json` (Documentación del bloque de configuración).
5. `tests/test_post_blackout_guard.py` (Pruebas unitarias de dominio y formato).
6. `tests/test_post_blackout_integration.py` (Pruebas de integración del bucle y callbacks).

---

## 2. Fases de Entrega

### Fase 1: Dominio Puro, Modelos y Tarjetas Móviles
- [ ] **P1.1**: Implementar `app/governance/post_blackout_guard.py` con `PostBlackoutTarget`, `evaluate_miner_post_blackout`, `render_post_blackout_alert` y `render_recovery_action_card`.
- [ ] **P1.2**: Implementar `tests/test_post_blackout_guard.py` validando lógica pura, interlocks y ancho $\le 32$ columnas.

### Fase 2: Integración en Bucle del Monitor y Callbacks Telegram
- [ ] **P2.1**: Conectar la supervisión periódica en el bucle principal de `app/miner_monitor.py` evaluando mineros en cada tick.
- [ ] **P2.2**: Conectar callbacks Telegram (`pbr:resume:all`, `pbr:resume:<id>`) enlazando a `execute_parallel_resume`.
- [ ] **P2.3**: Conectar la lógica de auto-reanudación tras ventana de gracia y persistencia de eventos en `event_store`.

### Fase 3: Pruebas de Integración, Documentación y Cierre
- [ ] **P3.1**: Desarrollar `tests/test_post_blackout_integration.py` cubriendo ciclo completo (detección $\to$ alerta Telegram $\to$ botón $\to$ reanudación $\to$ auto-resume).
- [ ] **P3.2**: Ejecutar suite global completa de tests ($\ge 727$ PASS).
- [ ] **P3.3**: Registrar evidencia en `evidence.md`, actualizar `DEVELOPMENT_LOG.md` y `ROADMAP.md`.

---

## 3. Matriz de Validación de Calidad

| Condición | Requisito | Mecanismo de Verificación |
|---|---|---|
| **C1** | Formato móvil $\le 32$ cols | Tests unitarios exhaustivos con `visible_line_width()` |
| **C2** | No-bloqueo del monitor principal | Evaluación O(1) en memoria; reanudación vía hilos desacoplados |
| **C3** | Respeto a Mantenimiento y Snooze | Tests con flags `maintenance: true` y snooze activo verificando supresión total |
| **C4** | Histeresis contra estados transitorios | Confirmación de $\ge 2$ ticks requerida antes de alertar |
| **C5** | Reanudación concurrente segura | Reutilización probada de `execute_parallel_resume` con restauración térmica |
| **C6** | Cobertura de tests | 100% tests PASS sin regresiones |
