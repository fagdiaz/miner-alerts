# RFC: Telegram Mobile UX & Visual/Functional Command Optimization
**Estado:** BORRADOR PARA AUDITORÍA  
**Fecha:** 2026-09-09  
**Autor Inicial:** Gemini 3.8 Flash High  
**Revisor Designado:** Claude Sonnet 4.6 (Thinking)  
**Ubicación:** `docs/speckit/RFC_TELEGRAM_MOBILE_UX_OPTIMIZATION.md`

---

## 1. Contexto y Justificación (Problem Statement)

### 1.1 Situación Actual (Baseline)
- El operador interactúa con **Miner Alerts** primordialmente desde su **teléfono móvil (Telegram Mobile)**.
- Gran parte de las respuestas de comandos actuales fueron diseñadas históricamente con formato tabular de terminal de escritorio (líneas horizontales de 70 a 90 caracteres):
  * `/fans`: Genera líneas de hasta **86 caracteres** (e.g. `S19JPRO-23: 🟠 SATURADO | 6,000 RPM (94% [HOLD_TARGET]) | 82.0°C (Margen: 3.0°C)`). En pantallas móviles (ancho útil de 32 a 36 caracteres), estas líneas sufren quiebres de texto arbitrarios (*soft-wrapping* desordenado), dificultando la lectura rápida.
  * `/efficiency`: Genera líneas de **77 caracteres** (`S19JPRO-23: 🟢 ÓPTIMA | 101.1 TH/s | 2,698 W (2.70 kW) | 26.7 J/TH`), sufriendo el mismo problema.
  * `/presets`: Concatena frecuencias, voltajes, potencia y autotuning en una sola línea de más de 80 caracteres.
  * `/status`: Presenta una lista plana de texto sin semáforos visuales destacados, temperaturas ni consumo.
  * `/help`: Vuelca un bloque plano de texto de más de 80 líneas con 28 comandos desordenados, omitiendo comandos clave agregados recientemente como `/menu`, `/panel`, `/start` y `/silent`. Además, `/info silent` y `/info menu` devuelven *"Comando desconocido"*.
- Escribir comandos con parámetros en un teclado táctil de celular (`/snooze S19JPRO-25 60`, `/chart fleet 24`, `/confirm reboot 23 123456`) genera fricción operativa y propensión a errores tipográficos.

### 1.2 Objetivos y Alcance
1. **Diseño Mobile-First (Regla de 32 Caracteres)**:
   - Reestructurar todas las salidas de texto de Telegram para que ninguna línea supere los 34 caracteres de ancho tabular.
   - Adoptar formato de tarjetas verticales (*card layout*) con viñetas claras (`•`), semáforos semánticos (🟢, 🟡, 🟠, 🔴) y métricas clave en líneas dedicadas.
2. **Help Interactivo y Paginado (`/help`)**:
   - Sustituir el vuelco plano de 80 líneas por una vista de bienvenida compacta con botones táctiles inline (`InlineKeyboardMarkup`) organizados por categorías operativas.
   - Navegación táctil *in-place* (`editMessageText`) por categorías:
     * `[ 📊 Monitoreo ]`: `/status`, `/chart`, `/digest`, `/info`
     * `[ 🌡️ Térmico & Fans ]`: `/fans`, `/gov`, `/silent`
     * `[ ⚡ Eficiencia & Presets ]`: `/efficiency`, `/presets`, `/balancer`, `/elevadores`
     * `[ 🔄 Acciones & Control ]`: `/menu`, `/reboot`, `/snooze`, `/unsnooze`
     * `[ 📜 Eventos & Diagnóstico ]`: `/events`, `/event`, `/why`, `/diagnose`
   - Incorporar formalmente `/menu` y `/silent` en `_COMMANDS` y en `/info <cmd>`.
3. **Optimización de Diagnósticos de Flota (`/status`, `/fans`, `/efficiency`, `/presets`)**:
   - Tarjetas individuales de 3-4 líneas por minero.
   - Botón inline al pie para refrescar en 1 toque (`[ 🔄 Actualizar ]`) y volver al menú principal (`[ 📱 Menú ]`).
4. **Preservación Invariante de Seguridad**:
   - Cero alteraciones en las políticas de confirmación en dos toques de reinicios.
   - Cero impacto en el bucle autoritativo de monitoreo ni en los cerrojos de concurrencia.

---

## 2. Visión Funcional & UX (Experience Design)

