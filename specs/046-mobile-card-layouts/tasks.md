# Tareas: Spec 046 - Mobile-First Card Layout & UX Harmonization across Fleet Reports

## Estado General
- **Total Tareas**: 8
- **Completadas**: 8
- **Pendientes**: 0

---

## Tareas de Fase 1 (Módulos Puros, Renderers y Tests Unitarios)

- [x] **T1: Inicialización de Artefactos Speckit Spec 046**: Crear `contracts/fleet-cards-api.md`, `checklists/requirements.md`, `evidence.md` y verificar `.specify/feature.json`.
- [x] **T2: Módulo Puro `app/telegram/fleet_cards.py`**:
  - Implementar `render_fleet_status_card()` para `/status` con tarjetas verticales $\le 32$ cols por minero.
  - Implementar `build_diagnostic_keyboard()` para generar botoneras táctiles (`[ 🔄 Actualizar ] [ 📊 Gráfico ] [ 📱 Menú ]`).
  - Implementar parser y constantes de callback `DIAG_PREFIX = "diag:"` con validación estricta $\le 64$ bytes.
- [x] **T3: Refactor Mobile-First de Fans (`app/governance/fan_health.py`)**:
  - Actualizar `build_fans_table_text()` reemplazando la fila horizontal de 86 cols por bloques verticales con viñetas `•` ($\le 32$ cols visibles).
  - Incluir recomendaciones claras y resumen de mineros saturados.
- [x] **T4: Refactor Mobile-First de Eficiencia (`app/governance/energy_efficiency.py`)**:
  - Actualizar `build_efficiency_table_text()` a tarjetas verticales por minero con viñeta `•` y resumen de flota en kW/J-TH ($\le 32$ cols visibles).
- [x] **T5: Refactor Mobile-First de Presets (`app/vnish/presets.py`)**:
  - Actualizar `build_presets_table_text()` a tarjetas verticales por minero con frecuencia, tensión y perfil inferido ($\le 32$ cols visibles).
- [x] **T6: Suite Unitaria Exhaustiva (`tests/test_fleet_cards.py`)**:
  - Probar límite estricto $\le 32$ columnas en todas las líneas de datos de `/status`, `/fans`, `/efficiency`, `/presets`.
  - Probar longitud total $< 3,600$ caracteres.
  - Probar resiliencia ante mineros desconectados, datos incompletos o errores.
  - Actualizar aserciones de tests existentes (`test_fan_health.py`, `test_energy_efficiency.py`).

---

## Tareas de Fase 2 (Integración en Monitor, Callbacks y Certificación)

- [x] **T7: Conexión en Dispatcher & Router de Callbacks (`app/miner_monitor.py`)**:
  - Cablear handler `_handle_diagnostic_callback()` en `_handle_callback_query` con ACK inmediato (< 50ms) y edición in-place para `diag:ref:status`, `diag:ref:fans`, `diag:ref:eff`, `diag:ref:presets`.
  - Conectar teclados inline en las respuestas de los comandos `/status`, `/fans`, `/efficiency`, `/presets`.
- [x] **T8: Smoke Testing de Integración, Release Audit y Documentación**:
  - Agregar pruebas en `tests/test_telegram_callbacks.py`.
  - Validar suite global completa ($\ge 660$ tests PASS).
  - Ejecutar `tools/release_audit.py --check-only`.
  - Actualizar `evidence.md`, `DEVELOPMENT_LOG.md`, `ROADMAP.md` y `prompt.txt`.
