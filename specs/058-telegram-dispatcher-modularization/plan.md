# Implementation Plan: Spec 058 — Telegram Command Center & Dispatcher Modularization (MT-01)

**Branch**: `codex/022-adaptive-acquisition` | **Date**: 2026-09-15 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/058-telegram-dispatcher-modularization/spec.md`  

---

## Summary

Desacoplar el bucle procedural y los manejadores de comandos y callbacks de Telegram (que actualmente suman más de 3,500 líneas en `app/miner_monitor.py`) en una arquitectura modular, orientada a handlers tipados e independientes bajo `app/telegram/`:
1. `app/telegram/context.py`: Objeto `TelegramRequestContext` con referencias seguras a `config`, `states`, `state_lock`, `event_store`, `hashcore_cfg`, etc.
2. `app/telegram/router.py`: Despachador de comandos por diccionario `TelegramCommandRouter` y despachador de callbacks `TelegramCallbackRouter`.
3. `app/telegram/commands/`: Paquete con handlers especializados (`status.py`, `fans.py`, `interventions.py`, `reboot.py`, `diagnostics.py`, `maintenance.py`, `help.py`).
4. `app/telegram/poller.py`: Worker de long polling limpio (<150 LOC) que gestiona offsets y reintentos sin lógica de negocio anidada.
5. Preservar fachadas delegatorias en `app/miner_monitor.py` para asegurar 100% de compatibilidad con los 902 tests unitarios e integraciones existentes.

---

## Technical Context

**Language/Version**: Python 3.12 (virtualenv en Windows 11)  
**Primary Dependencies**: Telegram Bot API (HTTP long polling), urllib / requests, SQLite (`EventStore`)  
**Storage**: `state.json` (persistencia atómica protegida por `_SAVE_STATE_LOCK` fuera de `state_lock`)  
**Testing**: `unittest` standard library (`tests/test_*.py`)  
**Target Platform**: Windows 11 Pro / Servicio Windows `MinerAlerts`  
**Performance Goals**: Latencia de respuesta de comandos <500ms; ACK de callbacks <50ms  
**Constraints**:
- Jerarquía anti-deadlock L1 (`state_lock`) $\rightarrow$ L2 (`_SAVE_STATE_LOCK`) estricta.
- No-Silence Policy de Telegram: todo fallo interno o timeout debe emitir mensaje de error amigable.
- Cero regresiones en los 902 tests existentes.
- Mantener las funciones facades en `miner_monitor.py` que importan los tests de integración (`_handle_command_center_callback`, etc.).

---

## Constitution Check

*GATE: Must pass before implementation.*

1. **Principio 1 (Monitoreo Continuo & Seguridad)**: ✅ Las modificaciones en Telegram están 100% aisladas del bucle autoritativo 4028.
2. **Principio 2 (Interlocks Constitucionales)**: ✅ Los comandos mutantes (`/reboot`, `/interventions`, `/snooze`) continúan canalizándose a través de las puertas lógicas y los 6 interlocks obligatorios.
3. **Principio 3 (Concurrencia y Locks)**: ✅ Respeta estrictamente QW-04 (`_build_state_payload` con `state_lock` y `_flush_state_payload` fuera de `state_lock`).
4. **Principio 4 (No Silencio Operativo)**: ✅ Toda ruta de ejecución del router cuenta con capturador de excepciones y fallback seguro.

---

## Proposed Project Structure

```text
app/
├── miner_monitor.py             # Reducido de 9,724 LOC a <7,000 LOC (delegando al router)
└── telegram/
    ├── __init__.py
    ├── callbacks.py             # Callbacks de UI y tokens
    ├── charts.py                # Gráficos ASCII
    ├── command_center.py        # Vistas Mobile-First y menús táctiles
    ├── context.py               # [NUEVO] TelegramRequestContext
    ├── daily_digest.py
    ├── fleet_cards.py
    ├── help_center.py
    ├── messages.py
    ├── poller.py                # [NUEVO] Worker desacoplado de long polling
    ├── router.py                # [NUEVO] TelegramCommandRouter & CallbackRouter
    ├── snooze.py
    └── commands/                # [NUEVO PAQUETE]
        ├── __init__.py
        ├── base.py              # Clase abstracta BaseCommandHandler
        ├── diagnostics.py       # /diagnose, /chart, /health, /quality
        ├── fans.py              # /fans, /silent, /silencio
        ├── help.py              # /help, /ayuda
        ├── interventions.py     # /interventions, /contingency
        ├── maintenance.py       # /snooze, /schedule_maintenance
        ├── reboot.py            # /reboot, /reiniciar, flujo 2-step
        └── status.py            # /status, /estado, /resumen, /metrics
```

---

## Phased Implementation Plan

### Fase 1: Interfaces y Router Central
- T001: Crear `app/telegram/context.py` con `TelegramRequestContext`.
- T002: Crear `app/telegram/commands/base.py` con `BaseCommandHandler`.
- T003: Crear `app/telegram/router.py` con `TelegramCommandRouter` y `TelegramCallbackRouter`.

### Fase 2: Implementación de Handlers de Comandos
- T004: Implementar `app/telegram/commands/status.py`.
- T005: Implementar `app/telegram/commands/fans.py`.
- T006: Implementar `app/telegram/commands/interventions.py`.
- T007: Implementar `app/telegram/commands/reboot.py`.
- T008: Implementar `app/telegram/commands/diagnostics.py`.
- T009: Implementar `app/telegram/commands/maintenance.py`.
- T010: Implementar `app/telegram/commands/help.py`.

### Fase 3: Desacoplamiento del Poller y Conexión en `miner_monitor.py`
- T011: Crear `app/telegram/poller.py` con `run_telegram_poller`.
- T012: Conectar el nuevo router en `miner_monitor.py`, sustituyendo el cuerpo procedimental de `telegram_polling_worker`.
- T013: Mantener fachadas de retrocompatibilidad para `_handle_command_center_callback` y wrappers legados.

### Fase 4: Pruebas Unitarias y Certificación
- T014: Crear `tests/test_telegram_dispatcher.py` con pruebas exhaustivas de ruteo, autenticación y errores.
- T015: Ejecutar la suite completa (902 tests) asegurando 100% PASS.
- T016: Verificar y compilar con `py_compile`.
