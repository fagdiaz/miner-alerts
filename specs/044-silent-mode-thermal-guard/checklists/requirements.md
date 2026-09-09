# Checklist de Requerimientos y Restricciones Constitucionales: Spec 044

## Restricciones Constitucionales P0 (Auditoría Claude §6.5)
- [ ] **Condición C1 (Concurrencia)**: Las escrituras de modo silencio a VNish desde Telegram se despachan vía `ThreadPoolExecutor` con `shutdown(wait=False)` y timeout de 2.5s; el hilo de polling jamás se bloquea.
- [ ] **Condición C2 (Persistencia FSM)**: Campos `silent_mode_*` independientes en `MinerState` y `state.json` (aislados del snooze de alertas); verificación explícita en `first_tick` tras reinicio de NSSM.
- [ ] **Condición C3 (Anti-Race Condition)**: `GovernorConfig` recibe límites dinámicos (`max_fan_duty_percent`) limitados al techo acústico si `silent_mode_active == True`, eliminando competencia entre el Governor y el Modo Silencio.
- [ ] **Condición C4 (Thermal Guard Atómico)**: Ante `EMERGENCY_SPIKE` (83.0°C) o falla térmica, el modo silencio se anula en memoria y en disco (`save_state()` bajo `state_lock`) de forma inmediata con fans al 100% y alerta urgente a Telegram.

## Requerimientos de Temporización
- [ ] Soporte para duraciones táctiles: 30m, 1h, 2h, 4h, 6h y modo indefinido.
- [ ] Al cumplirse el plazo, restauración automática de potencia y ventiladores con mensaje en Telegram.
- [ ] Soporte para desactivación manual anticipada mediante botón táctil o comando.

## Pruebas y Certificación
- [ ] `tests/test_silent_mode.py` con pruebas dedicadas para C1, C2, C3 y C4.
- [ ] Suite completa de tests pasando (> 595 tests PASS).
- [ ] Compilación sintáctica validada sin errores.
