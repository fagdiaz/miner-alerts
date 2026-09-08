# Tasks: Spec 040 - Dynamic Power & Preset Balancer

## Fase 1: Extensión del Cliente REST Vnish Presets
- [x] **T001**: [P1] Extender `app/vnish_client.py` con el método `get_available_presets(host, token)`.
- [x] **T002**: [P1] Extender `app/vnish_client.py` con el método `set_miner_preset(host, token, preset_name)`.
- [x] **T003**: [P1] Implementar `safe_set_miner_preset` con ciclo transaccional `unlock` -> `set` -> `lock` garantizado en `try ... finally`.
- [x] **T004**: [P1] Desarrollar tests unitarios con mocks HTTP para los métodos de preset en `tests/test_vnish_client.py`.

## Fase 2: Motor Matemático Puro de Balanceo Costo-Beneficio
- [x] **T005**: [P1] Crear `app/preset_balancer.py` con los modelos de datos `PresetTier`, `StabilityMetrics`, `BalancerConfig` y `BalancerDecision`.
- [x] **T006**: [P1] Definir la escalera estándar de presets Vnish para Antminer S19j Pro y funciones de ordenamiento.
- [x] **T007**: [P1] Implementar la función de cálculo de Hashrate Neto Efectivo ($H_{\text{eff}}$) penalizando reinicios.
- [x] **T008**: [P1] Implementar la lógica pura `evaluate_balancer_step()` con reglas de desescalado rápido ($\ge 2$ reinicios en 24h) y cascada grupal.
- [x] **T009**: [P1] Implementar la regla de escalado conservador ($> 72\text{h}$ sin reinicios y margen térmico $\ge 4^\circ\text{C}$).

## Fase 3: Suite de Pruebas Unitarias Deterministas
- [x] **T010**: [P1] Crear `tests/test_preset_balancer.py` y validar cálculo de función de costo $H_{\text{eff}}$.
- [x] **T011**: [P1] Implementar tests de desescalado preventivo por reinicios frecuentes en 24h.
- [x] **T012**: [P1] Implementar tests de protección ante caídas en cascada del mismo elevador.
- [x] **T013**: [P1] Implementar tests de hysteresis de 72h y respeto estricto de techo `max_preset`.

## Fase 4: Integración en Monitor y Comandos Telegram
- [ ] **T014**: [P1] Soporte para la clave `electrical_group` en cada minero en `app/config.json` y `app/config.example.json`.
- [ ] **T015**: [P1] Función extractora de métricas de estabilidad (`extract_miner_stability_metrics`) desde `data/miner_alerts.db` y `state.json`.
- [ ] **T016**: [P1] Ciclo evaluador periódico del balanceador integrado en `app/miner_monitor.py` en modo `dry_run: true` por defecto.
- [ ] **T017**: [P1] Comandos Telegram `/balancer` (tabla ejecutiva), `/balancer setmax <miner> <preset>`, `/balancer on` y `/balancer off`.

## Fase 5: Validación, Regresiones y Documentación
- [ ] **T018**: [P1] Verificar 100% de pase de suite global sin regresiones (>560 tests PASS).
- [ ] **T019**: [P1] Registrar evidencia de validación en `specs/040-dynamic-voltage-presets/evidence.md`.
- [ ] **T020**: [P1] Actualizar `docs/audit/DEVELOPMENT_LOG.md` y `docs/speckit/ROADMAP.md`.
