# Spec 055: Auto-Reboot ante Falla de Placa y Recuperación Automática de Hashboard (Self-Healing Hashboard Recovery)

## Estado y Metadatos
- **ID**: `055-hashboard-failure-auto-reboot`
- **Prioridad**: P0 (Resiliencia Crítica, Auto-Recuperación y Prevención de Paradas Nocturnas)
- **Estado**: PLANIFICADA / ESPECIFICACIÓN APROBADA (Pendiente de Implementación)
- **Fecha**: 2026-09-13
- **Autor**: Antigravity (Gemini 3.8 Flash High)
- **Documento Base**: Análisis Forense de Incidente Minero 23 (2026-09-13 00:38 - 07:44)
- **Dependencias**: Specs 008 (Valid Signal Reboot Gate), 018 (Fleet Restart Stability), 020 (Stable States Machine), 054 (Predictive Chain Diagnostics).

---

## 1. Contexto y Objetivos

### 1.1 El Problema Operativo (Incidente Minero 23)
Durante la madrugada del **2026-09-13**, el Minero 23 (`S19JPRO-23`) sufrió un reinicio interno a las `00:38:17` tras 50+ horas de operación continua a 2700W:
```text
[00:38:17] [INCIDENT] type=restart_detected miner=23 group=elevator_1 elapsed=181859->10
[00:38:17] [STATE] S19JPRO-23 OK -> LOW 0.00 TH/s
[00:40:51] S19JPRO-23 (miner) - chain/chain_break: Corte de cadena detectado
[00:40:50] S19JPRO-23 (status) - restart/watchdog_chain_restart: Reinicio interno por corte de cadena
[00:42:19] [STATE] S19JPRO-23 -> HASHBOARD boards=0/3
```
Durante el re-arranque del firmware, las 3 cadenas fallaron en inicializarse (`state=failure` en Cadenas 1, 2 y 3). El equipo quedó energizado, consumiendo energía auxiliar en controladores y ventiladores al 100%, pero con **0 placas activas y 0.0 TH/s de hashrate**.

### 1.2 Causa Raíz de la Falta de Auto-Reinicio
Una auditoría exhaustiva en la base de datos `data/miner_alerts.db` y en el código de `app/miner_monitor.py` reveló el cuello de botella arquitectónico:
1. Al caer las placas a `0/3` (`active_boards < expected_boards`), el monitor cambió de estado a `STATE_HASHBOARD`.
2. En `app/miner_monitor.py` (Línea 7543):
   ```python
   if new_state == STATE_LOW:
       if state.low_since_ts is None:
           state.low_since_ts = now_ts
   else:
       state.low_since_ts = None
       state.low_streak = 0
   ```
   Al salir de `STATE_LOW`, el temporizador de falla sostenida `low_since_ts` fue **anulado a `None`**.
3. En `app/miner_monitor.py` (Líneas 7897 y 7925):
   ```python
   if auto_reboot_candidate and new_state != STATE_LOW:
       record_auto_reboot_decision(event_store, result="not_low", ...)
   ...
   if new_state == STATE_LOW and state.low_since_ts:
       # Única rama donde se evalúa y ejecuta el auto-reboot
   ```
4. **Consecuencia**: El motor de auto-reinicio fue concebido en la Spec 008 exclusivamente para `STATE_LOW`. Cualquier equipo en `STATE_HASHBOARD` (incluso con 0/3 placas y 0 TH/s) es clasificado como `not_low`, ignorando el problema.
5. El Minero 23 permaneció **7 horas consecutivas** (desde las 00:42 hasta las 07:44) emitiendo cada 30 segundos:
   `[AUTO-REBOOT] blocked_by=not_low miner=23 rate_ths=0.0 threshold_ths=60.0 low_streak=0/1`
   hasta que el operador despertó e intervino manualmente.

### 1.3 Objetivos de la Spec 055
1. **Extensión de Auto-Reboot a `STATE_HASHBOARD`**:
   - Permitir que un minero en `STATE_HASHBOARD` con falla total (`active_boards == 0` o `rate_ths == 0.0`) califique como elegible para auto-reinicio seguro.
   - Permitir opcionalmente la recuperación de falla parcial (`active_boards < expected_boards`) con un umbral configurable.
2. **Temporizador de Falla de Placa Sostenida (`hashboard_since_ts`)**:
   - Medir el tiempo continuo en falla (ej. 600 segundos / 10 minutos) antes de actuar, evitando reinicios durante el arranque natural del firmware.
