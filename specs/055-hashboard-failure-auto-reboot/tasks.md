# Tasks - Spec 055: Auto-Reboot ante Falla de Placa y Recuperación Automática de Hashboard

## Dependency Graph
```
T001 (Config & Model Fields)
  ├──> T002 (Signal Classification & Gate Extension)
  │      └──> T003 (Evaluation & Interlock Loop in miner_monitor.py)
  │             └──> T004 (Audit & EventStore Decision Persistence)
  │                    └──> T005 (Unit Tests Suite test_hashboard_auto_reboot.py)
  │                           └──> T006 (Regression Tests & py_compile)
  │                                  └──> T007 (Documentation & Development Log)
```

---

## Tasks

### Fase 1: Configuración y Modelo de Datos
- [ ] **T001**: Agregar campo `hashboard_since_ts: Optional[float] = None` a `MinerState` y sus métodos de serialización `to_dict()` y `from_dict()` en `app/miner_monitor.py`.
- [ ] **T002**: Registrar claves de configuración con valores por defecto seguros en `app/config.example.json` y fallbacks en `app/miner_monitor.py`:
  - `auto_reboot_hashboard_enabled`: `true`
  - `auto_reboot_hashboard_sustained_seconds`: `600`
  - `auto_reboot_hashboard_partial_enabled`: `false`

### Fase 2: Puerta de Señal y Lógica de Evaluación
- [ ] **T003**: Extender `auto_reboot_signal_allows_evaluation` en `app/miner_monitor.py` para permitir evaluar reinicio cuando `new_state == STATE_HASHBOARD` y el temporizador `hashboard_since_ts` ha superado el umbral sostenido configurado.
- [ ] **T004**: Actualizar el ciclo de transición de estados en `app/miner_monitor.py` para fijar `state.hashboard_since_ts = now_ts` cuando entra a `STATE_HASHBOARD` y resetearlo a `None` cuando el minero regresa a `STATE_OK`.
- [ ] **T005**: Eliminar el bloqueo artificial `if auto_reboot_candidate and new_state != STATE_LOW: record_auto_reboot_decision(result="not_low")` para mineros en `STATE_HASHBOARD`. En su lugar, dirigir la evaluación a través de la canalización de interlocks común.

### Fase 3: Auditoría y Persistencia de Decisiones
- [ ] **T006**: Registrar en `reboot_decisions` del `EventStore` el motivo exacto (`hashboard_total_failure` con conteo de placas) cuando se evalúe o ejecute un reinicio por esta causa.
- [ ] **T007**: Actualizar el mensaje de Telegram ante auto-reinicio por falla de placa para brindar claridad ejecutiva al operador (`[AUTOREBOOT] Minero X reiniciado tras 10m sin placas operativas`).

### Fase 4: Pruebas Automatizadas y Verificación
- [ ] **T008**: Crear `tests/test_hashboard_auto_reboot.py` con pruebas unitarias exhaustivas:
  - Falla total (0/3 placas) califica y reinicia tras cumplir 600s sostenidos.
  - Falla no sostenida (< 600s) bloquea con `not_sustained`.
  - Guardián de inicio (startup guard) bloquea el reinicio si el monitor recién arranca.
  - Cooldown y ventana máxima de 3 reinicios/24h bloquean reinicios excesivos.
  - Interlock de flota bloquea si 2 o más mineros caen al unísono.
- [ ] **T009**: Adaptar `tests/test_auto_reboot_signal_gate.py` y suites existentes para reflejar la nueva firma de `auto_reboot_signal_allows_evaluation` sin romper compatibilidad.
- [ ] **T010**: Ejecutar suite completa (`unittest discover -s tests`) y certificar 840+ tests PASS al 100%.
- [ ] **T011**: Validar sintaxis con `py_compile` en `app/miner_monitor.py`.

### Fase 5: Documentación y Despliegue
- [ ] **T012**: Actualizar `docs/audit/DEVELOPMENT_LOG.md` con la especificación y los cambios de Spec 055.
- [ ] **T013**: Actualizar `docs/speckit/ROADMAP.md` y `docs/speckit/DELIVERY_PLAN.md`.
- [ ] **T014**: Realizar commit y push ordenado a Git.
- [ ] **T015**: Reiniciar servicio Windows `MinerAlerts` y verificar logs en producción.
