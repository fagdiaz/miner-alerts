# Implementation Plan - Spec 055: Auto-Reboot ante Falla de Placa y Recuperación Automática de Hashboard

## User Review Required

> [!IMPORTANT]
> Esta spec introduce la capacidad de auto-recuperar mineros que entran en `STATE_HASHBOARD` (falla de placas 0/3 con hashrate 0.0 TH/s como la ocurrida en el Minero 23). Todos los interlocks constitucionales de seguridad (Guardián de inicio 600s, Cooldown 1800s, Ventana diaria max 3 reinicios, Guardián térmico 85°C y Guardián de flota) se aplican de manera idéntica y sin excepciones.
> Para garantizar que el desarrollo sea seguro y no sobrecargue la capacidad de razonamiento (~50% por iteración), el trabajo se divide en **4 Iteraciones Estrictamente Acotadas y Verificables**.

- [x] Auto-reinicio ante falla total de placas (`active_boards == 0` o `rate_ths == 0.0` durante 10 minutos).
- [x] Falla parcial (`0 < active_boards < expected_boards`) deshabilitada por defecto para evitar ciclos de reinicio en placas con desgaste físico permanente.

---

## 4 Iteraciones Bounded para Gemini 3.8 Flash High

### Iteración 1: Modelo de Datos, Configuración y Puerta de Señal Pura
- **Objetivo**: Modificar `MinerState` (`hashboard_since_ts: Optional[float] = None`), agregar claves de configuración en `app/config.example.json` y fallbacks en `app/miner_monitor.py`, y extender la función pura `auto_reboot_signal_allows_evaluation` con suite de tests dedicada `tests/test_hashboard_auto_reboot.py`.
- **Riesgo Operativo**: **0%** (solo clases de datos y funciones puras desacopladas; sin impacto en el bucle en vivo).

### Iteración 2: Temporización Sostenida de Hashboard en el Monitor
- **Objetivo**: Integrar la lógica de activación del temporizador `hashboard_since_ts = now_ts` al entrar a `STATE_HASHBOARD` y su reseteo al volver a `STATE_OK`. Suprimir los falsos logs de `blocked_by=not_low` reemplazándolos por `hashboard_not_sustained`.
- **Riesgo Operativo**: Muy bajo (solo observabilidad y temporización; sin disparo de acciones de reinicio).

### Iteración 3: Canalización de Interlocks y Decisión de Auto-Reinicio
- **Objetivo**: Conectar la condición de falla sostenida de placas a `evaluate_auto_reboot_interlocks`. Probar mediante mocks y QA mode que los 6 candados (Guardián de inicio, Cooldown, Ventana diaria, Térmico, Flota y Firmware) bloquean y autorizan el reinicio con precisión matemática.
- **Riesgo Operativo**: Medio (controlado mediante pruebas unitarias y cobertura QA previa a producción).

### Iteración 4: UX Telegram, Auditoría Completa, Documentación y Despliegue
- **Objetivo**: Diseñar tarjeta de Telegram para auto-reinicio por falla de placa, certificar 840+ tests PASS en la suite completa, actualizar `DEVELOPMENT_LOG.md`, `ROADMAP.md` y `DELIVERY_PLAN.md`, realizar commit y push, y reiniciar el servicio Windows `MinerAlerts` verificando PID y logs limpios.
- **Riesgo Operativo**: Bajo (certificación formal y puesta en marcha con rollback inmediato en caso de anomalía).

---

## Verification Plan

### Automated Tests
- `tests/test_hashboard_auto_reboot.py` (suite nueva de Spec 055).
- `tests/test_auto_reboot_signal_gate.py` (compatibilidad hacia atrás).
- Ejecutar `& ".\.venv\Scripts\python.exe" -m unittest discover -s tests`.
- Validar compilación con `& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py`.

### Production Rollout & Gate
- Reinicio del servicio Windows `MinerAlerts`.
- Inspección de `logs/out.log` para certificar que ningún minero sufra acciones espurias.
