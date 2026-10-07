# Feature Specification: Descomposición y Modularización del Monolito (`miner_monitor.py`)

**Feature Name**: Monolith Decoupling & Architecture Modularization  
**Feature Code**: `087-monolith-decoupling`  
**Tracking Issue / Proposal**: PROP-021 (Continuación) / Spec 087  
**Status**: DRAFT / APPROVED FOR EXECUTION  
**Author**: Antigravity Assistant & Technical Architecture  
**Baseline**: 1520 tests PASS, 75 subtests PASS, NSSM Windows Service en producción  
**Target Outcome**: Reducción neta de `app/miner_monitor.py` de 9.074 líneas a $\le 500$ líneas a través de 5 fases acotadas.

---

## 1. Problem Statement & Motivation

A pesar de las iteraciones de estabilización previas, el archivo central [`app/miner_monitor.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py) ha alcanzado **9.074 líneas de código**, albergando más de 18 subsistemas distintos en un único archivo.
La función `main()` por sí sola contiene **3.568 líneas**, de las cuales **3.076 líneas** corresponden a un único bucle procedural `while True:`.

Esta hiperconcentración ("God Object") genera fricciones críticas en producción:
1. **Riesgo de Regresiones Cruzadas**: Múltiples subsistemas (gobernador de ventiladores, guardia térmica, balanceador de potencia, paradas de mantenimiento) mutan campos del mismo diccionario de estado sin fronteras claras de encapsulamiento. Esto causó recientemente el incidente donde S19JPRO-26 retuvo ventiladores al 100% de forma indefinida.
2. **Saturación Cognitiva y de Contexto**: La lectura y razonamiento sobre el archivo requiere decenas de miles de tokens de contexto para cualquier cambio menor.
3. **Imposibilidad de Testeo Aislado**: Las pruebas unitarias deben importar y mockear dependencias masivas del monolito en lugar de probar módulos con contratos cerrados.

---

## 2. User Stories & Value Proposition

### User Story 1: Confiabilidad y Seguridad Operativa para el Minero
> **Como** operador de la granja de minería ASIC,  
> **Quiero** que los subsistemas de control (térmico, potencia, reinicios y paradas) operen en módulos independientes y testeados de forma aislada,  
> **Para que** un cambio o comando en un área (ej. Telegram o balanceador) nunca pueda descalibrar inadvertidamente los ventiladores o la potencia de otra máquina en producción.

### User Story 2: Mantenibilidad y Agilidad de Desarrollo
> **Como** desarrollador o agente de mantenimiento,  
> **Quiero** que cada archivo del proyecto tenga una única responsabilidad bien definida ($\le 500$ líneas),  
> **Para que** auditar, reparar bugs o añadir nuevas características sea predecible, rápido y sin efectos secundarios ocultos.

### User Story 3: Cero Downtime en Producción
> **Como** responsable de la infraestructura,  
> **Quiero** que la modularización se ejecute de forma progresiva a través de 5 fases acotadas,  
> **Para que** en cada paso los 1520 tests continúen pasando al 100% y el servicio de Windows (`MinerAlerts`) pueda recargarse sin interrupciones.

---

## 3. Scope & Boundaries

### Included (In Scope)
* **Fase 1**: Extracción de todos los handlers de callbacks y despacho de Telegram (`_handle_command_center_callback`, etc., ~1.450 L) hacia `app/telegram/`.
* **Fase 2**: Extracción de la lógica restante de gobernanza (`execute_balancer_cycle` y `check_autotune_watchdog`, ~850 L) hacia `app/governance/`.
* **Fase 3**: Extracción de la recolección asíncrona de cadenas de chips y wrappers de sockets ASIC 4028 (~1.000 L) hacia `app/hardware/` y `app/network/`.
* **Fase 4**: Modernización del test legacy de inspección estricta de código fuente (`tests/test_startup_grace_period.py:222`) para permitir la refactorización de `main()`.
* **Fase 5**: Conversión del bucle procedural de `main()` en un pipeline de 7 etapas declarativas utilizando `CoreSupervisoryEngine` (`app/core/engine.py`), dejando `miner_monitor.py` en $\le 500$ líneas.

### Excluded (Out of Scope)
* Alterar la semántica de los comandos de Telegram existentes o las directivas de control de mineros.
* Modificar el esquema de la base de datos SQLite v7 o los formatos de persistencia en disco de `state.json`.
* Cambiar la frecuencia de polling (30s) o las temperaturas de consigna de los mineros.

---

## 4. Invariants & Safety Gates

1. **Invariante de Test Suite**: En ningún momento del refactor la suite de pruebas puede descender de **1520 tests PASS** ni admitir fallos o errores.
2. **Invariante de Interfaz (Backward Compatibility)**: Toda función o clase pública que sea movida de `miner_monitor.py` a un submódulo debe permanecer temporalmente re-exportada como alias en `miner_monitor.py` para no quebrar tests ni herramientas externas (`tools/`).
3. **Invariante de Thread Safety**: El acceso concurrente a `states` (entre el hilo principal de control y el hilo de polling de Telegram) debe seguir estrictamente protegido por `state_lock` y respetar la jerarquía de bloqueos anti-deadlock.
