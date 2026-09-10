# Plan de Implementación: Spec 049 - Active Thermal Purge Ramp & Acoustic Contrast on Safe Shutdown

**Feature Directory**: `specs/049-thermal-purge-ramp`
**Fecha**: 2026-09-10
**Motor Principal**: Gemini 3.8 Flash High
**Condiciones de Control**: RFC C1-C10
**Parent Plan**: `specs/048-safe-fleet-shutdown/plan.md`

---

## 1. Arquitectura y Desglose de Componentes

### 1.1 Principio de Operación y Rampa Térmica Activa
- **Rampa Activa de Ventilación (`app/governance/fleet_shutdown.py`)**:
  * Función paralela `execute_parallel_fan_duty(miners, duty_percent, password, timeout=2.5)`.
  * Utiliza `ThreadPoolExecutor(max_workers=min(4, len(miners)))`.
  * Al confirmarse la parada segura (`sd_cfm`): se despacha `execute_parallel_shutdown` (hash en 0W) e inmediatamente `execute_parallel_fan_duty(miners, 100)` para acelerar los ventiladores al 100% de PWM.
- **Temporizador de Purga y Caída a Reposo Acústico**:
  * En el hilo desacoplado `ShutdownPurgeNotify`, durante los 45 segundos los ventiladores permanecen al 100%.
  * Al expirar los 45s exactos: se despacha `execute_parallel_fan_duty(miners, 40)` para hacer caer instantáneamente los ventiladores al piso de reposo (40% PWM / ~2.400 RPM, cayendo sin carga a reposo de servidor ~720 RPM).
  * Simultáneamente, se envía la tarjeta `render_safe_area_card` a Telegram.
- **Restauración de Ventilación en `/resume`**:
  * Al reactivar el minado, se asegura que los ventiladores no queden atrapados en el piso del 40%, restableciendo la gestión del Fan Governor o subiendo preventivamente a régimen normal.
- **Tarjetas Mobile-First ($\le 32$ columnas)**:
  * Actualización de `render_shutdown_in_progress` y `render_safe_area_card` para incluir las métricas acústicas y de purga activa.

### 1.2 Módulos Afectados
1. `app/governance/fleet_shutdown.py`:
   - `execute_parallel_fan_duty(miners, duty_percent, password, timeout=2.5, fan_fn=None)`
   - Actualización de textos en `render_shutdown_in_progress` y `render_safe_area_card`.
2. `app/miner_monitor.py`:
   - Despacho de rampa al 100% en `sd_cfm` post-parada de hash.
   - Despacho de piso al 40% en `_purge_and_notify` al expirar los 45 segundos.
   - Restauración de control de coolers en `resume`.
3. `tests/test_fleet_shutdown.py`:
   - Pruebas unitarias de `execute_parallel_fan_duty` (éxito, fallos parciales, timeouts).
   - Pruebas de renderizado mobile-first ($\le 32$ columnas).
4. `tests/test_safe_fleet_shutdown_integration.py`:
   - Pruebas de integración de la secuencia completa: `sd_cfm` $\to$ rampa 100% $\to$ purga 45s $\to$ reposo 40% $\to$ área segura.

---

## 2. Fases de Entrega

### Fase 1: Dominio Puro y Despachador de Coolers
- [x] **P1.1**: Implementar `execute_parallel_fan_duty` en `app/governance/fleet_shutdown.py`.
- [x] **P1.2**: Actualizar `render_shutdown_in_progress` y `render_safe_area_card` con las leyendas de purga activa y reposo acústico ($\le 32$ cols).
- [x] **P1.3**: Desarrollar pruebas unitarias en `tests/test_fleet_shutdown.py`.

### Fase 2: Integración en Monitor y Secuencia de Purga
- [x] **P2.1**: Conectar la rampa al 100% en el handler de `sd_cfm` en `app/miner_monitor.py`.
- [x] **P2.2**: Conectar la caída al 40% (reposo acústico) en el hilo daemon `ShutdownPurgeNotify` tras los 45 segundos.
- [x] **P2.3**: Conectar la restauración de ventilación en el bloque de `resume`.
- [x] **P2.4**: Integrar registro de eventos en `event_store` para la purga y el reposo.

### Fase 3: Pruebas de Integración, Documentación y Cierre
- [x] **P3.1**: Desarrollar pruebas de integración en `tests/test_safe_fleet_shutdown_integration.py`.
- [x] **P3.2**: Ejecutar suite completa ($\ge 723$ tests PASS, 727 PASS obtenidos).
- [x] **P3.3**: Registrar evidencia en `evidence.md`, actualizar `DEVELOPMENT_LOG.md` y `ROADMAP.md`.

---

## 3. Matriz de Validación de Calidad

| Condición | Requisito | Mecanismo de Verificación |
|---|---|---|
| **C1** | Líneas de datos $\le$ 32 cols visibles | Verificación programática con `visible_line_width()` en tests |
| **C2** | Pureza y no-bloqueo del monitor | Rampa y caída ejecutadas en hilos desacoplados sin frenar el polling |
| **C3** | Rampa 100% inmediata | Despacho concurrente en paralelo con ThreadPoolExecutor |
| **C4** | Caída a reposo acústico sincronizada | Ejecución al segundo 45 simultánea a la notificación |
| **C5** | Seguridad en reanudación | Garantizar que `/resume` desactive el piso de reposo |
| **C6** | Suite completa de tests | 100% tests PASS sin regresiones |
