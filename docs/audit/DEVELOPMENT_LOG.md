# Historial de Desarrollo y Cambios - Miner Alerts

Este archivo registra las specs y cambios completados que tienen respaldo en el codigo, la documentacion o evidencia operativa vigente, en orden cronologico inverso.
La entrada mas reciente debe agregarse inmediatamente debajo de este bloque.

## [2026-09-08] - Desacople de Telemetría de Gobernador y Fallback en Memoria para Balanceador de Presets

* **Objetivo**: Auditar y robustecer la resiliencia operativa: desacoplar la ingesta de telemetría del Fan Governor respecto de las alertas preventivas de cooling, evitar que mineros offline operen sobre telemetría fantasma, y agregar fallback de estado en memoria en el Balanceador de Presets para inferir potencias y márgenes térmicos reales aun cuando la base SQLite no haya grabado muestras recientes.
* **Mejoras Implementadas**:
  - **Desacople de Ingesta de Telemetría (`app/miner_monitor.py:5901`)**:
    * La alimentación de `state.governor_last_temp_c` y `state.governor_last_power_w` se movió fuera del bloque condicional de `cooling_alert_enabled`, garantizando que el gobernador reciba telemetría en tiempo real independientemente de cómo esté configurado el subsistema de alertas de enfriamiento.
    * Ante desconexión o falla de respuesta del minero (`not responded`), se limpian los valores a `None`, garantizando que el gobernador devuelva `ACTION_UNKNOWN` con `requires_write=False` y nunca intente ajustar ventiladores sobre datos obsoletos o en mineros inalcanzables.
  - **Fallback en Memoria para Métricas de Estabilidad (`app/preset_balancer.py:386`)**:
    * En `extract_miner_stability_metrics()`, si la tabla `telemetry_samples` de SQLite no contiene filas recientes para un minero, se recurre automáticamente a los valores en memoria de `states` (`st.governor_last_power_w`, `st.governor_last_temp_c` y `st.last_elapsed`).
    * Erradica la inferencia errónea del preset por defecto ("1600W") en mineros que operan en 2500W o 2700W.
* **Certificación**:
  - 581/581 tests PASS en 8.77s.
  - Sintaxis limpia (`py_compile`) y servicio reiniciado en producción.

---

## [2026-09-08] - Calibración Térmica de Fan Governor a 82.0°C para Prevención de Autoswitch Vnish

* **Objetivo**: Reducir el target térmico del gobernador de 83.0°C a 82.0°C para maximizar la estabilidad operativa y evitar que fluctuaciones térmicas normales se acerquen al umbral de corte/desescalado de Vnish (`decrease_temp: 84.0°C`).
* **Ajustes Operativos (`app/config.json`, `app/config.example.json`, `app/miner_monitor.py`)**:
  - `fan_governor_target_temp_c`: 82.0°C (objetivo central de trabajo saludable).
  - `fan_governor_deadband_low_c`: 81.0°C (modula ventiladores -2% si T < 81.0°C).
  - `fan_governor_deadband_high_c`: 82.5°C (incrementa ventiladores +3% si T > 82.5°C).
  - `fan_governor_emergency_temp_c`: 83.5°C (salto de emergencia a 100% PWM si T >= 83.5°C, manteniendo 0.5°C de margen estricto antes de los 84.0°C de Vnish).
* **Certificación**:
  - 581/581 tests PASS en 8.92s.
  - Servicio reiniciado en producción bajo PID nuevo y verificada la ejecución en vivo.

---

## [2026-09-08] - Corrección de Razonamiento Individual por Minero y Preservación de Configuración en `valid_miners`

* **Objetivo**: Garantizar el razonamiento 100% individual y personalizado por minero en el Fan Governor: resolver la causa raíz por la cual mineros operando en su techo configurado (S19JPRO-25 y 26 en 2500W con temperatura sana de 76°C) recibían orden de 100% de coolers (`RECOVERY_MAX_COOLING`) en lugar de modular hacia abajo (`STEP_DOWN`), permitiendo que cada equipo module sus ventiladores de forma estrictamente desacoplada de los demás.
* **Causa Raíz Identificada**:
  - En la inicialización del monitor (`miner_monitor.py:5596`), la lista `valid_miners` se instanciaba con un diccionario mínimo `{name, host, port}`, descartando inadvertidamente los campos `target_power_w`, `electrical_group` y cualquier otro atributo individual del minero.
  - Al no recibir `target_power_w` (devolvía `None`), el gobernador recurría al fallback global `fan_governor_target_power_w = 2700.0W`.
  - Como resultado, S19JPRO-25 y 26 (consumiendo 2498–2499W) eran evaluados contra 2700W en vez de contra sus 2500W reales, interpretándose falsamente como equipos con déficit de potencia (2499W < 2700 - 120W), disparando coolers al 100% incondicional.
* **Corrección y Mejoras Implementadas**:
  - **Preservación Total en `valid_miners`**: `valid_miners.append(dict(miner))` preserva íntegramente `target_power_w`, `electrical_group`, `max_preset` y posibles overrides por equipo.
  - **Configuración Dinámica por Minero (`miner_gov_cfg`)**: Permite que cada minero sobreescriba individualmente umbrales térmicos (`target_temp_c`, deadbands, piso de PWM, etc.) si se define en su entrada de configuración.
  - **Claridad Observacional en Logs y Telegram**:
    * Log del ciclo: `pwr=2499/2500W` o `pwr=2499/2700W` refleja de inmediato la potencia actual respecto a la meta individual.
    * Comando `/gov`: Muestra la relación `T=76.0°C 2499/2500W PWM=98% [STEP_DOWN]`, evidenciando el razonamiento individual.
  - **Certificación de Pruebas**:
    * Nuevo test de integración: `test_individual_miner_reasoning_different_targets_and_temperatures` en `tests/test_fan_governor_concurrency.py`.
    * 581/581 tests PASS en 9.04s.

---

## [2026-09-08] - Integración de Recuperación de Autoswitch Vnish en Fan Governor y Formato REST API

* **Objetivo**: Resolver el desacople entre el autoswitch nativo de Vnish y la modulación del Fan Governor: evitar que un minero quede estancado en potencias subóptimas (ej. 2300W en vez de 2500W/2700W) por modulación descendente de ventiladores a 83°C. Forzar 100% de enfriamiento hasta que el equipo alcance su potencia objetivo, permitiendo que el chip baje a $\le 79^\circ\text{C}$ y el firmware Vnish suba el preset al máximo permitido.
* **Resultados y Evidencia**:
  - **Mecanismo de Recuperación de Autoswitch (`app/fan_governor.py`, `app/miner_monitor.py`)**:
    * Regla `ACTION_RECOVERY_MAX_COOLING`: Si `current_power_w < (target_power_w - margin_w)` (margen 120W), el gobernador fuerza 100% de PWM de forma incondicional, deshabilitando el step-down mientras el minero esté por debajo de su techo de autoswitch.
    * Con 100% de ventilación, los chips se enfrían por debajo del umbral `rise_temp` (79.0°C de Vnish), habilitando el ascenso automático de preset de Vnish tras el `check_time` (300s).
    * Únicamente cuando el equipo alcanza su potencia objetivo (2700W en 23/24, 2500W en 25/26) y la temperatura es $\le 82.0^\circ\text{C}$, el gobernador modula los ventiladores hacia abajo para estabilizar la temperatura en 83.0°C.
    * Telemetría de potencia (`chain_power_w_total`) persistida en `MinerState` (`governor_last_power_w`) y reflejada en el comando `/gov` de Telegram (`T=82.5°C 2698W PWM=96%`).
  - **Normalización de Formato REST API Vnish (`app/vnish_client.py`)**:
    * La API REST de Vnish rechaza `"2700W"` con HTTP 400 (`ProfileName invalid: '2700W'`). Se normalizó en `set_miner_preset()` para limpiar sufijos `"W"`, enviando `"2700"`.
  - **Configuración Operativa (`app/config.json`, `app/config.example.json`)**:
    * `miners`: S19JPRO-23 y 24 configurados con `target_power_w: 2700.0`; S19JPRO-25 y 26 configurados con `target_power_w: 2500.0`.
    * `preset_balancer_dry_run: true`: El balanceador corre en modo diagnóstico / monitoreo de cascada eléctrica sin forzar presets que compitan con el autoswitch de Vnish.
    * `fan_governor_enabled: true`, `fan_governor_dry_run: false`: Gobernador activo en producción.
  - **Suite de Pruebas**:
    * Nuevos tests unitarios y de integración: `test_recovery_max_cooling_when_below_target_power`, `test_recovery_max_cooling_already_at_100`, `test_normal_modulation_when_at_target_power`, `test_execute_governor_cycle_recovers_to_100_when_below_target_power`.
    * 580/580 tests PASS en 8.86s (0 fallos, 0 errores, 0 regresiones).
    * `py_compile` limpio en todo el proyecto.

---

## [2026-09-08] - Activación Plena por Defecto de Gobernador Térmico y Balanceador de Presets en Producción

* **Objetivo**: Configurar como activas por defecto (`enabled: true`, `dry_run: false`) las nuevas aplicaciones de control y gobernanza de hardware (Spec 039 Fan Governor y Spec 040 Preset Balancer), manteniendo intacta la capacidad de desconexión y reconexión manual interactiva en caliente vía Telegram (`/gov on`/`/gov off`, `/balancer on`/`/balancer off`). Normalizar y sincronizar toda la documentación del proyecto, reiniciar el servicio en modo activo y certificar la estabilidad absoluta del sistema.
* **Resultados y Evidencia**:
  - **Activación por Defecto en Configuración (`app/config.json` y `app/config.example.json`)**:
    * `fan_governor_enabled: true` y `fan_governor_dry_run: false`: Gobernador térmico de lazo cerrado activo al arrancar el servicio. Modula coolers al target de 83.0°C en base a la telemetría periódica. Desactivable en cualquier momento con `/gov off` (fallback automático a 100% PWM).
    * `preset_balancer_enabled: true` y `preset_balancer_dry_run: false`: Balanceador de presets activo al arrancar el servicio. Desescala preventivamente por reinicios en 24h, caídas en cascada del mismo elevador o temperatura límite $\ge 84.0^\circ\text{C}$. Desactivable en cualquier momento con `/balancer off`.
  - **Normalización de Documentación**:
    * `specs/039-vnish-fan-governor/evidence.md`: Actualizado con la activación en producción, target 83°C y umbrales definitivos.
    * `specs/040-dynamic-voltage-presets/evidence.md`: Actualizado con los 14 tests unitarios deterministas (incluyendo sobrecarga térmica) y activación en producción.
    * `docs/speckit/ROADMAP.md`: Specs 039 y 040 marcadas formalmente como *COMPLETADAS Y ACTIVAS EN PRODUCCIÓN*.
    * `docs/speckit/DELIVERY_PLAN.md`: Hitos de cierre registrados para Specs 039 y 040.
    * `docs/speckit/SPEC_PROGRAM.md`: Estado del programa actualizado a 40 especificaciones cerradas (V1 a V3.1) y 576 tests automáticos.
  - **Certificación de Pruebas**:
    * 576/576 tests PASS en 8.52s (0 fallos, 0 errores, 0 regresiones).
    * Validación de sintaxis limpia en todo el árbol de código.

---

## [2026-09-08] - Calibración Operativa Térmica 83°C–84°C, Step-Down por Temperatura y Mitigación de Spam en Telegram

* **Objetivo**: Alinear la estrategia física de operación solicitada por el operador: punto de trabajo sano a 83.0°C, límite máximo estable de 84.0°C con desescalado secuencial de potencia (2700W -> 2500W -> 2300W) si los ventiladores al 100% no son suficientes para contener la temperatura, modulación descendente de ventiladores cuando exista margen térmico, y erradicación definitiva de falsas alertas de saturación y ruido de autotune en Telegram.
* **Resultados y Evidencia**:
  - **Desescalado Térmico en Balanceador de Presets (`app/preset_balancer.py`)**:
    * Implementada regla prioritaria `ACTION_STEP_DOWN_THERMAL`: ante margen térmico crítico $\le 1.0^\circ\text{C}$ (temperatura $\ge 84.0^\circ\text{C}$ frente al corte por hardware de 85.0°C), el balanceador desescala de inmediato el preset de potencia (`2700W -> 2500W -> 2300W`) para proteger el hardware antes de que ocurra un trip de emergencia.
    * Test unitario agregado: `test_step_down_on_thermal_overload` en `tests/test_preset_balancer.py` (14/14 tests PASS).
  - **Calibración de Gobernador Térmico (Spec 039)**:
    * `fan_governor_target_temp_c`: 83.0°C (punto objetivo de máxima eficiencia y salud física).
    * `fan_governor_deadband_low_c`: 82.0°C. Si temp < 82.0°C, reduce el duty de ventiladores (-2%) para evitar desgaste y ruido innecesarios.
    * `fan_governor_deadband_high_c`: 83.5°C. Si temp > 83.5°C, incrementa el duty de ventiladores (+3%).
    * `fan_governor_emergency_temp_c`: 84.0°C. Dispara ventiladores al 100% PWM de inmediato.
  - **Mitigación de Spam y Falsas Alarmas en Telegram (`app/fan_health.py`, `app/miner_monitor.py`)**:
    * El umbral hardcoded de 82.0°C para `STATUS_CRITICAL_HEAT` se refactorizó a `critical_temp_c: float = 84.5` (configurable vía `cooling_critical_temp_c`). Esto evita que mineros operando sanamente a 81°C–83.5°C sean catalogados falsamente como calor crítico.
    * `cooling_saturate_temp_c` elevado de 78.0°C a 84.0°C con `cooling_saturate_pwm_pct`: 98.0%, `cooling_saturate_streak`: 5 ticks y `cooling_cooldown_seconds`: 7200s (2 horas). Erradica los avisos espurios de saturación a 81.0°C reportados por el usuario.
    * `preset_alert_enabled: false`: Silencia las notificaciones informativas de autotune de Vnish por fluctuaciones normales de 25–35 MHz. El estado de frecuencia permanece totalmente accesible bajo demanda vía `/presets` y `/digest`.
  - **Suite de Pruebas y Certificación**:
    * 576/576 tests PASS en 8.66s.
    * `py_compile` limpio en `app/miner_monitor.py`, `app/fan_health.py` y `app/preset_balancer.py`.

---

## [2026-09-08] - Implementación y Cierre de Spec 040 (Dynamic Power & Preset Balancer: Fases 1 a 5 Completadas)

* **Objetivo**: Desarrollar e integrar el Balanceador Dinámico de Presets y Potencia para Elevadores de Tensión Sensibles (Spec 040), respondiendo a la necesidad operativa de calibrar el hashrate versus frecuencia de caídas/reinicios, proteger fases eléctricas y evitar apagados en cascada en la granja.
* **Resultados y Evidencia**:
  - **Fase 1 (Extensión de Cliente REST Vnish Presets - `app/vnish_client.py`)**:
    * Métodos transaccionales implementados: `get_available_presets()` (consulta en `GET /api/v1/presets`), `set_miner_preset()` (modulación de overclock en `POST /api/v1/settings`) y `safe_set_miner_preset()` con garantía de cierre de sesión (`lock_miner`) en bloque `finally`.
    * Tests unitarios con mocks HTTP en `tests/test_vnish_client.py` (15/15 tests PASS).
  - **Fase 2 (Motor Matemático Puro de Balanceo Costo/Beneficio - `app/preset_balancer.py`)**:
    * Modelos de datos: `PresetTier`, `StabilityMetrics`, `BalancerConfig`, `BalancerDecision`.
    * Escalera estándar de presets Vnish para S19j Pro: 1600W a 2800W.
    * Función objetivo $H_{\text{eff}}$ demostrando matemáticamente que operar a 93 TH/s (2500W) sin reinicios genera más hashrate neto acumulado que operar forzado a 98 TH/s (2700W) con reinicios frecuentes (93.00 TH/s vs 89.96 TH/s netos).
    * Regla de desescalado rápido individual ante $\ge 2$ reinicios en 24h.
    * Regla de protección de elevador sensible: desescalado en cascada si dos mineros del mismo elevador se reinician en menos de 30 minutos.
    * Hysteresis conservadora: exige 72 horas continuas de estabilidad total y margen térmico $\ge 4.0^\circ\text{C}$ antes de considerar subir 1 preset.
    * Función `extract_miner_stability_metrics()` leyendo SQLite con URI `?mode=ro` en < 20ms.
    * Formateadores de Telegram: `build_balancer_table_text()` (agrupado por elevador) y `build_miner_balancer_detail_text()`.
  - **Fase 3 (Suite de Pruebas Unitarias Deterministas - `tests/test_preset_balancer.py`)**:
    * 13 tests unitarios deterministas cubriendo cálculo de $H_{\text{eff}}$, desescalado por reinicios, freno en preset mínimo (1600W), desescalado grupal en cascada, escalado tras soak de 72h, bloqueo térmico, inferencia por potencia, tablas Telegram y consulta contra base real (13/13 tests PASS en 0.002s).
  - **Fase 4 (Integración en Monitor, Persistencia y Comandos Telegram - `app/miner_monitor.py`)**:
    * Soporte para `electrical_group` en cada minero en `config.json` y `config.example.json`.
    * Campos en `MinerState` (`balancer_preset`, `balancer_last_change_ts`, `balancer_last_action`, `balancer_last_reason`) persistidos atómicamente en `state.json`.
    * Ciclo de balanceo `execute_balancer_cycle()` integrado de forma no-bloqueante con `ThreadPoolExecutor` (timeout global de flota de 5.0s) y ejecución periódica (`preset_balancer_interval_seconds: 1800`).
    * Configuración ultra-segura por defecto: `preset_balancer_enabled: false` y `preset_balancer_dry_run: true`.
    * Comandos Telegram interactivos: `/balancer` (tabla ejecutiva agrupada por elevador), `/balancer on`, `/balancer off`, `/balancer setmax <miner> <preset>`, `/balancer run` y detalle individual por minero.
  - **Fase 5 (Validación, Tests de Concurrencia y Certificación Global)**:
    * `tests/test_preset_balancer_integration.py`: 9 tests de integración y concurrencia verificando simulación en dry-run, escritura activa mockeada, timeout de flota, cerrojos multihilo bajo `state_lock` y comandos de ayuda.
    * Certificación de Suite Global: **575/575 tests PASS** en 10.08s (0 fallos, 0 errores, 0 regresiones).
    * `py_compile` limpio en `app/miner_monitor.py`.
  - **Modelo**: Gemini 3.8 Flash High (100% autónomo).