### 2.1 Menú de Ayuda Interactivo Mobile-First (`/help`)

#### Vista Inicial (Compacta y Categorizada):
```text
📖 *CENTRO DE AYUDA Y COMANDOS*
──────────────────────────────
Sistema de Supervisión S19j Pro
Selecciona una categoría táctil:

• 📊 *Monitoreo*: Telemetría y estado
• 🌡️ *Térmico*: Fans y modo silencio
• ⚡ *Energía*: Eficiencia y presets
• 🔄 *Control*: Reinicios y pausas
• 📜 *Eventos*: Diagnóstico y logs

💡 _O escribe /info <comando> para ayuda detallada._
```
*Inline Keyboard asociado:*
```text
[ 📊 Monitoreo ]     [ 🌡️ Térmico ]
[ ⚡ Energía ]       [ 🔄 Control ]
[ 📜 Eventos ]       [ 📱 Command Center ]
```

#### Submenú al pulsar `[ 🌡️ Térmico ]`:
```text
🌡️ *COMANDOS TÉRMICOS Y FANS*
──────────────────────────────
• `/fans [id]`
  Estado de coolers y margen térmico.
• `/gov [on|off|set]`
  Control de lazo cerrado a 82°C.
• `/silent [duración|off]`
  Modo Silencio acotado al 40%-70%.

💡 _Ejemplos táctiles:_
/fans 23  |  /silent 2h  |  /gov on
```
*Inline Keyboard asociado:*
```text
[ ❄️ Ver Fans ]       [ 🔇 Modo Silencio ]
[ ⬅️ Volver a Ayuda ] [ 📱 Menú Principal ]
```

---

### 2.2 Rediseño de Reportes de Diagnóstico para Pantalla Móvil

#### A. Nuevo Formato de `/status`:
*Antes (Línea horizontal saturada):*
```text
- 23 (192.168.100.23): 101.5 TH/s | /e1234
```
*Nuevo Formato Mobile-First (Tarjeta visual):*
```text
📊 *ESTADO DE FLOTA (15:00 hs)*
──────────────────────────────
🟢 *S19JPRO-23* (`.23`)
  • Hash: 101.5 TH/s (Placas 3/3)
  • Temp: 81.0°C | Fans: 94% PWM
  • Potencia: 2,698 W (26.6 J/TH)

🟢 *S19JPRO-24* (`.24`)
  • Hash: 93.6 TH/s (Placas 3/3)
  • Temp: 82.0°C | Fans: 100% PWM
  • Potencia: 2,499 W (26.7 J/TH)

🟢 *S19JPRO-25* (`.25`)
  • Hash: 96.4 TH/s (Placas 3/3)
  • Temp: 80.0°C | Fans: 100% PWM
  • Potencia: 2,498 W (25.9 J/TH)

🟢 *S19JPRO-26* (`.26`)
  • Hash: 100.6 TH/s (Placas 3/3)
  • Temp: 81.0°C | Fans: 89% PWM
  • Potencia: 2,699 W (26.8 J/TH)
──────────────────────────────
⚡ Total: 392.1 TH/s | 10.4 kW
```
*Botones adjuntos:*
`[ 🔄 Actualizar ] [ 📊 Gráfico ] [ 📱 Menú ]`

---

#### B. Nuevo Formato de `/fans`:
*Antes (86 caracteres por fila):*
```text
S19JPRO-23: 🟠 SATURADO | 6,000 RPM (94% [HOLD_TARGET]) | 82.0°C (Margen: 3.0°C)
```
*Nuevo Formato Mobile-First (Estructura limpia):*
```text
❄️ *SALUD DE VENTILADORES*
──────────────────────────────
🟠 *S19JPRO-23*: SATURADO
  • Temp: 82.0°C (Margen: 3.0°C)
  • Fans: 6,000 RPM (94% PWM)
  • Modo: HOLD_TARGET

🟠 *S19JPRO-24*: SATURADO
  • Temp: 82.0°C (Margen: 3.0°C)
  • Fans: 6,000 RPM (100% PWM)
  • Modo: RECOVERY_MAX

🟠 *S19JPRO-25*: SATURADO
  • Temp: 81.0°C (Margen: 4.0°C)
  • Fans: 6,000 RPM (100% PWM)
  • Modo: RECOVERY_MAX

🟠 *S19JPRO-26*: SATURADO
  • Temp: 81.0°C (Margen: 4.0°C)
  • Fans: 6,000 RPM (89% PWM)
  • Modo: HOLD_TARGET
──────────────────────────────
⚠️ _4 mineros en saturación térmica._
_Se sugiere inspección de filtros._
```

