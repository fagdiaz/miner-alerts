# Feature Specification: Desacoplamiento de Ciclos de Gobernanza (Spec 088)

**Feature Name**: Governance Cycles Decoupling (Balancer & Autotune Watchdogs)  
**Feature Code**: `088-governance-cycles-decoupling`  
**Tracking Issue / Proposal**: PROP-021 (Fase B) / Spec 088  
**Status**: DESIGNED / PLANNING ONLY (DO NOT IMPLEMENT UNTIL SPEC 087 IS CLOSED)  
**Author**: Antigravity Assistant & Technical Architecture  
**Baseline**: Requiere cierre exitoso de Spec 087 (1522+ tests PASS)  
**Target Outcome**: Extracción completa de `execute_balancer_cycle` (~252 LOC) y `check_autotune_watchdog` (~140 LOC) fuera de `app/miner_monitor.py` hacia `app/governance/`, reduciendo ~850 líneas netas.

---

## 1. Problem Statement & Motivation

En [`app/miner_monitor.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py), dos subsistemas de control de potencia y rescate de hardware residen directamente en el orquestador principal:
1. `execute_balancer_cycle` (L3362–L3614): Regula los presets de potencia de la flota entre 2300W, 2500W y 2700W en base a la salud de fuentes, horarios solares y balance de elevadores.
2. `check_autotune_watchdog` (L3615–L3754): Detecta mineros estancados en fase de autotuning (>600s con <20 TH/s) y ejecuta rescates forzosos mediante re-inyección de preset.

Tener estas rutinas adentro de `miner_monitor.py`:
- Viola el principio de responsabilidad única.
- Dificulta auditar los bloqueos de sincronización y estado (`state_lock`, `_orchestrator_state.py`).
- Impide testear los ciclos de balanceo de forma puramente determinista sin instanciar dependencias de Telegram.

---

## 2. User Stories & Value Proposition

### User Story 1: Confiabilidad en el Balanceo de Potencia
> **Como** operador de planta,  
> **Quiero** que el algoritmo del Dynamic Balancer opere como un módulo cerrado y aislado en `app/governance/balancer_cycle.py`,  
> **Para que** las decisiones de modulación de potencia no dependan ni interactúen con variables ajenas de UI o sockets.

### User Story 2: Rescate Autónomo Anti-Autotune Stall
> **Como** supervisor de infraestructura,  
> **Quiero** que el watchdog de autotune resida en `app/governance/autotune_watchdog.py`,  
> **Para que** su lógica de rescate esté 100% aislada y verificable con pruebas unitarias independientes.

---

## 3. Scope & Boundaries

### Included (In Scope)
* Creación de `app/governance/balancer_cycle.py` y migración de `execute_balancer_cycle`.
* Extracción de `check_autotune_watchdog` como `execute_autotune_watchdog_cycle` en `app/governance/autotune_watchdog.py`.
* Invocación de ambos módulos desde `main()` y creación de shims de re-export en `miner_monitor.py`.
* Verificación exhaustiva de thread-safety (`state_lock`).

### Excluded (Out of Scope)
* NO alterar las fórmulas matemáticas de balanceo de elevadores ni los umbrales de soak time.
* NO modificar los tiempos de espera de rescate de autotune (600s, 20 TH/s).

---

## 4. Invariants & Safety Gates

1. **Invariante Single-Spec**: Esta spec NO debe ser implementada mientras Spec 087 esté abierta.
2. **Invariante de Thread Safety**: Toda mutación de `state.balancer_preset`, `state.balancer_last_change_ts` o cerraduras de hardware debe ejecutarse bajo `state_lock`.
3. **Invariante de Test Suite**: $\ge 1522$ tests PASS, 0 regresiones.
