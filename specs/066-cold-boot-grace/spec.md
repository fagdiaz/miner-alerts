# Feature Specification: Spec 066 — Cold-Boot Fleet Grace Period Post-Arranque (PROP-001)

## Status
- **Date**: 2026-09-15
- **Priority**: P1 (Alta) | **Risk**: Bajo
- **Modules**: `app/miner_monitor.py`, `app/config.example.json`, `tests/test_startup_grace_period.py`
- **Baseline**: 1046 tests PASS, Windows Service `MinerAlerts` Running.

---

## 1. Problem Statement & Motivation
En incidentes de corte de suministro eléctrico o reinicio programado del host Windows, el sistema operativo arranca y el servicio `MinerAlerts` inicia en aproximadamente 30 segundos. Sin embargo, los mineros ASIC (Antminer S19j Pro con firmware Vnish) requieren físicamente entre **120 y 240 segundos** para:
1. Cargar el kernel Linux desde la memoria NAND.
2. Iniciar demonios de red y sincronizar fecha mediante NTP.
3. Ejecutar la calibración de autotuning de voltajes y frecuencias en las 3 placas.
4. Establecer conexión con el pool de minería y comenzar a generar hashrate real.

Como consecuencia de este desfase temporal:
- **Falsas alarmas inmediatas**: En el primer ciclo (`first_tick`), el monitor envía una notificación de `STARTUP` alertando que la flota está en `OFFLINE` o con `0.00 TH/s [LOW]`.
- **Riesgo de alertas espurias**: En los ciclos subsiguientes (segundos 30 a 180), la acumulación de streaks de `offline` o `low` puede disparar notificaciones de episodios irregulares (`EPISODE_ALERT`) antes de que el hardware haya completado su secuencia de calentamiento normal.
- **Inconsistencias en el estado**: Aunque el `startup_guard` existente bloquea el autorreinicio físico durante los primeros 600 segundos, los temporizadores de falla sostenida (`low_since_ts`, `hashboard_since_ts`) comienzan a acumularse prematuramente.

---

## 2. User Stories
- **US-01 (Calentamiento Pasivo Post-Arranque)**: Como operador de la flota, requiero que el monitor sondee pasivamente los mineros en segundo plano durante los primeros 180 segundos tras el arranque sin emitir alertas de falla (`OFFLINE`, `LOW`, `HASHBOARD`) ni acumular streaks de falla mientras el hardware realiza su autotuning.
- **US-02 (Tarjeta Consolidada y Limpia de Flota Restablecida)**: Como operador, requiero que el mensaje de arranque se postergue hasta que todos los mineros alcancen al menos 50 TH/s (o el umbral configurado), emitiendo una tarjeta unificada `🟢 FLOTA RESTABLECIDA` con la telemetría operativa de cada equipo.
- **US-03 (Expiración Segura por Timeout)**: Como operador, si transcurren 180 segundos sin que la totalidad de los mineros alcance el umbral, requiero que el período de gracia finalice automáticamente, emitiendo la tarjeta de arranque con el estado real observado y habilitando la detección regular de incidentes.
- **US-04 (Compatibilidad y Configuración)**: Como administrador de sistemas, requiero que el tiempo de gracia (`startup_fleet_grace_period_seconds`) y el umbral de estabilización (`startup_fleet_grace_threshold_ths`) sean configurables, y que un valor de `0` mantenga el comportamiento clásico sin período de gracia.

---

## 3. Functional Requirements

### FR-01: Parámetros de Configuración
- `"startup_fleet_grace_period_seconds"`: Entero $\ge 0$, por defecto `180` segundos. Define la duración de la ventana de calentamiento post-arranque.
- `"startup_fleet_grace_threshold_ths"`: Float $\ge 0.0$, por defecto `50.0` TH/s. Define la tasa mínima de hashrate que debe reportar cada minero para considerar su inicialización completa.

### FR-02: Detección y Control de la Fase WARMING_UP
- Al iniciar el proceso, el monitor calcula `startup_grace_active = (startup_fleet_grace_period_seconds > 0)`.
- Mientras `startup_grace_active` sea `True`:
  * El monitor adquiere telemetría en cada tick de forma habitual (30s) y registra muestras en `event_store`.
  * Se suprimen incrementos de streaks de falla (`offline_streak = 0`, `low_streak = 0`).
  * Se resetean temporizadores de falla sostenida (`low_since_ts = None`, `hashboard_since_ts = None`).
  * Se inhibe el disparo de alertas de episodios irregulares (`EPISODE_ALERT`) a Telegram.

### FR-03: Consolidación Temprana (Early Consolidation)
- Si en cualquier tick dentro de la ventana de gracia todos los mineros válidos responden (`responded is True`) con hashrate $\ge$ `startup_fleet_grace_threshold_ths`:
  * La flota se declara completamente estabilizada.
  * `startup_grace_active` se desactiva.
  * Se emite a Telegram la tarjeta consolidada:
    ```text
    🟢 FLOTA RESTABLECIDA (HH:MM:SS)
    Supervisión activa tras retorno de energía:
    - 23 (192.168.1.23): 89.10 TH/s
    - 24 (192.168.1.24): 98.90 TH/s
    ...
    ```
  * Se invoca `episode_notifications.acknowledge_active_initials()` para prevenir re-alertas.
  * Se registra un evento en `event_store` (`startup_fleet_grace_completed`).

### FR-04: Expiración de Gracia por Timeout (Timeout Consolidation)
- Si `(now_ts - process_start_ts) >= startup_fleet_grace_period_seconds` y la flota no completó la estabilización:
  * El período de gracia finaliza (`startup_grace_active = False`).
  * Se emite la tarjeta de arranque estándar `STARTUP` con el detalle de estado de cada minero.
  * Se invoca `episode_notifications.acknowledge_active_initials()`.
  * Se registra un evento en `event_store` (`startup_fleet_grace_expired`).
  * Se reanuda la supervisión y acumulación normal de streaks a partir del tick siguiente.

### FR-05: Preservación Inviolable de Contratos Legados
- Los contratos verificados por `inspect.getsource(main)` deben mantenerse estrictamente intactos:
  * `state.low_since_ts = None` dentro de `restart_reset`.
  * `elif (\n                    new_state == STATE_HASHBOARD`.
  * `time.sleep(poll_seconds)` al final del ciclo de supervisión.
  * Preservación del orden de interlocks de autorreinicio: startup guard < sustained < interlocks < cooldown < window < hashcore cli.

---

## 4. Non-Functional Requirements & Safety
- **NFR-01 (Cero Impacto en Latencia)**: Las evaluaciones de gracia se realizan en memoria ($\mathcal{O}(N)$ sobre la lista de mineros) sin llamadas de red adicionales.
- **NFR-02 (Resiliencia Operativa)**: Si la configuración de gracia está ausente o contiene valores erróneos, se aplican los valores por defecto seguros (`180s`, `50.0 TH/s`).
- **NFR-03 (Higiene de Secretos)**: No exponer credenciales ni IPs fuera de las estructuras canónicas del proyecto.
