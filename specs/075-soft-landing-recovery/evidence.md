# Evidence & Validation Log: Spec 075 — Recuperación Suave de Hasheo, Headroom Chilling y Blindaje Anticolapso de Fuentes APW12

## 1. Línea Base Técnica Pre-Implementación
- **Fecha**: 2026-09-18 12:15 hs
- **Rama**: `codex/022-adaptive-acquisition`
- **Servicio Windows**: `MinerAlerts` en estado `RUNNING` (PID 19204).
- **Suite de Pruebas**: 1221 tests PASS en 34.2s (100% de éxito, 0 fallos, 0 errores).

## 2. Evidencia Empírica de Producción que Justifica la Spec
1. **Episodio 17/09 19:11 hs (Minero 25)**: Bloqueo de protección (*Latch-Off*) de fuente APW12 al demandar carga completa abruptamente tras rearranque. Resuelto físicamente mediante ciclo de energía en enchufe.
2. **Episodio 18/09 05:50 hs (Minero 25)**: Dos comandos automáticos de `safe_restart_mining` enviados durante falla en Cadena 1 dispararon el corte de la fuente APW12. Resuelto físicamente a las 09:05 hs.
3. **Episodio 18/09 10:22 hs (Minero 26)**: Reinicio aislado que normalizó de forma autónoma a las 10:31 hs sin intervención violenta de software, con cero caídas en cascada hacia el minero 25 (validando el amortiguador pareado de la Spec 074).
4. **Episodio 18/09 11:38 hs (Minero 24)**: Equipo operando a 83.0°C con ventiladores al 96% escalando por pasos de +3% cada 90s hacia el umbral de 83.5°C; suboptimización a 2500W con ventiladores al 90% perdiendo potencial de subida a 2700W por margen térmico.
5. **Episodio 18/09 11:52 hs (Granja Completa)**: Corte general de suministro eléctrico detectado como `phase_drop_fleet` sin disparar falsos reinicios.
6. **Episodio 18/09 12:10 - 14:25 hs (Minero 24 - Diagnóstico Raíz Exhaustivo)**:
   - Al restablecerse la energía tras el apagón de las 11:52 hs, el Minero 24 inició en firmware de fábrica Bitmain (NAND eMMC, fecha Junio 2021, `BMMiner 1.0.0` en puerto 4028 y HTTP Digest realm `"antMiner Configuration"` en puerto 80).
   - Diagnóstico de Kernel Log (`/cgi-bin/log.cgi`): Placa de control BeagleBone Black (TI AM335x) sin detección de tarjeta MicroSD (`omap2-nand.0`). El firmware base cargado (`BHB42601`) no es compatible con las hashboards instaladas (`BHB42621`):
     `Sweep error string = J255:4. Fixture data load failed, exit. ERROR_SOC_INIT: basic init failed! stop_mining: basic init failed! ****power off hashboard****`
   - El bucle de auto-reboot externo intentó 3 reinicios en caliente (`auto_reboot`), bloqueándose a las 13:20 hs por ventana de seguridad (`blocked_by=window miner=24 window_count=3`).
   - Mitigación implementada en Spec 075:
     * Detección de header HTTP Digest/lighttpd en `unlock_miner()` (`stock_firmware_fallback_detected`).
     * Inhibición absoluta de reinicios (`INTERLOCK_STOCK_FIRMWARE`, `INTERLOCK_HARDWARE_FAULT`, `ACTION_INHIBIT_HARDWARE_FAULT`) para evitar someter a la fuente APW12 a ciclos destructivos inútiles cuando falta el firmware o hay fallas de sensor.
     * Alerta diagnóstica específica de fallback a Telegram para solicitar verificación física de la MicroSD.

## 3. Registro de Validación de Tareas
- [x] T001: Implementación de `app/governance/safe_recovery.py` (`SafeRecoveryState`, `RecoveryDecision`, `evaluate_safe_recovery`, ventana pasiva de 120s, pre-clamp a 1800W, e inhibición de fallas de hardware/firmware).
- [x] T002: Soporte `boost_cooling` (Headroom Chilling) y calibración a 83.0°C en `app/governance/fan_governor.py`.
- [x] T003: Acoplamiento Balancer ↔ Governor para Headroom Chilling (`boost_cooling_requested`) en `app/governance/preset_balancer.py`.
- [x] T004: Conexión en lazo de recuperación de dos niveles en `app/miner_monitor.py` (pre-clamp defensivo a 1800W, soak de 180s para staged ramp-up y compuerta anti-fallback de stock firmware).
- [x] T005: Suite dedicada `tests/test_safe_recovery.py` (7 tests), `tests/test_preset_balancer.py` (20 tests), `tests/test_fan_governor.py` (21 tests) y `tests/test_reboot_safety.py` (17 tests).
- [x] T006: Verificación de regresión completa: **1236 tests PASS** en 39.5s (100% de éxito, 0 fallos, 0 errores).
- [x] T007: Auditoría exhaustiva de concurrencia y subprocesos:
  - **Jerarquía L1/L2 Invariante**: `state_lock` (`threading.RLock`) protege mutaciones en memoria; `_SAVE_STATE_LOCK` gestiona escrituras atómicas en disco sin anidamiento.
  - **Aislamiento I/O de Red**: Cero llamadas de red (`safe_set_miner_preset`, `safe_restart_mining`, `requests.post`) se ejecutan reteniendo cerrojos, con timeouts estrictos de 2.5s.
  - **Desacoplamiento de Hilos**: Hilos `AutoRestart_{name}` corren en modo daemon independiente. Prevención de ráfagas garantizada mediante sellado atómico de `state.last_auto_restart_ts` previo al lanzamiento y bloqueo por `cooldown` (300s).
  - **Blindaje de Mutaciones de Estado**: Todas las mutaciones del ciclo de recuperación suave (`is_pre_clamped`, `staged_ramp_up_pending`, `staged_ramp_up_soak_start_ts`, `stopped_since_ts`, `stock_firmware_fallback_notified`) encapsuladas bajo `with state_lock:`.
  - **Evidencia Empírica Minero 24 en Vivo (15:13 hs)**: Ciclo físico de energía realizado en granja capturado en tiempo real. La placa BeagleBone Black inició en NAND interna (`CompileTime: Tue Jun 22 17:45:49 CST 2021`, HTTP Digest realm `"antMiner Configuration"`, `ERROR_SOC_INIT`). El sistema inhibió correctamente cualquier intento de auto-reboot o auto-restart protegiendo la fuente APW12 de pulsos de corriente.
- [x] T008: Certificación en producción y reinicio del servicio Windows `MinerAlerts`:
  - **Recuperación Minero 24 en VNish NAND**: Reinstalación limpia de VNish 1.2.6 en NAND eMMC completada con Hashcore Toolkit. Inyección autenticada de pools de Binance Pool para worker `fagdiaz.19216810024`. Minero salió de `failure` y completó auto-tuning con 378/378 chips afinados, alcanzando 81.5 TH/s en estado OK consolidado.
  - **Herramienta de Perfiles Dorados**: Implementación y ejecución de `tools/backup_miner_profiles.py` respaldando perfiles afinados y matrices de chips en `data/miner_profiles/` para toda la flota (23, 24, 25, 26).
  - **Servicio Windows**: Reiniciado bajo `Restart-Service MinerAlerts` con nueva versión de Spec 075 en producción. Flota completa (4/4 mineros) en estado OK.
