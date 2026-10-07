# Feature Specification: Desacoplamiento de Telemetría de Cadenas & Sockets ASIC 4028 (Spec 089)

**Feature Name**: Hardware Telemetry & ASIC Sockets Decoupling  
**Feature Code**: `089-hardware-telemetry-decoupling`  
**Tracking Issue / Proposal**: PROP-021 (Fase C) / Spec 089  
**Status**: DESIGNED / PLANNING ONLY (DO NOT IMPLEMENT UNTIL SPEC 088 IS CLOSED)  
**Author**: Antigravity Assistant & Technical Architecture  
**Baseline**: Requiere cierre exitoso de Spec 088  
**Target Outcome**: Extracción de `_async_collect_chain_telemetry` hacia `app/hardware/chain_collector.py`, eliminación de copias duplicadas de sockets 4028 reutilizando `app/network/cgminer_client.py`, reduciendo ~1.000 LOC netas en `app/miner_monitor.py`.

---

## 1. Problem Statement & Motivation

[`app/miner_monitor.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py) conserva:
1. **Recolección asíncrona de cadenas** (L2944–L3361, ~418 LOC): Realiza peticiones a VNish API para métricas chip-level y persiste en base de datos.
2. **Duplicación de sockets raw** (L1078–L1107, ~300 LOC): Funciones como `_read_command`, `read_summary`, `read_stats_snapshot`, `read_pools` y `read_version` están duplicadas en `miner_monitor.py`, a pesar de que ya existe un cliente completo y tipado en [`app/network/cgminer_client.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/network/cgminer_client.py).
3. **Formateadores de texto de diagnóstico** (L2150–L2436, ~280 LOC): Generan cadenas largas de texto Markdown para Telegram.

Tener estas rutinas en `miner_monitor.py` infla el archivo con funciones de transporte y formateo secundarias.

---

## 2. User Stories & Value Proposition

### User Story 1: Cliente ASIC Único y Canónico
> **Como** desarrollador,  
> **Quiero** que todas las consultas de socket TCP 4028 utilicen exclusivamente `app/network/cgminer_client.py`,  
> **Para que** no existan discrepancias de timeouts, buffers ni duplicación de código en la capa de red.

### User Story 2: Módulo Especializado de Telemetría de Cadenas
> **Como** supervisor de hardware,  
> **Quiero** que la salud de chips y el predictor de rotura de cadenas residan en `app/hardware/chain_collector.py`,  
> **Para que** los algoritmos de detección de fallas de silicon estén aislados del bucle de supervisión principal.

---

## 3. Scope & Boundaries

### Included (In Scope)
* Creación de `app/hardware/chain_collector.py` y migración de `_async_collect_chain_telemetry` y `_async_evaluate_predictive_chain_break`.
* Depuración de sockets 4028 duplicados en `miner_monitor.py`, re-exportando desde `app/network/cgminer_client.py`.
* Migración de formateadores de texto (`build_stability_health_text`, `build_mining_quality_text`, etc.) a `app/telegram/fleet_cards.py`.

### Excluded (Out of Scope)
* NO modificar las tablas SQLite de `chain_telemetry` ni alterar los umbrales de predicción de rotura de cadena.
* NO modificar el protocolo TCP de socket 4028.

---

## 4. Invariants & Safety Gates

1. **Invariante Single-Spec**: Esta spec NO debe ser implementada mientras Spec 088 esté abierta.
2. **Invariante de No-Regresión**: $\ge 1522$ tests PASS.
