# Tasks: Spec 044 - Modo Silencio Inteligente con Temporizador Persistente y Thermal Guard

## Fase 1: Extensión de Modelo y Persistencia (Condición C2)
- [x] T001 Extender `MinerState` con campos dedicados para modo silencio (`silent_mode_active`, `silent_mode_revert_ts`, `silent_mode_prev_duty`, `silent_mode_prev_preset`, `silent_mode_target_max_duty`).
- [x] T002 Actualizar funciones de serialización y carga en `app/core/` para persistir campos en `state.json`.
- [x] T003 Implementar verificación explícita en `first_tick` de `miner_monitor.py` para restaurar o purgar silencios expirados tras reinicios.

## Fase 2: Despacho Asíncrono de Acciones (Condición C1)
- [x] T004 Implementar despacho de cambios acústicos en `ThreadPoolExecutor` desacoplado evitando bloqueos en el polling worker.
- [x] T005 Configurar timeout estricto de 2.5s por equipo y respuesta instantánea `answerCallbackQuery`.

## Fase 3: Integración Dinámica con Fan Governor (Condición C3)
- [x] T006 Modificar cálculo de límites en `app/governance/fan_governor.py` para aceptar techos dinámicos de silencio.
- [x] T007 Inyectar `max_fan_duty_percent` acotado al modo silencio cuando `silent_mode_active == True`.

## Fase 4: Thermal Guard y Desactivación Atómica (Condición C4)
- [x] T008 Implementar lógica de desactivación atómica en `execute_governor_cycle` ante `EMERGENCY_SPIKE` (83.0°C) o fallas.
- [x] T009 Garantizar que `silent_mode_active = False` se guarde de inmediato en disco con `save_state()` bajo `state_lock`.
- [x] T010 Emitir alerta de emergencia prioritaria a través de Telegram informando la anulación térmica del modo silencio.

## Fase 5: Expiración Automática de Temporizadores
- [x] T011 Agregar chequeo de temporizadores en el loop principal de `miner_monitor.py`.
- [x] T012 Restaurar configuración previa al vencer el plazo y enviar notificación a Telegram.
- [x] T013 Proveer comando `/silent off` o botón de desactivación manual anticipada.

## Fase 6: Pruebas Unitarias, Concurrencia y Certificación
- [x] T014 Crear suite de pruebas `tests/test_silent_mode.py` cubriendo formalmente las condiciones C1, C2, C3 y C4.
- [x] T015 Ejecutar suite completa asegurando que los 587 tests existentes continúen pasando sin regresiones.
- [x] T016 Validar compilación de todos los módulos modificados (`py_compile`).
- [x] T017 Documentar evidencia de ejecución y pruebas en `specs/044-silent-mode-thermal-guard/evidence.md`.
- [x] T018 Actualizar `docs/speckit/ROADMAP.md` y `docs/audit/DEVELOPMENT_LOG.md`.

## Fase 7: Recalibración 30%–50% PWM, Regulación a 82°C y Autonomía por Elevador (2026-09-12)
- [x] T019 Recalibrar piso mínimo de hardware en `app/vnish/client.py` a 30% PWM (`max(30, min(100, int(duty_percent)))`).
- [x] T020 Corregir inversión de límites en `execute_governor_cycle` fijando corredor [30%, 50%] cuando `silent_mode_active` está habilitado.
- [x] T021 Incorporar clamps reactivos inmediatos fuera de banda en `app/governance/fan_governor.py` (forzar descenso a 50% o subida a 30% sin latencia de cooldown).
- [x] T022 Neutralizar `gov_target_pwr = None` en modo silencio para permitir modulación térmica libre hacia 30% a 82.0°C sin anclaje por déficit de potencia.
- [x] T023 Garantizar autonomía independiente por elevador y minero (aislamiento térmico y de ventiladores por equipo).
- [x] T024 Actualizar catálogo de comandos, Command Center y textos de ayuda en Telegram a 30%–50% PWM.
- [x] T025 Extender suite `tests/test_silent_mode.py` con pruebas de autonomía por elevador y certificar 800/800 tests PASS en producción.