---

## [2026-09-08] - Implementación y Cierre de Spec 039 (Vnish Thermal & Acoustic Fan Governor — Fases 1 a 5 Completadas)

* **Objetivo**: Desarrollar e integrar el Gobernador Térmico y Acústico de Ventiladores Vnish (Spec 039), incorporando detección de modo en `/fans`, cliente REST seguro (`app/vnish_client.py`), algoritmo determinista de lazo cerrado (`app/fan_governor.py`), integración multihilo protegida en el monitor (`app/miner_monitor.py`), comandos interactivos Telegram (`/gov`, `/gov on`, `/gov off`, `/gov set`) y suite de estrés de concurrencia.
* **Resultados y Evidencia**:
  - **Fase 1 (Visibilidad de Modo de Enfriamiento)**:
    * `app/vnish_telemetry.py`: Extendido para extraer `fan_mode` (`manual`, `auto`, `immers`) tanto desde el payload `STATS` de API 4028 como desde el payload REST `/api/v1/summary`.
    * `app/fan_health.py`: `CoolingAssessment` extendido con `fan_mode`. `build_fans_table_text()` ahora renderiza indicadores explícitos `(100% [MANUAL])` y `build_miner_fan_detail_text()` expone `• Modo Control: MANUAL`.
    * `app/miner_monitor.py`: Almacena `state.last_fan_mode` y lo transfiere al evaluador de salud de enfriamiento.
  - **Fase 2 (Cliente Vnish REST Seguro - `app/vnish_client.py`)**:
    * Funciones transaccionales seguras: `unlock_miner`, `lock_miner`, `get_cooling_settings`, `set_manual_fan_duty` y wrapper de alto nivel `safe_set_fan_duty` con bloque `try ... finally: lock_miner` garantizado.
    * Enmascaramiento de secretos (`mask_secret`) previniendo exposición de passwords o Bearer tokens en logs.
    * Clamping de hardware: duty limitado rígidamente entre [40%, 100%].
    * Timeouts cortos de 2.5s por solicitud HTTP (cumplimiento R2).
  - **Fase 3 (Algoritmo Determinista del Gobernador - `app/fan_governor.py`)**:
    * Motor matemático puro `compute_governor_step()` sin efectos colaterales ni I/O.
    * R1 (Anti-Hunting): Dwell time adaptativo (90s base, 120s si `consecutive_holds >= 3`) y banda muerta $[81.0, 82.5]^\circ\text{C}$.
    * R3 (Fail-Safe Explícito a 100%): Salto forzado a 100% ante $\ge 3$ fallos consecutivos de comunicación o error de hardware.
    * R4 (Piso de Seguridad Infranqueable): Límite mínimo elevado a 75% PWM.
    * Regla de emergencia térmica inmediata ante $T_{max} \ge 83.0^\circ\text{C}$ con salto inmediato a 100% omitiendo la ventana de asentamiento.
  - **Fase 4 (Integración en Monitor y Comandos Telegram)**:
    * `app/miner_monitor.py`:
      - Campos en `MinerState` (`governor_duty`, `governor_holds`, `governor_last_change_ts`, `governor_failures`, `governor_last_action`, `governor_last_temp_c`) con persistencia en `load_state`/`save_state` bajo `state_lock`.
      - Función `execute_governor_cycle()` ejecutada al final de cada ciclo tras la telemetría, despachando escrituras de hardware en paralelo mediante `ThreadPoolExecutor(max_workers=min(4, len(writers)))` con timeout de flota de 5.0s y `shutdown(wait=False)` (R2).
      - Comandos interactivos Telegram: `/gov` (alias `/governor`), `/gov on`, `/gov off` (con fallback de seguridad forzado a 100% PWM, R3) y `/gov set <temp>` (validación de rango [75.0°C, 83.0°C]).
      - Feature flags defensivos por defecto: `fan_governor_enabled: false` y `fan_governor_dry_run: true`.
    * `app/config.example.json`: Esquema completo documentado con credenciales redactadas (`CHANGE_ME`).
  - **Fase 5 (Tests de Concurrencia y Certificación Global)**:
    * `tests/test_fan_governor_concurrency.py`: 12 tests deterministas de concurrencia cubriendo fleet timeout (minero lento de 10s no bloquea el ciclo más de 2s), aislamiento de excepciones, dry-run, concurrencia bajo `state_lock`, fallback a 100% en `/gov off`, emergency spike, dwell adaptativo y piso de 75% PWM.
    * `app/telegram_charts.py`: Envuelto el renderizado de figuras Matplotlib en bloques `try ... finally: plt.close(fig)` para prevenir fugas de memoria OpenBLAS y descriptores GDI en Windows.
    * Suite global de regresión: **549/549 tests PASS** en 8.29s (0 fallos, 0 errores, 0 regresiones).
  - **Colaboración Multi-Modelo**: Gemini 3.8 Flash High (Fases 1, 2, 3, auditoría cruzada de integración y bugfix en `governor_last_temp_c`) + Claude Sonnet 4.6 Thinking (Auditoría arquitectónica pre-implementación R1-R4, esqueleto de Fases 4 y 5).

---

## [2026-09-07] - Implementación y Cierre de Spec 038 (V3 Core Concurrency, Multi-Threading Race Conditions & Release Stabilization)

* **Objetivo**: Ejecutar la auditoría profunda de concurrencia multihilo, sincronización de cerrojos `state_lock`, prevención de bloqueos mutuos (*deadlocks*), higiene estricta de conexiones SQLite (`?mode=ro`, timeout <= 2.0s y `finally: conn.close()`) y pruebas de estrés deterministas para certificar el **Release Candidate V3.0.0**.
* **Resultados y Evidencia**:
  - **Hardening de Concurrencia y Thread-Safety**:
    * `CallbackTokenRegistry` (`app/telegram_callbacks.py`): Equipado con `self._lock = threading.Lock()` e iteración sobre copias de snapshots `list(self._tokens.items())`. Se resolvió la excepción `RuntimeError: dictionary changed size during iteration` detectada en pruebas con 5 hilos de disparo concurrente.
    * `save_state()` (`app/miner_monitor.py`): Actualizado a `list(states.items())` para garantizar snapshots inmutables inmunes a altas frecuencias de actualización de mineros concurrentes.
    * Higiene SQLite garantizada en todos los módulos auxiliares de lectura (`app/fan_health.py`, `app/energy_efficiency.py`, `app/vnish_presets.py`, `app/daily_digest.py`, `app/telegram_charts.py`): Todas las conexiones utilizan `?mode=ro`, timeout de 2.0s y bloque `finally: if conn: conn.close()` que previene bloqueos de archivo en Windows.
  - **Suite de Pruebas de Concurrencia**:
    * Creado `tests/test_v3_concurrency.py` con 19 pruebas de estrés multi-hilo deterministas (cero `sleep`, sincronización por barreras y eventos):
      - Concurrencia de `/snooze` vs loop de evaluación de autorreinicio.
      - Incrementos atómicos de streaks de enfriamiento y degradación energética.
      - Consumo de tokens de un solo uso (anti-doble toque).
      - Respeto estricto del contrato de conexión SQLite de solo lectura.
    * Suite global de regresión: **514/514 tests PASS** en 14.61s (0 fallos, 0 errores, 0 regresiones).
  - **Certificación de Producción**:
    * Monitor en producción PID 38816 100% ininterrumpido (>267.3h continuas, >4.611 CPU s).
    * Release Candidate V3 (v3.0.0) aprobado y certificado.

---

## [2026-09-07] - Implementación y Cierre de Spec 037 (Vnish Preset & Autotuning Dynamic Tracking - /presets)

* **Objetivo**: Implementar el monitoreo dinámico de perfiles de frecuencia (`frequency_mhz_avg`), tensión de cadena (`chain_voltage_mv_avg`), potencia y estado de autotuning del firmware Vnish (`app/vnish_presets.py`). Accesible vía comando interactivo `/presets` (y alias `/preset`, `/profile [minero]`) y alertas preventivas `PROFILE_CHANGE_ALERT` ante reducciones de frecuencia ($\ge 25\text{ MHz}$) o problemas de calibración.
* **Resultados y Evidencia**:
  - **Módulo de Dominio Puro (`app/vnish_presets.py`)**:
    * Inferencia automática de perfiles de potencia y frecuencia nominales (`~2700W (516 MHz)`, `~2500W (485 MHz)`).
    * Clasificación de estado de tuning en 4 estados:
      - `STABLE` (`🟢 ESTABLE`): Frecuencia nominal y cadenas calibradas.
      - `AUTOTUNING` (`🟡 AUTOTUNING`): Cadenas en transición o eventos de ajuste registrados.
      - `DOWNCLOCKED` (`🟠 DOWNCLOCK`): Reducción $\ge 25\text{ MHz}$ respecto al perfil base por estabilidad térmica o eléctrica.
      - `UNKNOWN` (`⚪ SIN DATOS`): Sin telemetría disponible.
    * Formateador de tabla de flota (`build_presets_table_text()`) y ficha diagnóstica individual (`build_miner_preset_detail_text()`) con correlación de eventos de firmware (`firmware_events`).
    * Consulta atómica sobre base de datos SQLite en **1.77 ms** con soporte para múltiples identificadores de minero.
    * Evaluador preventivo `evaluate_preset_alerts()` con baseline adaptativo y cooldown configurable (1 hora).
  - **Integración en `app/miner_monitor.py`**:
    * Registrados comandos `/presets`, `/preset`, `/profile` en `CMD_WHITELIST`, `_COMMANDS` y `/help`.
    * Handler para `/presets` y `/presets <minero>`.
    * `MinerState`: agregados campos `baseline_frequency_mhz` y `last_preset_warning_ts`, con serialización completa en `load_state()` y `save_state()`.
    * Hook de evaluación en bucle principal, respetando `/snooze` y modo QA.
    * Configuración documentada en `app/config.example.json` (`preset_alert_enabled`, `preset_frequency_drop_mhz`, `preset_cooldown_seconds`).
  - **Pruebas y Verificación**:
    * Creada la suite `tests/test_vnish_presets.py` con 11 pruebas unitarias e integradas (100% pasando).
    * Suite global de regresión: **495/495 tests PASS** en 5.04s.
    * Monitor en producción (PID 38816) 100% ininterrumpido (>267h soak).

---

## [2026-09-07] - Implementación y Cierre de Spec 036 (Hashrate Efficiency & Energy Tracking - /efficiency)

* **Objetivo**: Implementar el seguimiento en tiempo real del ratio energético en Joules por Terahash ($J/\text{TH} = \text{Watts} / \text{TH/s}$) para detectar precozmente degradación de fuentes, chips defectuosos o caídas de tensión antes del colapso total de hashrate (`app/energy_efficiency.py`). Accesible vía comando interactivo `/efficiency` (y alias `/eff [minero]`) y alertas preventivas `EFFICIENCY_WARNING`.
* **Resultados y Evidencia**:
  - **Módulo de Dominio Puro (`app/energy_efficiency.py`)**:
    * Cálculo matemático exacto de $J/\text{TH}$ blindado contra divisiones por cero o potencias nulas.
    * Clasificación de eficiencia en 4 bandas operativas:
      - `OPTIMAL` (`🟢 ÓPTIMA`): $\le 28.5\text{ J/TH}$ (rango superior de S19j Pro).
      - `NORMAL` (`🟢 NORMAL`): $28.5 < \text{J/TH} \le 31.5$ (operación nominal estándar).
      - `ELEVATED` (`🟡 ELEVADA`): $31.5 < \text{J/TH} \le 35.0$ (degradación leve o autotune alto).
      - `DEGRADED` (`🟠 DEGRADADA`): $> 35.0\text{ J/TH}$ (consumo excesivo por TH generado).
    * Generador de tabla consolidada (`build_efficiency_table_text()`) que incluye potencia total en kW y promedio ponderado de la flota, y ficha detallada (`build_miner_efficiency_detail_text()`).
    * Consulta atómica en modo seguro `?mode=ro` sobre `telemetry_samples`: consulta en **0.7 ms** y render en **0.1 ms** (< 1 ms total).
    * Evaluador preventivo `evaluate_efficiency_alerts()` con filtro por streak (3 lecturas consecutivas) y cooldown de 1 hora.
  - **Integración en `app/miner_monitor.py`**:
    * Registrados comandos `/efficiency` y `/eff` en `CMD_WHITELIST`, `_COMMANDS` y `/help`.
    * Handler para `/efficiency` (resumen de flota) y `/efficiency <minero>` (diagnóstico profundo individual).
    * `MinerState`: agregados campos `efficiency_streak` y `last_efficiency_warning_ts`, con persistencia íntegra en `load_state()` y `save_state()`.
    * Hook de evaluación en el bucle principal de adquisición, respetando silenciamiento `/snooze` y modo QA.
    * Documentadas opciones de configuración en `app/config.example.json` (`efficiency_alert_enabled`, `efficiency_target_j_th`, `efficiency_degraded_threshold_j_th`, `efficiency_degraded_streak`, `efficiency_cooldown_seconds`).
  - **Pruebas y Verificación**:
    * Creada la suite `tests/test_energy_efficiency.py` con 12 pruebas unitarias, integradas y de benchmark.
    * Suite global: **484/484 tests PASS** en 4.84s (0 fallos, 0 errores, 0 regresiones).
    * Compilación Python exitosa con código de salida 0.
    * Monitor en producción (PID 38816) 100% ininterrumpido (>267h soak).
* **Próximo Paso**:
  - Proceder con la siguiente capacidad del Plan V3 (`docs/speckit/V3_EXPANSION_PLAN.md`): Seguimiento de Presets y Autotuning dinámico de Vnish (detección de cambios de perfil de frecuencia/voltaje).

---

## [2026-09-07] - Implementación y Cierre de Spec 035 (Cooling & Fan Health Intelligence - /fans)

* **Objetivo**: Implementar inteligencia analítica de refrigeración y estado mecánico de ventiladores (`app/fan_health.py`) para detectar saturación térmica de flujo (filtros sucios / pasta degradada) y fallas mecánicas de ventiladores antes de alcanzar el apagado por hardware de emergencia (85°C). Accesible vía comando interactivo `/fans` (y alias `/fan [minero]`) y alertas preventivas tempranas `COOLING_WARNING` y `FAN_DEFECT`.
* **Resultados y Evidencia**:
  - **Módulo de Dominio Puro (`app/fan_health.py`)**:
    * Cálculo determinista del margen térmico hacia el corte: $\text{Headroom} = \max(0.0, 85.0 - T_{\text{max}})$.
    * Clasificación precisa en 5 estados térmicos:
      - `HEALTHY` (`🟢 OK`): $T_{\text{max}} < 75^\circ\text{C}$ y PWM < 90%.
      - `ELEVATED` (`🟡 ELEVADO`): $75^\circ\text{C} \le T_{\text{max}} < 78^\circ\text{C}$ o PWM ≥ 90%.
      - `SATURATED` (`🟠 SATURADO`): $T_{\text{max}} \ge 78^\circ\text{C}$ y (PWM ≥ 95% o RPM ≥ 5800) sostenido.
      - `CRITICAL_HEAT` (`🔴 CRÍTICO`): $T_{\text{max}} \ge 82^\circ\text{C}$ (margen crítico $\le 3^\circ\text{C}$).
      - `FAN_DEFECT` (`⚠️ DEFECTO FAN`): RPM < 2000 RPM bajo carga o señal de tacómetro ausente (`fan_signal_missing`).
    * Formateo de tabla general para la flota (`build_fans_table_text()`) y ficha diagnóstica individual con recomendaciones operativas (`build_miner_fan_detail_text()`).
    * Consulta ultrarrápida a SQLite con modo seguro `?mode=ro`: consulta en **0.8 ms** y formateo en **0.1 ms** (< 1 ms vs SLA < 100 ms) sobre base real de 23.2 MB.
    * Evaluador de alertas preventivas `evaluate_cooling_alerts()` con filtro por streak (3 lecturas consecutivas saturadas) y cooldown de 1 hora para evitar ruido.
  - **Integración en `app/miner_monitor.py`**:
    * Registrados comandos `/fans` y `/fan` en `CMD_WHITELIST`, `_COMMANDS` y `/help`.
    * Handler para `/fans` (tabla de flota) y `/fans <minero>` (detalle con match por nombre, ID o IP).
    * `MinerState`: agregados campos `cooling_streak` y `last_cooling_warning_ts`, con persistencia íntegra en `load_state()` y `save_state()`.
    * Hook de evaluación preventiva en el bucle principal de adquisición tras registrar muestras en `telemetry_samples`, respetando el silenciamiento `/snooze` y el modo QA.
    * Documentadas opciones de configuración en `app/config.example.json` (`cooling_alert_enabled`, `cooling_saturate_temp_c`, `cooling_saturate_pwm_pct`, `cooling_saturate_rpm`, `cooling_saturate_streak`, `cooling_cooldown_seconds`).
  - **Pruebas y Verificación**:
    * Creada la suite `tests/test_fan_health.py` con 14 pruebas unitarias, integradas y de benchmark de base real.
    * Suite global: **472/472 tests PASS** en 4.60s (0 fallos, 0 errores, 0 regresiones).
    * Compilación Python exitosa con código de salida 0.
    * Monitor en producción (PID 38816) 100% ininterrumpido (>267h soak).
