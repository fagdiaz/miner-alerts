# Plan de Implementación: Spec 043 - Telegram Interactive Command Center & Rich UI

## 1. Arquitectura y Enfoque Modular
El objetivo de la Spec 043 es implementar la capa puramente visual, de navegación y de autorización táctil en Telegram, sin introducir llamadas bloqueantes de hardware (que corresponden a la Spec 044).

```text
[ Telegram User ]
       │
       ▼ (Callback Query / Comandos /menu)
[ app/telegram/callbacks.py ] ──(Verifica Admin)──► [ RBAC Guard ]
       │
       ▼ (Enrutamiento de callback_data)
[ app/telegram/command_center.py ]
       ├── build_main_menu() ──► Snapshot de Flota en RAM
       ├── build_metrics_submenu()
       ├── build_reboot_confirmation()
       └── build_alert_action_markup()
       │
       ▼ (editMessageText / answerCallbackQuery)
[ Telegram API ]
```

---

## 2. Fases de Implementación

### Fase 1: Motor del Command Center (`app/telegram/command_center.py`)
- Definición de constantes de callbacks (`CC_NAV_MAIN`, `CC_NAV_METRICS`, `CC_NAV_REBOOT`, etc.).
- Modelo de datos para vistas de menú.
- Funciones generadoras de `InlineKeyboardMarkup`:
  - `render_command_center_view(fleet_state_snapshot, config) -> tuple[str, dict]`
  - `render_metrics_view(fleet_state_snapshot) -> tuple[str, dict]`
  - `render_reboot_selection_view(fleet_state_snapshot) -> tuple[str, dict]`
  - `render_alert_actions(miner_id, alert_type) -> dict`

### Fase 2: Enrutamiento y Despacho en `app/telegram/callbacks.py`
- Extensión del manejador de `callback_query`:
  - Detección de prefijo `cc:`.
  - Validación de autorización de `user_id`.
  - Respuesta inmediata `answerCallbackQuery`.
  - Despacho de navegación y mutación del mensaje vía `editMessageText`.

### Fase 3: Integración en `app/miner_monitor.py`
- Registro del comando `/menu` (y alias `/start`, `/panel`) delegando a `command_center.py`.
- Inclusión del markup de acciones rápidas en la función de emisión de alertas.

### Fase 4: Batería de Pruebas Unitarias
- Creación de `tests/test_command_center.py` con cobertura completa de:
  - Generación de textos y botones.
  - Validación de tokens y callbacks.
  - Protección de seguridad RBAC.
  - Suite de regresión global (587 tests).

---

## 3. Matriz de Riesgos y Mitigación
| Riesgo | Impacto | Mitigación |
|---|---|---|
| Latencia en renderizado de menú | El usuario ve demora al tocar botones | Cero I/O: los datos se leen directamente de la estructura en memoria `states: dict[str, MinerState]`. |
| Rate-limit de Telegram por clics rápidos | Bloqueo temporal del bot | Control de excepciones `MessageNotModified` (si el usuario pulsa dos veces el mismo botón). |
| Ejecución accidental de reinicios | Caída de minero en producción | Diálogo de confirmación obligatorio en 2 pasos con expiración de 60s. |