---

#### C. Nuevo Formato de `/efficiency`:
*Antes (77 caracteres por fila):*
```text
S19JPRO-23: 🟢 ÓPTIMA | 101.1 TH/s | 2,698 W (2.70 kW) | 26.7 J/TH
```
*Nuevo Formato Mobile-First:*
```text
⚡ *EFICIENCIA ENERGÉTICA*
──────────────────────────────
🟢 *S19JPRO-23*: 26.7 J/TH
  • 101.1 TH/s  |  2,698 W

🟢 *S19JPRO-24*: 26.9 J/TH
  • 92.9 TH/s   |  2,499 W

🟢 *S19JPRO-25*: 26.6 J/TH
  • 93.8 TH/s   |  2,498 W

🟢 *S19JPRO-26*: 27.5 J/TH
  • 98.3 TH/s   |  2,699 W
──────────────────────────────
🔋 *Flota*: 26.9 J/TH Promedio
🔌 *Carga Total*: 10.4 kW (10,394 W)
```

---

## 3. Arquitectura Técnica & Componentes Afectados

### 3.1 Módulo Puro Desacoplado: `app/telegram/help_center.py`
Para mantener `miner_monitor.py` limpio y respetar la modularidad de dominios lograda en Spec 041-042:
- Se creará `app/telegram/help_center.py` conteniendo:
  * Diccionario exhaustivo y actualizado `HELP_REGISTRY` (incluyendo `/menu`, `/silent`, `/panel`, etc.).
  * `render_help_home(is_mobile=True)` -> `(text, markup)`.
  * `render_help_category(category_key)` -> `(text, markup)`.
  * `render_help_command_detail(cmd_name)` -> `(text, markup)`.
  * Router de callbacks bajo prefijo `help:` (e.g. `help:cat:thermal`, `help:cat:monitoring`, `help:nav:home`).

```mermaid
flowchart TD
    User([Telegram Mobile]) -->|"/help" o "cc:nav:help"| Bot[Telegram Dispatcher]
    Bot --> HC[app/telegram/help_center.py]
    HC -->|render_help_home| KB[InlineKeyboardMarkup Categorías]
    KB -->|Click "help:cat:thermal"| CBHandler[Callback Query Handler]
    CBHandler -->|editMessageText| HCat[render_help_category]
    HCat -->|Acción rápida o Volver| Bot
```

### 3.2 Refactor de Renderers en Governance & Dominios
- `app/governance/fan_health.py`: Actualizar `build_fans_table_text()` para usar el layout de tarjeta móvil (`max_width <= 34 chars`).
- `app/governance/energy_efficiency.py`: Actualizar `build_efficiency_table_text()`.
- `app/vnish/presets.py`: Actualizar `build_presets_table_text()`.
- `app/telegram/command_center.py`: Conectar botón táctil `[ ❓ Ayuda ]` en el pie del Command Center principal hacia el nuevo Help Center.

---

## 4. Análisis de Riesgos y Seguridad Operativa