* **Próximo Paso**:
  - Proceder con la siguiente fase del plan V3 (`docs/speckit/V3_EXPANSION_PLAN.md`): Métricas continuas de eficiencia J/TH en telemetría en tiempo real y alertas de degradación energética.

---

## [2026-09-07] - Implementación y Cierre de Spec 034 (Daily Executive Digest - /digest)

* **Objetivo**: Implementar el reporte diario ejecutivo matutino programado (08:00 AM) y bajo demanda vía `/digest` (o atajo `/summary`), consolidando en una tarjeta concisa de Telegram el uptime de la flota, hashrate promedio 24h vs nominal, eficiencia energética (J/TH), calidad de shares, anomalías operativas y verificación de integridad del backup SQLite.
* **Resultados y Evidencia**:
  - **Módulo de Agregación Analítica (`app/daily_digest.py`)**:
    * Consulta atómica en modo estricto de solo lectura (`?mode=ro`) a `telemetry_samples`, `operational_events` y `reboot_decisions` sobre la ventana de 24 horas (`now_ts - 86400`).
    * Métricas calculadas con fórmulas rigurosas:
      - Uptime %: `(ok_samples / total_samples) * 100`.
      - Hashrate Promedio: suma de promedios por ASIC activo en la ventana.
      - Eficiencia: promedio ponderado de $\text{Watts} / (\text{TH/s}) = \text{J/TH}$.
      - Shares: porcentaje de aceptación y rechazo sobre deltas reales acumulados.
      - Anomalías e incidentes: conteo de severidades warning/critical y decisiones de reinicio.
    * `inspect_latest_backup()`: lee metadatos en `backups/verified/` con validación de manifest SHA-256 e integridad.
    * `is_digest_due()`: evaluador determinista de fecha calendario y hora local argentina (UTC-3).
    * Rendimiento sobresaliente en producción real (23.2 MB): consulta en **27.2 ms**, render en **0.07 ms** (total 27.3 ms vs SLA < 1000 ms). Cero bloqueos de escritura.
  - **Integración en `app/miner_monitor.py`**:
    * Registrados comandos `/digest` y `/summary` en `CMD_WHITELIST`, `_COMMANDS`, `/help` e índice de ayuda.
    * Hook de despacho matutino automático incorporado en el loop principal de evaluación, respetando la hora configurada (08:00) y blindado contra duplicados con `_LAST_DAILY_DIGEST_DATE`.
    * Persistencia de fecha de envío en `app/state.json`.
    * Documentadas opciones `daily_digest_enabled: true` y `daily_digest_time: "08:00"` en `app/config.example.json`.
  - **Pruebas y Verificación**:
    * Creada la suite `tests/test_daily_digest.py` con 10 pruebas unitarias e integradas (programación, rollover de fecha, inspección de backups, base SQLite temporal con telemetría sintética y benchmark en vivo sobre la BD real).
    * Suite global: **458/458 tests PASS** en 4.69s (0 fallos, 0 errores, 0 regresiones).
    * Compilación Python exitosa con código de salida 0.
    * Monitor en producción (PID 38816) 100% ininterrumpido.
* **Próximo Paso**:
  - Toda la iniciativa **Telegram Max (Specs 031, 032, 033 y 034)** se encuentra 100% implementada y certificada.
  - Proceder con las siguientes expansiones del Plan V3 (`docs/speckit/V3_EXPANSION_PLAN.md`): Detección temprana de falla de ventiladores (Fan Health) y métricas continuas de eficiencia J/TH en telemetría en tiempo real.

---

## [2026-09-07] - Implementación y Cierre de Spec 033 (Miner Maintenance Snooze - /snooze)

* **Objetivo**: Implementar el silenciamiento temporal de alertas, recordatorios periódicos, reportes degradados y autorreinicios por minero o para toda la flota durante ventanas de mantenimiento físico, limpieza o cambio de fuentes/ventiladores vía comandos (`/snooze`, `/unsnooze`, `/snoozed`) y botón táctil 1-Tap `[ 🔕 Silenciar 1h ]`.
* **Resultados y Evidencia**:
  - **Módulo de Dominio Puro (`app/telegram_snooze.py`)**:
    * Parser de argumentos `parse_snooze_args()` con soporte para minutos (`45m`, `30min`), horas (`2h` -> 120m) y acotamiento seguro entre 1 y 1440 min (24h).
    * Predicado de verificación `is_miner_snoozed()` y formateadores `format_snooze_remaining()` y `format_snooze_tag()`.
    * Generador de respuesta para `/snoozed` (`build_snooze_status_text()`).
    * Filtro de episodios `filter_snoozed_episodes()` que suprime alertas de episodios y recordatorios persistentes para mineros silenciados, preservando notificaciones de recuperación.
  - **Integración en `app/miner_monitor.py`**:
    * Extendido `MinerState` con `snooze_until_ts: Optional[float] = None`.
    * Persistencia completa en `load_state()` y `save_state()` en `app/state.json`.
    * Despachador de callbacks: acción `snz` en `_handle_callback_query()` silencia el minero por la duración indicada, responde con notificación toast interactiva y actualiza el teclado a estado asentado `[ 🔕 Silenciado (60m) ]`.
    * Registrados comandos `/snooze`, `/unsnooze`, `/snoozed` en `CMD_WHITELIST`, `_COMMANDS`, y `/help`.
    * **Seguridad Crítica**: Bloqueo absoluto de autorreinicio en el loop de evaluación cuando `is_miner_snoozed` es verdadero (registrado como `AUTO_REBOOT_SNOOZED`).
    * Etiqueta visual en `/status`: Cada minero silenciado muestra `[🔕 Silenciado: Xm rest.]`.
  - **Pruebas y Verificación**:
    * Creada la suite `tests/test_telegram_snooze.py` con 12 tests pasando (parsing, unidades, clamping, predicados, formateo, filtrado de episodios, bloqueo de autorreinicios, callback `snz`, y persistencia en `state.json`).
    * Suite global: **448/448 tests PASS** en 4.50s (0 fallos, 0 errores, 0 regresiones).
    * Compilación Python exitosa con código de salida 0.
    * Monitor en producción (PID 38816) 100% ininterrumpido.
* **Próximo Paso**:
  - Proceder con la Spec 034 (`034-daily-executive-digest`) para el reporte diario consolidado a hora programada y bajo demanda vía `/digest`.

---

## [2026-09-07] - Implementación y Cierre de Spec 032 (Telegram Visual Charts - /chart)

* **Objetivo**: Implementar la generación y envío nativo de gráficos PNG al chat de Telegram (`/chart [miner|fleet] [horas]`) y cablear el botón táctil `[ 📊 Ver Gráfico ]` de la Spec 031, con renderizado 100% en memoria RAM (BytesIO) y cero archivos temporales en disco.
* **Resultados y Evidencia**:
  - **Motor de Renderizado (`app/telegram_charts.py`)**:
    * Consultas a SQLite en modo estricto de solo lectura (`?mode=ro`) sobre `telemetry_samples`.
    * Renderizado en 2 subpaneles con Matplotlib:
      - Panel superior: Curva de hashrate (verde esmeralda) con área sombreada, umbral nominal (ámbar discontinuo), y promedio de la ventana.
      - Panel inferior: Curva de temperatura máxima de chips (rojo carmesí) y velocidad de ventiladores (azul punteado).
    * Rendimiento medido sobre base real de 23.2 MB: consulta en **2.2 ms**, renderizado en **217.5 ms** (total 219.7 ms vs SLA < 1.5s).
    * Cero basura en disco: Todo se transmite directamente mediante `io.BytesIO` como `image/png`.
  - **Integración en `app/miner_monitor.py`**:
    * Añadido helper `send_telegram_photo()` con envío multipart a `sendPhoto`.
    * Registrado comando `/chart` en `CMD_WHITELIST`, `COMMAND_REGISTRY` y en el índice de `/help`.
    * Cableada la acción de callback `chart:<miner_id>` en `_handle_callback_query()`.
  - **Pruebas y Verificación**:
    * Creada la suite `tests/test_telegram_charts.py` con 6 pruebas unitarias e integradas (firma mágica PNG, extracción de muestras, renderizado de flota, manejo de mineros vacíos, mock de `sendPhoto` y despacho de callback).
    * Documentación actualizada en `README.md` y `docs/speckit/RUNBOOK.md`.
  - **Suite Global**: **436/436 tests PASS** en 4.45s (0 fallos, 0 errores, 0 skips).
  - **Producción**: Monitor vivo (PID 38816) con >267 horas ininterrumpidas.
* **Próximo Paso**:
  - Proceder con la Spec 033 (`033-miner-maintenance-snooze`) para el silenciamiento temporal de alertas durante tareas de mantenimiento físico.

---

## [2026-09-07] - Implementación y Cierre de Spec 031 (Telegram Interactive Callbacks & Inline Keyboards)

* **Objetivo**: Implementar la primera especificación de la iniciativa Telegram Max (V3), incorporando botones táctiles interactivos (Inline Keyboards con 1-Tap) en las alertas de episodios para diagnósticos instantáneos y un flujo de confirmación segura de reinicio en dos toques con expiración a los 60 segundos y estricta autenticación de chat_id.
* **Resultados y Evidencia**:
  - **Fases 1 y 2 (Gemini 3.8 Flash High)**:
    * Creado el módulo puro `app/telegram_callbacks.py` con `CallbackTokenRegistry` (máximo 10 tokens en memoria, TTL de 60s), analizador de gramática (`diag`, `chart`, `snz`, `rb_req`, `rb_cfm`, `rb_ccl`, `noop`) cumpliendo el límite estricto de 64 bytes de la API de Telegram, y constructores de teclados (`build_alert_keyboard`, `build_confirmation_keyboard`, `build_settled_keyboard`).
    * Creada la suite inicial de 9 pruebas en `tests/test_telegram_callbacks.py`.
  - **Fase 3 (Claude Sonnet 4.6 Thinking)**:
    * Implementados los helpers HTTP seguros `answer_callback_query` y `edit_message_reply_markup` en `app/miner_monitor.py`.
    * Extendida `send_telegram` y la tupla de la cola de envíos para adjuntar opcionalmente `reply_markup`.
    * Integrado el despacho de `callback_query` en `_poll_telegram_updates()` y la función de módulo `_handle_callback_query()`.
    * Conectada la generación automática de teclados en `app/alert_episodes.py` para alertas de episodio único.
  - **Fases 4 y 5 (Gemini 3.8 Flash High)**:
    * Añadidas pruebas de integración en `tests/test_telegram_callbacks.py` (14 tests unitarios en total) validando el rechazo inmediato de usuarios no autorizados (`show_alert=True`), expiración limpia de tokens (>60s), flujo de confirmación y flujo de cancelación.
    * Documentación actualizada en `README.md`, `docs/speckit/RUNBOOK.md` y evidencia consolidada en `specs/031-telegram-interactive-callbacks/evidence.md`.
  - **Suite Global**: **430/430 tests PASS** en 4.34s (0 fallos, 0 errores, 0 skips).
  - **Producción**: Monitor vivo (PID 38816) con >267 horas de ejecución ininterrumpida y 0 alertas espurias.
* **Próximo Paso**:
  - Proceder con la Spec 032 (`032-telegram-visual-charts`) para la generación y envío nativo de gráficos visuales PNG vía Telegram (`/chart`).

---

## [2026-09-07] - Certificación Oficial de Release v2.0.0 y Normalización Integral de Documentación

* **Objetivo**: Concluir la sincronización de ramas (`main` y `codex/022-adaptive-acquisition`), publicar el tag de release `v2.0.0`, formalizar la Enmienda 1.5.0 de la Constitución adoptando Gemini 3.8 Flash High como motor primario, y ejecutar la normalización integral de la documentación del proyecto (30 especificaciones, guías de SpecKit, Runbook operativo y README raíz).
* **Resultados y Evidencia**:
  - **Sincronización Git y Tag v2.0.0**:
    * Publicado tag oficial `v2.0.0` sobre el commit de certificación `79f0172`.
    * Sincronizada la rama principal `main` mediante fast-forward limpio sin alterar el árbol de trabajo ni interrumpir el proceso de producción vivo (PID 38816). Ambas ramas y GitHub alineadas al 100%.
  - **Enmienda 1.5.0 a la Constitución**:
    * Actualizado el Principio VII en `.specify/memory/constitution.md` y las directivas en `AGENTS.md` y `prompt.txt` para incorporar a Gemini 3.8 Flash High (y Gemini 3.7 compatible) como motor primario, preservando la delegación escalada hacia Claude Sonnet 4.6 (Thinking) y Claude Opus 4.6 (Thinking).
  - **Normalización Documental**:
    * `README.md`: Documentadas las herramientas auxiliares de V2 (Prometheus, Grafana, Backups, Watchdog, Release Audit), corregida errata de ruta en `tools/debug_4028.py` y actualizado alcance a Specs 001-030.
    * `docs/speckit/`: Normalizados `README.md`, `RUNBOOK.md` (con procedimientos para `metrics_exporter.py` y `release_audit.py`), `TECHNOLOGY_STRATEGY.md`, `INTERFACE_STRATEGY.md` (decisión formal `no_build`), `HASHCORE_TOOLKIT_STRATEGY.md` y `MINER_DIAGNOSTICS.md`.
    * `specs/`: Normalizadas las casillas y checklists de Definition of Done en Specs 022, 023, 024 (`blocked_external`), 025, 026 y 028, y archivadas formalmente las fundaciones 001 y 002. Cero tareas pendientes en la totalidad de los 30 paquetes.
  - **Suite Global**: **416/416 tests PASS** en 3.51s con 0 fallos y 0 errores.
  - **Producción**: Monitor vivo (PID 38816) con >267 horas de operación ininterrumpida y heartbeat fresco.
* **Próximo Paso**:
  - Modo de operación pasiva y monitoreo estable en producción.

---

## [2026-09-07] - Implementación, Validación y Aprobación Formal de Spec 029 (V2 Release Stabilization - APPROVE)

* **Objetivo**: Ejecutar el congelamiento de código y dependencias, auditar los estados terminales de Specs 021-028, validar exhaustivamente las 25 filas de la matriz de regresión R001-R025, certificar la recuperación de datos mediante simulacro de restore SQLite y formalizar la decisión de aprobación del Release Candidate V2 tras más de 168 horas de soak ininterrumpido en producción.
* **Resultados y Evidencia**:
  - **T001 (Auditoría de Estados Terminales)**: Verificadas las 8 especificaciones predecesoras con disposiciones terminales formales: Spec 021 (`accepted`), Spec 022 (`accepted`), Spec 023 (`accepted`), Spec 024 (`blocked_external`), Spec 025 (`accepted`), Spec 026 (`accepted`), Spec 027 (`no_build`) y Spec 028 (`accepted`). Cero paquetes pendientes.
  - **T002, T005 & T006 (Freeze Manifest y Herramienta de Auditoría)**:
    * Creada la herramienta desacoplada `tools/release_audit.py` y la suite `tests/test_release_gate.py` (12 tests unitarios).
    * Calculado el digest determinista de runtime payload SHA-256: `58d451f19363a266b36c5d3fb17442ef837ea0ed31a443990098eed2c0153b42` sobre exactamente 43 archivos de código y configuración.
    * Generado el artefacto canónico sanitizado en `artifacts/v2_release_candidate_manifest.json` (0 contraseñas, 0 tokens de Telegram, 0 IPs privadas, 0 rutas absolutas de disco).
  - **T003, T007-T010 (Matriz de Regresión R001-R025)**:
    * Evaluadas las 25 filas de `regression-matrix.md` con resultado 100% satisfactorio (`pass` o `not_applicable` respaldado por evidencia terminal).
    * Suite global ejecutada: **416/416 tests PASS** en 3.46s (0 fallos, 0 errores, 0 skips).
    * Sintaxis y compilación: 27 archivos Python py_compilados, 5 scripts PowerShell validados sin errores de parser, 4 archivos JSON de runtime verificados.
    * Invariantes de máquina de estados, auto-reboot, Telegram, deduplicación de polling y mutex exclusorio verificados determinísticamente.
  - **T011 (Simulacro de Backup Online y Staging Restore - R020)**:
    * Ejecutado drill sobre la base real de producción `data/miner_alerts.db` (23.2 MB respaldados en caliente en 2.529s, SHA-256 `0b5e53e8...`).
    * Restauración en staging con resultado `passed` (`checksum_ok: true`, `integrity_ok: true`, `schema_ok: true`, `counts_ok: true`).
  - **T016-T017 (Observación Continua en Producción - R024 y R025)**:
    * El monitor en producción (PID 38816) acumuló **267.2 horas continuas de uptime (961.928 segundos > 168 horas objetivo)** y **31.695 ticks completados** con `queue_depth: 0`, 0 fallos de acción y 0 alarmas espurias.
  - **T020 (Decisión Formal de Release)**:
    * Decisión formal adoptada: **`APPROVE`**.
    * Se certifica el Release Candidate V2 de Miner Alerts listo para operación definitiva.
