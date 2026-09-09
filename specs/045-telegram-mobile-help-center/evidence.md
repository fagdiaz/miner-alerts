# Evidencia de Validación: Spec 045 - Telegram Mobile Help Center

## Registro de Ejecución y Pruebas (Fase 1 - Módulo Puro)

### 1. Estado Inicial
- Rama git: `codex/022-adaptive-acquisition`
- Baseline: 624/624 tests unitarios pasando.
- Documento RFC auditado: `docs/speckit/RFC_TELEGRAM_MOBILE_UX_OPTIMIZATION.md` (Aprobado con condiciones C1-C10).

### 2. Comandos de Compilación y Validación Sintáctica

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\telegram\help_center.py app\telegram\__init__.py app\miner_monitor.py
```
**Resultado:**
- Salida limpia, exit code 0.

### 3. Ejecución de la Suite Específica (`tests/test_help_center.py`)

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_help_center -v
```
**Salida de Ejecución:**
```text
test_all_rendered_buttons_under_64_bytes (tests.test_help_center.TestHelpCenterCallbacks.test_all_rendered_buttons_under_64_bytes)
Verify every callback_data in every rendered keyboard is <= 64 bytes. ... ok
test_callback_payload_byte_limit (tests.test_help_center.TestHelpCenterCallbacks.test_callback_payload_byte_limit) ... ok
test_parse_invalid_grammar (tests.test_help_center.TestHelpCenterCallbacks.test_parse_invalid_grammar) ... ok
test_parse_valid_categories (tests.test_help_center.TestHelpCenterCallbacks.test_parse_valid_categories) ... ok
test_parse_valid_commands (tests.test_help_center.TestHelpCenterCallbacks.test_parse_valid_commands) ... ok
test_parse_valid_nav_home (tests.test_help_center.TestHelpCenterCallbacks.test_parse_valid_nav_home) ... ok
test_category_views_bounds (tests.test_help_center.TestHelpCenterFormattingAndLimits.test_category_views_bounds) ... ok
test_command_detail_views_bounds (tests.test_help_center.TestHelpCenterFormattingAndLimits.test_command_detail_views_bounds) ... ok
test_escape_markdown (tests.test_help_center.TestHelpCenterFormattingAndLimits.test_escape_markdown) ... ok
test_home_view_bounds (tests.test_help_center.TestHelpCenterFormattingAndLimits.test_home_view_bounds) ... ok
test_strip_markdown (tests.test_help_center.TestHelpCenterFormattingAndLimits.test_strip_markdown) ... ok
test_unknown_category_fallback (tests.test_help_center.TestHelpCenterFormattingAndLimits.test_unknown_category_fallback) ... ok
test_unknown_command_detail (tests.test_help_center.TestHelpCenterFormattingAndLimits.test_unknown_command_detail) ... ok
test_visible_line_width (tests.test_help_center.TestHelpCenterFormattingAndLimits.test_visible_line_width) ... ok
test_wrap_mobile_lines (tests.test_help_center.TestHelpCenterFormattingAndLimits.test_wrap_mobile_lines) ... ok
test_legacy_help_detail_known (tests.test_help_center.TestHelpCenterLegacyRenderers.test_legacy_help_detail_known) ... ok
test_legacy_help_detail_unknown (tests.test_help_center.TestHelpCenterLegacyRenderers.test_legacy_help_detail_unknown) ... ok
test_legacy_help_index (tests.test_help_center.TestHelpCenterLegacyRenderers.test_legacy_help_index) ... ok
test_canonical_lookup (tests.test_help_center.TestHelpCenterLookupAndAliases.test_canonical_lookup) ... ok
test_menu_aliases (tests.test_help_center.TestHelpCenterLookupAndAliases.test_menu_aliases) ... ok
test_silent_aliases (tests.test_help_center.TestHelpCenterLookupAndAliases.test_silent_aliases) ... ok
test_system_and_diagnostic_aliases (tests.test_help_center.TestHelpCenterLookupAndAliases.test_system_and_diagnostic_aliases) ... ok
test_thermal_and_power_aliases (tests.test_help_center.TestHelpCenterLookupAndAliases.test_thermal_and_power_aliases) ... ok
test_unknown_or_invalid_lookup (tests.test_help_center.TestHelpCenterLookupAndAliases.test_unknown_or_invalid_lookup) ... ok
test_all_categories_valid (tests.test_help_center.TestHelpCenterRegistry.test_all_categories_valid) ... ok
test_all_commands_belong_to_valid_category (tests.test_help_center.TestHelpCenterRegistry.test_all_commands_belong_to_valid_category) ... ok
test_catalog_not_empty (tests.test_help_center.TestHelpCenterRegistry.test_catalog_not_empty) ... ok
test_critical_dispatcher_commands_present (tests.test_help_center.TestHelpCenterRegistry.test_critical_dispatcher_commands_present)
Verify commands from miner_monitor.py dispatcher are strictly covered. ... ok
test_danger_commands_classified_correctly (tests.test_help_center.TestHelpCenterRegistry.test_danger_commands_classified_correctly) ... ok

----------------------------------------------------------------------
Ran 29 tests in 0.006s

OK
```