1. **Riesgo de Inyección de Formato (Markdown Parsing Error)**:
   - Telegram falla y no entrega mensajes si hay caracteres especiales sin escapar en modo Markdown (e.g. `_`, `*`, `[`, `` ` ``).
   - *Mitigación*: Utilizar funciones de sanitización o escapar rigurosamente nombres de mineros y argumentos de usuario antes de renderizar.
2. **Riesgo de Rate Limit en Callbacks**:
   - El operador puede presionar múltiples botones de categorías rápidamente.
   - *Mitigación*: Enviar `answerCallbackQuery` de inmediato (< 200ms) y capturar `MessageNotModified` para evitar spam de excepciones.
3. **Aislamiento de Hilos**:
   - Toda la lógica de renderizado de texto y teclados es **100% pura y en memoria** (sin I/O ni locks de larga duración), ejecutándose en < 5ms sin impactar el loop de monitoreo.

---

## 5. Programa de Especificaciones Propuesto

Para una entrega disciplinada y segura, se propone dividir el alcance en dos paquetes de trabajo:

### Spec 045: Telegram Mobile Help Center & Categorized Interactive Navigation
* **Alcance**:
  - Creación de `app/telegram/help_center.py` con registro canónico completo de comandos (incorporando `/menu`, `/silent` y alias).
  - Teclados inline para navegación por categorías (`help:cat:*`) y detalle individual en 1-tap.
  - Soporte `/info <cmd>` completo y actualizado.
  - Botón de ayuda en el Command Center `/menu`.
* **Pruebas**: Suite unitaria en `tests/test_help_center.py` con verificación de ancho máximo de línea y renderizado de callbacks.
* **Asignación sugerida**: `Gemini 3.8 Flash High` (lógica pura de formato, schemas y tests).

### Spec 046: Mobile-First Card Layout & UX Harmonization across Fleet Reports
* **Alcance**:
  - Rediseño de salidas de `/status`, `/fans`, `/efficiency`, `/presets` y `/events` a tarjetas verticales acotadas a 32-34 caracteres.
  - Adición de botones inline de refresco y retorno al pie de cada reporte diagnóstico.
  - Armonización de semáforos Unicode y espaciados móviles en alertas de episodios.
* **Pruebas**: Verificación de renderizado en `tests/test_compact_ux.py`, `tests/test_fan_health.py`, etc.
* **Asignación sugerida**: `Gemini 3.8 Flash High` para diseño de plantillas; `Claude Sonnet 4.6` para revisión de concurrencia y auditoría de despacho en `miner_monitor.py`.

---

## 6. Sección de Auditoría Arquitectónica (2026-09-09)

### Veredicto formal

**APROBADO CON CONDICIONES OBLIGATORIAS C1-C10.**

La necesidad está demostrada por la implementación actual: `render_help_index()` en
`app/miner_monitor.py` sigue siendo un índice textual largo y su registro no
incluye los comandos productivos `/menu` ni `/silent`; los renderizadores de
flota de fans, eficiencia y presets construyen filas horizontales extensas. El
Command Center de Spec 043 ya prueba que Telegram Mobile admite navegación
táctil segura: `app/telegram/command_center.py` contiene builders puros de
teclados `cc:` y `_handle_command_center_callback()` confirma el tap antes de
tomar `state_lock` o construir la vista.

La división entre **Spec 045** y **Spec 046** es correcta y debe mantenerse.
Spec 045 define la base canónica de ayuda, navegación y contratos de entrega;
Spec 046 migra los reportes de diagnóstico sobre esa base. No deben fusionarse:
una falla de navegación no debe retrasar ni mezclar cambios de lectura de
telemetría, y las tarjetas deben poder probarse sin polling ni Telegram.

### Hallazgos del baseline

1. `split_telegram_message()` en `app/telegram/messages.py` parte texto
   normalizado, pero no conoce la sintaxis de Markdown ni preserva pares de
   marcadores abiertos.
2. `send_telegram()` adjunta `reply_markup` solo a la última parte encolada.
   Una pantalla interactiva no puede depender del particionador genérico.
3. `_send_telegram_direct()` conserva texto, pero actualmente no recibe ni
   reenvía `reply_markup` o `parse_mode`; ante `queue=None` el texto de ayuda
   llegaría sin botones.
4. `answer_callback_query()` y `edit_message_text()` existen. El Command Center
   ya ignora `Message is not modified`, aunque el timeout HTTP actual de cinco
   segundos impide prometer 200 ms como garantía absoluta de red.
5. `/status` entrega el snapshot preconstruido del monitor; Spec 046 debe
   localizar y encapsular su renderer. `/fans`, `/efficiency` y `/presets` ya
   usan builders puros separados.

### Condiciones técnicas obligatorias

**C1. Contrato Mobile-First medible.** Cada línea de datos de una tarjeta debe
tener ancho visible máximo de 32 columnas, comprobado después de retirar
marcadores Markdown y con nombres largos, datos faltantes, Unicode y errores.
No se permiten tablas horizontales ni bloques de código. Los emojis no pueden
ser el único portador de significado.

**C2. Registro canónico.** `app/telegram/help_center.py` debe ser puro,
determinista y libre de I/O. Debe ser la fuente única para categorías, nombre,
aliases, uso, riesgo y detalle. Incluye solo comandos que reconoce el
dispatcher, entre ellos `/menu` con `/start` y `/panel`, y `/silent` con sus
aliases reales. Los renderizadores existentes deben delegar o migrarse sin
duplicar metadatos.

**C3. Callbacks aislados y ACK temprano.** `help:` tiene gramática cerrada,
versionada y validada, con `callback_data` de hasta 64 bytes. Se enruta antes
del parser genérico y conserva RBAC. Todo callback recibe exactamente un
`answerCallbackQuery` antes de I/O, SQLite, `state_lock`, Hashcore o edición de
mensaje. Objetivo: inicio del ACK menor a 50 ms y p95 observado menor a 200 ms;
las pruebas verifican orden de llamadas, no una latencia WAN imposible de
garantizar.

**C4. Paginación antes que particionado.** Home, categoría y detalle interactivo
caben completos en una página menor a 3,600 caracteres. Si una categoría crece,
se pagina por callback; no se pasa Markdown ni un teclado a
`split_telegram_message()`.

**C5. Política de formato única.** Antes de interpolar nombres, aliases,
argumentos o texto de firmware, la spec debe elegir escape compatible con el
`parse_mode` o texto plano para tarjetas dinámicas. No se mezclan reglas de
Markdown y MarkdownV2. Se prueban `*`, `_`, `` ` ``, `[`, `]`, barra invertida
y saltos de línea; cada parte entregada es sintácticamente válida.

**C6. Fallback equivalente.** Antes de activar botones, el fallback directo de
`send_telegram()` debe conservar `reply_markup`, `parse_mode` y redacción para
un mensaje de una parte. Sigue limitado a comandos y cola no disponible, sin
reintentos ni cambios a notificaciones.

**C7. Límites de seguridad.** Spec 045 no modifica auto-reboot,
confirmaciones, estado de mineros, offsets, mutex ni workers. Spec 046 no cambia
la semántica o fuente de los diagnósticos; solo presentación. Refresh y retorno
se agregan después de tarjetas puras y reutilizan el mecanismo de callback
existente, sin usar `help:` ni crear workers o colas.

**C8. Fases por spec.** Spec 045 comienza con registro, renderizadores, parser y
pruebas puras; la integración mínima en `miner_monitor.py` se revisa por
separado. Spec 046 comienza con tarjetas y pruebas de ancho para `/fans`,
`/efficiency` y `/presets`; `/status` se encapsula luego de mapear
explícitamente `snapshot_ref`. Los botones de refresh son una segunda tarea de
Spec 046.

**C9. Regresión y delivery.** Cada spec agrega pruebas de ancho móvil, N/A,
nombres largos, markup hostil, callback inválido/no autorizado/repetido,
`MessageNotModified`, límite de 64 bytes y fallback de cola. Se preservan las
pruebas existentes de Command Center, callbacks, mensajes y comandos. Validar
`py_compile`, suite completa y smoke de `/help`, `/menu`, `/silent`, `/fans`,
`/efficiency`, `/presets` y `/status` con `DBG_TELEGRAM=1` cuando sea posible.

**C10. Evidencia y activación.** La ergonomía iOS/Android requiere smoke manual
en Telegram Mobile. Cada activación conserva evidencia de servicio Windows,
queue, acknowledgement y entrega. No se reinicia el servicio por cambios solo
documentales o de renderer antes de completar pruebas y plan de activación.

### Matriz de asignación de trabajo

| Área | Gemini 3.8 Flash High | Claude Sonnet 4.6 (Thinking) / Codex | Claude Opus 4.6 (Thinking) |
| --- | --- | --- | --- |
| Registro, categorías, tarjetas, ancho y escapes puros | Implementa y prueba | Revisión puntual de contratos | No requerido |
| Spec Kit, fixtures, documentación y evidencia | Implementa y mantiene | Revisión de gates | No requerido |
| `help_center.py` sin I/O y tests determinísticos | Implementa | Revisión de integración | No requerido |
| Router `help:`, ACK, `send_telegram`, fallback, cola y `miner_monitor.py` | Prepara contrato y patch mínimo | Supervisión y aprobación obligatorias | Solo si persiste un race/concurrencia |
| `snapshot_ref`, locks, polling, timeout HTTP y confirmaciones | No modifica sin handoff | Implementa o revisa cambios necesarios | Solo si Sonnet/Codex no resuelve un fallo recurrente |

### Decisión de secuencia

1. Crear Spec 045 con C1-C6 y C9 como requisitos no negociables.
2. Implementar primero el módulo puro y sus pruebas bajo Gemini 3.8 Flash High.
3. Someter cambios de callback, fallback o `miner_monitor.py` a revisión de
   Claude Sonnet 4.6 (Thinking) o Codex antes de activarlos.
4. Crear Spec 046 solo después de cerrar las interfaces de ayuda, formato y
   entrega de Spec 045; mantener su fase de tarjetas independiente de callbacks
   de refresh.