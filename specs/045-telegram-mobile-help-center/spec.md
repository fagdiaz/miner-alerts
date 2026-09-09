# Spec 045: Telegram Mobile Help Center & Categorized Interactive Navigation

## Estado y Metadatos
- **ID**: `045-telegram-mobile-help-center`
- **Prioridad**: P1 (Ergonomía Móvil Telegram, UX Táctil y Reducción de Fricción Operativa)
- **Estado**: ESPECIFICACIÓN IMPLEMENTADA (Módulo Puro y Pruebas Completas)
- **Fecha**: 2026-09-09
- **Autor**: Antigravity (Gemini 3.8 Flash High)
- **Revisor Arquitectónico Designado**: Claude Sonnet 4.6 (Thinking) / Codex
- **Documento Base**: `docs/speckit/RFC_TELEGRAM_MOBILE_UX_OPTIMIZATION.md` (Aprobado con Condiciones C1-C10)
- **Dependencias**: Specs 030 (Telegram Quality), 031 (Callbacks Base), 041 (Modular Architecture en `app/telegram/`), 043 (Interactive Command Center), 044 (Silent Mode Thermal Guard).

---

## 1. Contexto y Justificación

### 1.1 El Problema Actual
El operador interactúa con **Miner Alerts** primordialmente desde su **teléfono móvil (Telegram Mobile)**.
1. `/help` actualmente vuelca un bloque plano de texto de más de 80 líneas con 28 comandos desordenados, requiriendo scroll vertical excesivo en pantallas móviles.
2. Comandos operativos de alto impacto agregados en specs recientes (`/menu`, `/start`, `/panel`, `/silent`, `/silencio`, `/modo_silencio`) son reconocidos por el dispatcher pero fueron omitidos de `_COMMANDS` y de `render_help_index()`. Como resultado, `/help` no los menciona y consultas como `/info silent` o `/info menu` responden con *"Comando desconocido"*.
3. La interfaz carece de una navegación táctil categorizada en 1-2 toques que permita explorar comandos por dominio operativo sin tener que escribir nombres extensos en teclados virtuales.

### 1.2 Objetivos de la Spec 045
1. **Módulo Puro y Desacoplado (`app/telegram/help_center.py`)**:
   - Centralizar el registro canónico de comandos reales (`HELP_REGISTRY`), categorías, aliases, niveles de riesgo, descripciones y ejemplos.
   - Cero dependencias de I/O, sockets, SQLite o estado de mineros (100% en memoria y determinista).
2. **Navegación Interactiva Táctil Mobile-First**:
   - Vista Home compacta (< 32-34 columnas) con botones inline (`InlineKeyboardMarkup`) organizados en 5 categorías operativas:
     * `[ 📊 Monitoreo ]`: `/status`, `/chart`, `/digest`, `/info`
     * `[ 🌡️ Térmico ]`: `/fans`, `/gov`, `/silent`
     * `[ ⚡ Energía ]`: `/efficiency`, `/presets`, `/balancer`, `/elevadores`
     * `[ 🔄 Control ]`: `/menu`, `/reboot`, `/reboot_no_ok`, `/restart`, `/confirm`, `/snooze`, `/unsnooze`, `/snoozed`
     * `[ 📜 Diagnóstico ]`: `/events`, `/event`, `/why`, `/diagnose`, `/health`, `/quality`, `/firmware`, `/selftest`, `/help`
   - Submenús de categoría con listado de comandos y botón directo para ver detalle o ejecutar acción rápida.
   - Vista de detalle individual accesible vía botón inline o mediante comando `/info <cmd>` / `/help <cmd>`.