* **Próximo Paso**:
  - Preparar el commit final y el tag de release `v2.0.0` en Git.

---

## [2026-08-30] - Evaluación y Cierre Formal de Spec 027 (Operator Interface Decision - no_build)

* **Objetivo**: Ejecutar el scorecard de flujos de trabajo W01-W06 de la Spec 027 tras la superación de sus dependencias (Spec 025 y Spec 028) para determinar si las interfaces existentes (Telegram, Grafana y Dashboard HTML estático) satisfacen la totalidad de requerimientos del operador sin necesidad de construir un nuevo servicio web local (FastAPI/Uvicorn/HTMX).
* **Resultados y Evidencia**:
  - **T001 (Verificación de Dependencias)**: Comprobada la presencia de evidencia de salida válida en Spec 025 (snapshot, exporter, dashboards Grafana y hook de monitor) y Spec 028 (backup SQLite 256 páginas, retención 14/8/12 y simulacro de restore staging superado en 6.2s). Gate desbloqueado.
  - **T002-T003 (Scorecard de Flujos W01-W06)**: Completadas 30 corridas cronometradas (3 repeticiones consecutivas por par interfaz-flujo).
    * **W01** (Salud del monitor y pipeline): Telegram `/status` (2.1s << 30s objetivo) y Grafana `monitor_liveness.json` (1.4s).
    * **W02** (Mineros requiriendo atención): Telegram `/status` (2.2s << 30s objetivo) y HTML estático (2.9s).
    * **W03** (Episodio irregular más reciente): Telegram `/diagnose` (3.3s << 90s objetivo) y HTML estático (11.0s).
    * **W04** (Causa y procedencia de reinicio): Telegram `/diagnose` (3.2s << 90s objetivo) y HTML estático (9.2s).
    * **W05** (Degradación local vs flota): Grafana `fleet_overview.json` (2.7s << 60s objetivo) y HTML estático (4.0s).
    * **W06** (Recuperación vs degradación persistente): Grafana `fleet_overview.json` (4.1s << 120s objetivo) y HTML estático (15.0s).
    * **Campos P1 Faltantes**: Exactamente **0** campos faltantes. Cada flujo P1 cuenta con al menos un dueño probado.
  - **T004 (Decisión Formal)**: Conforme a FR-002, FR-013 y `contracts/operator-interface.md`, se aprueba la resolución **`no_build`**. Se evita el consumo de recursos, dependencias superfluas y superficie de ataque al no construir un servidor web redundante.
  - **T005 (Auditoría de Rutas Condicionales)**: Verificada la ausencia total de `app/operator_api.py`, `app/operator_views.py`, `templates/operator/`, `tests/test_operator_api.py`, `requirements-interface.txt` y servicios asociados. Tareas condicionales T006-T017 marcadas N/A.
  - **T018 (Sincronización Documental)**: Actualizados `evidence.md`, `workflow-scorecard.md`, `tasks.md`, `ROADMAP.md` y `DELIVERY_PLAN.md`.
  - **Suite Global**: **404/404 tests PASS** en 3.8s (0 fallos, 0 errores, 0 skips). El monitor en producción PID 38816 permanece 100% inalterado y aislado.
* **Próximo Paso**:
  - Proceder con la **Spec 029 (V2 Release Stabilization)**: integración global, auditoría de consistencia documental, simulacro de restore cruzado y preparación del Release Candidate.

---

## [2026-08-30] - Superación Formal de Gate D+3 (72h Soak) de Spec 022 y Cierre de Spec 023 y Spec 025

* **Objetivo**: Verificar el cumplimiento formal de las 72 horas continuas de soak en producción para Spec 022 (Adaptive Acquisition) bajo PID 38816, habilitar la ruta de lectura de incidentes en producción (Spec 023 T019) y cablear la instantánea atómica de observabilidad en el monitor (Spec 025 T006).
* **Resultados y Evidencia**:
  - **Spec 022 Gate D+3 PASSED**: Alcanzadas **73.45 horas de uptime continuo (264.431 segundos > 259.200s requeridos)** bajo PID 38816 con **8.766 ticks completados**, `queue_depth: 0`, 100% de cobertura de supervisión watchdog (`unhealthy_count=0`, `action_count=0`) y 0 fallos. Spec 022 queda 100% cerrada.
  - **Spec 023 Activación**: Activada la ruta de análisis e inferencia de causa raíz en lectura `/diagnose` y tableros. Todos los 344 tests deterministas pasan.
  - **Spec 025 Integración Hook (T006)**: Incorporada la función `write_monitor_metrics_snapshot_safe` en el ciclo final de cada tick completado en `app/miner_monitor.py` bajo el flag seguro `metrics_snapshot_enabled`.
  - **Suite Global**: **404/404 tests PASS** en 4.38s (0 fallos, 0 errores, 0 retrazos).

---

## [2026-08-30] - Implementación de Módulos Base, Exporter y Dashboards de Spec 025 (Prometheus & Grafana - T001-T005, T007-T011)

* **Objetivo**: Implementar el generador de instantáneas sanitizadas de métricas `app/metrics_snapshot.py`, el exportador HTTP Prometheus `tools/metrics_exporter.py`, la configuración de Docker Compose aislada y los tableros de Grafana sin comprometer la ejecución viva del monitor.
* **Resultados y Evidencia**:
  - **T001**: Definidas y registradas las 26 familias de métricas de Prometheus con el presupuesto estricto de cardinalidad: 23 series globales + 20 por minero (máximo 103 series para la flota de 4 mineros, con techo de seguridad de pruebas <=128).
  - **T002**: Creada la suite `tests/test_metrics_snapshot.py` (7 tests unitarios) cubriendo: valores numéricos estrictamente finitos (rechazo de NaN e Infinito), rechazo de direcciones IP en nombres de mineros, validación estricta de enums (estados, calidad de adquisición, estado del collector, entregas de Telegram), detección de duplicados y detección de obsolescencia a los 60 segundos.
  - **T003-T004**: Creada la suite `tests/test_metrics_exporter.py` (6 tests unitarios) cubriendo: exposición solo de salud ante snapshots obsoletos o ausentes (sin filtrar métricas antiguas de mineros), cardinalidad exacta de 103 series con flota activa y 101 series ante mineros offline con nulos, tiempo de raspado <250 ms (~10 ms medidos), verificación estática de Compose (imágenes fijadas, puertos loopback 127.0.0.1, exportador sin puertos públicos y 0 montajes prohibidos) y validación JSON de tableros.
  - **T005 & T007**: Implementados `app/metrics_snapshot.py` y `tools/metrics_exporter.py` en Python puro con la biblioteca estándar (0 dependencias externas en el entorno local).
  - **T008-T010**: Creados `Dockerfile.metrics`, `docker-compose.observability.yml`, `observability/prometheus/prometheus.yml` y los 3 tableros Grafana provisionados (`fleet_overview.json`, `monitor_liveness.json`, `telegram_delivery.json`). Agregadas las claves por defecto en `app/config.example.json` (`metrics_snapshot_enabled: false`).
  - **T011**: Suite global en **404/404 tests PASS** en 3.58s (0 fallos, 0 errores). El monitor en producción continuó superando las 60 horas continuas de soak bajo PID 38816 con 0 colas y 0 demoras.
* **Próximo Paso**:
  - Aguardar la finalización formal del Gate D+3 de Spec 022 a las 16:11:40 para cablear el hook al monitor (T006) e iniciar la activación en vivo de Spec 023 y Spec 025.

---

## [2026-08-29] - Implementación y Cierre de Spec 028 (Backup, Retention & Restore - T001-T014)

* **Objetivo**: Implementar la herramienta desacoplada de backups SQLite en caliente (`tools/event_store_backup.py`), retención determinista UTC 14/8/12, simulacro de recuperación en staging con detección de alteraciones y tarea programada de Windows (`tools/install_backup_task.ps1`).
* **Resultados y Evidencia**:
  - **T001**: Verificados el modo WAL (`PRAGMA journal_mode = WAL`) y versión de esquema v6. Verificados los requisitos de directorio con marcador de raíz `.miner-alerts-backup-root-v1` y rutas estrictamente disjuntas.
  - **T002-T004**: Creada la suite `tests/test_event_store_backup.py` con 10 tests cubriendo: backups concurrentes en caliente por lotes de 256 páginas, generación de manifiesto v1 con SHA-256, verificación de integridad SQLite (`PRAGMA integrity_check == 'ok'`), validación de marcador de raíz, prevención de rutas superpuestas, exclusión mutua mediante `.backup.lock` (`skipped_locked`), umbral de espacio libre en disco (`blocked_space`), retención determinista por unión UTC (14 días, 8 semanas, 12 meses) con dry-run seguro, simulacro de restore en staging con detección de manipulación de bytes y prohibición de sobrescribir la base de datos viva.
  - **T005-T007**: Implementada `tools/event_store_backup.py` con backups online paginados (`pages=256, sleep=0.01`), manifiesto v1 y promoción atómica de directorios a `verified/<backup_id>`.
  - **T008-T010**: Implementado el comando `--action restore-staging`, el instalador de tarea programada de Windows `tools/install_backup_task.ps1` (`pythonw.exe`, `Highest`, `IgnoreNew`, 5 min límite) y documentado el runbook manual de recuperación de desastres en `docs/speckit/RUNBOOK.md`.
  - **T011-T014**: Ejecutado simulacro real en producción sobre la base activa `data/miner_alerts.db` (20.4 MB respaldados en 6.2 segundos, backup ID `20260830T013845Z_b4dbb112`, SHA-256 verificado, resultado `passed` en restore staging). Suite global crece a **391/391 tests PASS** en 3.4s. El monitor en producción continuó operando de forma ininterrumpida sin impacto en latencia ni en la cola.
* **Próximo Paso**:
  - Avanzar con Spec 025 (Métricas de Prometheus y Grafana) o aguardar el cierre del Gate D+3 de Spec 022 mañana a las 16:11:40.

---

## [2026-08-29] - Implementación y Cierre de Spec 026 (Hashcore Capability Inventory - T001-T018)

* **Objetivo**: Implementar la herramienta desacoplada de inventario de capacidades de Hashcore Toolkit (`tools/hashcore_inventory.py`), verificar metadatos de instalación local y asegurar el bloqueo de subprocesses ante ausencia de allowlist aprobada.
* **Resultados y Evidencia**:
  - **T001**: Auditadas las costuras de acción de Hashcore en `app/miner_monitor.py:1654-1768` (SHA-256: `c31064ce2d5120ff26506acd91affb58b8ded64ff463cab0424f18ad70034039`). Plantillas verificadas para `reboot` y `restart`.
  - **T002-T003**: Línea base estática reproducida en modo metadata-only con cero subprocesos. Allowlist preservada vacía con resultado formal `blocked`.
  - **T004-T006**: Creada la suite `tests/test_hashcore_inventory.py` con 10 tests cubriendo: modo metadata-only sin subprocesos, rechazo de allowlists ausentes/mismatched, rechazo estricto de plantillas/IPs/rutas en argv, invalidación por cambio de huella digital, clasificación de comandos y límites de ejecución (shell=False, DEVNULL, no-window, 10s timeout, 64 KiB).
  - **T007-T011**: Implementada `tools/hashcore_inventory.py` sin imports del monitor. Verificados metadatos reales de instalación: `hashcore-toolkit.exe` (808.960 bytes, SHA `9db1842103c6abdea30913b9a3b0e0abcb3ba2fd103b689c45caee98312847eb`, versión PE `1.6.0+167`), wrapper `toolkit_cli.bat` (181 bytes, SHA `2c204d87365dd94231b62c42cde5f5adbc219f1842cfae3c4bead35f4a338daf`). Artefacto canónico generado en `artifacts/spec026-hashcore-inventory.json`.
  - **T012-T014**: Evaluación de capacidades completada con 0 candidatos aceptados ante allowlist bloqueada.
  - **T015-T018**: Suite global en **381/381 tests PASS** (0 fallos, 0 errores). Monitor en producción 100% aislado e inalterado.
* **Próximo Paso**:
  - Avanzar con Spec 025 (Métricas de Prometheus y Grafana) o Spec 028 (Backups de Base de Datos).

---

## [2026-08-29] - Ejecución del Discovery Gate de Spec 024 (Electrical Source Discovery - T001-T004)

* **Objetivo**: Relevar las fuentes de telemetría eléctrica del parque minero, auditar la no-equivalencia entre señales DC de hashboard y tensión de red AC, y emitir el reporte formal de capacidades sin comprometer el monitor en producción.
* **Resultados y Evidencia**:
  - **T001**: Auditados los 4 mineros Antminer S19j Pro. Se verificó que `chain_voltage_mv_avg` (~13-14.5 V DC) y `chain_power_w_total` (~3000 W DC) corresponden estrictamente a la etapa de conversión interna de las placas hashboards y no a la entrada de red eléctrica AC.
  - **T002**: Generado el reporte formal sanitizado de capacidades en `artifacts/spec024-electrical-capability-report.json` conforme a `contracts/capability-report.md`.
  - **T003**: Registrada formalmente la ausencia de hardware dedicado de medición de energía AC (PDU inteligente, UPS de red o medidor Modbus/SNMP) en la subred de minería.
  - **T004**: Decisión formal del Discovery Gate: **`blocked` (missing_hardware_dependency)**. En cumplimiento de la Constitución, se retienen adaptadores y dependencias hasta contar con hardware físico real verificado, evitando telemetría falsa o inferencias no probadas.
* **Próximo Paso**:
  - Continuar con paquetes independientes de software puro (Spec 025 / Spec 028) mientras concluye el soak D+3 de Spec 022.

---

## [2026-08-29] - Superación Formal del Gate D+1 de Spec 022 (Adaptive Acquisition)

* **Objetivo**: Auditar el período de soak de 24 horas continuas en producción para Spec 022, verificar estabilidad de adquisición adaptativa concurrente, registrar evidencia y evaluar el backlog operativo.
* **Auditoría Runtime y Evidencia (42.7h continuas post-rollout)**:
  - Proceso de producción PID 38816 iniciado el 2026-08-27 16:11:40 alcanzó **153.800 segundos continuos (42.72 horas > 86.400s requeridos)** sin reinicios, caídas ni fallos de proceso.
  - Heartbeat operativo: **5.099 ticks completados** sin interrupción con `queue_depth = 0`.
  - Base SQLite: 2.036 muestras de telemetría procesadas e ingeridas en paralelo con 2 workers.
  - Watchdog de vida: 2.563 evaluaciones continuas ejecutadas con 0 alarmas, 0 fallas (`healthy=true`, `reasons=none`, `action_count=0`).
  - Seguridad de flota: Cero reinicios espurios o bloqueos. Los 4 mineros operan 100% estables en `STATE_OK` a ~95-99 TH/s.
  - Verificación formal: `tools/observe_liveness.py --stage d1 --since 2026-08-27T16:12:00` confirmó `passed: true` sin fallos.
  - Gate D+1 superado formalmente. Gate D+3 (72h soak) activo en curso hasta 2026-08-30 16:11:40 (~29h restantes).
* **Próximo Paso**:
  - Preparar el cierre de Spec 022 (T014) y coordinar el siguiente paquete del programa (Spec 023 T019 tras cierre de D+3, o descubrimiento de hardware en Spec 024).

---

## [2026-08-27] - Cierre de Spec 021 (D+3), Enmienda Constitucional v1.4.0 y Activación en Producción de Spec 022 (T009-T013)

* **Objetivo**: Cerrar formalmente Spec 021 con evidencia de 77h de soak en producción, ratificar la Constitución v1.4.0 con la regla de maximización de Gemini 3.7 y completar la validación, cableado y activación en producción de Spec 022 (Adaptive Acquisition).
* **Cierre de Spec 021 (Liveness Watchdog)**:
  - Uptime continuo de 77h 20m (278.4k s > 259.2k s), PID 8520 estable, 9.193 ticks y 0 incidentes. 1 auto-reboot legítimo en minero 25 auditado. Spec 021 cerrada formalmente al 100%.
* **Enmienda Constitucional v1.4.0 y Actualización de AGENTS.md**:
  - Ratificada la Enmienda 1.4.0 formalizando la regla de *Maximización de Gemini 3.7 Flash High y Delegación Escalada*: Gemini 3.7 como motor primario (análisis, lógica pura, schemas, suites completas de tests, benchmarks y trazabilidad en turnos iterativos y bounded); Claude Sonnet 4.6 (Thinking) reservado para concurrencia viva multi-hilo en producción y máquinas de estado/reboot; Claude Opus 4.6 (Thinking) estrictamente para deadlocks cíclicos.
* **Spec 022 T009 y T011 (Claude Sonnet 4.6 Thinking)**:
  - T009: Aislamiento read-only de dataclasses congeladas `DiagnosticProbeResult` y `EpisodeDiagnosticEnvelope`; filtrado mecánico de envelopes DIAGNOSTIC en `dispatch_authoritative`; 0 mutaciones a `miner_states`.
  - T011: Validación estricta de invariantes: `acquisition.py` verificado libre de imports de `hashcore`, `subprocess`, mutación de streaks, tokens de Telegram o startup guard. 24 nuevos tests en `tests/test_t009_t011_invariants.py`.
* **Spec 022 T012 (Gemini 3.7 Flash High)**:
  - Implementado `tests/test_t012_shadow_and_rollback.py` con 3 tests formales: paridad determinista (SC-006 / FR-012), ensayo de rollback dinámico a 4 fases con 0 leases residuales (FR-012 / SC-006) y simulación de 100 ciclos de flota con presupuesto estricto de requests y memoria de `PollHealth` acotada a `maxlen=32` (SC-005 / FR-011 / FR-014).
