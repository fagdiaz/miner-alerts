# Feature Specification: Desacoplamiento de Callbacks de Telegram (`app/telegram/`)

**Feature Name**: Telegram Callbacks Decoupling  
**Feature Code**: `087-telegram-callbacks-decoupling`  
**Tracking Issue / Proposal**: PROP-021 (Fase A) / Spec 087  
**Status**: APPROVED FOR IMPLEMENTATION  
**Author**: Antigravity Assistant & Technical Architecture  
**Baseline**: 1522 tests PASS, 75 subtests PASS, NSSM Windows Service en producción  
**Target Outcome**: Extracción completa de los manejadores de callbacks interactivos fuera de `app/miner_monitor.py` hacia `app/telegram/`, reduciendo ~1.450 líneas en el archivo principal sin alterar la operación de los mineros.

---

## 1. Problem Statement & Motivation

En [`app/miner_monitor.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py), más de **1.420 líneas de código** (líneas 3755 a 5228) están dedicadas exclusivamente al manejo, formateo, verificación de tokens y despacho de botones interactivos de Telegram:
* `_handle_command_center_callback` (~506 líneas)
* `_handle_help_callback` (~45 líneas)
* `_handle_diagnostic_callback` (~240 líneas)
* `_handle_callback_query` (~680 líneas)

Tener este volumen de código de interfaz de usuario incrustado en el motor de monitoreo de planta genera:
1. **Acoplamiento Artificial**: El despachador [`app/telegram/router.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/telegram/router.py#L154) fue diseñado para enrutar callbacks, pero actualmente re-importa estos métodos desde `miner_monitor.py`.
2. **Ruido Visual Masivo**: 1.450 líneas de lógica de interfaz móvil que no interactúa directamente con los sockets de hardware de los mineros saturan el archivo central.
3. **Mantenimiento Lento**: Cada ajuste o añadido de botón requiere editar el archivo principal de 9.000 líneas.

---

## 2. User Stories & Value Proposition

### User Story 1: Modularidad Limpia en Telegram
> **Como** desarrollador y operador,  
> **Quiero** que toda la lógica de presentación, interacción y respuestas de botones táctiles de Telegram resida íntegramente dentro del paquete `app/telegram/`,  
> **Para que** `miner_monitor.py` quede libre de lógica de vistas y callbacks.

### User Story 2: Estabilidad Cero-Downtime
> **Como** responsable de la infraestructura de minado,  
> **Quiero** que esta extracción preserve el 100% de los contratos de callback existentes (`cc:*`, `help:*`, `diag:*`, `rb_cfm:*`, etc.),  
> **Para que** los operadores móviles continúen usando `/menu` y botones 1-Tap con total normalidad y sin fallos.

---

## 3. Scope & Boundaries

### Included (In Scope)
* **Extracción de `_handle_command_center_callback`**: Mover a [`app/telegram/command_center.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/telegram/command_center.py).
* **Extracción de `_handle_help_callback`**: Mover a [`app/telegram/help_center.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/telegram/help_center.py).
* **Extracción de `_handle_diagnostic_callback` y `_handle_callback_query`**: Mover a [`app/telegram/callbacks.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/telegram/callbacks.py).
* **Actualización del Router**: Modificar [`app/telegram/router.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/telegram/router.py) para despachar directamente a las funciones dentro de `app.telegram.*`.
* **Shims de Compatibilidad**: Dejar re-exports de una sola línea en `miner_monitor.py` para garantizar 0 roturas en tests legacy o invocaciones externas:
  ```python
  from app.telegram.command_center import _handle_command_center_callback
  from app.telegram.help_center import _handle_help_callback
  from app.telegram.callbacks import _handle_diagnostic_callback, _handle_callback_query
  ```

### Excluded (Out of Scope)
* NO tocar el bucle de control de hardware de mineros (`while True:` en `main()`).
* NO modificar el algoritmo del Fan Governor, Preset Balancer o Thermal Guard.
* NO cambiar el formato de `callback_data` ni la gramática de tokens (mantener $\le 64$ bytes).

---

## 4. Invariants & Safety Gates

1. **Invariante de Test Suite**: La suite de pruebas debe mantener los **1522 tests PASS** (o sumar nuevos tests de regresión) con 0 fallos.
2. **Invariante de Formato Mobile-First**: Todos los mensajes editados o emitidos por callbacks deben continuar respetando $\le 32$ columnas visibles por línea.
3. **Invariante de Thread Safety**: Las lecturas y modificaciones de `states` durante el procesamiento de callbacks deben continuar protegidas bajo `state_lock`.
4. **Compuerta de Salida**: Pasar `speckit-stabilize` (8/8 gates PASS), registrar entrada en `docs/audit/DEVELOPMENT_LOG.md` y commit feature-scoped.
