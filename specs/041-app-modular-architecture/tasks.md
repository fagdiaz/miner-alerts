# Tasks: Spec 041 - Arquitectura Modular y Reorganización de Dominios en `app/`

## Fase 1: Preparación y Blueprint Inicial
- [x] T001 Crear directorio de especificación `specs/041-app-modular-architecture` y checklist de requisitos.
- [x] T002 Redactar `spec.md` con objetivos arquitectónicos, tabla de dominios y protocolo de shims retrocompatibles.
- [x] T003 Redactar `plan.md` con grafo de dependencias, orden de migración y criterios de pase.
- [ ] T004 Verificar línea base de tests (587 tests pasando) y estado limpio de git.

## Fase 2: Dominio Telegram (`app/telegram/`)
- [x] T005 Crear subpaquete `app/telegram/` con su correspondiente `__init__.py`.
- [x] T006 Mover `telegram_callbacks.py` -> `app/telegram/callbacks.py` y crear shim en `app/telegram_callbacks.py`.
- [x] T007 Mover `telegram_charts.py` -> `app/telegram/charts.py` y crear shim en `app/telegram_charts.py`.
- [x] T008 Mover `telegram_messages.py` -> `app/telegram/messages.py` y crear shim en `app/telegram_messages.py`.
- [x] T009 Mover `telegram_snooze.py` -> `app/telegram/snooze.py` y crear shim en `app/telegram_snooze.py`.
- [x] T010 Mover `daily_digest.py` -> `app/telegram/daily_digest.py` y crear shim en `app/daily_digest.py`.
- [x] T011 Configurar re-exportaciones canónicas en `app/telegram/__init__.py`.
- [x] T012 Validar compilación (`py_compile`) y verificar que 587/587 tests pasen.
- [x] T013 Realizar commit atómico de la Fase 2: `refactor(app): modularize telegram domain into app/telegram`.

## Fase 3: Dominio Vnish (`app/vnish/`)
- [ ] T014 Crear subpaquete `app/vnish/` con su correspondiente `__init__.py`.
- [ ] T015 Mover `vnish_client.py` -> `app/vnish/client.py` y crear shim en `app/vnish_client.py`.
- [ ] T016 Mover `vnish_presets.py` -> `app/vnish/presets.py` y crear shim en `app/vnish_presets.py`.
- [ ] T017 Mover `vnish_logs.py` -> `app/vnish/logs.py` y crear shim en `app/vnish_logs.py`.
- [ ] T018 Mover `vnish_telemetry.py` -> `app/vnish/telemetry.py` y crear shim en `app/vnish_telemetry.py`.
- [ ] T019 Configurar re-exportaciones canónicas en `app/vnish/__init__.py`.
- [ ] T020 Validar compilación (`py_compile`) y verificar que 587/587 tests pasen.
- [ ] T021 Realizar commit atómico de la Fase 3: `refactor(app): modularize vnish integration domain into app/vnish`.

## Fase 4: Dominio Governance (`app/governance/`)
- [ ] T022 Crear subpaquete `app/governance/` con su correspondiente `__init__.py`.
- [ ] T023 Mover `fan_governor.py` -> `app/governance/fan_governor.py` y crear shim en `app/fan_governor.py`.
- [ ] T024 Mover `preset_balancer.py` -> `app/governance/preset_balancer.py` y crear shim en `app/preset_balancer.py`.
- [ ] T025 Mover `fan_health.py` -> `app/governance/fan_health.py` y crear shim en `app/fan_health.py`.
- [ ] T026 Mover `energy_efficiency.py` -> `app/governance/energy_efficiency.py` y crear shim en `app/energy_efficiency.py`.
- [ ] T027 Configurar re-exportaciones canónicas en `app/governance/__init__.py`.
- [ ] T028 Validar compilación (`py_compile`) y verificar que 587/587 tests pasen.
- [ ] T029 Realizar commit atómico de la Fase 4: `refactor(app): modularize governance and cooling domain into app/governance`.

## Fase 5: Dominio Core (`app/core/`)
- [ ] T030 Crear subpaquete `app/core/` con su correspondiente `__init__.py`.
- [ ] T031 Mover módulos de adquisición (`acquisition.py`), persistencia (`event_store.py`) y episodios (`alert_episodes.py`) a `app/core/` con sus respectivos shims.
- [ ] T032 Mover módulos de telemetría y diagnósticos (`evidence_fusion.py`, `liveness.py`, `metrics_snapshot.py`, `mining_quality.py`) a `app/core/` con sus shims.
- [ ] T033 Mover módulos de estabilidad y reinicio (`reboot_safety.py`, `restart_intelligence.py`, `stability_profile.py`) a `app/core/` con sus shims.
- [ ] T034 Configurar re-exportaciones canónicas en `app/core/__init__.py`.
- [ ] T035 Validar compilación (`py_compile`) y verificar que 587/587 tests pasen.
- [ ] T036 Realizar commit atómico de la Fase 5: `refactor(app): modularize core acquisition and storage domain into app/core`.

## Fase 6: Modernización de Imports y Certificación Final
- [ ] T037 Actualizar importaciones en `app/miner_monitor.py` y herramientas de `tools/` apuntando a los nuevos subpaquetes.
- [ ] T038 Ejecutar suite completa de tests unitarios e integrados (587/587 PASS).
- [ ] T039 Ejecutar auditoría de release: `tools/release_audit.py --check-only`.
- [ ] T040 Registrar evidencia y telemetría en `specs/041-app-modular-architecture/evidence.md`.
- [ ] T041 Actualizar `docs/speckit/ROADMAP.md` y agregar entrada en `docs/audit/DEVELOPMENT_LOG.md`.
- [ ] T042 Realizar commit de cierre y sincronizar con repositorio remoto.