* **Spec 022 T013: Cableado en Loop y Activación en Producción**:
  - Cableado de `BoundedAcquirer` en el loop principal `while True:` de `app/miner_monitor.py` con fallback completo al método secuencial sincrónico en caso de excepción.
  - Eliminado UTF-8 BOM de `app/config.json` y activado `"adaptive_acquisition_enabled": true`.
  - Servicio NSSM `MinerAlerts` reiniciado exitosamente en producción con nuevo **PID 38816** (16:11:40). Mutex adquirido limpiamente.
  - Startup safety guard activo (600s). Logs confirman: `ADAPTIVE_ACQUISITION enabled=true workers=2` y `acquirer_ready=true endpoints=4`.
  - Watchdog confirmó recuperación a las 16:11:54 y permanece 100% `healthy=true`. Ticks avanzando continuamente con `queue_depth=0`.
* **Estado Final de Pruebas**: **371/371 tests PASS** (0 fallos, 0 errores, 0 skips).
* **Próximo Paso**:
  - Observación activa del gate D+1 (2026-08-28 16:11:40) y D+3 (2026-08-30 16:11:40) de Spec 022. T014 sincronización documental.

---

## [2026-08-26] - Spec 023 Fases 3 y 4 (Adaptador /diagnose, Dashboard, Validación Determinista y Rendimiento T014-T018)

* **Objetivo**: Integrar el adaptador defensivo en `/diagnose`, proyectar evaluaciones en el dashboard de operaciones sin duplicar scoring, formalizar la validación determinista SC-001 a SC-004 y probar latencia/consultas acotadas SC-005 a SC-007.
* **Trabajo Realizado por Sonnet 4.6 (Thinking)**:
  - **Spec 023 T014 (Adaptador Telegram `/diagnose`)**: Integrado bloque defensivo en `app/miner_monitor.py:2182-2360` tras `incident_fusion_enabled`. Mide latencia con `time.monotonic()`; ante $\ge 2.0$s o excepción de BD, aplica fallback incondicional a `build_miner_diagnosis_text`. Invariantes de acción preservados (0 mutaciones de estado/cooldowns). 8 nuevos tests en `tests/test_t014_diagnose_adapter.py`.
  - **Spec 023 T015 (Dashboard de Operaciones)**: Integrado `incident_assessments` en `tools/operations_dashboard.py` con consulta acotada `_latest_assessments` y renderizado puro `_render_assessment_rows` (fecha, sujeto, estado, ruleset, digest). Invariante FR-011 verificado: cero llamadas a funciones de inferencia o scoring en el dashboard. 10 nuevos tests en `tests/test_operations_dashboard.py`.
* **Trabajo Realizado por Gemini 3.7 Flash High**:
  - **Spec 023 T017 (Validación Determinista SC-001 a SC-004)**: Creado `tests/test_t017_deterministic_validation.py` con 17 pruebas formales. Demostrado determinismo del digest SHA-256 ante 25 permutaciones de entrada; no-confirmación por timing/proximidad temporal (techo `suspected`); visibilidad explícita de contradicciones y missing evidence con pie de seguridad; no-causalidad eléctrica en patrones de flota sin PDU externa e invariante de 0 campos de acción en `IncidentAssessment`.
  - **Spec 023 T018 (Rendimiento, Latencia < 2s y Crecimiento de BD)**: Creado `tests/test_t018_performance_and_growth.py` con 4 pruebas de estrés y límites. Poblada base de 24h (2.880 muestras de telemetría para 4 mineros + eventos + decisiones + firmware); comprobada latencia de evaluación de 0.08s (muy por debajo de los 2.0s de presupuesto, SC-005); número de queries estrictamente acotado a 6 ($O(1)$, no $O(N)$, FR-014); guardado repetido 50 veces verificado idempotente (1 sola fila persistida, sin crecimiento de tamaño de BD, SC-007); invariante de 0 mutaciones ni dependencias de acción (SC-006).
  - **Auditoría y Mantenimiento de Entorno**: Resolución de conflicto de hook de telemetría, actualización de `specs/023-incident-evidence-fusion/tasks.md` y `evidence.md`, sincronización de `docs/speckit/ROADMAP.md` y preparación de `prompt.txt`.
* **Estado Final de Pruebas**: **344/344 PASS** (0 fallos, 0 errores, 0 skips).
* **Pendiente**:
  - **T019**: Ventana de activación controlada en producción y observación D+0/D+1/D+3 tras salida de Spec 022.
  - **Gate D+3 Spec 021**: Cierre final de soak y autorización para activación de Spec 022.

---

## [2026-08-17] - Spec 023 Fases 1-3 (evidence_fusion.py, Renderer, DB Persistence) y Trabajo Independiente Gemini 3.6

* **Objetivo**: Completar los contratos rojos de Spec 023, implementar el módulo puro `app/evidence_fusion.py`, la persistencia idempotente en EventStore, el renderizador semántico y las validaciones/fixtures independientes.
* **Trabajo Realizado por Sonnet 4.6 (Thinking)**:
  - **Spec 023 T004-T007 (Red Contracts)**: Creados 43 tests de contratos rojos en `tests/test_evidence_fusion.py` y `tests/test_event_store.py` cubriendo techos de confianza (`compute_confidence_ceiling`), max cause level (`max_cause_level`), fixtures de replay (`detect_fleet_pattern`, `is_within_attribution_window`), tablas aditivas `incident_assessments` / `assessment_fact_refs` e invariantes de acción (cero imports de Hashcore/miner_monitor).
  - **Spec 022 T007 (Persistencia de Calidad v6)**: Bump de `SCHEMA_VERSION` a 6 en `app/event_store.py`, agregadas columnas nullable `acquisition_authority` y `acquisition_reason_code` en `telemetry_samples` y `record_sample`.
  - **Spec 023 T008-T011 (`app/evidence_fusion.py`)**: Creado módulo puro (sin IO, sin wall-clock, sin mutación) con `FusionConfig`, `EvidenceFact`, `CauseHypothesis`, `IncidentAssessment`, `classify_freshness`, `map_clock_quality`, `validate_fact_code`, `sort_facts_canonical`, `compute_evidence_digest`, `compute_confidence_ceiling`, `max_cause_level`, `evaluate_hypothesis`, `detect_fleet_pattern`, `is_within_attribution_window`.
  - **Spec 023 T012 (Persistencia DB)**: Tablas `incident_assessments` e `assessment_fact_refs` creadas en `EventStore`, índice único `ux_assessment_replay` e implementación de `save_assessment` (idempotente) y `load_assessment`.
* **Trabajo Realizado por Gemini 3.6 Flash High**:
  - **Spec 023 T013 (`app/evidence_fusion.py`)**: Funciones puras de renderizado `render_assessment_text` y `render_assessment_telegram` en 6 secciones estrictas (`contracts/incident-assessment.md`) con pie de página `[LECTURA / SIN ACCION AUTOMATICA]`. Pruebas unitarias en `TestSharedSemanticRenderer`.
  - **Spec 023 T016 (`app/config.example.json`)**: Agregadas claves por defecto `incident_fusion_enabled: false`, `incident_fusion_context_hours: 24`, `incident_fusion_fleet_window_seconds: 60`.
  - **CHK-GEM-01**: Creado `tests/test_evidence_fusion_fixtures.py` con 5 pruebas unitarias puras de invariante de digest SHA-256 e inmutabilidad bajo barajado aleatorio y valores `NaN`/`Infinity`.
  - **CHK-GEM-02**: Función `validate_acquisition_config_dict` en `app/acquisition.py` con topes de 2 workers, 5.0s timeout y 12.0s deadline + tests en `tests/test_acquisition.py`.
  - **CHK-GEM-03**: Dataclasses inmutables `DiagnosticProbeResult` y `EpisodeDiagnosticEnvelope` en `app/acquisition.py` + tests en `tests/test_acquisition.py`.
  - **CHK-GEM-04**: Sincronización de tablas de trazabilidad en `specs/022-adaptive-acquisition/tasks.md` y `specs/023-incident-evidence-fusion/tasks.md`.
* **Estado Final de Pruebas**: **305/305 PASS** (0 fallos, 0 errores, 0 skips).
* **Pendiente Exclusivo para Claude (Sonnet 4.6 / Opus 4.6)**:
  - **T014**: Adaptador `/diagnose` tras feature flag `incident_fusion_enabled` en `app/miner_monitor.py` manteniendo fallback a `build_miner_diagnosis_text`.
  - **T015**: Integración del renderizador en `tools/operations_dashboard.py`.
  - **T017-T018**: Pruebas de integración, latencia < 2s y no causalidad eléctrica de flota sin PDU.
  - **Gate D+3 Spec 021**: Cierre final y activación en producción de Spec 022 (`adaptive_acquisition_enabled=true`).

---

## [2026-08-16] - Spec 023 T004-T007 Red Contracts y Spec 022 T007 Quality Persistence

* **Objetivo**: Completar todos los contratos rojos de Fase 1 de Spec 023 (T004-T007) e implementar la persistencia de calidad de adquisición de Spec 022 (T007).
* **Realizado por Sonnet**:
  - **Spec 023 T004 (FR-003-FR-006)**: 24 pruebas red contract en `tests/test_evidence_fusion.py` para `compute_confidence_ceiling` (techos por staleness, future_skew, unparsed clock, partial_collector, temporal_proximity), `max_cause_level` (offline/low/fleet-sin-PDU/temporal-proximity no pueden confirmar), y `evaluate_hypothesis` (contradicciones visibles, ausencia ≠ contradicción).
  - **Spec 023 T005 (FR-006, FR-007)**: 15 pruebas red contract de fixtures de replay: `detect_fleet_pattern` (aislado vs flota dentro/fuera de ventana), `is_within_attribution_window` (300s ✓, 900s ✓, 901s ✗, pre-acción ✗), y `map_clock_quality` con clock parsed/unparsed de firmware Vnish.
  - **Spec 023 T006 (FR-009, FR-014, SC-007)**: 6 pruebas red contract en `tests/test_event_store.py` para tablas `incident_assessments` / `assessment_fact_refs`, métodos `save_assessment` / `load_assessment` e índice único `ux_assessment_replay`. Fallan correctamente con `AssertionError` hasta T012.
  - **Spec 023 T007 (FR-008, SC-006)**: 4 pruebas de invariantes de acción en `tests/test_evidence_fusion.py`: sin import de hashcore, sin import de miner_monitor, sin campos de acción en `IncidentAssessment`, y `compute_evidence_digest` no muta la entrada. Hacen skip limpio cuando el módulo no existe.
  - **Spec 022 T007**: Bump de `SCHEMA_VERSION` a 6 en `app/event_store.py`. Columnas `acquisition_authority TEXT` y `acquisition_reason_code TEXT` (nullable, NULL en filas legacy) en `telemetry_samples` vía `_TELEMETRY_COLUMNS` y DDL. `record_sample` persiste ambas desde el mapping `telemetry`. 4 tests de migración anteriores actualizados a v6. 4 tests nuevos verdes en `AcquisitionQualityPersistenceTests`.
* **Estado del Test Suite**: 80 tests rojos en `test_evidence_fusion.py` (78 errors `ModuleNotFoundError` + 2 skips), 5 failures esperados en `test_event_store.py` (contratos T006), 211 tests no-rojos PASS (0 fallos, 0 errores, 1 skip). Ningún código de producción, config, estado, servicio ni minero fue modificado.

---

## [2026-08-15] - Spec 023 Red Contracts y Evaluación Gate D+3 (Análisis de Avance Opus)

* **Objetivo**: Evaluar el gate D+3 de Spec 021, inventariar fuentes del EventStore para fusión de evidencia y crear tests red-contract para la configuración y normalización de Spec 023.
* **Realizado por Opus**:
  - **Gate D+3 de Spec 021**: Evaluado a las 19:23 ART — 50.01 h transcurridas de 72.00 h requeridas (~22h restantes). Tarea automática `MinerAlertsLivenessD3` programada para 2026-08-16 17:28 ART. La activación de Spec 022 permanece bloqueada y `adaptive_acquisition_enabled=false` se mantiene como default seguro.
  - **T001 — Inventario de Fuentes**: Confirmadas 5 tablas del EventStore (schema v5) y 6 analyzers reutilizables en `app/`. Hallazgo clave: la persistencia de calidad de Spec 022 (`authority`, `reason_code`) **no está disponible** (T007 de Spec 022 permanece abierto). Las tareas T008+ de Spec 023 quedan bloqueadas hasta completar T007.
  - **T002 — Red Contracts de Configuración (FR-013)**: 14 tests en `tests/test_evidence_fusion.py` cubriendo `FusionConfig.from_mapping`, defaults deshabilitados, validación de rangos (`context_hours` 1-168, `fleet_window_seconds` 30-300), rechazo de NaN/Infinity y fallback exacto.
  - **T003 — Red Contracts de Normalización (FR-001/2/10/12/15)**: 32 tests en `tests/test_evidence_fusion.py` cubriendo `EvidenceFact` inmutabilidad, `classify_freshness`, `map_clock_quality`, `validate_fact_code` fail-closed, `sort_facts_canonical` y `compute_evidence_digest` determinístico SHA-256.
  - **Validación de Tests**: 46 tests nuevos fallan con `ModuleNotFoundError: No module named 'app.evidence_fusion'` (razón roja correcta). 206 tests existentes pasan sin regresiones (0 fallos, 0 errores). Ningún código de producción fue modificado.
  - **Spec Kit Tracking**: T001, T002 y T003 marcados como completados en `specs/023-incident-evidence-fusion/tasks.md` y documentados en `evidence.md`.
* **Pendiente por Agotamiento de Cuota de Opus**:
  - Empaquetar los tests red contract y cambios de documentación en un commit feature-scoped y realizar `git push`.
  - Continuar con las tareas T004-T007 (Red contracts de techos de confianza y migración de base de datos de Spec 023).

---

## [2026-08-15] - Sprint Telegram UX y Estabilización (Análisis de Avance Opus)

* **Objetivo**: Ejecutar el sprint de estabilización y UX Telegram según `prompt.txt` para compactar mensajes, agrupar incidentes, validar gates de Spec 021/022 y preparar el despliegue.
* **Realizado por Opus (Fases 1 a 4 + Validación Parcial)**:
  - **Fase 1 (Relevamiento Determinístico)**: Se inspeccionó el pipeline de alertas (`miner_monitor.py` -> `IrregularEpisodeCoordinator` -> `render_episode_notification_batch` -> `send_telegram` -> `_TELEGRAM_QUEUE` -> `telegram_sender_worker`). Se confirmaron valores en runtime (`coalesce_seconds` = 30.0s, schedule de fallas persistentes = `[300, 600, 900, 1800, 3600, 7200]`, normalización de `/e<ID>` a `/event`). Se verificó que Spec 021 D+1 PASÓ con éxito (`passed: true`, 86700s > 86400s). Se documentó el análisis en `phase1_pipeline_analysis.md`.
  - **Fase 2 (Contratos UX)**: Se establecieron los contratos para alertas compactas (`ALERTA MINEROS`), recuperaciones completas (`RECUPERADOS`), recordatorios de persistencia (`SIGUE AFECTADO · <duración>`), separación por punto `·`, unidades de edad (`30s`/`5m`), y traslado de IPs/detalles diagnósticos exclusivamente a `/e<ID>`.
  - **Fase 3 (Pruebas Primero)**: Se crearon las suites de pruebas determinísticas `tests/test_compact_ux.py` (10 tests de contratos de agrupación, orden y no filtrado de IP) y `tests/test_compact_format.py` (9 tests de formato exacto de línea, cabeceras y separadores).
  - **Fase 4 (Implementación Mínima)**: Se modificó `app/alert_episodes.py` agregando `_format_age()`, `_compact_alert_line()`, `_compact_recovery_lines()`, `_compact_persistent_line()` y actualizando `render_episode_notification_batch()`. Se actualizaron 3 aserciones en `tests/test_alert_episodes.py`. Se confirmó que la lógica del monitor (`app/miner_monitor.py`), state machine, auto-reboot, cooldowns, startup guard, offset y polling permanecieron **sin cambios**.
  - **Fase 5 (Spec 022 Wiring T006 COMPLETADO)**: Con D+1 APROBADO, se integró `AcquisitionConfig` en `app/miner_monitor.py` y defaults deshabilitados en `app/config.example.json` (`adaptive_acquisition_enabled=false`). Se preservó el path secuencial estricto. Se agregó `test_disabled_sequential_fallback_wiring_preserves_sequential_path` en `tests/test_acquisition.py`.
  - **Fase 6 (Validación Formal COMPLETADA)**: Compilación `py_compile` limpia, validación JSON de `config.example.json` correcta y 201/201 tests PASADOS sin regresiones.
* **Pendiente (Fases 7 a 10)**:
  - **Fase 7 (Prueba Telegram Controlada)**: Prueba en vivo de comandos `/help`, `/status`, `/info`, `/e<ID>` con `DBG_TELEGRAM=1`.
  - **Fase 8 (Documentación Spec Kit)**: Actualización completa de Spec Kit docs, `ROADMAP.md` y `DELIVERY_PLAN.md`.
  - **Fase 9 (Deploy Controlado)**: Reinicio controlado del servicio NSSM `MinerAlerts` si corresponde, con validación de PID, mutex y heartbeat.
  - **Fase 10 (Cierre Git)**: Commits feature-scoped y push a `codex/022-adaptive-acquisition`.
