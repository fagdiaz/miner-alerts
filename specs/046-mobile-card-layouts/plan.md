# Plan de Implementación: Spec 046 - Mobile-First Card Layout & UX Harmonization across Fleet Reports

**Feature Directory**: `specs/046-mobile-card-layouts`
**Fecha**: 2026-09-09
**Motor Principal**: Gemini 3.8 Flash High
**Condiciones de Control**: RFC C1-C10

---

## 1. Arquitectura y Desglose de Componentes

### 1.1 Principio de Pureza y Desacoplamiento
Para preservar la estabilidad productiva y cumplir con la Condición C7:
- Cada función de renderizado es **pura, determinista y libre de I/O**.
- Los datos de entrada provienen de snapshots ya obtenidos en memoria (`assessments` o `states`), evitando llamadas de red o bloqueos de sockets durante la generación visual.
- Las funciones helper de ancho (`visible_line_width`, `strip_markdown`, `wrap_mobile_lines`) creadas en `app/telegram/help_center.py` son reutilizadas canónicamente como utilidades del dominio Telegram.

### 1.2 Módulo Dedicado: `app/telegram/fleet_cards.py`
Para encapsular el formateo de `/status` y la generación de teclados diagnósticos comunes:
- `render_fleet_status_card(states, config, miners, now_str)` -> `(text, reply_markup)`.
- `build_diagnostic_keyboard(report_type, miner_id=None)` -> `reply_markup`:
  * `report_type == "status"`: `[ 🔄 Actualizar ] [ 📊 Gráfico ] [ 📱 Menú ]`
  * `report_type in ("fans", "efficiency", "presets")`: `[ 🔄 Actualizar ] [ 📱 Menú ]`
- Callbacks dedicados con gramática acotada $\le 64$ bytes:
  * `diag:ref:status`
  * `diag:ref:fans`
  * `diag:ref:eff`
  * `diag:ref:presets`
  * Retorno universal: `cc:nav:main` (Command Center)

---

## 2. Fases de Entrega

### Fase 1: Módulo Puro, Rediseño de Renderers y Tests Deterministas
- [x] **P1.1**: Crear `app/telegram/fleet_cards.py` con `render_fleet_status_card()` y constructores de teclados inline diagnósticos.
- [x] **P1.2**: Actualizar `build_fans_table_text()` en `app/governance/fan_health.py` al formato vertical Mobile-First $\le 32$ columnas.
- [x] **P1.3**: Actualizar `build_efficiency_table_text()` en `app/governance/energy_efficiency.py` al formato vertical Mobile-First $\le 32$ columnas.
- [x] **P1.4**: Actualizar `build_presets_table_text()` en `app/vnish/presets.py` al formato vertical Mobile-First $\le 32$ columnas.
- [x] **P1.5**: Crear suite `tests/test_fleet_cards.py` validando:
  * Límite estricto $\le 32$ columnas visibles por línea de datos (Condición C1).
  * Longitud total $< 3,600$ caracteres (Condición C4).
  * Resiliencia ante datos nulos o faltantes (None, 0 TH/s, sin lecturas de fans).
  * Callbacks con payload $\le 64$ bytes (Condición C3).
- [x] **P1.6**: Adaptar aserciones de formato en suites existentes (`tests/test_fan_health.py`, `tests/test_energy_efficiency.py`).

### Fase 2: Conexión en Dispatcher, Callbacks de Refresco y Certificación
- [x] **P2.1**: Conectar handler de callbacks `diag:ref:*` en `_handle_callback_query()` de `app/miner_monitor.py` con ACK temprano (< 50ms) y edición in-place.
- [x] **P2.2**: Adjuntar `reply_markup` en las respuestas de los comandos `/status`, `/fans`, `/efficiency`, `/presets` en el dispatcher de Telegram.
- [x] **P2.3**: Agregar pruebas de integración en `tests/test_telegram_callbacks.py` verificando el despacho in-place de `diag:ref:*`.
- [x] **P2.4**: Ejecutar suite global completa de tests ($\ge 660$ PASS), release audit y comprobación sintáctica.

---

## 3. Matriz de Validación de Calidad

| Condición | Requisito | Mecanismo de Verificación |
|---|---|---|
| **C1** | Líneas de datos $\le$ 32 cols visibles | Tests unitarios automáticos iterando sobre cada línea con `visible_line_width()` |
| **C2** | Pureza de renderizado | Cero imports de red, sockets o SQLite dentro de las funciones de layout |
| **C3** | Callbacks $\le$ 64 bytes & ACK < 50ms | `parse_diagnostic_callback()` con límite estricto y orden de llamada en tests |
| **C4** | Sin particionado roto | Longitud total $< 2,000$ caracteres por reporte (límite Telegram: 4,096; límite split: 3,600) |
| **C5** | Sanitización Markdown | Nombres de mineros y fallas sanitizados con `escape_markdown()` |
| **C6** | Fallback de entrega | Textos 100% legibles si se omiten botones en fallback directo |
| **C7** | Seguridad e Invariantes | Cero cambios en FSM (`MinerState`), auto-reboot, Hashcore CLI ni loop de monitoreo |
