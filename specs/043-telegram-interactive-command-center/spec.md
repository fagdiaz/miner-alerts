# Spec 043: Telegram Interactive Command Center & Rich UI

## Estado y Metadatos
- **ID**: `043-telegram-interactive-command-center`
- **Prioridad**: P1 (Operabilidad Móvil en 1-2 Clicks, UX Visual y Alertas Accionables)
- **Estado**: ESPECIFICACIÓN APROBADA (Lista para Implementación)
- **Fecha**: 2026-09-08
- **Autor**: Antigravity (Gemini 3.8 Flash High)
- **Revisor Arquitectónico**: Claude Sonnet 4.6 (Thinking)
- **Documento Base**: `docs/speckit/RFC_TELEGRAM_INTERACTIVE_CONTROL.md` (RFC Aprobado con Condiciones P0)
- **Dependencias**: Specs 030 (Telegram Reliability), 031 (Callbacks Base), 038 (V3 Concurrency), 041 (Modular Architecture en `app/telegram/`), 042 (Clean Tests).

---

## 1. Contexto y Visión

### 1.1 El Problema Actual
Actualmente, la interacción del operador con `miner-alerts` a través de Telegram depende fuertemente de comandos de texto tipeados manualmente (`/status`, `/gov`, `/balancer`, `/fans`, `/reboot <miner>`).  
En situaciones de movilidad (teléfono móvil, notificaciones push en guardia):
1. Escribir comandos con parámetros exactos es lento y propenso a errores de tipeo.
2. Los mensajes de alerta son informativos pero pasivos: obligan al operador a recordar el comando para diagnosticar, graficar o intervenir.
3. La interfaz carece de una consola central táctil ("Command Center") que resuma en un único mensaje interactivo el estado de salud, potencia, temperaturas y accesos rápidos de la flota.

### 1.2 Objetivos de la Spec 043
1. **Centro de Mando Interactivo (`/menu` o `/start`)**:
   - Mensaje visual enriquecido con barras de estado, métricas agregadas y teclado inline (`InlineKeyboardMarkup`).
   - Navegación jerárquica con edición en caliente del mensaje (`editMessageText`) para evitar spam en el chat.
2. **Alertas Accionables con Botones de Contexto**:
   - Al emitirse una alerta de caída, temperatura o reinicio, adjuntar botones táctiles de 1-toque: `[ 🔄 Reiniciar ]`, `[ 📊 Gráfico ]`, `[ 🔍 Diagnóstico ]`, `[ 🔕 Silenciar 1h ]`.
   - Flujo de confirmación segura en dos pasos para acciones de reinicio (`¿Confirmar reinicio? [ Sí ] [ Cancelar ]`), protegiendo el hardware de toques accidentales.
3. **Desacoplamiento Estricto de Concurrencia (Condición C1-Ready)**:
   - Toda la lógica de construcción de teclados, parseo de callbacks y renderizado de texto es **pura y libre de llamadas bloqueantes de red**.
   - Respuestas inmediatas a Telegram con `answerCallbackQuery` (< 500ms) para eliminar el spinner del cliente.
4. **Seguridad y Control de Acceso**:
   - Verificación estricta de `user_id == admin_chat_id` en cada interacción con botones. Usuarios no autorizados reciben rechazo silencioso con notificación de seguridad en auditoría.

---

## 2. Requerimientos Funcionales

### RF-1: Menú Principal Táctil (`Command Center`)
Al recibir `/menu` o `/start`, el bot debe responder con el dashboard general y el teclado de primer nivel:
```text
╔══════════════════════════════════════╗
║   ⛏️ MINER-ALERTS COMMAND CENTER    ║
╚══════════════════════════════════════╝

🟢 ESTADO: Todos Minando (3/3)
⚡ Hashrate: 342.5 TH/s  |  🔌 10,240 W
🌡️ Temp Max: 78.4°C      |  🌪️ Fans: 62% - 68%

[ 📊 Métricas ]       [ ⚙️ Perfiles ]
[ 🔇 Modo Silencio ]  [ 🔄 Reinicios ]
[ ⏱️ Temporizadores ] [ 🔔 Alertas ]
```

### RF-2: Navegación de Submenús en el Mismo Mensaje
- Al pulsar un botón (ej. `[ 📊 Métricas ]`), el mensaje debe actualizarse en el lugar mostrando las métricas por máquina junto con un botón `[ ⬅️ Volver al Menú ]`.
- Cada callback data debe seguir un esquema estructurado: `cc:<action>:<target>:<param>`.
  - Ejemplos: `cc:nav:main`, `cc:nav:metrics`, `cc:nav:reboot_list`, `cc:act:reboot_confirm:24`.

### RF-3: Alertas con Teclado de Acción Rápida
Toda alerta crítica o de advertencia emitida por `miner_monitor.py` debe soportar la inclusión opcional de una botonera inline:
```text
⚠️ ALERTA: ASIC-24 (192.168.1.102)
Hashrate cayó a 45.2 TH/s (Esperado: 110 TH/s)

[ 🔄 Reiniciar ASIC ]   [ 📊 Ver Gráfico ]
[ 🔍 Diagnóstico ]     [ 🔕 Silenciar 1h ]
```

### RF-4: Confirmación en Dos Pasos para Acciones Críticas
- Pulsar `[ 🔄 Reiniciar ASIC ]` no reinicia la máquina inmediatamente.
- Edita el teclado inline con un token efímero de confirmación con expiración de 60 segundos:
  `¿Confirmar reinicio de ASIC-24? [ ✅ Sí, Reiniciar ] [ ❌ Cancelar ]`.

### RF-5: Guardián de Autorización (RBAC)
- Si un `callback_query` proviene de un `user_id` distinto al `admin_chat_id` configurado:
  - Responder `answerCallbackQuery(text="⛔ Acción no autorizada.", show_alert=True)`.
  - No alterar el mensaje ni despachar la acción.

---

## 3. Arquitectura Técnica y Restricciones

### 3.1 Ubicación en la Arquitectura Modular
Siguiendo la estructura canónica de la Spec 041/042, todo el código nuevo reside en el subpaquete `app/telegram/`:
- `app/telegram/command_center.py`: Generador de vistas, estados de menú y constructores de `InlineKeyboardMarkup`.
- `app/telegram/callbacks.py`: Enrutador y despachador de `callback_query`, gestión de tokens de confirmación y autorización.

### 3.2 Invariantes de No-Bloqueo
1. **Cero llamadas I/O síncronas en callbacks de renderizado**: La información del Command Center se obtiene leyendo snapshots inmutables en memoria del estado de la flota (`MinerState`).
2. **Cero impacto en el loop principal**: El procesamiento de callbacks ocurre enteramente en el hilo `telegram_polling_worker`.

---

## 4. Criterios de Aceptación y Definición de Terminado (DoD)

1. **Pruebas Unitarias Exhaustivas (`tests/test_command_center.py`)**:
   - Renderizado correcto del menú principal con datos simulados de flota.
   - Navegación de ida y vuelta entre submenús mediante `callback_data`.
   - Rechazo de usuarios no autorizados.
   - Expiración determinista de tokens de confirmación de reinicio.
2. **Integración con Alertas**: Alertas de episodios pueden incorporar botones contextuales sin romper el formato existente.
3. **Compatibilidad Total de Suite**: 587/587 tests existentes continúan pasando (0 fallos, 0 regresiones).
4. **Validación Sintáctica**: `python -m py_compile app/telegram/command_center.py` y `python -m py_compile app/miner_monitor.py` 100% OK.
