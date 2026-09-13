# Evidencia de Implementación: Spec 054 (100% Completado y Certificado)

- **Fecha**: 2026-09-12
- **Estado**: COMPLETADO Y CERTIFICADO (Fases 1 a 6)
- **Suite de Pruebas**: 835/835 tests PASS (33 nuevos tests añadidos, cero regresiones)

---

## 1. Fase 1: Esquema de Base de Datos y Modelo de Datos (v7)

### 1.1 Modelo de Datos `ChainSensor` y `ChainTelemetry`
- Creado en `app/vnish/chains.py`.
- Soporta parseo seguro desde `/api/v1/chains` para sensores térmicos (`state`, `board`, `chip`, `loc`) y chips individuales.
- Métricas calculadas: `hr_deficit_pct`, `is_healthy`, `max_chip_temp`, `max_board_temp`, `sensors_error_count`, `chips_error_count`, `chips_throttled_count`.

### 1.2 Migración de Esquema SQLite v7 (`chain_telemetry_samples`)
- `app/core/event_store.py`: `SCHEMA_VERSION = 7`.
- DDL con tabla `chain_telemetry_samples` e índices:
  - `ix_chain_telemetry_miner_time ON chain_telemetry_samples(miner_key, observed_ts DESC)`
  - `ix_chain_telemetry_chain_error ON chain_telemetry_samples(chain_id, sensors_error_count)`
  - `ix_chain_telemetry_time ON chain_telemetry_samples(observed_ts DESC)`
- Métodos implementados en `EventStore`:
  - `record_chain_samples(miner_key, samples, observed_ts=None) -> int`
  - `get_latest_chain_samples(miner_key) -> List[Dict[str, Any]]`
  - `get_chain_samples_window(miner_key, start_ts, end_ts, chain_id=None) -> List[Dict[str, Any]]`
  - `get_chain_error_history(miner_key=None, limit=50) -> List[Dict[str, Any]]`

---

## 2. Fase 2: Colector Asíncrono de Cadenas Vnish

### 2.1 Módulo Desacoplado `app/vnish/chain_collector.py`
- `fetch_miner_chains(host, token=None, timeout=2.5, session=None) -> Tuple[bool, List[ChainTelemetry], Optional[str]]`
- `fetch_fleet_chains(miner_hosts, token=None, timeout=2.5, max_workers=4) -> Dict[str, Tuple[bool, List[ChainTelemetry], Optional[str]]]`
- Manejo resiliente de timeouts (2.5s), errores de conexión, códigos HTTP 401/500 y JSON malformado.

### 2.2 Integración en `app/miner_monitor.py`
- Función worker en hilo de fondo `_async_collect_chain_telemetry`.
- Programador periódico (T005): Cada 900s (15 min) en hilo daemon `ChainTelemetryScheduled`.
- Disparadores reactivos (T006):
  - Al detectarse `reboot_reason` (`elapsed_drop` / `elapsed_reset`).
  - Al cambiar de estado hacia `STATE_HASHBOARD` o `STATE_LOW`.

---

## 3. Fase 3: Motor de Diagnóstico Predictivo (`chain_health.py`)

### 3.1 Evaluador de Salud y Clasificación
- Creado en `app/governance/chain_health.py`:
  - `assess_single_chain`: evalúa sensores I2C, temperatura, frecuencia y chips degradados. Clasifica en `CHAIN_OK`, `CHAIN_SENSOR_ERROR`, `CHAIN_DEFICIT`, `CHAIN_FAULT`.
  - `assess_miner_chains`: consolida el estado de las 3 placas por minero.
  - `find_culprit_chain_for_restart`: determina la placa física anómala previa a un reinicio.
  - `evaluate_chain_health_streak`: filtro antirrebote de racha consecutiva (mínimo 2 capturas) y cooldown (7200s) para evitar spam de alertas.

### 3.2 Enriquecimiento de Incidentes
- Conectado a `record_elevator_restart_circumstance` en `preset_balancer.py`.
- Campo `details_json` en `operational_events` incluye `culprit_chain` (`chain_id`, `reason`, `faulty_locs`).
- `render_event_detail` en `event_store.py` muestra la placa culpable exacta (`• Causa física: Cadena X`).

---

## 4. Fase 4: UX Telegram y Comando Interactivo `/chains`

### 4.1 Tarjetas Mobile-First (`<= 32` columnas)
- `build_chains_card_text`: detalle completo de las 3 placas por equipo (TH/s real/nominal, temps, frecuencias, locs de sensor y recomendaciones).
- `build_chains_fleet_summary_text`: resumen compacto de la flota ASIC con badges de salud por placa (`C1:OK C2:ERR C3:OK`).
- `build_chains_keyboard`: botones de acceso directo a cada minero, botón de actualización y botón de retorno al menú principal.

### 4.2 Integración de Comando y Callbacks
- Comando `/chains [minero]` despachado en `miner_monitor.py`.
- Atajos y alias: `/chain`, `/placas`.
- Callbacks interactivos: `diag:ref:chains`, `diag:chains:<id>`, `diag:ref:chains:<id>` con actualización en el mensaje existente sin generar ruido.
- Catálogo registrado en `app/telegram/help_center.py` dentro de categoría `diag`.

---

## 5. Fase 5: Herramienta Analítica de Historial

### 5.1 CLI `tools/analyze_chain_breaks.py`
- Conexión de solo lectura (`ro`) sobre SQLite.
- Agregación temporal por minero y cadena (`--days`, `--hours`, `--miner`).
- Detección de fallas térmicas y cálculo de porcentajes de error por sensor I2C.
- Correlación automática con eventos históricos de reinicio (`operational_events`).
- Soporte para salida de tabla formateada y `--json` estándar.
- Protegido contra codificación de caracteres en consolas Windows (`sys.stdout.reconfigure`).

---

## 6. Comandos de Validación y Certificación

### 6.1 Compilación de Sintaxis
```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app/vnish/chains.py app/vnish/chain_collector.py app/vnish/__init__.py app/core/event_store.py app/governance/chain_health.py app/governance/__init__.py app/telegram/fleet_cards.py app/telegram/help_center.py app/telegram/command_center.py tools/analyze_chain_breaks.py app/miner_monitor.py
```
**Resultado**: Salida limpia (código 0).

### 6.2 Tests Unitarios Específicos
```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests/test_chain_collector.py tests/test_chain_health.py tests/test_analyze_chain_breaks.py tests/test_event_store.py tests/test_fleet_cards.py
```
**Resultado**: `Ran 70 tests, OK`.

### 6.3 Ejecución en Producción de la Herramienta Analítica
```powershell
& ".\.venv\Scripts\python.exe" tools/analyze_chain_breaks.py --hours 24
```
**Resultado**: Capturó correctamente los datos en tiempo real de `data/miner_alerts.db`, confirmando el fallo del sensor térmico I2C en la Cadena 2 del Minero 24 (loc 28) con 100% de error mientras Mineros 23 y 26 operan al 100% saludables.

### 6.4 Suite de Regresión Completa
```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests
```
**Resultado**:
```text
Ran 835 tests in 13.637s
OK
```
Cero errores, cero fallos, cero regresiones. 100% de cobertura certificada.
