# Spec 069: Telemetría Profunda por Cadena & Diagnóstico Predictivo Chain Break (PROP-008)

**ID**: 069  
**Módulos**: `app/governance/chain_health.py`, `app/vnish/chain_collector.py`, `app/miner_monitor.py`, `app/core/event_store.py`  
**Riesgo**: Medio (Consultas SQLite WAL, evaluación de series temporales sin falsas alarmas)  
**Prioridad**: P1 (Alta - Impacto Operativo Directo)  
**Estado**: Especificado  
**Dependencias**: Spec 054 (Chain Break Predictive Diagnostics), Spec 061 (SQLite WAL Integrity)  

---

## 1. Contexto y Problema

Durante el incidente del 2026-09-12 (Evento 940), el Minero 24 (`S19JPRO-24`) sufrió un reinicio abrupto no programado tras registrar un error crítico de `chain_break` en el firmware Vnish.
La auditoría forense de `/api/v1/chains` reveló que el equipo venía operando durante días con un sensor térmico I2C en fallo continuo en la **Cadena 2 (Board 2)**:
```json
{"state": "error", "board": 39, "chip": 54, "loc": 28}
```

### Brecha Operativa:
- Aunque la tabla `chain_telemetry_samples` ya almacena las muestras recolectadas periódicamente (Spec 054), el monitor **carece de un evaluador proactivo continuo que emita alertas antes de que ocurra el aborto por hardware**.
- Tampoco existe un mecanismo de discriminación que distinga si una caída de hashrate en una placa es un defecto físico del silicio o el resultado de una fluctuación de tensión externa en la fase eléctrica que alimenta al grupo de elevadores (`elevator_1` vs `elevator_2`).

---

## 2. Arquitectura de Solución

### Componente 1: Optimización de Base de Datos SQLite WAL
Para garantizar que las consultas de series temporales sobre `chain_telemetry_samples` tomen **menos de 8 ms** sin bloquear transacciones concurrentes:
- Se añade el índice compuesto optimizado de forma segura durante la inicialización de schema:
  ```sql
  CREATE INDEX IF NOT EXISTS ix_chain_telemetry_miner_chain_time
      ON chain_telemetry_samples(miner_key, chain_id, observed_ts DESC);
  ```
- Todas las consultas de diagnóstico histórico se ejecutan a través de `execute_readonly_with_retry` en el pool multi-lector con backoff exponencial.

### Componente 2: Reglas Matemáticas de Detección Predictiva
Implementadas en `app/governance/chain_health.py`:

1. **Regla 1 — Fallo Persistente de Sensor Térmico I2C (QA-069-01)**:
   - **Condición de Significancia Mínima**: Se requiere un mínimo de $N \ge 24$ muestras válidas recolectadas en la ventana de 12 horas ($T_{\text{window}} = 43\,200\text{ s}$). Si $N < 24$ (ej. equipo recién iniciado o red inestable), la evaluación se descarta como estadísticamente no concluyente.
   - **Condición de Falla**: Si $N \ge 24$ y $\ge 90\%$ de las muestras presentan `sensors_error_count > 0` con al menos una ubicación física idéntica persistente (`faulty_sensor_locs`).
   - Disparo: Alerta preventiva a Telegram (deduplicada: máximo 1 alerta por cadena cada 24 horas):
     ```
     ⚠️ RIESGO PREVENTIVO DE CHAIN BREAK
     Minero: S19JPRO-24
     Cadena: 2 (Board 2)
     Diagnóstico: Sensor térmico I2C (loc 28) en fallo continuo por >12h (28/30 muestras).
     Recomendación: Programar inspección física para evitar parada abrupta por firmware.
     ```
2. **Regla 2 — Detección de Déficit de Hashrate Localizado**:
   - Condición: Una placa individual reporta `hr_deficit_pct >= 10.0%` durante $\ge 3$ horas consecutivas mientras las placas adyacentes del mismo minero reportan `hr_deficit_pct <= 2.0%`.
   - Diagnóstico: Degradación localizada de chips (ASIC throttled o dominio de tensión descalibrado).
3. **Regla 3 — Aislamiento Causal Eléctrico con Fallback Seguro (QA-069-02)**:
   - Condición: Si el minero tiene asignado un grupo eléctrico en configuración (`group` / `elevator` / `phase_drop_discriminator`) y $\ge 2$ mineros del mismo grupo sufren caídas de hashrate simultáneas en un intervalo de 60 segundos:
     * Clasificación: `POWER_DISTURBANCE` (Perturbación eléctrica externa).
     * Supresión: Se inhibe la alerta de fallo de silicio individual para evitar falsos diagnósticos de hardware.
   - Fallback: Si el minero no tiene grupo configurado o es el único minero del segmento, la regla se omite con seguridad sin lanzar excepciones.

---

## 3. Requisitos Funcionales y Técnicos

1. **RF-01 (Latencia Acotada $< 15\text{ ms}$)**: La consulta de evaluación histórica de 12h debe completarse en $< 15\text{ ms}$ por minero.
2. **RF-02 (Deduplicación Estricta de Alertas)**: Las alertas preventivas no deben inundar Telegram; se almacena la marca de tiempo del último despacho por cadena (`last_chain_warning_ts`) con enfriamiento de 24 horas.
3. **RF-03 (Tolerancia a Muestras Faltantes & Significancia)**: Si un minero está apagado, en mantenimiento o cuenta con $<24$ muestras, el evaluador descarta la ventana sin generar falsas alarmas.
4. **RF-04 (Compatibilidad Invariante)**: Mantener 100% de contratos `inspect.getsource(main)`.

---

## 4. Configuración (`app/config.example.json`)

```json
{
  "predictive_chain_break_enabled": true,
  "chain_sensor_error_persistence_hours": 12.0,
  "chain_sensor_error_min_samples": 24,
  "chain_sensor_error_sample_pct": 90.0,
  "chain_deficit_threshold_pct": 10.0,
  "chain_deficit_duration_hours": 3.0,
  "chain_warning_cooldown_hours": 24.0
}
```

---

## 5. Estrategia de Pruebas Unitarias

- `test_chain_health_sensor_error_persistence`: Verificación del umbral de 12 horas y $\ge 90\%$ de fallos I2C.
- `test_chain_health_localized_deficit_detection`: Verificación de placa rezagada respecto a placas hermanas.
- `test_chain_health_electrical_group_isolation`: Verificación de supresión de alerta de silicio ante caída simultánea en el grupo eléctrico.
- `test_chain_health_sqlite_query_performance`: Benchmark de ejecución de consulta histórica en $< 15\text{ ms}$.