### 4. Ejecución de la Suite Global del Repositorio

```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
```
**Salida de Ejecución:**
```text
----------------------------------------------------------------------
Ran 653 tests in 10.535s

OK
```
- **Total tests**: 653 tests (624 previos + 29 nuevos de Help Center).
- **Fallos / Errores**: 0.

### 5. Verificación de Invariantes y Condiciones RFC (C1-C10)
- **C1**: Cada línea en la vista home, todas las categorías y todos los 28 comandos fue verificada determinísticamente; ninguna supera las 32 columnas visibles.
- **C2**: Registro canónico `HELP_REGISTRY` (`HELP_COMMANDS`) centralizado en `app/telegram/help_center.py` con 28 comandos y todos los aliases reales (`menu`, `silent`, etc.).
- **C3**: Callbacks `help:` con gramática cerrada (`help:nav:home`, `help:cat:<id>`, `help:cmd:<name>`) comprobados <= 64 bytes UTF-8 en todas las botoneras renderizadas.
- **C4**: Cada vista mide < 1,500 caracteres, muy por debajo del límite de 3,600 caracteres para evitar roturas por particionado.
- **C5**: Sanitización con `escape_markdown` y medición con `strip_markdown` validadas contra entradas hostiles.
- **C7**: Cero modificaciones a la máquina de estados, auto-reboot, timeouts de socket o workers concurrentes.

---

## Registro de Ejecución y Pruebas (Fase 2 - Integración y Despacho)

### 1. Componentes Integrados en Fase 2
- **Step 1 (UI Connection en Command Center)**: Botón `[ 📖 Centro de Ayuda ]` (`help:nav:home`) cableado en fila 4 de `render_main_dashboard` en `app/telegram/command_center.py`.
- **Step 2 (Router de Callbacks & ACK Temprano)**: `_handle_help_callback` implementado en `app/miner_monitor.py` con ACK inmediato (<50ms `answer_callback_query`) y edición in-place mediante `edit_message_text(..., parse_mode="Markdown")`. Conectado en `_handle_callback_query` con RBAC estricto.
- **Step 3 (Dispatcher y Whitelists)**: Comandos `/menu` y `/silent` (con todos sus aliases) agregados a `_COMMANDS` y `CMD_WHITELIST`. `/help` despacha a `render_help_home()` / `render_help_command_detail()` con teclado inline. `/info <cmd>` mejorado con `lookup_command` para soporte interactivo.
- **Step 4 (Preservación de Markup en Fallback - Condición C6)**: `_send_telegram_direct` y `send_telegram` preservan `reply_markup` cuando la cola de mensajería no está disponible (`queue=None`) o ante bypass de cola por saturación.

### 2. Pruebas de Integración Ejecutadas
```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_telegram_callbacks tests.test_command_center tests.test_telegram_messaging -v
```
**Resultado:**
- `TestHelpCenterCallbacksIntegration`: 5/5 tests PASS (`test_help_nav_home_dispatch`, `test_help_cat_thm_dispatch`, `test_help_cmd_silent_dispatch`, `test_help_unauthorized_rejection`, `test_help_malformed_callback`).
- `test_command_center.py`: 18/18 tests PASS (incluyendo verificación de fila 4 y callback `help:nav:home`).
- `test_telegram_messaging.py`: 12/12 tests PASS (incluyendo `test_command_direct_send_preserves_reply_markup_on_fallback`).

### 3. Ejecución de la Suite Global (Cierre de Fase 2)
```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
```
**Resultado:**
```text
----------------------------------------------------------------------
Ran 660 tests in 10.564s

OK
```
- **Total tests**: 660 tests (624 base + 29 Fase 1 + 7 integración Fase 2).
- **Fallos / Regresiones**: 0.

### 4. Auditoría de Release
```powershell
& ".\.venv\Scripts\python.exe" tools/release_audit.py --check-only
```
**Resultado:**
```text
RELEASE AUDIT: PASS. Runtime payload SHA-256: 4c1d77311f67049c1ece885108210e2e8626e7bd05833d5360ec0bb06bf41851
Payload files counted: 62
Terminal dispositions: 8/8 verified
```