3. **Contratos Estrictos de Entrega y Seguridad (C1-C10)**:
   - **C1**: Cada línea de datos respeta `max_width <= 32` caracteres visibles (excluyendo tags Markdown).
   - **C2**: Registro canónico único que incluye `/menu` y `/silent` con sus aliases reales.
   - **C3**: Protocolo de callbacks `help:` con payload <= 64 bytes y aislamiento estricto.
   - **C4**: Cada vista interactiva se mantiene estrictamente por debajo de 3,600 caracteres para evitar particionado que rompa tags Markdown.
   - **C5**: Sanitización robusta y escape de caracteres especiales Markdown (`*`, `_`, `` ` ``, `[`).

---

## 2. Requerimientos Funcionales

### RF-1: Menú Principal de Ayuda Táctil (`render_help_home`)
Al emitir `/help` (sin argumentos) o recibir el callback `help:nav:home`, el bot debe generar una vista compacta y un teclado inline categorizado:
```text
📖 *CENTRO DE AYUDA Y COMANDOS*
──────────────────────────────
Sistema de Supervisión S19j Pro
Selecciona una categoría táctil:

• 📊 *Monitoreo*: Telemetría y estado
• 🌡️ *Térmico*: Fans y modo silencio
• ⚡ *Energía*: Eficiencia y presets
• 🔄 *Control*: Reinicios y pausas
• 📜 *Diagnóstico*: Eventos y salud

💡 _O usa /info <comando> para detalle._
```
*Inline Keyboard asociado:*
```text
[ 📊 Monitoreo ]     [ 🌡️ Térmico ]
[ ⚡ Energía ]       [ 🔄 Control ]
[ 📜 Diagnóstico ]   [ 📱 Menú ]
```

### RF-2: Submenú por Categoría Táctil (`render_help_category`)
Al pulsar una categoría (ej. `help:cat:thm`), se presenta un resumen de los comandos correspondientes y botones de detalle:
```text
🌡️ *COMANDOS TÉRMICOS Y FANS*
──────────────────────────────
• `/fans [id]`
  Coolers y margen a 85°C.
• `/gov [on|off|set]`
  Lazo cerrado a 82°C.
• `/silent [duración|off]`
  Modo silencio al 40%-70%.

💡 _Ejemplos táctiles:_
/fans 23  |  /silent 2h  |  /gov on
```
*Inline Keyboard asociado:*
```text
[ ❄️ /fans ]       [ 🔇 /silent ]
[ ⬅️ Volver ]      [ 📱 Menú ]
```

### RF-3: Detalle de Comando Táctil (`render_help_command_detail`)
Al pulsar un comando en la lista (ej. `help:cmd:silent`) o escribir `/info silent` o `/help silent`, se renderiza una tarjeta vertical con el detalle completo:
```text
/silent
──────────────────────────────
Modo silencioso acotado para coolers (40%-70% PWM) con guarda térmica de escape automático ante >80°C o fallas.

Uso:
/silent <30m|1h|2h|4h|6h|indef|off>

Ejemplos:
/silent 2h
/silent off

Notas:
• Se revierte automáticamente.
• Emergencia térmica restaura fans al 100%.
```
*Inline Keyboard asociado:*
```text
[ ⬅️ Categoría ] [ 📖 Ayuda ] [ 📱 Menú ]
```

### RF-4: Resolución Exhaustiva de Comandos y Aliases
El sistema debe resolver indistintamente nombres canónicos y aliases:
- `silent` -> `silencio`, `modo_silencio`
- `menu` -> `start`, `panel`
- `gov` -> `governor`
- `efficiency` -> `eff`
- `presets` -> `preset`, `profile`
- `balancer` -> `bal`, `power`
- `elevadores` -> `elevators`, `sensibilidad`, `elev`
- `selftest` -> `test`
- `digest` -> `summary`

### RF-5: Gramática de Callbacks `help:` Acotada a 64 Bytes
- `help:nav:home` (13 bytes)
- `help:cat:<cat_id>` (máx 15 bytes)
- `help:cmd:<cmd_name>` (máx 32 bytes)
Cualquier callback fuera de esta gramática o superior a 64 bytes debe ser rechazado de forma segura retornando `None`.

---

## 3. Arquitectura Técnica y Restricciones

### 3.1 Módulo Puro `app/telegram/help_center.py`
- Implementado como módulo funcional y determinista.
- Exporta:
  * `HELP_CATEGORIES`
  * `HELP_COMMANDS`
  * `HelpAction`
  * `parse_help_callback(raw_data: str) -> Optional[HelpAction]`
  * `lookup_command(needle: str) -> Optional[CommandDefinition]`
  * `render_help_home() -> Tuple[str, Dict[str, Any]]`
  * `render_help_category(cat_key: str) -> Tuple[str, Dict[str, Any]]`
  * `render_help_command_detail(cmd_name: str) -> Tuple[str, Dict[str, Any]]`
  * `strip_markdown(text: str) -> str`
  * `visible_line_width(line: str) -> int`
  * `escape_markdown(text: str) -> str`

### 3.2 Invariantes de Seguridad (C7)
- Cero alteraciones en el loop de monitoreo, cerrojos de auto-reboot, o lógica de Hashcore.
- Integración en `miner_monitor.py` diferida a la fase supervisada por Claude Sonnet 4.6 (Thinking) / Codex.

---

## 4. Criterios de Aceptación y DoD

1. **Suite de Pruebas Unitaria (`tests/test_help_center.py`)**:
   - 100% de los comandos y aliases verificados.
   - Límites de ancho visible <= 32 caracteres verificados en todas las tarjetas y líneas de datos.
   - Tamaño de mensaje < 3,600 caracteres en todas las vistas interactivas.
   - Payloads de `callback_data` <= 64 bytes comprobados.
   - Caracteres hostiles de Markdown escapados adecuadamente.
2. **Compatibilidad Global**:
   - La suite completa de tests de Miner Alerts debe pasar sin regresiones (624 tests base + nuevos tests de Help Center).
   - Sintaxis 100% limpia (`py_compile`).
