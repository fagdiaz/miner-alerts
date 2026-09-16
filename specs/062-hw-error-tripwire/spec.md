# Feature Specification: Spec 062 — HW Error Tripwire & Rollback Automático de Overclock (GOV-01)

**Feature Directory**: `specs/062-hw-error-tripwire`
**Created**: 2026-09-15
**Status**: In Planning
**Initiative**: GOV-01 (Gobernanza de Overclock y Protección de Silicio)
**Audited by**: Claude Sonnet 4.6 Thinking (2026-09-15 — Correcciones incorporadas)
**Input**: Proteger el silicio de los ASICs cuando el balanceador dinámico (Spec 040) eleva la potencia a 2500W o 2700W y surgen Hardware Errors por degradación de pasta térmica o caída de tensión. Implementar un tripwire con umbral combinado (tasa porcentual y delta absoluto), cálculo de delta no volátil vía `EventStore`, candado de 48 horas contra re-escalado y mecanismo anti-cascada adversarial tras reboots.

---

## User Scenarios & Testing

### User Story 1 - Detección Precisa de Ráfagas de Errores HW y Rollback Inmediato (Priority: P1)

Como operador de la granja de minería, deseo que si un minero operando con overclock (2500W o 2700W) comienza a generar shares corruptos y acumula errores de hardware por encima del umbral de seguridad, el sistema desescale inmediatamente un peldaño la potencia configurada (por ejemplo, de 2700W a 2500W) sin esperar a que el equipo se cuelgue o reinicie.

**Why this priority**: Evita el consumo ineficiente de electricidad en shares inválidos y previene la degradación física acelerada de las placas de minado sometidas a estrés térmico y eléctrico.

**Independent Test**: Simular un minero en preset 2700W que acumula 250 HW errors en 10 minutos con una tasa de error del 0.8%, verificando que `evaluate_balancer_step` emite la acción `ACTION_STEP_DOWN_HW_ERRORS`, selecciona el preset 2500W y activa el candado temporal.

---

### User Story 2 - Blindaje Anti-Cascada Post-Reboot L1/L2 (Priority: P1)

Como administrador del sistema, deseo que si un minero cuyo overclock fue desescalado por el tripwire sufre un reinicio posterior (ya sea por caída de red, caída de hashrate o auto-reboot del monitor), el sistema recuerde de forma persistente el preset bloqueado y no permita que el firmware restaure automáticamente el overclock de 2700W al reiniciar.

**Why this priority**: Rompe el bucle adversarial en el que el firmware vuelve a aplicar 2700W tras el reinicio, reactivando los errores de hardware y el estrés de silicio.

**Independent Test**: Configurar un estado con `hw_error_lock_until_ts` en el futuro y `hw_error_locked_preset = "2500W"`. Simular un reinicio de minero con lectura de summary post-reboot y verificar que el monitor restaura y mantiene `2500W` durante la vigencia del candado de 48 horas.

---

### User Story 3 - Notificación Telegram Mobile-First de Protección de Silicio (Priority: P2)

Como operador en guardia, deseo recibir una notificación en Telegram formateada en tarjeta móvil vertical (ancho <= 32 columnas) cuando el tripwire se active, informando la cantidad de errores, la tasa porcentual, el ajuste de preset y el tiempo restante de bloqueo.

**Why this priority**: Proporciona visibilidad operativa inmediata para evaluar si un equipo requiere mantenimiento físico (limpieza, reapriete de bornes o cambio de pasta térmica).

**Independent Test**: Renderizar la tarjeta con `render_hw_error_tripwire_alert` y verificar que todas las líneas cumplen la restricción de ancho `<= 32` columnas.

---

## Functional Requirements

1. **FR-01 (Métricas de Errores HW no volátiles en `StabilityMetrics`)**:
   - Añadir campos `hw_errors_delta_10m: int` y `hw_error_rate_pct: float` a `StabilityMetrics`.
   - En `extract_miner_stability_metrics`, calcular `hw_errors_delta_10m` y `hw_error_rate_pct` comparando el último sample $T$ de telemetría contra el sample $T - 10\text{m}$ (entre 540s y 660s atrás) consultado en `EventStore` (`telemetry_samples`).
   - Manejar reinicios de contador de hardware de forma defensiva: si `hw_errors_total(T) < hw_errors_total(T - 10m)`, el delta es igual a `hw_errors_total(T)`.
   - Calcular `hw_error_rate_pct = (delta_hw / total_shares) * 100.0` si `total_shares > 0`, caso contrario `0.0`.

2. **FR-02 (Regla de Disparo del Tripwire en `evaluate_balancer_step`)**:
   - Nuevo tipo de acción: `ACTION_STEP_DOWN_HW_ERRORS = "STEP_DOWN_HW_ERRORS"`.
   - Configuración en `BalancerConfig`:
     * `hw_error_rate_threshold_pct: float = 0.5` (tasa mayor a 0.5%).
     * `hw_error_delta_threshold: int = 200` (al menos 200 errores en 10 minutos).
     * `hw_error_lock_hours: float = 48.0` (duración del candado de seguridad).
   - Condición de disparo: `metrics.hw_error_rate_pct >= cfg.hw_error_rate_threshold_pct AND metrics.hw_errors_delta_10m >= cfg.hw_error_delta_threshold`.
   - Si se cumple la condición y el minero no está en el escalón mínimo:
     * Emitir `ACTION_STEP_DOWN_HW_ERRORS` con objetivo `tiers[curr_idx - 1].name`.
     * Requiere escritura: `requires_write = True`.

3. **FR-03 (Candado de Seguridad y Persistencia en `state.json`)**:
   - Añadir `hw_error_lock_until_ts: Optional[float] = None` y `hw_error_locked_preset: Optional[str] = None` a `MinerState`.
   - Incluir ambos campos en la serialización (`_serialise_miner_state` en `StateManager` y `_build_state_payload` en `miner_monitor.py`) y en `load_state`.
   - Si `now < st.hw_error_lock_until_ts`:
     * Bloquear cualquier intento de escalado hacia arriba (`ACTION_STEP_UP_OPTIMIZE`).
     * Techo efectivo restringido a `st.hw_error_locked_preset`.

4. **FR-04 (Interlock Anti-Cascada Post-Reboot)**:
   - En la lógica de monitoreo de `miner_monitor.py`, si un minero reporta o descubre un preset de firmware superior a `st.hw_error_locked_preset` mientras el candado `st.hw_error_lock_until_ts > now` esté activo:
     * El sistema programa la re-aplicación del `hw_error_locked_preset` para impedir que el firmware permanezca en el preset alto por defecto.
   - El auto-reboot por `STATE_LOW` o `STATE_HASHBOARD` **no se bloquea**; el tripwire regula exclusivamente la potencia y no la supervisión de salud.

5. **FR-05 (Notificación Telegram y Tarjeta Móvil)**:
   - Implementar `render_hw_error_tripwire_card(...) -> str` en `app/governance/preset_balancer.py` o módulo de ayuda Telegram.
   - Estricto formato Mobile-First con ancho de línea `<= 32` columnas.
