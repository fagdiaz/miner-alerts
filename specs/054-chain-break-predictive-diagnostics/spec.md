# Spec 054: Telemetría Profunda por Cadena y Diagnóstico Predictivo de Hashboard (Chain Break Analysis)

## Estado y Metadatos
- **ID**: `054-chain-break-predictive-diagnostics`
- **Prioridad**: P1 (Diagnóstico Preventivo, Salud de Silicio e Inteligencia de Falla)
- **Estado**: PLANIFICADA / ESPECIFICACIÓN APROBADA (Pendiente de Implementación)
- **Fecha**: 2026-09-12
- **Autor**: Antigravity (Gemini 3.8 Flash High)
- **Documento Base**: `docs/proposals/SYSTEM_IMPROVEMENT_PROPOSALS.md` (PROP-008)
- **Dependencias**: Specs 023 (Incident Evidence Fusion), 037 (Vnish Presets), 041 (Modular Architecture), 051 (Phase Drop Discriminator).

---

## 1. Contexto y Objetivos

### 1.1 El Problema Operativo
Durante el incidente del 2026-09-12 (Evento 940), el minero 24 (`S19JPRO-24`) sufrió un reinicio abrupto tras 32 horas de estabilidad. El firmware Vnish registró:
```text
[16:28:11] S19JPRO-24 (miner) - chain/chain_break: Corte de cadena detectado
[16:28:12] S19JPRO-24 (status) - restart/miner_stopped: Proceso de minado detenido
```
Una auditoría en caliente reveló que el Elevador 1 operó de forma completamente estable (el minero peer 23 mantuvo 2.698W continuos sin caídas), confirmando que no fue un problema de alimentación AC general.

Al realizar una sonda directa sobre la API REST de Vnish (`/api/v1/chains`), se descubrió que el Minero 24 presenta un fallo persistente en el sensor térmico I2C de la **Cadena 2 (Board 2)**:
```json
{"state": "error", "board": 39, "chip": 54, "loc": 28}
```
mientras que los otros tres mineros de la flota (23, 25, 26) mantienen el 100% de sus sensores en estado saludable `measure`.

**Limitación Actual**:
El monitor Miner Alerts solo consulta la API consolidada 4028, la cual devuelve promedios agregados (`chain_voltage_mv_avg` y `active_boards: 3/3`), descartando por completo los datos granulares de cada placa individual que Vnish expone nativamente en `/api/v1/chains`.

### 1.2 Objetivos de la Spec 054
1. **Adquisición Desacoplada de Telemetría por Cadena**:
   - Polling programado (cada 15 a 30 min) y reactivo (al instante ante `reboot_detected`, `state_transition` a `HASHBOARD`/`LOW` o eventos de firmware `chain_break`).
   - Timeout estricto de 2.5s por equipo ejecutado en background sin impactar el loop principal.
2. **Persistencia Histórica Estructurada (Esquema SQLite v7)**:
   - Creación de tabla `chain_telemetry_samples` para registrar hashrate real vs nominal por placa, frecuencias, fallas de sensores y mapa de chips degradados/con errores.
3. **Motor de Diagnóstico Predictivo (`app/governance/chain_health.py`)**:
   - Alerta temprana preventiva en Telegram ante sensores en error persistente antes de que ocurra la caída física.
   - Detección de placas con déficit crónico de hashrate ($< 90\%$ del nominal).
   - Enriquecimiento automático de las alertas de reinicio indicando la placa y causa exacta (ej. *"Causa aislada: Falla I2C en Cadena 2, sensor loc 28"*).
4. **Comando de Inspección Táctil `/chains`**:
   - Interfaz en tarjetas Mobile-First (<= 32 cols) para inspeccionar la salud de las 3 placas de cualquier minero bajo demanda.
5. **Herramienta Analítica de Correlación (`tools/analyze_chain_breaks.py`)**:
   - Análisis retrospectivo de datos acumulados para correlacionar errores de chip, tensión y sensores con fallas históricas de hardware.

---

## 2. Requisitos Funcionales y Restricciones

### RF-001: Consulta No Bloqueante a `/api/v1/chains`
- Las peticiones HTTP a `/api/v1/chains` deben realizarse exclusivamente en un hilo worker desacoplado o mediante `ThreadPoolExecutor` con timeout de 2.5s por minero.
- Prohibido bloquear el hilo principal de monitoreo o el hilo de Telegram.

### RF-002: Esquema SQLite v7 (`chain_telemetry_samples`)
- Campos mínimos:
  - `id`: Autoincremental.
  - `observed_ts`: Timestamp Unix de captura.
  - `miner_key`: Clave canónica del minero.
  - `chain_id`: Identificador de placa (1, 2, 3).
  - `state`: Estado reportado por Vnish (`mining`, `error`, `initializing`, etc.).
  - `hr_realtime`: Hashrate real en MH/s o TH/s.
  - `hr_nominal`: Hashrate nominal esperado.
  - `hr_deficit_pct`: Porcentaje de desviación.
  - `freq_avg`: Frecuencia media de los chips en la placa.
  - `sensors_error_count`: Conteo de sensores en estado `error`.
  - `sensors_json`: Serialización JSON de los 4 sensores (temperatura placa, chip, loc y estado).
  - `chips_error_count`: Cantidad de chips con errores de hardware acumulados.
  - `chips_throttled_count`: Cantidad de chips estrangulados térmicamente.

### RF-003: Reglas de Diagnóstico Predictivo
- **Alerta Preventiva de Bus I2C**: Si `sensors_error_count >= 1` por 2 capturas consecutivas, clasificar como `WARNING_CHAIN_SENSOR_FAULT` y encolar notificación preventiva.
- **Alerta Preventiva de Déficit de Placa**: Si `hr_deficit_pct >= 10.0%` de forma sostenida con temperatura normal, alertar posible degradación de dominio de potencia.
- **Correlación de Incidentes**: Al registrarse `restart_detected`, buscar la última muestra de cadena del minero; si tenía sensor en error en una placa específica, asociar la placa en el campo `details_json` del incidente y reflejarlo en la tarjeta de Telegram.

### RF-004: UX Móvil `/chains`
- Formato vertical Mobile-First (ancho visible <= 32 caracteres por línea).
- Muestra el estado de Cadena 1, 2 y 3 con indicadores claros: `[OK]`, `[WARN Sensor]`, `[DEFICIT]`.