3. **Preservación Incondicional de Todos los Interlocks de Seguridad**:
   - Mantener intacto el Guardián de Inicio (600s), Cooldown de reinicios (1800s), Ventana máxima de 3 reinicios en 24h, Guardián Térmico (máx 85°C), Guardián de Flota (bloqueo si >= 2 mineros fallan al unísono por corte de fase) y Guardián de Transición de Firmware.
4. **Auditoría y Diagnóstico Limpio en EventStore**:
   - Registrar resultados deterministas: `eligible_hashboard`, `hashboard_not_sustained`, `executed_hashboard` en `reboot_decisions` en lugar del falso `not_low`.
5. **Notificación Ejecutiva en Telegram**:
   - Tarjeta clara: `[AUTOREBOOT] Minero 23 reiniciado automáticamente por falla total de placas (0/3 activas durante 10 min)`.

---

## 2. Requisitos Funcionales y Restricciones

### RF-001: Clasificación de Señal de Auto-Reinicio para Hashboard
- Extender `classify_auto_reboot_signal` o introducir `classify_hashboard_reboot_signal(responded, active_boards, expected_boards, rate_ths)`:
  - Si `responded is True` y `active_boards == 0`: Clasificar como señal `AUTO_REBOOT_SIGNAL_ELIGIBLE_HASHBOARD_TOTAL`.
  - Si `responded is True` y `0 < active_boards < expected_boards`: Clasificar como `AUTO_REBOOT_SIGNAL_ELIGIBLE_HASHBOARD_PARTIAL`.
  - Si `rate_ths >= threshold_ths` y `active_boards == expected_boards`: `AUTO_REBOOT_SIGNAL_NOT_LOW`.

### RF-002: Temporización Sostenida Independiente
- Incorporar en `MinerState` el campo `hashboard_since_ts: Optional[float] = None`.
- Cuando `new_state == STATE_HASHBOARD`:
  - Si `state.hashboard_since_ts is None`, fijarlo en `now_ts`.
  - Si el estado vuelve a `STATE_OK`, resetear `state.hashboard_since_ts = None`.
- Configuración en `app/config.json`:
  - `"auto_reboot_hashboard_enabled": true` (default: true).
  - `"auto_reboot_hashboard_sustained_seconds": 600` (default: 600s / 10 minutos).
  - `"auto_reboot_hashboard_partial_enabled": false` (default: false; solo reiniciar automáticamente ante falla total 0/3).

### RF-003: Evaluación Unificada de Interlocks
- El disparo de auto-reinicio por `STATE_HASHBOARD` debe pasar **estrictamente** por la misma función pura `evaluate_auto_reboot_interlocks`:
  - Si el minero está dentro de la ventana de `startup_guard_seconds` -> `startup_guard`.
  - Si el tiempo sostenido `< hashboard_sustained_seconds` -> `hashboard_not_sustained`.
  - Si `now_ts - last_reboot_ts < cooldown_seconds` -> `cooldown`.
  - Si se superó el límite de reinicios en 24h -> `window`.
  - Si la temperatura supera el límite -> `thermal_guard`.
  - Si múltiples mineros cayeron al unísono -> `fleet_guard`.
- Bajo ninguna circunstancia se ejecutará un reinicio sin pasar por estos 6 candados.

### RF-004: Persistencia y Trazabilidad en Base de Datos
- En `reboot_decisions`:
  - `result` guardará `"executed"` con `details={"trigger": "hashboard_total_failure", "active_boards": 0, "expected_boards": 3}`.
  - En caso de bloqueo por tiempo: `result="not_sustained"` con `details={"trigger": "hashboard_failure", "elapsed": elapsed, "required": 600}`.
- Eliminar por completo el log espurio `blocked_by=not_low` cuando el minero está en `STATE_HASHBOARD`.

---

## 3. Criterios de Aceptación y Pruebas
1. **Prueba Unitaria de Clasificación**:
   - `test_hashboard_total_failure_qualifies_for_auto_reboot`: Minero con `active_boards=0`, `expected_boards=3`, `rate=0.0` califica como elegible.
2. **Prueba Unitaria de Temporizador Sostenido**:
   - `test_hashboard_sustained_timer_blocks_before_threshold`: No reinicia a los 300s de falla; reinicia a los 601s.
3. **Prueba Unitaria de Interlocks**:
   - `test_hashboard_reboot_respects_startup_guard`: Bloqueado si el monitor recién inicia.
   - `test_hashboard_reboot_respects_cooldown_and_window`: Bloqueado tras 3 reinicios diarios.
   - `test_hashboard_reboot_respects_fleet_interlock`: Bloqueado si 2 mineros fallaron simultáneamente.
4. **Prueba de Regresión Global**:
   - Las 840 pruebas existentes deben continuar pasando al 100%.