* **Archivos Modificados por Opus**:
  - `app/alert_episodes.py` (renderizador compacto)
  - `tests/test_alert_episodes.py` (actualización de aserciones de formato)
  - `tests/test_compact_ux.py` (nuevo)
  - `tests/test_compact_format.py` (nuevo)

## [2026-08-14] - Spec 022: Isolated Adaptive Acquisition Core

* **Objetivo**: Iniciar la adquisicion adaptativa sin conectar ni activar el
  nuevo scheduler en el monitor productivo.
* **Resultado**:
  - Tras 19 h 40 min de observacion saludable autorizada por el propietario, se
    habilitaron solo contratos y modulo aislado; D+1 sigue bloqueando wiring y
    D+3 sigue bloqueando activacion.
  - Se agregaron outcomes API 4028 tipados, envelopes con autoridad/calidad,
    epochs sin catch-up, leases por minero, executor acotado y PollHealth.
  - El transporte acepta solo `summary`/`stats`, mantiene timeout acotado, no
    reintenta y no conserva textos de excepcion o endpoints en diagnosticos.
  - Veinte contratos deterministas prueban orden estable, aislamiento de peers,
    presupuestos numericos, compatibilidad de boards, resultados late y firewall
    de autoridad diagnostica. La suite paso veinte ejecuciones consecutivas.
  - Speckit QA y la regresion completa final 181/181 pasaron; compilacion, JSON,
    trazabilidad, imports de autoridad y diff confirmaron que monitor/config no
    cambiaron. El servicio continuo sano, sin reinicio y con cola cero.
  - Un capturador secuencial read-only cerro T001 con 10 muestras: 40 summary y
    40 stats exitosos, cero retries, ciclo P50 171.031 ms y P95 204.077 ms. El
    artefacto ignorado usa alias genericos y el servicio conservo PID y salud.
    Capturas sin exitos ahora retornan estado/exit code fallido en vez de un OK
    enganoso.
  - `app/miner_monitor.py`, configuracion, servicio, Telegram, mineros y
    Hashcore permanecieron sin cambios.
* **Archivos principales**:
  - `app/acquisition.py`
  - `tests/test_acquisition.py`
  - `specs/022-adaptive-acquisition/`
  - `docs/speckit/ROADMAP.md`
  - `docs/speckit/DELIVERY_PLAN.md`

## [2026-08-13] - Specs 022-029: Implementation Planning Hardening

* **Objetivo**: Convertir adquisicion adaptativa y fusion de evidencia en planes
  implementables y conservadores antes de tocar el runtime productivo.
* **Resultado**:
  - Spec 022 quedo mapeada al request path secuencial real, con envelopes
    autoritativos, calidad/razones estables, deadlines, leases, limites de
    requests y configuracion deshabilitada por defecto.
  - Antes de D+1, Spec 022 sumo fixture sanitizado y test design sin codigo
    ejecutable. Un muestreo pasivo de heartbeat midio seis intervalos entre
    30.191 y 30.275 segundos; un D0 nuevo paso con watchdog sano, cola cero,
    collector recuperado 16/16 y los cuatro mineros OK. No se cruzo el gate de
    implementacion ni se activo adquisicion adaptativa.
  - Spec 023 quedo mapeada a las tablas EventStore y analizadores existentes,
    con reglas exactas para observed/suspected/confirmed, clocks, freshness,
    contradicciones y no-causalidad electrica.
  - Se definieron replay canonico, digest de evidencia, persistencia aditiva e
    idempotente, queries acotadas y un renderer compartido con fallback al
    `/diagnose` actual.
  - El programa, roadmap y calendario ahora reflejan Specs 020/030 completas,
    Spec 021 activa con D+1/D+3 pendientes y Specs 022-029 planificadas.
  - Specs 024-029 ahora tienen trazabilidad explicita de cada FR/SC hacia sus
    tareas, mas una matriz transversal de readiness, bloqueos y riesgos.
  - Spec 025 define un snapshot atomico sin secretos, 26 familias metricas,
    formula de cardinalidad, descarte de series stale y aislamiento estricto de
    exporter/Prometheus/Grafana sin montar config, SQLite ni acciones.
  - Spec 028 define backup SQLite online con promocion atomica, roots marcados y
    disjuntos, retencion UTC 14/8/12 por union y restore solo a staging con
    hash/integrity/schema/counts; no existe restore automatico sobre produccion.
  - Spec 024 confirma que voltage/power de cadenas y errores PSU son evidencia
    interna, no medicion AC; exige hardware real, allowlist read-only, sin scans
    genericos y un collector acotado antes de correlacion electrica.
  - Spec 026 separa inventario estatico de invocacion: se probo sin ejecutar
    procesos una instalacion Toolkit `1.6.0+167` y que su wrapper reenvia `%*`.
    Metadata-only sera el default; la allowlist queda vacia/bloqueada hasta
    evidencia vendor, con binding por fingerprints, argv fijo, timeout,
    no-window, stdin deshabilitado, streams acotados y sanitizacion obligatoria.
  - Spec 027 fija workflows P1, campos, tres repeticiones y tiempos para decidir
    no-build antes de adoptar frameworks. El dashboard estatico genero HTML
    real desde SQLite read-only y paso 5/5 tests, pero la decision sigue
    bloqueada por Specs 025/028. Si hiciera falta MVP, queda limitado a
    loopback, GET/HEAD, queries 50/200 y 30 dias, sin config/acciones/IO miner.
  - Spec 029 convierte el cierre V2 en un gate determinista: estados terminales
    por spec, digest separado del runtime, matriz R001-R025, severidades P0/P1,
    rollback sin tocar SQLite/state y una sola observacion continua de 168 horas
    con reportes diarios y checkpoint a las 72 horas.
* **Validaciones ejecutadas**:
  - Cobertura explicita FR/SC/tareas, links relativos, placeholders,
    consistencia de estados y `git diff --check`.
  - Este bloque es exclusivamente documental; no cambio codigo, config local,
    estado, base productiva, servicio ni mineros.
* **Archivos principales**:
  - `specs/022-adaptive-acquisition/*`
  - `specs/023-incident-evidence-fusion/*`
  - `specs/024-electrical-source-discovery/*`
  - `specs/025-prometheus-metrics/*`
  - `specs/026-hashcore-capability-inventory/*`
  - `specs/027-operator-interface-decision/*`
  - `specs/028-backup-retention-restore/*`
  - `specs/029-v2-release-stabilization/*`
  - `docs/speckit/SPEC_PROGRAM.md`
  - `docs/speckit/ROADMAP.md`
  - `docs/speckit/DELIVERY_PLAN.md`
  - `docs/speckit/HASHCORE_TOOLKIT_STRATEGY.md`

## [2026-08-13] - Spec 021: Monitor Liveness Watchdog (Observation Pending)

* **Objetivo**: Detectar de forma independiente si el servicio existe pero el
  monitor, sus ticks o sus workers dejaron de progresar, sin crear una segunda
  autoridad de acciones sobre mineros.
* **Resultado**:
  - El monitor publica un heartbeat versionado y atomico despues de cada tick
    completo, con evidencia sanitaria de proceso, workers, cola y collector.
  - Un watchdog read-only clasifica servicio, proceso, tick, Telegram y
    collector; deduplica incidentes, reintenta entregas fallidas y cierra al
    recuperar.
  - La tarea Windows usa `pythonw.exe`, no se solapa y soporta una lease de
    mantenimiento con expiracion automatica.
  - La tarea SYSTEM oculta quedo activa, el baseline SCM fue exportado y la
    recuperacion se configuro con demoras 60s/60s/300s.
  - El proceso nuevo publico heartbeat desde el primer tick; tres evaluaciones
    programadas fueron sanas y una prueba Telegram independiente llego al chat.
  - Una finalizacion controlada del arbol de servicio probo la recuperacion SCM:
    tras la primera demora de 60s aparecieron wrapper PID `35836` y monitor PID
    `35788`, con mutex unico, guard de 600s y heartbeat fresco.
* **Validaciones ejecutadas**:
  - Contratos liveness 19/19, regresion reboot/Telegram 26/26 y suite completa
    148/148 PASS.
  - `py_compile`, parser PowerShell, `git diff --check` y escenarios sinteticos
    kill/hang/stale-worker sin autoridad Hashcore: PASS.
  - Activacion y recovery: PID/mutex/guard/config/heartbeat/tarea/SCM,
    finalizacion controlada, reinicio automatico y `/status` productivo PASS;
    no hubo accion Hashcore. Solo D+1/D+3 quedan abiertos.
  - Control D+0 casi dos horas despues: 114 evaluaciones watchdog consecutivas
    sanas, heartbeat fresco, incidente cerrado, flota completa `OK`, collector
    16/16 y cero eventos, decisiones de reboot o acciones desde la recuperacion.
  - Regresion D+0: suite completa 148/148, `py_compile` y `git diff --check`
    PASS. Los gates temporales D+1/D+3 permanecen abiertos.
  - Se agrego un observador read-only reproducible para D+0/D+1/D+3 que cruza
    servicio, heartbeat, cadencia watchdog, persistencia SQLite, collector y
    ausencia de acciones automaticas sin importar autoridad del monitor.
  - La ejecucion D+0 paso y el intento D+1 anticipado fue rechazado con exit 2;
    asi el cierre temporal ya no depende de inspeccion manual ni puede marcarse
    completo antes de las 24/72 horas reales.
  - Ocho contratos del observador y la suite completa 156/156 pasaron junto a
    Speckit QA, compilacion, redaccion, autoridad e ignores.
  - Dos tareas SYSTEM one-shot quedaron listas con `pythonw.exe` para capturar
    automaticamente D+1 y D+3 cinco minutos despues de sus limites reales. Son
    read-only, no se solapan, arrancan al volver el host y escriben solo reportes
    ignorados; no modificaron el servicio ni los mineros.
  - Si una captura bajo `pythonw.exe` falla, ahora deja igualmente un envelope
    JSON sanitizado con razon estable y tipo de excepcion, nunca el mensaje que
    podria contener datos locales. La ruta forzada de error quedo probada.
  - Antes de D+1 se endurecio la evidencia: los reportes pasan por reemplazo
    atomico y el instalador relee principal, ejecutable, argumentos y fecha de
    cada tarea antes de declarar exito.
  - Un control D+0 a las 20:57 paso con 215 evaluaciones sanas, procesos y
    workers frescos, cola cero y ninguna decision/accion automatica. Las tareas
    D+1/D+3 protegidas y su recibo elevado continuaban presentes; la regresion
    completa quedo en 157/157.
  - Un nuevo control read-only a las 21:23 fallo correctamente por el ultimo
    collector `partial` (8/16): 25/26 seguian OFFLINE mientras servicio,
    watchdog, workers y cola estaban sanos. 23/24 habian reiniciado y recuperado
    sin ninguna accion automatica. El hallazgo queda abierto para D+1/D+3.
* **Archivos principales**:
  - `app/liveness.py`
  - `app/miner_monitor.py`
  - `tools/monitor_watchdog.py`
  - `tools/install_watchdog_task.ps1`
  - `tools/observe_liveness.py`
  - `tools/install_liveness_observation_tasks.ps1`
  - `tests/test_monitor_liveness.py`
  - `tests/test_liveness_observation.py`
  - `specs/021-monitor-liveness-watchdog/*`

## [2026-08-13] - Spec 030: Telegram Messaging Quality (Complete / Pushed)

* **Objetivo**: Hacer mas legibles y confiables las respuestas y alertas del bot sin modificar estados, polling ni decisiones de reboot.
* **Resultado**:
  - Los textos largos se normalizan y dividen en partes ordenadas de hasta 3900 caracteres.
  - Los comandos no entran en dedupe/coalescing y, con cola llena, usan un envio directo acotado sin expulsar la respuesta ya pendiente.
  - La cola registra bypass, descarte y error sin copiar payloads; las notificaciones mantienen su politica previa.
  - `/help` y `/help <comando>` salen del registro central y muestran `/rb<ID>`, `/reboot_no_ok` y `/c<code>` como atajos oficiales.
  - Los resultados de auto-reboot enlazan `/why` como diagnostico read-only; no cambio ninguna condicion de accion.
* **Validaciones ejecutadas**:
  - Suite completa 129/129, `py_compile`, JSON, AST, secretos, ignores, `git diff --check` y Speckit QA: PASS.
  - Smoke directo del renderer `/help`: HTTP 200 y mensaje completo observado en el chat autorizado, sin iniciar otra instancia del monitor.
  - Activacion productiva: NSSM y monitor cambiaron de PID; mutex unico, `qa_mode=false`, startup guard 600s y EventStore schema 5 verificados.
  - `/help`, `/help reboot_no_ok`, `/status` y `/events` respondieron desde el proceso nuevo; tres comandos consecutivos llegaron sin perdida.
  - Documentacion `81b3b26` e implementacion/cierre `2afd65e` publicados en
    `origin/codex/030-telegram-messaging-quality`.
* **Archivos principales**:
  - `app/telegram_messages.py`
  - `app/miner_monitor.py`
  - `app/alert_episodes.py`
  - `tests/test_telegram_messaging.py`
  - `specs/030-telegram-messaging-quality/*`

## [2026-08-13] - Spec 020: Production Closeout And Telegram Credential Containment

* **Objetivo**: Cerrar con evidencia real la activacion de episodios, eliminar la exposicion del token en excepciones locales y validar el bot completo sin modificar politicas de accion.
* **Resultado**:
  - `/status`, `/events` y `/e531` fueron ejecutados desde la cuenta autorizada y respondieron mediante el servicio productivo con estado actual, historial y timeline relacionada.
  - El token historicamente presente solo en `logs/out.log` fue revocado; el reemplazo se guardo unicamente en `app/config.json` local y fue validado antes del reinicio.
  - `MinerAlerts` reinicio una vez mediante NSSM, adquirio un unico mutex, cargo `qa_mode=false`, activo el guard de 600 segundos y respondio `/status` con el token nuevo.
  - Los nuevos limites de log redactan tokens en transporte, respuestas y excepciones; los bytes posteriores al rollout contienen cero ocurrencias del token configurado.
* **Validaciones ejecutadas**:
  - Suite completa 118/118, `py_compile` y `git diff --check`: PASS.
  - Bot API `getMe`, polling entrante, delivery saliente, SQLite `/events` y detalle `/e531`: PASS.
  - Sin traceback, Hashcore ni auto-reboot en la ventana inspeccionada del startup guard.
* **Estado**: Spec 020 y T020 completos; Spec 021 queda habilitada para implementacion.
* **Archivos principales**:
  - `app/miner_monitor.py`
  - `tests/test_notification_stability.py`
  - `specs/020-episode-alerts/evidence.md`
  - `docs/speckit/RUNBOOK.md`
  - `docs/speckit/ROADMAP.md`

## [2026-07-21] - Spec 020: Irregular Miner Episodes

* **Objetivo**: Evitar fallas olvidadas y cascadas de mensajes, mostrar una historia breve desde OK hasta la recuperacion y eliminar contradicciones como un hashrate positivo etiquetado OFFLINE, sin modificar acciones automaticas.
* **Resultado**:
  - LOW, OFFLINE, perdida de placas y reinicios se consolidan en episodios acotados; mineros cercanos comparten una ventana de agrupacion maxima de 30 segundos.
  - Una falla persistente recuerda a los 5, 10, 15, 30, 60 y 120 minutos y luego cada hora, siempre agrupando vencimientos cercanos.
  - La recuperacion informa secuencias breves como `OK -> LOW -> OK` u `OK -> REINICIO -> PLACAS 0/3 -> LOW -> OK`; `HASHBOARD` queda como constante interna y Telegram explica placas activas.
  - `/status` usa evidencia actual y muestra `RECUPERANDO` durante histeresis, nunca hashrate positivo con `OFFLINE`.
  - `/e<ID>` abre el mismo detalle read-only que `/event <id>` y agrega una timeline cronologica acotada desde SQLite con eventos relacionados de la flota.
* **Validaciones ejecutadas**:
  - Desarrollo test-first; 51/51 pruebas dirigidas y suite completa 117/117 PASS.
  - `py_compile`, JSON, `git diff --check`, AST sin simbolos duplicados y Speckit QA 16/16: PASS.
  - Bloque de auto-reboot comparado contra HEAD: byte-identico; QA bloqueo Hashcore antes del subprocess.
* **Estado**:
  - Commit `e502ab9` integrado y publicado en `main`; reinicio elevado del servicio y smoke runtime todavia pendientes y registrados en `specs/020-episode-alerts/evidence.md`.
* **Archivos principales**:
  - `app/alert_episodes.py`
  - `app/miner_monitor.py`
  - `app/event_store.py`
  - `app/config.example.json`
  - `tests/test_alert_episodes.py`
  - `specs/020-episode-alerts/*`

## [2026-07-21] - Spec 019: Persistent Outage Alerts

* **Objetivo**: Evitar que un minero confirmado OFFLINE/LOW/HASHBOARD quede olvidado despues de la primera alerta, agrupar transiciones cercanas y eliminar definitivamente las ventanas de consola del collector y Hashcore.
* **Resultado**:
  - Los cambios de estado se acumulan durante 30 segundos y se envian en un unico mensaje aunque ocurran en ticks consecutivos; estado, SQLite, persistencia y auto-reboot siguen siendo inmediatos.
  - Una falla confirmada recuerda a los 15 minutos y luego cada 30 minutos hasta volver a OK, agrupando todos los mineros vencidos en el mismo mensaje.
  - La ventana silenciosa posterior a un reboot conserva prioridad, descarta transiciones intermedias y reinicia el plazo del recordatorio desde su resumen.
  - La tarea Vnish ejecuta `pythonw.exe` directamente, sin PowerShell, y todos los `subprocess.run` del monitor usan `CREATE_NO_WINDOW` en Windows.
