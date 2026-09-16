# Feature Specification: Spec 064 — Telemetría Visual y Gráficos Comparativos Multi-Miner en Telegram (UX-01)

## Status
- **Date**: 2026-09-15
- **Priority**: P2 (Media) | **Risk**: Bajo
- **Modules**: `app/telegram/charts.py`, `app/telegram/commands/diagnostics.py`, `app/telegram/callbacks.py`, `app/miner_monitor.py`
- **Baseline**: 985 tests PASS, Windows Service `MinerAlerts` Running.

---

## 1. Problem Statement & Motivation
El comando actual `/chart <miner>` (Spec 032) genera gráficos individuales de hashrate y temperatura.
En una granja con distribución eléctrica por elevadores (ej. Elevator 1: S19JPRO-1 y S19JPRO-2; Elevator 2: S19JPRO-3 y S19JPRO-4):
1. **Falta de Vista de Grupo / Elevador**: El operador debe solicitar gráficos separados para cada máquina para evaluar el comportamiento térmico o desbalance de un elevador eléctrico.
2. **Spam en el Canal por Cambio de Rango**: Cambiar la escala temporal (ej. de 1h a 24h) genera nuevos mensajes con imágenes separadas en Telegram en lugar de actualizar in-place la imagen existente.
3. **Gestión Estricta de Memoria en Windows**: En entornos headless de Windows, `matplotlib` puede acumular figuras no cerradas en memoria si no se enforza un ciclo estricto `try...finally: plt.close(fig)`.

---

## 2. User Stories
- **US-01 (Gráficos Comparativos por Elevador/Grupo)**: Como operador, deseo ejecutar `/chart elevator_1` o `/chart elevator_2` y ver un gráfico superpuesto con doble panel (Hashrate y Temperatura de Chip) de todos los mineros de ese grupo para detectar anomalías eléctricas o de ventilación conjuntas.
- **US-02 (Selector Interactivo de Rango Temporal sin Spam)**: Como operador, deseo tocar botones inline `[ 1h ] [ 6h ] [ 24h ] [ 7d ]` bajo el gráfico para cambiar el horizonte temporal actualizando la imagen in-place mediante `editMessageMedia`, manteniendo el canal limpio.
- **US-03 (Higiene de Memoria y Rendimiento)**: Como administrador de sistemas, requiero que el renderizado de gráficos no presente fugas de memoria (`RSS` acotado) y use exclusivamente el backend `Agg` no interactivo con cierre explícito de figuras.

---

## 3. Functional Requirements

### FR-01: Gráficos de Grupo y Flota Multi-Miner
- Extender `app/telegram/charts.py` con `fetch_group_chart_data(db_path, group_name, configured_miners, hours, now_ts)`.
- Soportar `render_group_chart_png(group_data, hours)` con diseño de dos subplots:
  * Subplot superior: Hashrate individual de cada minero del grupo con paleta de colores fija (`COLOR_PALETTE`) y línea de umbral.
  * Subplot inferior: Temperatura máxima de chip individual de cada minero del grupo.
- Actualizar `ChartCommand` en `app/telegram/commands/diagnostics.py` para reconocer nombres de grupo (ej. `elevator_1`, `elevator_2`, o cualquier grupo presente en la configuración de mineros) y despachar el gráfico correspondiente.

### FR-02: Teclado Inline y Selector de Rango Temporal In-Place
- Extender `app/telegram/callbacks.py` con la acción `chart_range:<target>:<hours>` (ej. `chart_range:23:6`, `chart_range:elevator_1:24`, `chart_range:fleet:168`).
- Generar teclado inline interactivo `build_chart_range_keyboard(target, current_hours)` con botones para `1h`, `6h`, `24h` y `7d` (168h), marcando visualmente el rango activo (ej. `[ • 1h • ]`).
- Implementar `edit_telegram_photo(bot_token, chat_id, message_id, photo_bytes, caption, reply_markup)` en `app/miner_monitor.py` utilizando la API `editMessageMedia` de Telegram con `multipart/form-data` y adjunto `attach://file_0`.
- En `_handle_callback_query`, procesar `chart_range`: actualizar la imagen in-place y responder a la callback query con notificación emergente breve.

### FR-03: Gestión de Memoria y Ciclo de Vida de Figuras
- Enforzar `matplotlib.use("Agg")` headless al inicio de `app/telegram/charts.py`.
- Garantizar el patrón `try: ... fig.savefig(buf) ... finally: plt.close(fig)` en todas las funciones de renderizado (`render_miner_chart_png`, `render_fleet_chart_png`, `render_group_chart_png`).
- Implementar test de estrés de memoria validando que 100 renders consecutivos mantengan el uso de memoria acotado.

---

## 4. Verification Gate
1. `& ".\.venv\Scripts\python.exe" -m py_compile app\telegram\charts.py app\telegram\commands\diagnostics.py app\telegram\callbacks.py app\miner_monitor.py`
2. Suite dedicada `tests/test_multi_miner_charts.py` cubriendo gráficos de grupo, selector de rango, `edit_telegram_photo` y prueba de retención de memoria.
3. 985+ tests globales PASS sin regresiones.
4. Servicio Windows `MinerAlerts` en estado `Running`.
