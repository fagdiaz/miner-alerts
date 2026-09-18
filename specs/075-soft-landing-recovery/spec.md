# Feature Specification: Spec 075 — Recuperación Suave de Hasheo, Desescalada Pre-Reinicio y Blindaje Anticolapso de Fuentes APW12 (PROP-010)
## (Soft-Landing Recovery, Headroom Chilling & APW12 Latch-Off Defense)

## Status
- **Date**: 2026-09-18
- **Priority**: P1 (Alta) | **Risk**: Medio
- **Modules**: `app/miner_monitor.py`, `app/vnish/client.py`, `app/governance/fan_governor.py`, `app/governance/safe_recovery.py`, `app/config.example.json`
- **Baseline**: 1221 tests PASS, Windows Service `MinerAlerts` Running (PID 19204).
- **Incidentes de Origen**: Bloqueos de protección (*Latch-Off*) de fuente Bitmain APW12 en minero 25 (17/09 19:11 hs y 18/09 05:50 hs); suboptimización térmica de ventiladores a 83°C y 81°C/2500W.

---

## 1. Problem Statement & Motivation

En la operación continua de mineros ASIC Antminer S19j Pro gobernados por firmware VNish sobre autotransformadores elevadores monofásicos, se identificaron dos limitaciones críticas de estabilidad y rendimiento:

1. **Vulnerabilidad de Bloqueo de Fuente (*APW12 Latch-Off*) ante Reinicios Violentos de Software**:
   Cuando un minero experimenta una caída de cadena (`CHAIN_FAULT`) o detención de hasheo (`stopped_state`), el monitor externo actualmente despacha comandos REST inmediatos de `safe_restart_mining`. Al recibir este comando, la máquina intenta energizar los 3 rieles de hashboards simultáneamente desde 0 A hasta ~12 A en su preset nominal (2300W-2700W).
   Si una cadena presenta una micro-fuga o falla transitoria, el transitorio inductivo y pico de corriente ($\Delta I / \Delta t$) dispara la protección interna de sobrecorriente/subtensión (OCP/UVP) de la fuente **Bitmain APW12**, entrando en **auto-bloqueo permanente (*Latch-Off*)**. En este estado, la línea secundaria de 12V DC se apaga, la placa de control muere y el minero queda 100% inerte hasta que un operador humano realiza un ciclo manual de corte de energía en el enchufe.

2. **Suboptimización Térmica y Atascamiento Balancer ↔ Governor (*The Sub-Optimal Fan Trap*)**:
   El **Fan Governor** modula ventiladores buscando equilibrio cerca de `target_temp_c = 82.0°C` con zona muerta entre 81.0°C y 82.5°C, manteniendo ventiladores al 88-90% para ahorrar ruido.
   Simultáneamente, el **Preset Balancer** exige un margen térmico de $\ge 3.0^\circ\text{C}$ hacia el límite de 84.0°C ($T_{max} \le 81.0^\circ\text{C}$) para permitir el salto a 2700W.
   Como consecuencia, un minero en 2500W a 81.5°C queda atrapado en un equilibrio subóptimo con un **10% de capacidad de disipación ociosa**, impidiendo que el equipo suba a 2700W y perdiendo entre 5 y 8 TH/s de hashrate productivo.

---

## 2. User Stories