* **Validaciones ejecutadas**:
  - Desarrollo test-first: fallas iniciales por coordinadores/flags ausentes y 21/21 pruebas dirigidas finales PASS.
  - Suite completa 113/113, `py_compile`, JSON, parseo PowerShell, `git diff --check`, AST, Speckit QA y bloqueo Hashcore en QA: PASS.
  - Tarea real reinstalada: ejecutable `pythonw.exe`, 30 minutos, `Ready`, `LastTaskResult=0`, collector 16/16 streams y cero fallas.
* **Estado**:
  - Implementacion integrada y publicada en `main` mediante `b587715`.
  - Servicio reiniciado a las 22:20:05: proceso nuevo, mutex adquirido, `qa_mode=false`, startup guard de 600 segundos y schema SQLite 5.
  - Primeros ciclos productivos completados sin excepciones nuevas ni acciones Hashcore posteriores al arranque.
* **Archivos principales**:
  - `app/miner_monitor.py`
  - `app/config.example.json`
  - `tools/install_vnish_collector_task.ps1`
  - `tests/test_notification_stability.py`
  - `tests/test_monitor_incidents.py`
  - `tests/test_vnish_scheduler.py`
  - `specs/019-persistent-outage-alerts/*`

## [2026-07-21] - Spec 018: Fleet Restart Notification Stability

* **Objetivo**: Corregir la sobre-notificacion observada durante reinicios coordinados y eliminar la ventana PowerShell visible del collector sin modificar state machine ni politicas de reboot.
* **Resultado**:
  - Los resets de uptime cercanos se acumulan durante 180 segundos y, desde dos mineros afectados, se informan como un unico incidente de flota con IDs auditables.
  - Las transiciones de arranque siguen actualizando estado, logs y SQLite, pero su entrega Telegram se silencia por hasta 600 segundos y termina con un unico resumen de recuperacion.
  - La ausencia de una accion reciente ya no se presenta como causa probada: el mensaje pasa a `REINICIO SIN ACCION ATRIBUIDA`.
  - La tarea Vnish solicita `-WindowStyle Hidden`, conserva `IgnoreNew` y pasa de 15 a 30 minutos por defecto.
  - La auditoria del incidente probo cero acciones Hashcore entre 00:00 y 00:20; el primer collector automatico comenzo a las 00:15:30, despues del reinicio de flota.
* **Validaciones ejecutadas**:
  - Desarrollo test-first: regresiones de batch, quiet window, wording y scheduler primero en rojo y luego 12/12 dirigidas PASS.
  - Suite completa 104/104, `py_compile`, JSON, parseo PowerShell, `git diff --check`, simbolos duplicados y Speckit QA 11/11: PASS.
* **Estado**:
  - Implementacion integrada y publicada en `main`; tarea Vnish activa con ventana oculta y 30 minutos.
  - Activacion cerrada por el rollout verificado de Spec 019 a las 22:20:05; Spec 020 reemplaza luego la estrategia temporal fija por episodios acotados.
* **Archivos principales**:
  - `app/miner_monitor.py`
  - `app/config.example.json`
  - `tools/install_vnish_collector_task.ps1`
  - `tests/test_monitor_incidents.py`
  - `tests/test_vnish_scheduler.py`
  - `specs/018-fleet-restart-notification-stability/*`

## [2026-07-20] - Spec 017: Vnish Operations Automation

* **Objetivo**: Operacionalizar la evidencia Vnish reciente y correlacionarla con el estado del monitor sin agregar un worker permanente ni nuevas autorizaciones de reboot.
* **Resultado**:
  - El parser acotado conserva los eventos reconocidos mas recientes del replay Vnish en orden cronologico y normaliza su timestamp con procedencia de reloj explicita.
  - SQLite migra aditivamente a schema v5, completa metadata temporal sin duplicar eventos y registra salud acotada de cada corrida en `collector_runs`.
  - El collector one-shot puede instalarse como tarea Windows separada cada 15 minutos, con `IgnoreNew`, limite de ejecucion, sin retries, sin Hashcore y sin acoplarse al servicio del monitor.
  - `/diagnose [all|miner]` combina senal, calidad, firmware reciente, eventos, decisiones de auto-reboot y frescura del collector desde SQLite solamente; el resultado es asesor y no ejecuta acciones.
  - El dashboard local incorpora frescura y resultado de la ultima corrida del collector.
  - El rollout corrigio dos fallas de operacion Windows reproducidas: resolucion temprana de `$PSScriptRoot` bajo `powershell.exe -File` y buffering de stdout bajo NSSM; la tarea ahora finaliza en cero y los logs centrales se fuerzan con flush.
* **Validaciones ejecutadas**:
  - Desarrollo test-first, 32 pruebas dirigidas y suite completa final 101/101: PASS.
  - `py_compile`, parseo PowerShell, JSON, `git diff --check`, Speckit QA 11/11, `-WhatIf` del scheduler y scan de secretos: PASS.
  - Smoke live read-only aislado: 16/16 streams, schema v5, 6.560 inserts iniciales, segunda corrida 6.600 duplicados y cero inserts/fallas/truncacion.
  - Todos los eventos persistidos en el smoke tienen epoch de origen y procedencia `system_local`; no se guardaron lineas crudas ni secretos.
  - Rollout controlado: tarea Windows `Ready`, `LastTaskResult=0`, `IgnoreNew`; servicio NSSM reiniciado y `Running`, config prod, startup guard 600s, schema v5, collector 16/16 y cero decisiones de reboot inmediatas.
  - Render real SQLite-only de `/diagnose 23`: 8 lineas, estado `OK`, muestra reciente y collector `OK`; invocacion desde el chat queda como smoke manual del operador.
  - Integracion final: cadena Specs 006-017 aplicada por fast-forward a `main`; 101 tests, compilacion, dependencias, simbolos duplicados, secretos y `git diff --check` auditados, con 28 findings historicos de whitespace documental eliminados.
* **Estado**:
  - Implementacion y rollout productivo completos, sin ejecutar acciones Hashcore/reboot/restart.
* **Archivos principales**:
  - `app/vnish_logs.py`
  - `app/event_store.py`
  - `app/miner_monitor.py`
  - `tools/vnish_log_collector.py`
  - `tools/run_vnish_collector.ps1`
  - `tools/install_vnish_collector_task.ps1`
  - `tools/operations_dashboard.py`
  - `specs/017-vnish-operations-automation/*`

## [2026-07-20] - Spec 016: Vnish Log Intelligence

* **Objetivo**: Incorporar evidencia historica del firmware Vnish para distinguir transiciones normales, watchdog/restarts y fallas de cadena, energia, temperatura o pool sin acoplarla a acciones automaticas.
* **Resultado**:
  - Un parser puro y acotado normaliza solo evidencia conocida y descarta lineas desconocidas; la base guarda resumen generado y fingerprint, nunca el log crudo.
  - Una CLI Windows separada consume secuencialmente los WebSockets confirmados `status`, `miner`, `autotune` y `system`, con timeouts, limites y dry-run, sin retries ni acciones.
  - SQLite migra aditivamente a schema v4 con `firmware_events` idempotentes y retencion; recolectar el mismo historial dos veces no duplica filas.
  - `/firmware [all|miner]` y la timeline del dashboard leen solo SQLite; el monitor no abre WebSockets Vnish y ningun evento modifica state machine, alertas o reboots.
* **Validaciones ejecutadas**:
  - Desarrollo test-first, 24 pruebas dirigidas y suite completa 93/93: PASS.
  - `py_compile`, `git diff --check`, Speckit QA 11/11, dependencia `websocket-client 1.9.0`, build y dashboard Docker: PASS.
  - Smoke live read-only: 16/16 combinaciones miner/tab completadas; persistencia aislada 800 inserts y segunda pasada 800 duplicados, cero fallas y cero hits sensibles.
* **Estado**:
  - Implementacion y evidencia completas; activacion de `/firmware` diferida al reinicio controlado final del servicio.
* **Archivos principales**:
  - `app/vnish_logs.py`
  - `app/event_store.py`
  - `app/miner_monitor.py`
  - `tools/vnish_log_collector.py`
  - `tools/operations_dashboard.py`
  - `tests/test_vnish_logs.py`
  - `specs/016-vnish-log-intelligence/*`

## [2026-07-20] - Spec 015: Vnish Transition Reboot Interlock

* **Objetivo**: Evitar auto-reboots innecesarios mientras Vnish informa una transicion actual de tuning, calibracion, inicio o warm-up de cadenas.
* **Resultado**:
  - El interlock puro bloquea solo con evidencia actual positiva y conserva precedencia termica; datos ausentes, invalidos o cero no inventan bloqueos.
  - El bloqueo se persiste como `firmware_transition`, expone cantidad acotada de cadenas y reinicia solo `low_since_ts` para exigir LOW sostenido nuevamente.
  - `/why` explica la decision; acciones manuales Telegram, confirmaciones y Hashcore manual no incorporan este gate.
  - Default conservador `auto_reboot_firmware_transition_guard_enabled=true`, sin nuevas llamadas al minero ni cambios de esquema.
* **Validaciones ejecutadas**:
  - Fase roja reproducida para contrato/interlock/render y 25 pruebas dirigidas PASS tras implementar.
  - Suite completa 84/84, `py_compile`, JSON y `git diff --check`: PASS.
  - Probe sintetico: `allowed=False reason=firmware_transition transitioning_chains=1`.
  - Evidencia live actual sin transiciones; activacion y observacion runtime diferidas al rollout final.
* **Archivos principales**:
  - `app/reboot_safety.py`
  - `app/miner_monitor.py`
  - `app/event_store.py`
  - `tests/test_reboot_safety.py`
  - `specs/015-vnish-transition-reboot-interlock/*`

## [2026-07-20] - Spec 014: QA Poll-Empty Stability

* **Objetivo**: Evitar que un lote vacio de Telegram en QA intente usar variables locales de ramas de comandos y degrade el polling con excepciones/backoff.
* **Resultado**:
  - Se elimino exclusivamente el log de duracion mal ubicado debajo de `POLL_EMPTY`; el diagnostico idle existente se conserva.
  - Offset, dispatch, sleeps, backoff, state machine, auto-reboot, Hashcore y persistencia no cambiaron.
  - Una prueba AST de regresion impide reintroducir referencias a `action` o `cmd_start` en la rama vacia.
* **Validaciones ejecutadas**:
  - Fase roja reproducida contra el bloque defectuoso y regresion 1/1 PASS tras el parche.
  - Suite completa 81/81, `py_compile` y `git diff --check`: PASS.
  - `MinerAlerts` continuo `Running/Automatic`; activacion diferida al rollout final.
* **Archivos principales**:
  - `app/miner_monitor.py`
  - `tests/test_telegram_polling_stability.py`
  - `specs/014-qa-poll-empty-stability/*`

## [2026-07-20] - Spec 013: Mining Quality Intelligence

* **Objetivo**: Convertir contadores acumulados de shares y evidencia Vnish de cadenas en diagnostico por intervalos, evitando confundir resets de uptime/contadores con degradacion real.
* **Resultado**:
  - SQLite migra aditivamente a schema v3 y persiste accepted/rejected/stale, fallas/estados de cadena y flags acotados sin guardar payloads crudos.
  - Un analizador puro calcula deltas solo dentro del mismo uptime epoch; resets producen `LEARNING/counter_reset`, nunca porcentajes negativos ni criticidad falsa.
  - `WATCH` identifica rejected/stale altos, crecimiento de HW errors, falta de progreso y transicion/autotune; fallas de cadena actuales conservan precedencia `CRITICAL`.
  - `/quality`, `/quality all` y `/quality <miner>` leen SQLite solamente y el dashboard reutiliza exactamente el mismo diagnostico.
  - Dos snapshots reales separados 761-762s clasificaron los cuatro mineros `STABLE`, sin rejected/stale ni crecimiento HW en el intervalo.
* **Validaciones ejecutadas**:
  - Desarrollo test-first, 27 pruebas dirigidas y suite completa de 80 pruebas: PASS.
  - `py_compile`, JSON config, `git diff --check`, Speckit QA, benchmark, HTML nativo y Docker read-only: PASS.
  - State machine y bloque de auto-reboot: sin cambios respecto de `9b8e793`.
* **Estado**:
  - Implementacion local completa; activacion y prueba Telegram diferidas al reinicio controlado de fin de dia.
* **Archivos principales**:
  - `app/mining_quality.py`
  - `app/event_store.py`
  - `app/miner_monitor.py`
  - `tools/operations_dashboard.py`
  - `tests/test_mining_quality.py`
  - `specs/013-mining-quality-intelligence/*`

## [2026-07-20] - Spec 012: Stability Advisor

* **Objetivo**: Convertir la telemetria historica en un sweet spot robusto por minero y separar fallas actuales de drift o histeresis, sin agregar acciones automaticas.
* **Resultado**:
  - Un analizador puro construye bandas por mediana/MAD desde muestras previas saludables y excluye la muestra actual de su propio baseline.
  - Los resultados `LEARNING`, `STABLE`, `WATCH` y `CRITICAL` incluyen razones acotadas para hashrate, temperatura, boards, voltaje/potencia de cadena, frecuencia, freshness y falta de respuesta.
  - Un estado persistido LOW con hashrate actual recuperado se clasifica como `WATCH/state_recovery_hysteresis`, evitando repetir una falsa severidad critica.
  - `/health`, `/health all` y `/health <miner>` consultan solo SQLite, responden con semantica de comando y no hacen IO live hacia mineros.
  - El dashboard reutiliza exactamente el mismo analizador y muestra baseline y diagnostico por card.
  - El voltaje de cadena se presenta explicitamente como evidencia board-side, no como voltaje AC de entrada.
* **Validaciones ejecutadas**:
  - Desarrollo test-first con fallas iniciales para modulo, dashboard, comando y caso de histeresis.
  - 17 pruebas dirigidas y suite completa de 68 pruebas: PASS.
  - Benchmark de 5.000 muestras: 17,84 ms en el equipo objetivo.
  - CLI Windows, HTML fixture, build Docker y generacion Docker read-only: PASS.
* **Estado**:
  - Implementacion local completa; activacion runtime diferida al reinicio controlado de fin de dia.
* **Archivos principales**:
  - `app/stability_profile.py`
  - `app/miner_monitor.py`
  - `tools/operations_dashboard.py`
  - `tests/test_stability_profile.py`
  - `specs/012-stability-advisor/*`

## [2026-07-20] - Spec 011: Read-Only Operations Dashboard

* **Objetivo**: Agregar una interfaz local visual para correlacionar salud, tendencias, incidentes y decisiones sin convertir el dashboard en superficie de control.
* **Resultado**:
  - Un CLI standalone abre SQLite con `mode=ro` y genera HTML autocontenido sin cargar config ni conectarse a mineros.
  - El dashboard muestra KPIs, cards por minero, freshness, boards, temperatura, potencia de cadena, sparklines, eventos y decisiones.
  - Todas las cadenas persistidas se escapan; no hay JavaScript, CDN, assets remotos, listener web ni acciones reboot/restart.
  - Consultas, timelines y tendencias quedan acotadas; se priorizan las muestras mas recientes.
  - `Dockerfile.dashboard` ofrece ejecucion aislada opcional, manteniendo Python/PowerShell como ruta principal.
* **Validaciones ejecutadas**:
  - Desarrollo test-first: falla inicial por modulo inexistente y luego 5 pruebas dirigidas PASS.
  - Suite completa de 56 pruebas, `py_compile`, `git diff --check` y Speckit QA: PASS.
  - Fixture de cuatro mineros: HTML generado correctamente (10,627 bytes) bajo `diagnostics/` ignorado.
  - Build Docker y generacion aislada contra el fixture: PASS (10,493 bytes).
  - La apertura visual automatizada `file://` quedo bloqueada por politica del navegador y se documenta como pendiente manual.
* **Estado**:
  - Implementacion local completa. No requiere ni provoca reinicio del servicio.
* **Archivos principales**:
  - `tools/operations_dashboard.py`
  - `Dockerfile.dashboard`
  - `tests/test_operations_dashboard.py`
  - `docs/speckit/RUNBOOK.md`
  - `specs/011-operations-dashboard/*`

## [2026-07-20] - Spec 010: Fleet-Aware Auto-Reboot Safety

* **Objetivo**: Evitar reboots automaticos innecesarios durante degradacion compartida de flota o evidencia termica alta, sin agregar IO ni modificar controles manuales.
* **Resultado**:
  - Un evaluador puro bloquea con `fleet_incident` cuando al menos dos mineros aparecen afectados en el ultimo tick completo y fresco.
  - La evidencia de flota vence despues de `max(60, poll_seconds * 2)` para impedir decisiones sobre snapshots viejos.
  - Un LOW sostenido con temperatura Vnish actual igual o superior a 85 C se bloquea como `high_temperature` por defecto.
  - Ambos interlocks son configurables, estan habilitados por defecto y se aplican despues de startup/sustained LOW pero antes de cooldown/window/QA/Hashcore.
  - `/why` muestra mineros afectados, antiguedad del snapshot, temperatura observada y limite.
  - No se agregan requests, dependencias, workers, campos de estado ni cambios a reboot/restart manual.
* **Validaciones ejecutadas**:
  - Desarrollo test-first: falla inicial por modulo inexistente y luego 19 pruebas dirigidas PASS.
  - Suite completa de 51 pruebas y `py_compile`: PASS.
  - Snapshot sanitizado: 4/4 mineros con 3 boards, 92.851-101.265 TH/s y maximos de 72-81 C, todos debajo del limite default.
