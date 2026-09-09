# Plan de Implementación: Spec 045 - Telegram Mobile Help Center

## Metadatos
- **Spec**: `045-telegram-mobile-help-center`
- **Fase Actual**: Fase 1 (Módulo Puro, Contratos y Pruebas Unitarias)
- **Engine Asignado Fase 1**: Gemini 3.8 Flash High
- **Revisor de Integración Fase 2**: Claude Sonnet 4.6 (Thinking) / Codex

---

## 1. Desglose de Fases de Entrega

### Fase 1: Módulo Puro, Esquemas y Pruebas Deterministas (Gemini 3.8 Flash High)
- [x] Crear estructura de especificación en `specs/045-telegram-mobile-help-center/`.
- [x] Actualizar `.specify/feature.json` a `specs/045-telegram-mobile-help-center`.
- [x] Diseñar e implementar `app/telegram/help_center.py` con registro canónico `HELP_REGISTRY`.
- [x] Implementar helpers de ancho de línea (`visible_line_width`), sanitización (`escape_markdown`, `strip_markdown`).
- [x] Implementar renderizadores interactivos:
  - `render_help_home()` -> Vista principal por categorías.
  - `render_help_category(cat_key)` -> Vista de submenú.
  - `render_help_command_detail(cmd_name)` -> Vista de comando individual.
- [x] Implementar parser de callbacks `parse_help_callback()` con límite estricto de 64 bytes.
- [x] Crear suite de pruebas exhaustiva en `tests/test_help_center.py`.
- [x] Verificar que toda línea de datos cumpla `<= 32` caracteres visibles y que ninguna vista interactiva supere los 3,600 caracteres.
- [x] Compilar sintácticamente (`py_compile`) y ejecutar la suite global (624 base + nuevos tests).

### Fase 2: Integración en Dispatcher de Telegram y Handoff (Gemini 3.8 Flash High - Micro-pasos)
- [x] Conectar `help:` en el router de callbacks de `_handle_callback_query` en `app/miner_monitor.py`.
- [x] Asegurar ACK temprano con `answer_callback_query` antes de edición de mensaje o acceso a locks.
- [x] Conectar fallback de entrega cuando `queue=None` para preservar `reply_markup` y `parse_mode`.
- [x] Conectar comando `/help` y `/info` al nuevo módulo manteniendo compatibilidad legacy si la cola o cliente no admiten inline keyboard.
- [x] Agregar botón de acceso a Ayuda `[ 📖 Centro de Ayuda ]` en el Command Center `/menu`.
- [x] Ejecutar smoke testing con mocks integrados, suite completa (660 tests PASS) y release audit limpio.


---

## 2. Puntos de Control y Reglas de Calidad (C1-C10)
- **C1**: Tarjetas móviles con límite de 32 caracteres visibles por línea de datos.
- **C2**: Registro canónico único en `app/telegram/help_center.py`.
- **C3**: Callbacks `help:` acotados a 64 bytes y validados por gramática cerrada.
- **C4**: No usar particionador `split_telegram_message()` en vistas interactivas (vistas <= 3,600 caracteres).
- **C5**: Escape adecuado de caracteres Markdown.
- **C6**: Preservar markup en fallbacks directos.
- **C7**: Cero cambios en FSM, auto-reboot, polling ni Hashcore.
- **C8**: Separación estricta de fases; Spec 046 queda para la siguiente iteración.
- **C9**: Cobertura de tests para entradas hostiles, nombres largos y Unicode.
- **C10**: Evidencia registrada sin saltarse validación de servicio.
