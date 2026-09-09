# Tasks: Spec 043 - Telegram Interactive Command Center & Rich UI

## Fase 1: Arquitectura y Módulo del Command Center
- [x] T001 Crear `app/telegram/command_center.py` con constantes de navegación (`CC_PREFIX = "cc:"`).
- [x] T002 Implementar función constructora de teclados inline estándar (`build_inline_keyboard(rows)`).
- [x] T003 Implementar `render_main_dashboard(fleet_snapshot, config)` con formato enriquecido, barras de estado y métricas agregadas.
- [x] T004 Implementar submenú `render_metrics_view(fleet_snapshot)` con detalle por minero y botón de retorno.
- [x] T005 Implementar submenú `render_reboot_menu(fleet_snapshot)` con lista de mineros y confirmación de dos pasos.
- [x] T006 Implementar `build_alert_action_buttons(miner_id)` con botones de Reinicio, Gráfico, Diagnóstico y Snooze.

## Fase 2: Enrutamiento de Callbacks y Autorización
- [x] T007 Integrar router de callbacks en `app/telegram/callbacks.py` / `miner_monitor.py` para procesar eventos `cc:*`.
- [x] T008 Implementar guardián RBAC (`is_authorized_admin(user_id)`) para rechazar clics no autorizados.
- [x] T009 Implementar despacho de `answerCallbackQuery` inmediato (< 500ms) para respuesta táctil instantánea.
- [x] T010 Implementar edición in-place de mensajes (`editMessageText`) capturando errores de `MessageNotModified`.

## Fase 3: Integración en el Monitor Principal
- [x] T011 Agregar comandos `/menu` y `/start` en el loop de Telegram de `app/miner_monitor.py` apuntando al Command Center.
- [x] T012 Adjuntar markup de acciones rápidas a las alertas de caídas y anomalías en `miner_monitor.py`.

## Fase 4: Pruebas Unitarias y Certificación
- [x] T013 Crear suite exhaustiva `tests/test_command_center.py` con tests de vistas, callbacks, autorización y tokens.
- [x] T014 Validar compilación sintáctica: `python -m py_compile app/telegram/command_center.py` y `python -m py_compile app/miner_monitor.py`.
- [x] T015 Ejecutar suite global completa de pruebas asegurando cero regresiones (602 tests PASS).
