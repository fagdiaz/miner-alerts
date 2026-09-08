# Evidence: Spec 039 - Vnish Thermal & Acoustic Fan Governor

**Fecha**: 2026-09-08  
**Implementado por**: Gemini 3.8 Flash High (Fases 1-3) + Claude Sonnet 4.6 Thinking (Fases 4-5)

---

## 1. Auditoria Arquitectonica Formal (Pre-Implementacion)

**Auditado por**: Claude Sonnet 4.6 (Thinking) - 2026-09-08T13:17  
**Veredicto**: AUTORIZADO para Fases 1-3. Fases 4-5 condicionadas a 4 requisitos de hardening (R1-R4).

**Requisitos de hardening cumplidos**:
- R1 (Anti-Hunting): Dwell adaptivo a 120s cuando consecutive_holds >= 3. OK
- R2 (HTTP Concurrency): ThreadPoolExecutor con shutdown(wait=False) + fleet timeout 5.0s. OK
- R3 (Fail-Safe Explicito): ACTION_FAILSAFE_FAULT a 100% tras 3 fallos + /gov off con fallback. OK
- R4 (PWM Floor): min_fan_duty_percent = 75% (subido de 70%). OK

---

## 2. Modulos Implementados

### Fase 1 - Visibilidad de Modo (Gemini)
- app/vnish_telemetry.py: Parseo de fan_mode ("manual"/"auto") y fan_pwm.
- app/fan_health.py: CoolingAssessment extendido con fan_mode. Renderizado en /fans.

### Fase 2 - Cliente REST Vnish (Gemini)
- app/vnish_client.py (NUEVO): unlock_miner, lock_miner, get_cooling_settings,
  set_manual_fan_duty, safe_set_fan_duty (try/finally garantizado), get_summary_cooling,
  mask_secret para redaccion de contrasenas.

### Fase 3 - Algoritmo Gobernador Termico (Gemini)
- app/fan_governor.py (NUEVO): GovernorConfig, GovernorDecision, compute_governor_step.
  - R1: Dwell adaptivo 120s (3+ holds consecutivos).
  - R4: min_fan_duty_percent = 75.
  - Spike override a 83.0 degrees C.
  - Failsafe a 100% tras max_consecutive_failures = 3.
  - Funcion pura, 0 I/O, 100% determinista.

### Fase 4 - Integracion en Monitor y Comandos Telegram (Claude)
- app/miner_monitor.py:
  - Nuevos campos MinerState: governor_duty, governor_holds, governor_last_change_ts,
    governor_failures, governor_last_action, governor_last_temp_c.
  - save_state / load_state: persistencia de campos del gobernador en state.json.
  - _GOVERNOR_RUNTIME_ENABLED: flag global de override para /gov on/off.
  - execute_governor_cycle(): Evaluacion + dispatch paralelo con ThreadPoolExecutor,
    shutdown(wait=False), fleet_timeout=5.0s. Hook en el tick principal.
  - Alimentacion de telemetria: governor_last_temp_c y governor_duty desde API 4028.
  - Comando /gov (alias /governor): status, /gov on, /gov off, /gov set <temp>.
- app/config.example.json: Seccion fan_governor_* y vnish_api_password documentados.

### Fase 5 - Tests de Concurrencia (Claude)
- tests/test_fan_governor_concurrency.py (NUEVO): 12 tests, 8 clases.
  - TestFleetTimeout: miner lento (10s) no bloquea mas de 2s (fleet_timeout).
  - TestDryRun: sin escritura en dry_run, duty actualizado en estado.
  - TestExceptionIsolation: excepcion en miner-1 no bloquea a miner-2.
  - TestStateLockConcurrency: 10 hilos concurrentes sin corrupcion de estado.
  - TestFailsafeFault: 3 fallos -> FAILSAFE_FAULT a 100%.
  - TestEmergencySpike: >=83 degrees C ignora dwell, spike inmediato a 100%.
  - TestAdaptiveDwell: dwell adaptivo 120s activado tras 3 holds.
  - TestPWMFloor: STEP_DOWN respeta piso 75%, no escribe si ya esta en piso.

---

## 3. Validacion

### py_compile (T011)
```
py_compile app/miner_monitor.py app/fan_governor.py app/vnish_client.py
ExitCode=0
```

### Tests de Concurrencia (T018)
```
Ran 12 tests in 2.019s
OK
```

### Suite Global (T019)
```
Ran 549 tests in 7.444s
OK
```
Baseline pre-Spec 039: 537 tests. Delta: +12 tests nuevos de gobernador.

### PID de Produccion
```
Id     CPU      WorkingSet   StartTime
88348  245.34s  41779200 B   2026-09-07 22:40:56
```
Activo, saludable. NO tocado durante la implementacion.

---

## 4. Feature Flags (Activación en Producción y Calibración 83°C)

fan_governor_enabled: true (gobernador activo por defecto)
fan_governor_dry_run: false (modulación activa en hardware Vnish)
fan_governor_target_temp_c: 83.0 (target de trabajo sano)
fan_governor_deadband_low_c: 82.0 (reducción -2% duty por debajo)
fan_governor_deadband_high_c: 83.5 (incremento +3% duty por encima)
fan_governor_emergency_temp_c: 84.0 (spike a 100% duty inmediato)
vnish_api_password: "CHANGE_ME" (cargar en config.json, nunca commitar)

---

## 5. Seguridad de Credenciales

- vnish_api_password leido desde app/config.json (en .gitignore).
- mask_secret() en vnish_client.py redacta contrasenas y tokens en logs.
- app/config.example.json contiene "CHANGE_ME", nunca una contrasena real.
- state.json no persiste contrasenas, solo metricas del gobernador.
