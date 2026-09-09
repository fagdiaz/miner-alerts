# Evidencia de Validación: Spec 046 - Mobile-First Card Layouts

## Registro de Pruebas y Validación

### 1. Baseline Previo
- Rama: `codex/022-adaptive-acquisition`
- Tests Previos: **660/660 tests PASS**
- Release Audit SHA-256: `4c1d77311f67049c1ece885108210e2e8626e7bd05833d5360ec0bb06bf41851`
- Servicio Activo: Windows Service `MinerAlerts` en ejecución bajo PID 31384 / 30588.

# Evidencia de Validación: Spec 046 - Mobile-First Card Layouts

## Registro de Pruebas y Validación

### 1. Baseline Previo
- Rama: `codex/022-adaptive-acquisition`
- Tests Previos: **660/660 tests PASS**
- Release Audit SHA-256: `4c1d77311f67049c1ece885108210e2e8626e7bd05833d5360ec0bb06bf41851`
- Servicio Activo: Windows Service `MinerAlerts` en ejecución bajo PID 31384 / 30588.

### 2. Validación de Fase 1 (Módulos Puros y Tests Unitarios)
- [x] **Compilación sintáctica**:
  - `& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py`: OK (0 errores)
  - `& ".\.venv\Scripts\python.exe" -m py_compile tools\miner_diagnostics.py`: OK (0 errores)
- [x] **Suite de tarjetas de flota (`tests/test_fleet_cards.py`)**: 9/9 PASS (0.001s)
  - Límite de ancho de línea estricto $\le 32$ columnas visibles comprobado en todas las líneas de `/status`, `/fans`, `/efficiency`, `/presets` (Condición C1).
  - Límite de tamaño total $< 3,600$ caracteres comprobado ($< 1,200$ caracteres por reporte) (Condición C4).
  - Tolerancia a fallos, mineros sin respuesta y datos ausentes validada.
  - Validación de callbacks $\le 64$ bytes y parser estricto (Condición C3).
- [x] **Suites de dominio existentes**:
  - `tests/test_fan_health.py`: 16/16 PASS
  - `tests/test_energy_efficiency.py`: 13/13 PASS
  - `tests/test_vnish_presets.py`: 11/11 PASS

### 3. Validación de Fase 2 (Integración en Monitor y Callbacks)
- [x] **Integración de callbacks diagnósticos (`tests/test_telegram_callbacks.py`)**: 25/25 PASS (0.160s)
  - `test_diag_ref_status_dispatch`: PASS (edición in-place, ACK instantáneo, teclado status)
  - `test_diag_ref_fans_dispatch`: PASS (edición in-place, ACK instantáneo, teclado fans)
  - `test_diag_ref_eff_dispatch`: PASS (edición in-place, ACK instantáneo, teclado eff)
  - `test_diag_ref_presets_dispatch`: PASS (edición in-place, ACK instantáneo, teclado presets)
  - `test_diag_unauthorized_rejection`: PASS (bloqueo con alerta modal a usuarios no autorizados)
  - `test_diag_malformed_callback`: PASS (rechazo seguro de payloads corruptos)
- [x] **Suite Global del Repositorio**:
  - Comando: `& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"`
  - Resultado: **675/675 tests PASS** (10.691s) — 0 fallas, 0 errores (+15 tests netos sobre baseline).
- [x] **Auditoría de Liberación (Release Audit)**:
  - Comando: `& ".\.venv\Scripts\python.exe" tools/release_audit.py --check-only`
  - Resultado: `RELEASE AUDIT: PASS. Runtime payload SHA-256: 57cc9185739a9685bb4d5f013298233dcf074aa00bea03c1441492a6710706ea`
  - Archivos de runtime auditados: 63
  - Disposiciones terminales verificadas: 8/8

### 4. Resumen de Certificación
- Todas las condiciones de control (C1-C10) han sido verificadas y satisfechas.
- Invariantes de producción preservados: Cero modificaciones a FSM (`MinerState`), lógica de reinicio, Hashcore CLI ni loop de monitoreo.
- Release Gate: **APROBADO PARA DESPLIEGUE EN PRODUCCIÓN**.