- **US-01 (Desescalada Pre-Reinicio / Soft-Landing Clamp)**: Como operador de la flota, requiero que el monitor NUNCA reinicie el minado en caliente a plena potencia, sino que desescale preventivamente el preset al piso seguro (1800W-2000W) antes de enviar la orden de reinicio, amortiguando el transitorio $di/dt$ y previniendo que la fuente APW12 se bloquee por Latch-Off.
- **US-02 (Ventana de Normalización Pasiva / Settle Window)**: Como operador, requiero que ante una detención de hasheo el monitor espere una ventana pasiva de 120s a 180s antes de emitir órdenes externas, permitiendo que el watchdog nativo de VNish intente su ciclo de auto-recuperación sin interferencias de software.
- **US-03 (Protección e Inhibición ante `CHAIN_FAULT` Físico)**: Como operador, si una placa presenta falla física persistente, requiero que el sistema inhiba reintentos agresivos de re-arranque y permita la operación segura con las placas sanas restantes (minería de contención en preset reducido) en lugar de apagar el minero completo.
- **US-04 (Enfriamiento Proactivo / Headroom Chilling)**: Como operador, si un minero es elegible para subir de preset (ej. 2500W $\to$ 2700W) pero está frenado únicamente por margen térmico ($80.5^\circ\text{C} \le T \le 82.0^\circ\text{C}$) y los ventiladores están por debajo del 98%, requiero que el sistema fuerce temporalmente los ventiladores al 100% durante 180s para bajar la temperatura a $\le 78.5^\circ\text{C}$ y habilitar el salto de preset (+6 TH/s de ganancia).
- **US-05 (Respuesta Inmediata a 83.0°C)**: Como operador, requiero que ante lecturas de temperatura $\ge 83.0^\circ\text{C}$ el Governor no demore ciclos de dwell y salte inmediatamente a máxima ventilación preventiva.

---

## 3. Functional Requirements

### FR-01: Secuencia de Recuperación Suave (Soft-Landing Restart)
- Antes de invocar `safe_restart_mining(host, password)`:
  1. Invocar `safe_set_miner_preset(host, safe_preset, clamp_top_preset=True)` donde `safe_preset` es `"1800"` o `"2000"`.
  2. Aguardar 2.0 segundos para confirmar la fijación de voltajes bajos en firmware.
  3. Despachar `safe_restart_mining`.
  4. Marcar en el estado en memoria que el minero está en `staged_ramp_up_pending = True`.

### FR-02: Ventana Pasiva de Settle (Passive Settle Window)
- Ante la detección de `stopped_state` o `restart_required_flag`:
  * Si `elapsed_since_stopped < safe_recovery_settle_window_seconds` (120s por defecto), registrar en log `[SAFE-RECOVERY] miner={name} en ventana pasiva de settle ({elapsed}s/120s)` y NO emitir órdenes REST.
  * Si el firmware normaliza por sí solo durante la ventana pasiva, cancelar la intervención.

### FR-03: Inhibición de Reinicios ante Falla Física de Cadena
- Si el minero reporta `CHAIN_FAULT` con 0 ASICs o error de bus persistente en una placa:
  * Permitir como máximo 1 intento de soft-landing restart.
  * Si tras el intento la cadena no responde, fijar el minero en modo degradado seguro (preset de 2 placas, ej. 1600W-1800W) y notificar a Telegram sin forzar reintentos que pongan en riesgo la fuente.

### FR-04: Protocolo de Enfriamiento Proactivo (Headroom Chilling)
- En la evaluación de subida de preset del Preset Balancer:
  * Si `action == STEP_UP_BLOCKED_THERMAL` y `miner_target_power_w < top_power_w` y `current_fan_duty < 98%`:
  * Emitir solicitud `boost_cooling = True` al Fan Governor por 180 segundos.
  * Fan Governor fija ventiladores al 100% PWM.
  * Si $T_{max}$ desciende a $\le 78.5^\circ\text{C}$, Balancer ejecuta la subida a 2700W.

### FR-05: Ajuste de Umbral de Emergencia a 83.0°C
- Calibrar `"fan_governor_emergency_temp_c": 83.0` (o acelerador a +6% por step si $T \ge 82.8^\circ\text{C}$), eliminando retrasos de modulación por encima de 82.5°C.

---

## 4. Safety Invariants (Inviolables)
1. **Prioridad Absoluta Térmica**: Nada en el protocolo de Headroom Chilling o Soft-Landing puede suprimir un `EMERGENCY_SPIKE` si $T \ge 83.0^\circ\text{C}$.
2. **Determinismo y Libre de Efectos Secundarios**: La lógica pura de decisión de recuperación suave debe evaluarse en un módulo determinista sin I/O directo.
3. **Cero Regresiones**: La suite completa de 1221 pruebas unitarias debe mantenerse en 100% PASS.
