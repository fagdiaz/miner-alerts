# Feature Specification: Spec 093 — Watchdog de Elevadores Eléctricos, Corrección de Rachas y Auto-Recuperación de Firmware Stock

**Feature Name**: Elevator Outage Watchdog, Detection Streak Hotfix & Autonomous Firmware Recovery  
**Feature Code**: `093-elevator-watchdog-and-firmware-autorecovery`  
**Tracking Issue / Incident**: Falla de Relé en Elevador 2, Caída Silenciosa de M25/M26 y Reversión a Firmware Stock en M26  
**Status**: IN IMPLEMENTATION  
**Author**: Antigravity Assistant & Production Engineering  
**Baseline**: V6.0 Hookified Architecture (1530 tests PASS, NSSM Service RUNNING)  
**Target Outcome**:
1. Eliminación del bug de reseteo prematuro de rachas (`offline_streak` / `low_streak`) en `DetectionHook`, asegurando que cortes de energía o caídas de conectividad transicionen inequívocamente a `OFFLINE` tras `fails_before_alert` ticks.
2. Reconexión y cableado formal de `process_phase_drop_cycle` en el pipeline de hooks supervisores, emitiendo alertas críticas de Telegram inmediatas (`⚡ DISPARO DE CIRCUITO`) ante cortes de energía en elevadores.
3. Incorporación de un watchdog autónomo de firmware stock (`StockFirmwareRecoveryHandler`) que, ante la detección de `stock_firmware_fallback_detected`, intente un reinicio Bitmain seguro (`/cgi-bin/reboot.cgi`) y, en caso de persistir, reinstale limpiamente VNish 1.2.6 desde `C:\asicto\` y restaure el perfil dorado (`miner_profiles/{miner}.json`).

---

## 1. Problem Statement & Root Cause Forensic Summary

El 26 de octubre de 2026, la planta experimentó una falla física en un relé del Elevador 2 (`elevator_2`), cortando la alimentación de `S19JPRO-25` y `S19JPRO-26` durante 95 minutos continuos. El incidente expuso tres deficiencias críticas:

1. **Bug de Anulación Prematura de Rachas en `DetectionHook`**:
   - `DetectionHook.execute` (líneas 1087-1090 de `app/core/engine.py`) evaluaba `if new_state == STATE_OK: state.offline_streak = 0; state.low_streak = 0`.
   - Durante los ticks 1 y 2 de una desconexión, como `offline_streak < fails_before_alert` (umbral 3), `classify_state` devolvía el estado previo (`OK`).
   - Al ser `new_state == "OK"`, la racha `offline_streak` era reiniciada a 0 en cada tick, impidiendo matemáticamente que cualquier minero en `OK` alcanzara 3 fallos.
   - Como resultado, durante 95 minutos los mineros permanecieron clasificados como `OK` pese a no responder, y nunca se envió la alerta `🔴 MINERO OFFLINE`.

2. **Desconexión del Ciclo de Caída de Fase / Elevador (`process_phase_drop_cycle`)**:
   - En la refactorización modular a hooks de Spec 091, la función `process_phase_drop_cycle` (diseñada en Spec 051) quedó importada en `app/core/pipeline.py` pero huérfana de invocación en los hooks.
   - Cuando el 100% de los mineros de `elevator_2` cayeron, el sistema no disparó la alerta unificada `⚡ DISPARO DE CIRCUITO`.

3. **Reversión a Firmware Stock tras Apagón Brusco**:
   - Tras el corte eléctrico abrupto, el BeagleBone Black de `S19JPRO-26` booteó en su imagen de recuperación de fábrica Bitmain (`BMMiner 1.0.0`).
   - El monitor detectó `unlock_failed: stock_firmware_fallback_detected` pero no contaba con un actuador para enviar el reboot seguro a `/cgi-bin/reboot.cgi` ni para re-flashear automáticamente VNish 1.2.6 si el reinicio fallaba.

---

## 2. User Stories & Value Proposition

### User Story 1 — Detección Confiable de Mineros Offline
> **Como** operador del centro de minado,  
> **Quiero** que cuando un minero deje de responder por socket 4028 durante 3 ticks consecutivos, transicione inmediatamente a `OFFLINE` y me notifique por Telegram,  
> **Para** no operar a ciegas ante desconexiones de red o cortes individuales de energía.

### User Story 2 — Alerta Crítica Inmediata por Falla de Elevador Eléctrico
> **Como** supervisor de infraestructura eléctrica,  
> **Quiero** que el sistema detecte cuando todos los mineros de un mismo elevador (`elevator_1` o `elevator_2`) caen simultáneamente y envíe una alerta urgente `⚡ DISPARO DE CIRCUITO / CORTE EN ELEVADOR`,  
> **Para** acudir de inmediato al tablero eléctrico a verificar térmicas y relés pegados.

### User Story 3 — Auto-Recuperación de Firmware Stock de Bitmain
> **Como** ingeniero de operaciones,  
> **Quiero** que si un minero bootea en firmware stock tras un apagón, el supervisor intente un reboot de NAND vía HTTP Digest `/cgi-bin/reboot.cgi`, y si persiste, ejecute la instalación desatendida de VNish 1.2.6 desde `C:\asicto\` reinyectando las pools y presets correspondientes,  
> **Para** que la flota vuelva a hashear a potencia nominal sin requerir intervención manual.

---

## 3. Scope & Technical Specifications

### In Scope
1. **Hotfix de Rachas en `app/core/engine.py`**:
   - Modificar `DetectionHook.execute` para que `offline_streak` y `low_streak` solo se reseteen cuando el minero responda favorablemente (`responded=True` y rate por encima del umbral) o cuando transicione formalmente desde otro estado a `STATE_OK`.
2. **Reconexión de `process_phase_drop_cycle` en `app/core/pipeline.py`**:
   - Invocar `process_phase_drop_cycle` en `GovernanceHook` (o `DetectionHook`), alimentado con `tick_failed_miners` y `tick_responded_miners`, garantizando el bypass de histéresis y la alerta Telegram de elevador.
3. **Módulo de Auto-Recuperación de Firmware (`app/governance/firmware_recovery.py`)**:
   - Actuador con cooldown y límites de intentos para:
     a) Disparar reboot Bitmain a `http://{host}/cgi-bin/reboot.cgi`.
     b) Si persiste tras el reinicio, invocar `FirmwareFlasher.flash_bitmain_nand()` con `C:\asicto\asicto-s19jpro-bb-nand-v1.2.6-install.tar.gz`.
     c) Restaurar el perfil guardado en `data/miner_profiles/{miner}.json`.
     d) Notificar el progreso detallado a Telegram.
4. **Pruebas Automatizadas**:
   - Pruebas unitarias de streaks en `tests/test_detection_hook_streaks.py`.
   - Pruebas de integración de alerta de elevador y auto-recuperación de firmware.

### Out of Scope
- Modificación del hardware de los elevadores físicos ni de relés.

---

## 4. Invariants & Safety Gates
1. **Invariante de Test Suite**: $\ge 1530$ tests PASS, 0 fallos, 0 regresiones.
2. **Invariante de No Bloqueo**: El flasheo o reinicio de firmware debe ejecutarse en hilos desacoplados (`threading.Thread`), sin bloquear el bucle de supervisión ni el poller de Telegram.
3. **Invariante de Cooldown de Elevador**: Las alertas de disparo de circuito deben respetar un cooldown mínimo de 300 segundos para evitar tormentas de mensajes.
