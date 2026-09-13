# Tasks: Spec 054 - Telemetría Profunda por Cadena y Diagnóstico Predictivo de Hashboard

## Fase 1: Esquema de Base de Datos y Modelo de Datos (v7)
- [x] T001 Definir dataclass `ChainTelemetry` y `ChainSensor` en `app/vnish/chains.py` o módulo equivalente.
- [x] T002 Implementar migración de base de datos SQLite v7 creando la tabla `chain_telemetry_samples` con índices en `(miner_key, observed_ts)` y `(chain_id, sensors_error_count)`.
- [x] T003 Implementar funciones de inserción por lotes y consulta histórica en `app/core/event_store.py`.

## Fase 2: Colector Asíncrono de Cadenas Vnish
- [x] T004 Implementar cliente HTTP desacoplado `fetch_miner_chains` en `app/vnish/chain_collector.py` con timeout de 2.5s y parseo seguro de arrays `sensors` y `chips`.
- [x] T005 Integrar el programador de captura periódica (cada 15m) en hilo de fondo dentro de `app/miner_monitor.py`.
- [x] T006 Conectar disparador reactivo inmediato al detectarse un evento `reboot_detected`, `state_transition` a `HASHBOARD`/`LOW` o firmware `chain_break`.


## Fase 3: Motor de Diagnóstico Predictivo (`chain_health.py`)
- [x] T007 Implementar evaluador `assess_chain_health` en `app/governance/chain_health.py` para clasificar estados: `CHAIN_OK`, `CHAIN_SENSOR_ERROR`, `CHAIN_DEFICIT`, `CHAIN_FAULT`.
- [x] T008 Implementar regla de racha y cooldown en `evaluate_chain_alerts` para emitir advertencias preventivas por Telegram ante fallos de sensor I2C sostenidos.
- [x] T009 Enriquecer `record_elevator_restart_circumstance` y `operational_events` para asociar la placa específica culpable en los incidentes de reinicio.

## Fase 4: UX Telegram y Comando Interactivo `/chains`
- [x] T010 Implementar formateador de tarjeta Mobile-First `build_chains_card_text` asegurando ancho visible `<= 32` columnas.
- [x] T011 Registrar comando `/chains [minero]` en `app/telegram/command_center.py` y agregar botones de navegación rápida.
- [x] T012 Actualizar catálogo de ayuda en `app/telegram/help_center.py`.

## Fase 5: Herramienta Analítica de Historial
- [x] T013 Crear herramienta desacoplada `tools/analyze_chain_breaks.py` para análisis retrospectivo y cálculo de correlaciones entre sensores/chips y caídas de hardware.

## Fase 6: Pruebas Unitarias, Verificación y Certificación
- [x] T014 Crear suite de pruebas `tests/test_chain_collector.py` y `tests/test_chain_health.py`.
- [x] T015 Verificar compilación de sintaxis con `py_compile`.
- [x] T016 Ejecutar suite completa asegurando que los 802 tests existentes continúen pasando al 100%.
- [x] T017 Documentar evidencia de pruebas y validación en `specs/054-chain-break-predictive-diagnostics/evidence.md`.
- [x] T018 Actualizar `docs/speckit/ROADMAP.md` y `docs/audit/DEVELOPMENT_LOG.md`.
