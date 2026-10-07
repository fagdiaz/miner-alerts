# Feature Specification: Conversión del Core Daemon en Pipeline Declarativo de Hooks (Spec 091)

**Feature Name**: Core Daemon Hookification & Monolith Dissolution  
**Feature Code**: `091-core-daemon-hookification`  
**Tracking Issue / Proposal**: PROP-021 (Cierre Definitivo) / Spec 091  
**Status**: DESIGNED / PLANNING ONLY (DO NOT IMPLEMENT UNTIL SPEC 090 IS CLOSED)  
**Author**: Antigravity Assistant & Technical Architecture  
**Baseline**: Requiere cierre exitoso de Spec 090  
**Target Outcome**: Transformación de las 3.076 líneas procedurales del bucle `while True:` de `main()` en el pipeline de 7 etapas de `CoreSupervisoryEngine` (`app/core/engine.py`), reduciendo `app/miner_monitor.py` a $\le 450$ LOC finales. Release V6.0.

---

## 1. Problem Statement & Motivation

Una vez completadas las extracciones de Telegram (Spec 087), Gobernanza (Spec 088), Telemetría de Hardware (Spec 089) y la modernización de tests (Spec 090), el único remanente monolítico es el cuerpo interno de `main()` en [`app/miner_monitor.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py).

El bucle `while True:` ejecuta secuencialmente decenas de comprobaciones inline en vez de aprovechar la arquitectura de hooks de 7 etapas creada en la Spec 065 ([`app/core/engine.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/core/engine.py)).
Esta spec culmina la visión arquitectónica del proyecto: disolver el monolito y convertir `miner_monitor.py` en un mero orquestador de inicio liviano y declarativo.

---

## 2. User Stories & Value Proposition

### User Story 1: Arquitectura Limpia y Profesional de Grado Industrial
> **Como** ingeniero de software y operador de planta,  
> **Quiero** que el ciclo de supervisión de los mineros esté estructurado en etapas estrictas y aisladas (`PreTick`, `Acquisition`, `Detection`, `Governance`, `Actuator`, `Persistence`, `PostTick`),  
> **Para que** cada fase del ciclo tenga una responsabilidad única, tiempos de ejecución medibles y contención defensiva contra excepciones.

### User Story 2: Código Legible y Mantenible
> **Como** desarrollador,  
> **Quiero** que `miner_monitor.py` tenga menos de 450 líneas,  
> **Para que** cualquier modelo o humano pueda leer, auditar y entender el funcionamiento del sistema en menos de 2 minutos.

---

## 3. Scope & Boundaries

### Included (In Scope)
* Encapsular la inicialización de `main()` (bootstrap, IPC pipe, EventStore, mutex) en `CoreSupervisoryEngine.initialize()`.
* Mapear las 18 lógicas procedurales del `while True:` a los 7 hooks ya existentes en `app/core/engine.py`.
* Reducir `main()` en `miner_monitor.py` a:
  ```python
  def main() -> None:
      config = load_config()
      init_logger_from_config(config)
      mutex = acquire_mutex_or_exit(_mutex_name())
      try:
          engine = CoreSupervisoryEngine(config)
          engine.register_standard_hooks()
          engine.run_forever()
      finally:
          release_mutex()
  ```
* Certificar que `app/miner_monitor.py` mida $\le 450$ líneas totales.

### Excluded (Out of Scope)
* NO alterar ninguna política de reinicio, cooldowns ni gobernanza térmica.
* NO modificar el formato de telemetría ni los registros de base de datos.

---

## 4. Invariants & Safety Gates

1. **Invariante Single-Spec**: Esta spec NO debe ser implementada mientras Spec 090 esté abierta.
2. **Invariante de Persistencia Garantizada**: La etapa `PERSISTENCE` debe ejecutarse SIEMPRE, incluso si fallan etapas previas, garantizando que el estado se vuelque a disco.
3. **Invariante de Test Suite**: $\ge 1522$ tests PASS, 0 regresiones.
4. **Compuerta de Cierre V6.0**: `speckit-stabilize` 8/8 gates PASS, release mayor del proyecto.
