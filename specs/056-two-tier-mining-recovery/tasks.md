# Tasks - Spec 056: Two-Tier Mining Recovery (Auto-Restart vs Auto-Reboot)

## Protocolo de Ejecución Segura para Gemini 3.8 Flash High
Para garantizar precisión matemática absoluta, carga al ~40-50% de contexto por iteración, y cero riesgo de alucinación o regresiones en producción, la Spec 056 se divide en **4 Iteraciones Bounded y Secuenciales**:

```
[Iteración 1: Cliente REST Vnish] -> [Iteración 2: Evaluación y Cooldown N1] -> [Iteración 3: Canalización y Escalación N2] -> [Iteración 4: Telegram, Regresión y Despliegue]
```

---

## Iteración 1: Cliente REST Vnish y Modelo de Estado de Minado
> **Alcance**: Extender cliente Vnish para reiniciar minado y extraer discriminadores. Riesgo en producción: **0%**.
- [x] **T001**: Implementar función `restart_mining(host, token, timeout, session)` y el wrapper transaccional `safe_restart_mining(host, password, timeout)` en `app/vnish/client.py` usando `POST /api/v1/mining/restart`.
- [x] **T002**: Extender `get_miner_status` en `app/vnish/client.py` para devolver un objeto o dict normalizado con `restart_required: bool`, `reboot_required: bool` y `miner_state: str`.
- [x] **T003**: Exportar `safe_restart_mining` en `app/vnish/__init__.py`.
- [x] **T004**: Crear `tests/test_two_tier_recovery.py` con pruebas unitarias para `safe_restart_mining` y `get_miner_status` (mockeando respuestas exitosas 200, errores 401, timeouts y estados).
- [x] **T005**: Ejecutar `unittest tests.test_two_tier_recovery` y verificar 100% PASS.

---

## Iteración 2: Evaluación de Nivel 1 (Soft Auto-Restart Policy)
> **Alcance**: Función de decisión pura, campos de estado y configuración de cooldown.
- [x] **T006**: Agregar campos `last_auto_restart_ts: Optional[float] = None` y `auto_restart_count: int = 0` a `MinerState` en `app/miner_monitor.py` con serialización segura.
- [x] **T007**: Agregar claves de configuración en `app/miner_monitor.py` y `app/config.example.json`:
  - `auto_restart_mining_enabled: bool = true`
  - `auto_restart_cooldown_seconds: int = 300`
  - `auto_restart_max_retries_before_reboot: int = 2`
- [x] **T008**: Implementar función pura `evaluate_auto_restart_candidate(...)` que determine si corresponde un auto-reinicio de software (Nivel 1).
- [x] **T009**: Agregar pruebas unitarias en `tests/test_two_tier_recovery.py` para la función de decisión de Nivel 1.

---

## Iteración 3: Canalización en el Monitor y Escalación a Nivel 2
> **Alcance**: Integración en el bucle principal de monitorización con escalación limpia a auto-reboot.
- [x] **T010**: En `app/miner_monitor.py`, integrar la evaluación de Nivel 1:
  - Si el minero califica para auto-reinicio de software y no está en cooldown -> invocar `safe_restart_mining` en un thread desacoplado / seguro.
  - Incrementar `auto_restart_count` y registrar timestamp `last_auto_restart_ts`.
  - Registrar decisión en `EventStore`.
- [x] **T011**: Si tras `auto_restart_max_retries_before_reboot` el minero sigue con placas en falla (`0/3`) o 0.0 TH/s y transcurre la ventana sostenida (Spec 055), permitir la escalación a `run_hashcore_cli(..., "reboot")` (Nivel 2).
- [x] **T012**: Validar en `tests/test_two_tier_recovery.py` que Nivel 1 se ejecuta antes de Nivel 2 y que Nivel 2 solo escala si Nivel 1 no recuperó el minero.

---

## Iteración 4: UX Telegram, Certificación Global, Commit y Despliegue
> **Alcance**: Notificaciones operativas, regresión completa, commit, push y reinicio en producción.
- [x] **T013**: Formatear mensaje/tarjeta de Telegram para Nivel 1:
  `[AUTO-RESTART] Minero {name} hasheo detenido -> reinicio rápido de minado enviado (Nivel 1)`.
- [x] **T014**: Ejecutar suite completa de pruebas (`unittest discover -s tests`) y certificar 100% PASS (860+ tests).
- [x] **T015**: Validar sintaxis con `py_compile`.
- [x] **T016**: Actualizar `DEVELOPMENT_LOG.md`, `ROADMAP.md` y `DELIVERY_PLAN.md`.
- [x] **T017**: Commit y push a `origin/codex/022-adaptive-acquisition`.
- [x] **T018**: Reinicio del servicio Windows `MinerAlerts` (`Restart-Service`) y verificación del nuevo PID y logs limpios en `logs/out.log`.