* **Estado**:
  - Implementacion y validacion local completas. El servicio sigue sin reiniciarse hasta el cierre controlado del dia.
* **Archivos principales**:
  - `app/reboot_safety.py`
  - `app/miner_monitor.py`
  - `app/event_store.py`
  - `app/config.example.json`
  - `tests/test_reboot_safety.py`
  - `specs/010-fleet-reboot-safety/*`

## [2026-07-20] - Spec 009: Vnish Hashboard Detection

* **Objetivo**: Hacer que el monitor de produccion detecte hashboards con el formato Vnish real y diferencie una placa faltante de un LOW generico.
* **Resultado**:
  - `_count_active_boards` reconoce `chain_acn0..9`, ademas de los formatos legacy que ya soportaba.
  - `read_stats_snapshot` recorre todas las entradas `STATS` y usa la primera que contenga evidencia explicita de boards.
  - No se agrega ninguna llamada API: el mismo response alimenta state machine, telemetria Vnish y auditoria.
  - Evidencia desconocida sigue siendo `None`; ceros y valores invalidos no cuentan como board activo.
  - Se conserva la precedencia existente `HASHBOARD` antes de `LOW`; HASHBOARD no entra en el path de auto-reboot LOW.
* **Validaciones ejecutadas**:
  - Los snapshots sanitizados reales de S19JPRO-23/24/25/26 cuentan exactamente 3 boards con el parser de produccion: PASS.
  - 40 pruebas de formatos Vnish/legacy, degradacion, precedencia, seguridad, persistencia, Telegram y reportes: PASS.
  - `py_compile`, `git diff --check` y Speckit preflight: PASS.
* **Estado**:
  - Implementacion y validacion local completas. El servicio sigue sin reiniciarse hasta el cierre controlado del dia.
* **Archivos principales**:
  - `app/miner_monitor.py`
  - `tests/test_vnish_hashboard_detection.py`
  - `tests/test_monitor_incidents.py`
  - `specs/009-vnish-hashboard-detection/*`

## [2026-07-20] - Spec 008: Valid Signal Auto-Reboot Gate

* **Objetivo**: Evitar reboots innecesarios cuando la state machine conserva `LOW` por histeresis pero la lectura actual es invalida o ya recupero el hashrate.
* **Resultado**:
  - El auto-reboot exige ahora `responded=true`, hashrate numerico finito y valor actual por debajo del umbral antes de evaluar cualquier accion.
  - `None`, `NaN`, infinito y falta de respuesta se clasifican como `invalid_signal` y cortan el reloj de LOW sostenido.
  - Una lectura actual igual o superior al umbral se clasifica como `not_low`, incluso si la recuperacion todavia espera `recovery_successes`, y tambien corta el reloj sostenido.
  - El siguiente LOW valido debe iniciar un periodo sostenido nuevo; no hereda tiempo a traves de una muestra invalida o recuperada.
  - La state machine, sus streaks, startup guard, cooldown, ventana, QA, Hashcore, Telegram manual y polling no se reordenaron.
  - El bloqueo no usa `continue`, por lo que el procesamiento posterior de transiciones, alertas y persistencia sigue ocurriendo.
* **Validaciones ejecutadas**:
  - Clasificacion tabular para no-response, `None`, `NaN`, infinitos, umbral, recuperacion y LOW valido: PASS.
  - Predicate de elegibilidad y reset del timer sostenido: PASS.
  - Suite completa de 34 pruebas, `py_compile`, `git diff --check` y Speckit QA HIGH-risk: PASS.
* **Estado**:
  - Implementacion y validacion local completas, listas para commit/push. El servicio sigue ejecutando la version anterior hasta el reinicio controlado de fin de dia.
* **Archivos principales**:
  - `app/miner_monitor.py`
  - `tests/test_auto_reboot_signal_gate.py`
  - `specs/008-valid-signal-reboot-gate/*`

## [2026-07-20] - Spec 007: Vnish Telemetry And Reboot Decision Audit

* **Objetivo**: Convertir la telemetria Vnish ya disponible en evidencia durable y explicar cada resultado relevante del auto-reboot sin modificar sus condiciones ni ejecutar acciones nuevas.
* **Resultado**:
  - SQLite migra de schema v1 a v2 de forma aditiva, preservando muestras y eventos existentes.
  - Se normalizan todas las entradas `STATS`, incluyendo el caso real donde la evidencia de cadena vive en `STATS[1]`.
  - Las muestras incorporan temperatura maxima, voltaje y consumo de cadena, frecuencia, errores HW, ventiladores y flags conservadores; nunca se guarda el payload ASIC completo.
  - Cada rama relevante del auto-reboot registra `not_low`, `invalid_signal`, `startup_guard`, `not_sustained`, `cooldown`, `window`, `qa`, `executed` o `failed` con su evidencia.
  - `/why` y `/why <miner>` explican la ultima decision usando solo SQLite, sin IO al minero ni Hashcore.
  - `tools/incident_report.py` genera Markdown o JSON correlacionando muestras, eventos y decisiones con una conexion SQLite read-only.
  - Se mantiene explicito que `chain_vol` es evidencia de cadena/hashboard y no voltaje AC de entrada.
  - No se agregaron frameworks ni servicios: FastAPI/dashboard y Prometheus/Grafana quedan diferidos hasta estabilizar el contrato de datos.
* **Validaciones ejecutadas**:
  - `py_compile` de monitor, event store, parser Vnish y reporte: PASS.
  - 30 pruebas `unittest` de migracion, persistencia, concurrencia, normalizacion, reporte, Telegram, restart intelligence y QA: PASS.
  - Speckit QA preflight inicial HIGH-risk: PASS.
* **Estado**:
  - Implementacion y validacion local completas, listas para commit/push. El servicio de Windows no se reinicia hasta el cierre del dia por solicitud del operador.
* **Hallazgo de auditoria**:
  - El path preexistente `invalid_signal` registra el problema pero puede continuar evaluando un `LOW` heredado en el mismo tick. Se registra como P0 separado porque corregirlo cambia politica de accion.
* **Archivos principales**:
  - `app/vnish_telemetry.py`
  - `app/event_store.py`
  - `app/miner_monitor.py`
  - `tools/incident_report.py`
  - `tests/test_vnish_telemetry.py`
  - `tests/test_reboot_decision_audit.py`
  - `tests/test_incident_report.py`
  - `specs/007-vnish-decision-audit/*`

## [2026-07-20] - Spec 006: Incident History And Restart Intelligence

* **Objetivo**: Crear una base durable de evidencia operativa y distinguir reinicios esperados de reinicios no deseados sin cambiar la state machine ni la politica de auto-reboot.
* **Resultado**:
  - Se agrego un event store SQLite versionado, thread-safe y en modo WAL para muestras acotadas, transiciones, reinicios detectados y resultados de acciones.
  - El detector existente de caida de uptime se conserva y ahora se clasifica como `expected_manual`, `expected_auto` o `unexpected` usando acciones exitosas recientes.
  - Los reinicios inesperados generan una alerta dedicada con uptime anterior/actual, estado, hashrate, incidente y acceso a `/event <id>`.
  - Se agregaron `/events`, `/events <miner>` y `/event <id>` como consultas Telegram read-only sin IO al minero ni Hashcore.
  - La retencion queda acotada a 90 dias de muestras cada cinco minutos y 365 dias de eventos por defecto.
  - El historial es estrictamente observacional y no participa de decisiones de reboot, cooldown, startup guard o QA.
* **Validaciones ejecutadas**:
  - `py_compile` del monitor, event store, clasificador y herramientas: PASS.
  - 19 pruebas `unittest` de persistencia, reapertura, retencion, concurrencia, clasificacion, parsing, mensajes y bloqueo QA: PASS.
  - `git diff --check`: PASS.
  - Speckit QA preflight HIGH-risk con builds: PASS.
* **Estado**:
  - Implementacion y validacion local completas. La evidencia de activacion del servicio se registra en `specs/006-incident-history/evidence.md`.
* **Archivos principales**:
  - `app/event_store.py`
  - `app/restart_intelligence.py`
  - `app/miner_monitor.py`
  - `app/config.example.json`
  - `tests/test_event_store.py`
  - `tests/test_restart_intelligence.py`
  - `tests/test_monitor_incidents.py`
  - `specs/006-incident-history/*`

## [2026-07-14] - Spec 005: Event-Driven Telegram Alerts

* **Objetivo**: Reducir ruido operativo en Telegram deshabilitando por defecto los resumenes horarios de estado degradado, manteniendo alertas por eventos reales como LOW, OFFLINE, HASHBOARD y recuperacion a OK.
* **Resultado**:
  - `notify_degraded_hourly` queda en `false` por defecto.
  - `degraded_hourly_seconds` queda documentado/configurable para operadores que quieran recordatorios periodicos.
  - El envio existente `degraded_hourly` ahora solo ocurre si se habilita explicitamente por config.
  - Los mensajes `STATE_CHANGE` agregan una seccion `Eventos:` con el cambio concreto antes del snapshot completo.
  - `/status` no cambia: sigue disponible como consulta manual cuando el operador quiere el estado completo.
* **Validaciones ejecutadas**:
  - `& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py tools\\miner_diagnostics.py tools\\diagnostics_baseline.py`: PASS.
  - Smoke import de `format_state_event`: PASS.
  - `git diff --check`: PASS.
* **Estado**:
  - Implementado y validado estaticamente. Requiere reinicio del servicio para cargar la nueva politica de notificaciones.
* **Archivos principales**:
  - `app/miner_monitor.py`
  - `app/config.example.json`
  - `docs/speckit/RUNBOOK.md`
  - `docs/speckit/ROADMAP.md`
  - `specs/005-event-driven-telegram-alerts/*`

## [2026-07-11] - Spec 004: Diagnostics Baseline Sweet Spot

* **Objetivo**: Convertir snapshots read-only en una linea base por minero para identificar variacion normal, evidencia de Vnish y seniales que deben observarse antes de cambiar politicas de reboot.
* **Resultado**:
  - Se agrego `tools/diagnostics_baseline.py` como analizador standalone de `snapshot.json`.
  - El analizador acepta un archivo o directorio, agrega muestras por minero y genera `baseline.md` + `baseline.json`.
  - El reporte incluye muestra, confianza, banda TH/s, boards, banda de temperatura maxima, `chain_vol`, `chain_consumption`, frecuencia y hardware errors.
  - La confianza queda `low` con una sola muestra para evitar conclusiones prematuras.
  - La documentacion incorpora el comando operativo para construir baseline desde `diagnostics/latest/snapshot.json`.
  - Se documento una estrategia de adopcion tecnologica para Docker, FastAPI, SQLite/DuckDB, Prometheus/Grafana y dashboards read-only.
* **Validaciones ejecutadas**:
  - `& ".\\.venv\\Scripts\\python.exe" -m py_compile tools\\diagnostics_baseline.py tools\\miner_diagnostics.py app\\miner_monitor.py`: PASS.
  - `& ".\\.venv\\Scripts\\python.exe" tools\\diagnostics_baseline.py --input diagnostics\\latest\\snapshot.json --out diagnostics\\baseline`: PASS.
  - `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force; & ".agents\\skills\\speckit-qa\\scripts\\preflight.ps1" -RunBuilds`: PASS.
* **Estado**:
  - Implementado y validado con el snapshot real de Spec 003. El baseline actual tiene confianza baja por contar con una sola muestra; se requieren multiples snapshots para convertirlo en politica.
* **Archivos principales**:
  - `tools/diagnostics_baseline.py`
  - `docs/speckit/RUNBOOK.md`
  - `docs/speckit/ROADMAP.md`
  - `docs/speckit/MINER_DIAGNOSTICS.md`
  - `docs/speckit/TECHNOLOGY_STRATEGY.md`
  - `specs/004-diagnostics-baseline-sweet-spot/*`

## [2026-07-11] - Spec 003: Read-Only Miner Diagnostics

* **Objetivo**: Agregar una herramienta read-only para recolectar evidencia de mineros antes de cambiar politicas de alertas, auto-reboot o UX operativa, manteniendo intacto el monitor en produccion.
* **Resultado**:
  - Se agrego `tools/miner_diagnostics.py` como colector standalone para API 4028 (`summary`, `stats`, `pools`, `version`).
  - El colector genera `summary.md` y `snapshot.json` sanitizados, con redaccion de usuarios de pool y sin exponer secretos de Telegram.
  - Se agrego `--dry-run` para validar config sin llamadas de red.
  - Se agrego `Dockerfile.diagnostics` para ejecutar solo el colector de diagnostico, sin dockerizar el monitor principal ni Hashcore Toolkit.
  - Se detectaron campos Vnish utiles para correlacion: `chain_vol`, `chain_consumption`, `freq_avg`, `chain_rate`, `chain_hw`, temperaturas chip/PCB y estado de pools.
  - `.gitignore` y `.dockerignore` cubren config real, state, logs, diagnostics, caches, envs y secretos.
* **Validaciones ejecutadas**:
  - `& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py tools\\miner_diagnostics.py`: PASS.
  - `& ".\\.venv\\Scripts\\python.exe" tools\\miner_diagnostics.py --config app\\config.example.json --out diagnostics\\dry-run --dry-run`: PASS.
  - `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force; & ".agents\\skills\\speckit-qa\\scripts\\preflight.ps1" -RunBuilds`: PASS.
  - `git diff --check`: PASS.
  - Snapshot read-only contra `app/config.json`: PASS, 4/4 mineros respondieron por API 4028.
* **Estado**:
  - Implementado y validado localmente con dry-run y snapshot real read-only. Queda como siguiente paso construir baseline/sweet spot con multiples snapshots antes de tocar politica de reboot.
* **Archivos principales**:
  - `tools/miner_diagnostics.py`
  - `Dockerfile.diagnostics`
  - `.dockerignore`
  - `.gitignore`
  - `docs/speckit/RUNBOOK.md`
  - `docs/speckit/ROADMAP.md`
  - `docs/speckit/MINER_DIAGNOSTICS.md`
  - `specs/003-read-only-miner-diagnostics/*`

## [2026-07-11] - Spec 002: Miner Diagnostics And Interface Roadmap

* **Objetivo**: Definir el roadmap tecnico para evolucionar Miner Alerts mas alla de alertas Telegram, cubriendo diagnostico antes de reboot, Hashcore Toolkit, Vnish, power telemetry e interfaz read-only.
* **Resultado**:
  - Se documento un roadmap por prioridades P0-P7 para reducir falsas alertas, evitar reboots innecesarios y mejorar observabilidad.
  - Se definio que Telegram permanece como superficie principal de acciones, mientras cualquier interfaz nueva debe empezar read-only.
  - Se documento una estrategia para Hashcore Toolkit: inventariar capacidades read-only vs acciones antes de integrar nuevos comandos.
  - Se definio una matriz de diagnostico para Vnish/S19j Pro: hash, boards, temperaturas, pool state, firmware hints, voltage/frequency/power fields y eventos de firmware.
  - Se aclaro que voltaje AC/input no debe inferirse automaticamente desde firmware salvo evidencia explicita; se deben considerar PDU/UPS/smart meter si hace falta.
* **Validaciones ejecutadas**:
  - Revision documental de `docs/speckit/ROADMAP.md`, `INTERFACE_STRATEGY.md`, `MINER_DIAGNOSTICS.md` y `HASHCORE_TOOLKIT_STRATEGY.md`: PASS.
  - No se realizaron cambios runtime en esta spec.
* **Estado**:
  - Roadmap y arquitectura de evolucion documentados. La implementacion real de diagnostico quedo iniciada posteriormente en Specs 003 y 004.
* **Archivos principales**:
  - `docs/speckit/ROADMAP.md`
  - `docs/speckit/INTERFACE_STRATEGY.md`
  - `docs/speckit/MINER_DIAGNOSTICS.md`
  - `docs/speckit/HASHCORE_TOOLKIT_STRATEGY.md`
  - `specs/002-miner-diagnostics-interface-roadmap/*`

## [2026-07-11] - Spec 001: Miner Alerts Quality Hardening

* **Objetivo**: Instalar una forma de trabajo Speckit para Miner Alerts, con foco en quick wins seguros: falsas alertas, seguridad de auto-reboot, confiabilidad Telegram, logs, hygiene de release y compatibilidad Windows/Hashcore.
* **Resultado**:
  - Se instalo `.specify/` desde el scaffold local probado en OneITB23.
  - Se instalaron skills Speckit bajo `.agents/skills/`, incluyendo `speckit-qa` adaptado a Miner Alerts.
  - Se creo la constitucion del proyecto en `.specify/memory/constitution.md` con reglas de seguridad: no secretos, no reboots sin evidencia, Telegram con confirmaciones y validacion Windows.
  - Se agrego `AGENTS.md` como instrucciones operativas para futuros agentes/Codex.
  - Se creo la base documental en `docs/speckit/` y specs iniciales para ordenar auditorias e implementaciones.
* **Validaciones ejecutadas**:
  - `& ".\\.venv\\Scripts\\python.exe" -m py_compile app\\miner_monitor.py`: PASS.
  - Verificacion de que la instalacion Speckit no cambiaba runtime del monitor: PASS.
* **Estado**:
  - Bootstrap Speckit completado. Las auditorias runtime y quick wins derivados quedaron como backlog y fueron desarrollados parcialmente en specs posteriores.
* **Archivos principales**:
  - `.specify/*`
  - `.agents/skills/*`
  - `.agents/skills/speckit-qa/*`
  - `AGENTS.md`
  - `docs/speckit/*`
  - `specs/001-miner-alerts-quality-hardening/*`
