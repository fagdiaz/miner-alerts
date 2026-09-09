# Tareas: Spec 045 - Telegram Mobile Help Center

## Estado General
- **Total Tareas**: 8
- **Completadas**: 8 (Fase 1 y Fase 2 completadas)
- **Pendientes**: 0 (Implementación e Integración Completada)

---

## Tareas de Fase 1 (Gemini 3.8 Flash High)

- [x] **T1: Inicialización de Speckit Spec 045**: Crear directorio `specs/045-telegram-mobile-help-center/` con `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/help-center-api.md`, `quickstart.md`, `checklists/requirements.md` y `evidence.md`. Actualizar `.specify/feature.json`.
- [x] **T2: Registro Canónico de Comandos**: Definir `CommandDefinition`, `HelpCategory`, `HELP_CATEGORIES`, `HELP_COMMANDS` y `HELP_ALIASES` en `app/telegram/help_center.py` cubriendo la totalidad de comandos del dispatcher (incluyendo `/menu`, `/silent` y todos sus aliases).
- [x] **T3: Utilidades de Formato Seguro y Ancho**: Implementar `strip_markdown`, `visible_line_width` y `escape_markdown` en `app/telegram/help_center.py`.
- [x] **T4: Renderizadores Mobile-First**: Implementar `render_help_home()`, `render_help_category()` y `render_help_command_detail()` asegurando formato vertical, viñetas `•`, límites `<= 32` caracteres visibles por línea de datos y tamaño total `< 3,600` caracteres.
- [x] **T5: Parser y Validador de Callbacks**: Implementar `parse_help_callback()` con límite estricto de 64 bytes y gramática cerrada `help:nav:home`, `help:cat:<id>`, `help:cmd:<name>`.
- [x] **T6: Suite Unitaria Exhaustiva**: Crear `tests/test_help_center.py` con pruebas para registro, aliases, anchos de línea, tamaño total, escape de Markdown hostil, callbacks válidos/inválidos/largos y desacoplamiento de I/O.

---

## Tareas de Fase 2 (Micro-pasos Implementados y Certificados)

- [x] **T7: Integración en Dispatcher de Telegram**: Conectar router `help:` en `_handle_callback_query` de `app/miner_monitor.py` con ACK temprano (`answer_callback_query`), manejo de `MessageNotModified`, integración en Command Center (`[ 📖 Centro de Ayuda ]`), enriquecimiento de `/info <cmd>`, registro en whitelists y fallback seguro ante `queue=None` preservando `reply_markup` (Condición C6).
- [x] **T8: Smoke Testing y Validación Móvil**: Ejecutar suite de integración completa en `tests/test_telegram_callbacks.py`, `tests/test_telegram_messaging.py` y `tests/test_command_center.py`. Registrar evidencia de navegación y release audit (660 tests PASS) en `evidence.md`.

