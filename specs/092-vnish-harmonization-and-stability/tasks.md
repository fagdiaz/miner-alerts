# Tasks: Armonización Térmica y Estabilidad VNish (Spec 092)

**Feature**: `092-vnish-harmonization-and-stability`
**Dependencies**: Arquitectura V6.0 (`specs/091-core-daemon-hookification`)
**Target Outcome**: Eliminación definitiva de reinicios en M24 y M26, Fan Governor con headroom de 3°C, silicio asimétrico clampeado, y telemetría SQLite periódica reactivada.

---

## Tareas de Implementación

- [x] **T001** [P0] [Riesgo Medio]: Modificar los umbrales térmicos del Fan Governor en `app/config.json` y `app/config.example.json` (`target_temp_c: 79.5`, `deadband_low_c: 78.0`, `deadband_high_c: 81.0`, `emergency_temp_c: 82.5`).
- [x] **T002** [P0] [Riesgo Medio]: Configurar perfiles asimétricos por minero en `app/config.json` y `app/config.example.json` (M24 y M26 con `target_power_w: 2500.0`, `max_hardware_preset: "2500W"`; M23 y M25 con `target_power_w: 2700.0`, `max_hardware_preset: "2700W"`).
- [x] **T003** [P0] [Riesgo Alto]: Clampear la configuración de firmware VNish en M24 y M26 a través de su API REST (`top_preset: "2500"`, `preset: "2500"`), verificando que no soliciten reinicio físico (`restart_required: false`).
- [x] **T004** [P0] [Riesgo Medio]: Reconectar la telemetría periódica de cadenas (`_async_collect_chain_telemetry`), evaluación predictiva de fallas (`_async_evaluate_predictive_chain_break`) y mantenimiento periódico SQLite WAL en `PostTickHook` de `app/core/pipeline.py`.
- [x] **T005** [P0] [Riesgo Alto]: Validar compilación de sintaxis (`py_compile`) y ejecutar la suite completa de pruebas (`pytest tests/`) certificando $\ge 1530$ tests PASS (0 fallos).
- [x] **T006** [P0] [Riesgo Medio]: Ejecutar preflight QA de `speckit-qa` (`.agents/skills/speckit-qa/scripts/preflight.ps1`).
- [x] **T007** [P0] [Riesgo Alto]: Reiniciar el servicio Windows NSSM `MinerAlerts`, verificar en caliente la adquisición y telemetría en `logs/out.log` y registrar inserciones en `chain_telemetry_samples`.
- [x] **T008** [P0] [Riesgo Alto]: Ejecutar la compuerta de certificación y release `speckit-stabilize` (`preflight_stabilize.ps1` 8/8 gates PASS).
- [x] **T009** [P0] [Riesgo Bajo]: Documentar la sesión en `docs/audit/DEVELOPMENT_LOG.md`, actualizar `docs/speckit/ROADMAP.md` y refrescar `prompt.txt`.
