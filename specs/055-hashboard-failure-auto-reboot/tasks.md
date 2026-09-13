# Tasks - Spec 055: Auto-Reboot ante Falla de Placa y Recuperación Automática de Hashboard

## Protocolo de Ejecución Segura para Gemini 3.8 Flash High
Para garantizar precisión matemática absoluta, carga al ~50% de contexto por iteración, y cero riesgo de alucinación o regresiones en producción, la Spec 055 se divide en **4 Iteraciones Bounded y Secuenciales**:

```
[Iteración 1: Dominio Puro y Puertas] -> [Iteración 2: Temporización y Estado] -> [Iteración 3: Canalización de Interlocks] -> [Iteración 4: Telegram, QA y Despliegue]
```

---

## Iteración 1: Modelo de Datos, Configuración y Puerta de Señal Pura
> **Alcance**: Funciones puras y contratos de datos. Riesgo en producción: **0%**.
- [x] **T001**: Agregar campo `hashboard_since_ts: Optional[float] = None` a `MinerState` con serialización `to_dict()` y deserialización `from_dict()` en `app/miner_monitor.py`.
- [x] **T002**: Registrar claves de configuración con fallbacks seguros en `app/miner_monitor.py` y documentar en `app/config.example.json`:
  - `auto_reboot_hashboard_enabled`: `true`
  - `auto_reboot_hashboard_sustained_seconds`: `600`
  - `auto_reboot_hashboard_partial_enabled`: `false`
- [x] **T003**: Extender la función pura `auto_reboot_signal_allows_evaluation` para aceptar `hashboard_since_ts`, `active_boards`, `expected_boards` y `allow_partial_hashboard` manteniendo 100% de compatibilidad hacia atrás con los callers existentes de `STATE_LOW`.
- [x] **T004**: Crear `tests/test_hashboard_auto_reboot.py` con pruebas unitarias para `auto_reboot_signal_allows_evaluation` con casos:
  - Falla total (0/3 placas) con `hashboard_since_ts` activo -> `True`.
  - Falla total sin `hashboard_since_ts` -> `False`.
  - Falla parcial con `allow_partial=False` -> `False`.
  - Falla parcial con `allow_partial=True` -> `True`.
  - Preservación idéntica de comportamiento para `STATE_LOW` y `STATE_OK`.
- [x] **T005**: Ejecutar `tests/test_auto_reboot_signal_gate.py` y la suite para verificar cero regresiones en la puerta de señales.

---

## Iteración 2: Temporización Sostenida de Hashboard en el Monitor
> **Alcance**: Seguimiento temporal en el bucle principal. Solo observabilidad, sin acciones de reinicio.
- [x] **T006**: En el ciclo de actualización de estado de `app/miner_monitor.py`:
  - Cuando `new_state == STATE_HASHBOARD`: si `state.hashboard_since_ts is None`, fijarlo en `now_ts`.
  - Cuando `new_state == STATE_OK`: resetear `state.hashboard_since_ts = None`.
- [x] **T007**: Suprimir la clasificación espuria `result="not_low"` cuando `new_state == STATE_HASHBOARD`, registrando en su lugar `result="hashboard_not_sustained"` mientras el tiempo transcurrido sea `< hashboard_sustained_seconds`.
- [x] **T008**: Crear tests unitarios en `tests/test_hashboard_auto_reboot.py` verificando que el reloj `hashboard_since_ts` acumula segundos determinísticamente en cada tick y se reinicia adecuadamente ante la recuperación de placas.

---

## Iteración 3: Canalización de Interlocks y Decisión de Auto-Reinicio
> **Alcance**: Evaluación y toma de decisión estricta a través de los 6 interlocks constitucionales.
- [ ] **T009**: Conectar la condición de `STATE_HASHBOARD` sostenido a la llamada de `evaluate_auto_reboot_interlocks`:
  - Si `startup_guard_active` -> Bloqueado por `startup_guard`.
  - Si `elapsed < hashboard_sustained_seconds` -> Bloqueado por `not_sustained`.
  - Si `now_ts - last_reboot_ts < cooldown_seconds` -> Bloqueado por `cooldown`.
  - Si `window_count >= max_reboots_in_window` -> Bloqueado por `window`.
  - Si `max_temp_c >= thermal_limit_c` -> Bloqueado por `thermal_guard`.
  - Si `fleet_affected >= fleet_min_affected` -> Bloqueado por `fleet_guard`.
  - Si `firmware_transition_active` -> Bloqueado por `firmware_transition_guard`.
- [ ] **T010**: Persistir en la tabla `reboot_decisions` del `EventStore` el registro determinista con `trigger: "hashboard_total_failure"`, número de placas activas y tiempo sostenido.
- [ ] **T011**: Validar la ejecución simulada (QA / Dry-run) en `tests/test_hashboard_auto_reboot.py` verificando que `run_hashcore_cli(..., "reboot")` solo se invoca cuando todos los 6 interlocks están en verde.

---

## Iteración 4: UX Telegram, Auditoría Completa, Documentación y Despliegue
> **Alcance**: Notificación al operador, regresión global (840+ tests), commit, push y reinicio en producción.
- [ ] **T012**: Formatear mensaje/tarjeta de Telegram para auto-reinicio por falla de placas:
  `[AUTOREBOOT] Minero {name} reiniciado automáticamente tras 10 min sin placas activas (0/3)`.
- [ ] **T013**: Ejecutar suite completa de pruebas (`unittest discover -s tests`) y certificar 100% PASS (840+ tests).
- [ ] **T014**: Validar sintaxis con `py_compile` en `app/miner_monitor.py`.
- [ ] **T015**: Actualizar `docs/audit/DEVELOPMENT_LOG.md`, `docs/speckit/ROADMAP.md` y `docs/speckit/DELIVERY_PLAN.md`.
- [ ] **T016**: Commit y push a `origin/codex/022-adaptive-acquisition`.
- [ ] **T017**: Reinicio del servicio Windows `MinerAlerts` (`Restart-Service`) y verificación del nuevo PID y logs limpios en `logs/out.log`.
