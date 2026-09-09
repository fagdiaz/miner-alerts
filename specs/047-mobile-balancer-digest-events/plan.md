# Plan de Implementación: Spec 047 - Mobile-First Card Layout for Balancer, Digest & Operational Events

**Feature Directory**: `specs/047-mobile-balancer-digest-events`
**Fecha**: 2026-09-09
**Motor Principal**: Gemini 3.8 Flash High
**Condiciones de Control**: RFC C1-C10

---

## 1. Arquitectura y Desglose de Componentes

### 1.1 Principio de Pureza y Reutilización
- Todas las funciones de renderizado modificadas son **puras, deterministas y libres de I/O**.
- Los wrappers de líneas móviles (`wrap_mobile_lines`) y medidores de ancho (`visible_line_width`, `strip_markdown`) de `app/telegram/help_center.py` se reutilizan canónicamente para garantizar que descripciones largas, diagnósticos y recomendaciones queden estrictamente $\le 32$ columnas visibles.
- La botonera diagnóstica común y el parser de callbacks se expanden centralizadamente en `app/telegram/fleet_cards.py`.

### 1.2 Módulos Afectados
1. `app/telegram/fleet_cards.py`:
   - Extensión de `DIAG_PREFIX = "diag:"` para soportar `diag:ref:balancer`, `diag:ref:elev`, `diag:ref:digest`, `diag:ref:events`.
   - Extensión de `build_diagnostic_keyboard()` para los nuevos reportes diagnósticos.
2. `app/governance/preset_balancer.py`:
   - Refactor de `build_balancer_table_text()` y `build_miner_balancer_detail_text()`.
   - Refactor de `build_elevator_sensitivity_text()`.
3. `app/telegram/daily_digest.py`:
   - Refactor de `format_daily_digest()`.
4. `app/telegram/snooze.py`:
   - Refactor de `build_snooze_status_text()`.
5. `app/core/event_store.py`:
   - Refactor de `render_event_list()`, `render_event_detail()` y `render_reboot_decision()`.
6. `app/miner_monitor.py`:
   - Integración de teclados inline en el dispatcher (`/balancer`, `/elevadores`, `/digest`, `/events`).
   - Routing y actualización in-place en `_handle_diagnostic_callback()`.

---

## 2. Fases de Entrega

### Fase 1: Módulos Puros, Rediseño de Renderers y Tests Deterministas
- [x] **P1.1**: Extender `app/telegram/fleet_cards.py` con las nuevas opciones de teclado inline y tipos de reporte en `parse_diagnostic_callback()`.
- [x] **P1.2**: Refactorizar `build_balancer_table_text()`, `build_miner_balancer_detail_text()` y `build_elevator_sensitivity_text()` en `app/governance/preset_balancer.py` a formato vertical Mobile-First $\le 32$ columnas.
- [x] **P1.3**: Refactorizar `format_daily_digest()` en `app/telegram/daily_digest.py` a formato vertical Mobile-First $\le 32$ columnas.
- [x] **P1.4**: Refactorizar `build_snooze_status_text()` en `app/telegram/snooze.py` a formato vertical Mobile-First $\le 32$ columnas.
- [x] **P1.5**: Refactorizar `render_event_list()`, `render_event_detail()` y `render_reboot_decision()` en `app/core/event_store.py` a formato vertical Mobile-First $\le 32$ columnas.
- [x] **P1.6**: Crear suite exhaustiva `tests/test_mobile_diagnostics.py` validando $\le 32$ columnas visibles en todas las salidas y resiliencia ante datos nulos.
- [x] **P1.7**: Adaptar aserciones de formato en suites existentes (`tests/test_preset_balancer.py`, `tests/test_daily_digest.py`, `tests/test_telegram_snooze.py`, `tests/test_event_store.py`).

### Fase 2: Conexión en Dispatcher, Callbacks de Refresco y Certificación
- [x] **P2.1**: Conectar handler `_handle_diagnostic_callback()` en `app/miner_monitor.py` para despachar `diag:ref:balancer`, `diag:ref:elev`, `diag:ref:digest`, `diag:ref:events` con ACK rápido (< 50ms) y edición in-place.
- [x] **P2.2**: Adjuntar `reply_markup` en las respuestas de los comandos `/balancer`, `/elevadores`, `/digest`, `/events` en el dispatcher de Telegram.
- [x] **P2.3**: Agregar pruebas de integración en `tests/test_telegram_callbacks.py`.
- [x] **P2.4**: Ejecutar suite global completa de tests ($\ge 687$ PASS), release audit y comprobación sintáctica.

---

## 3. Matriz de Validación de Calidad

| Condición | Requisito | Mecanismo de Verificación |
|---|---|---|
| **C1** | Líneas de datos $\le$ 32 cols visibles | Tests unitarios automáticos iterando sobre cada línea con `visible_line_width()` |
| **C2** | Pureza de renderizado | Cero imports de red, sockets o mutación de estado dentro de las funciones de layout |
| **C3** | Callbacks $\le$ 64 bytes & ACK < 50ms | `parse_diagnostic_callback()` con validación estricta y orden de llamada en tests |
| **C4** | Sin particionado roto | Longitud total $< 2,000$ caracteres por reporte |
| **C5** | Sanitización Markdown | Nombres de mineros y fallas sanitizados con `escape_markdown()` |
| **C6** | Fallback de entrega | Textos 100% legibles si se omiten botones en fallback directo |
| **C7** | Seguridad e Invariantes | Cero cambios en FSM (`MinerState`), auto-reboot, Hashcore CLI ni loop de monitoreo |
