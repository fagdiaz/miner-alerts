# Evidence: Spec 044 - Modo Silencio Inteligente con Temporizador Persistente y Thermal Guard

## Estado y Metadatos
- **Spec ID**: `044-silent-mode-thermal-guard`
- **Fecha**: 2026-09-08
- **Línea Base Inicial**: 602 tests PASS (Spec 043 certificado). Payload files: 61.
- **Resultado Global**: **COMPLETO Y CERTIFICADO** (621/621 tests PASS, 17 tests dedicados a Spec 044 + 17 tests de Command Center, 0 regresiones, payload 61 archivos).

---

## 1. Cumplimiento Constitucional P0 (Auditoría Claude Sonnet 4.6)

### Condición C1: Concurrencia No Bloqueante en Telegram Polling
- Las acciones de Telegram (`/silent` y `cc:act:silent:*`) operan exclusivamente sobre `MinerState` bajo `state_lock` y persisten con `save_state()`.
- No se realizan llamadas HTTP síncronas a las APIs de VNish dentro del hilo de polling de Telegram.
- La confirmación visual y el ACK (`answerCallbackQuery`) se emiten de forma instantánea (< 500ms).
- La aplicación física de límites de PWM es ejecutada de manera desacoplada por el Fan Governor en su ciclo normal de supervisión.

### Condición C2: Aislamiento de FSM y Reconciliación en Arranque
- Campos dedicados en `MinerState`: `silent_mode_active`, `silent_mode_revert_ts`, `silent_mode_prev_duty`, `silent_mode_prev_preset`, `silent_mode_target_max_duty`.
- Totalmente desacoplados e independientes de `snooze_until_ts` (silenciamiento de software vs límite físico de actuadores).
- En `first_tick` tras reinicio de Windows o NSSM: se analiza si el temporizador expiró durante el downtime del servicio; de ser así, se purga el estado inmediatamente y se notifica al usuario vía Telegram para no operar con fans reducidos y potencia desprotegida.

### Condición C3: Coexistencia Dinámica con Fan Governor
- Inyección de `max_fan_duty_percent` dinámico al gobernador (`silent_mode_target_max_duty`, por defecto 70% PWM, mínimo 40% PWM).
- El Fan Governor modula dentro de la ventana acústica permitida sin competir contra el modo silencio ni considerar error el techo acotado.

### Condición C4: Thermal Guard y Desactivación Atómica
- Ante evento térmico crítico (`EMERGENCY_SPIKE` a ≥ 83.5°C o `FAILSAFE_FAULT`), el gobernador anula atómicamente el modo silencio (`silent_mode_active = False`), persiste el estado a disco en `state.json` bajo `state_lock`, fuerza ventiladores al 100% PWM y despacha una alerta crítica de emergencia por Telegram.

---

## 2. Verificación de Compilación de Sintaxis (`py_compile`)
```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py app\telegram\command_center.py app\telegram\__init__.py tests\test_command_center.py tests\test_silent_mode.py
# Salida: Código 0, sin errores ni warnings.
```

---

## 3. Certificación de Suite Completa de Tests (621/621 PASS)
```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
```
**Resultado**:
```text
Ran 621 tests in 10.947s

OK
```

---

## 4. Certificación de Release Audit
```powershell
& ".\.venv\Scripts\python.exe" tools\release_audit.py --check-only
```
**Resultado**:
```text
RELEASE AUDIT: PASS. Runtime payload SHA-256: 7d59e841532e752d9281dd0e491a60cb2f8d7b0dcc8feebe903e4b655320ad1f
Payload files counted: 61
Terminal dispositions: 8/8 verified
```

---

## 5. Matriz de Cobertura de Condiciones en `test_silent_mode.py` y `test_command_center.py`
- `test_silent_mode_fields_default` (C2): Valores por defecto seguros.
- `test_silent_mode_independent_from_snooze` (C2): Aislamiento estructural con respecto a snooze.
- `test_snooze_cancel_does_not_touch_silent` (C2): Invarianza cruzada.
- `test_startup_reconcile_purges_expired_silence` (C2): Purgado en `first_tick` con downtime.
- `test_startup_reconcile_retains_active_silence` (C2): Preservación de silencios vigentes tras reinicio.
- `test_silent_command_activates_in_memory_only` (C1): Mutación pura sin I/O en hilo de comandos.
- `test_silent_command_durations_calculated` (C1): Conversión precisa de duraciones (30m, 1h, 2h, 4h, 6h, indef).
- `test_silent_off_clears_state` (C1/C2): Desactivación manual limpia.
- `test_governor_respects_silent_ceiling` (C3): Gobernador acotado por techo acústico.
- `test_governor_steps_up_within_ceiling` (C3): Aumento gradual de fans contenido dentro de límites.
- `test_emergency_spike_cancels_silent_mode` (C4): Anulación forzada y ventiladores al 100% ante 83.5°C.
- `test_failsafe_fault_cancels_silent_mode` (C4): Anulación ante falla de telemetría / sensores.
- `test_emergency_spike_persists_state_atomic` (C4): Guardado inmediato bajo `state_lock`.
- `test_dispatch_nav_silent`: Navegación interactiva táctil en Command Center.
- `test_dispatch_act_silent_30m_and_off`: Activación y desactivación táctil de 1 toque desde teclado inline.
