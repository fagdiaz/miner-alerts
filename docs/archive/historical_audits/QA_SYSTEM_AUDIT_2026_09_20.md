# Informe de Auditoría Técnica y QA Especializado — Sistema Miner Alerts

- **Fecha de Auditoría**: 2026-09-20 (10:30 hs)
- **Rol / Especialidad**: Lead QA Engineer & Mining Systems Reliability Specialist
- **Estado**: Documento de Auditoría y Diagnóstico Preventivo (**Sin Implementación de Código**)
- **Línea Base Analizada**: 1358 tests unitarios PASS (100%), Servicio Windows `MinerAlerts` en producción, Firmware VNish 1.2.6 sobre 4x Antminer S19j Pro.
- **Archivos Auditados**:
  - [`app/miner_monitor.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py) (8.633 líneas)
  - [`app/governance/preset_balancer.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/preset_balancer.py)
  - [`app/governance/elevator_budget.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/elevator_budget.py)
  - [`app/governance/fan_governor.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/fan_governor.py)
  - [`app/governance/autotune_watchdog.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/autotune_watchdog.py)
  - [`app/governance/facility_agent.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/facility_agent.py)
  - [`app/governance/power_progression.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/power_progression.py)
  - [`app/telegram/poller.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/telegram/poller.py) y [`app/telegram/router.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/telegram/router.py)
  - [`app/core/event_store.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/core/event_store.py)

---

## 1. Resumen Ejecutivo

La reciente neutralización de `auto_restart_mining=True`, la corrección del resolver de potencia eléctrica real en `_get_miner_wattage` y la introducción del orquestador de progresión asimétrica han elevado a la planta a su cota histórica de mayor estabilidad: **más de 15 horas continuas sin reinicios en Minero 24 y más de 5 horas en Mineros 23, 25 y 26, sosteniendo ~10.2 kW y ~380 TH/s continuos**.

No obstante, un análisis forense y de aseguramiento de calidad (QA) de nivel de arquitectura profunda revela **deuda técnica, duplicaciones críticas de lógica y potenciales condiciones de carrera latentes** que, de no ser documentadas y atendidas en futuros ciclos de refactorización, representan puntos de falla potenciales ante variaciones de carga, cortes de red o cambios de configuración.

---

## 2. Hallazgos Críticos: Arquitectura y Gobernanza

### 🔴 Hallazgo 1: Conflicto Multicabezal de Gobernanza sobre el Mismo Actuador (Multi-Head Contention)

#### El Problema
Actualmente coexisten en el sistema **cuatro lazos de decisión independientes** que evalúan el preset y la potencia de los mineros:

```
                                    ┌────────────────────────────────┐
                                    │      ACTUADOR DE HARDWARE      │
                                    │ safe_set_miner_preset() (VNish)│
                                    └────────────────▲───────────────┘
                                                     │
         ┌───────────────────┬───────────────────────┼───────────────────────┐
         │                   │                       │                       │
┌────────┴────────┐ ┌────────┴────────┐     ┌────────┴────────┐     ┌────────┴────────┐
│ PRESET BALANCER │ │ SOFT CONTINGENCY│     │POWER PROGRESSION│     │ FACILITY AGENT  │
│(Historial 24h   │ │(Horario Pico,   │     │(Perfiles C0-C4, │     │(Resistencia Rth,│
│ reinicios, soak)│ │ Solar, Temp>84C)│     │ 15m soak, lock) │     │ Cohortes silicio│
└─────────────────┘ └─────────────────┘     └─────────────────┘     └─────────────────┘
```

1. **Preset Balancer** ([`app/governance/preset_balancer.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/preset_balancer.py)): Evalúa reinicios en las últimas 24h, soak de 72h, delta de errores HW. Si `restarts_24h >= 2`, decide `STEP_DOWN_RESTARTS` a 2300W.
2. **Soft Contingency** ([`app/miner_monitor.py#L8230-L8430`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py#L8230-L8430)): En horario valle y fuera de franja solar, si un minero está a `< 2500W`, decide escalarlo a 2500W o 2700W.
3. **Power Progression** ([`app/governance/power_progression.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/power_progression.py)): Modela perfiles integrales de planta (C0, C1, C2, C4) con compuertas de ventiladores ($<90\%$) y remojo térmico de 15 minutos.
4. **Facility Governance Agent (FGA)** ([`app/governance/facility_agent.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/facility_agent.py)): Calcula $R_{th}$ y asignación asimétrica por silicio.

#### El Riesgo Operativo Latente
En los logs de producción se observó:
```text
[BALANCER DRY] miner=S19JPRO-23 group=elevator_1 action=STEP_DOWN_RESTARTS preset=2500W->2300W restarts_24h=7 uptime=7h reason='Inestabilidad eléctrica (7 reinicios en 24h >= 2): desescalando a 2300W'
```
El `preset_balancer` está corriendo actualmente en modo `dry_run=True`. **Si un operador desactiva `dry_run` en `config.json`**:
- El `preset_balancer` forzará una desescalada del Minero 23 a 2300W debido a los reinicios viejos ocurridos antes del fix.
- Inmediatamente en el siguiente tick, el bloque de `soft_contingency` verá al Minero 23 en 2300W durante horario valle y ordenará una escalada a 2500W.
- **Resultado**: Los dos lazos de gobernanza entrarán en un **bucle oscilatorio permanente**, mutando presets cada 180 segundos.

#### Recomendación de Ingeniería
Unificar la gobernanza en un único **Pipeline Jerárquico de Decisión (Single Source of Truth)** con 3 capas estrictas de precedencia:
- **Capa 1 (Emergencia Físico-Eléctrica)**: Tripwire térmico inmediato ($\ge 83.5^\circ\text{C}$), Tripwire de errores HW, Rescate de autotuning stall.
- **Capa 2 (Envolvente Ambiental y Eléctrica)**: Franja solar (11:00-17:00 hs), Horario pico tarifario, Capacidad de transformadores (5400W por elevador).
- **Capa 3 (Optimización y Progresión)**: Orquestador de perfiles (`power_progression.py` / `facility_agent.py`).
- **Retiro o absorción de `preset_balancer.py`**: Desacoplarlo o integrarlo como métrica informativa dentro de la Capa 3 para evitar que luche contra el orquestador de planta.

---

## 3. Hallazgos en Red, Telemetría y E/S

### 🔴 Hallazgo 2: Tormenta de Escritura a Disco por Lote en el Poller de Telegram (`state.json` Churn)

#### El Problema ([`app/miner_monitor.py#L5307-L5315`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py#L5307-L5315))
En el bucle de recepción de comandos de Telegram:
```python
for item in result:
    update_id = item.get("update_id")
    # ...
    with state_lock:
        _payload = _build_state_payload(states, current_last_update_id)
    _flush_state_payload(state_path, _payload)  # <--- DENTRO DEL BUCLE FOR
```
La función `_flush_state_payload`:
1. Serializa el JSON completo de los 4 mineros (`json.dumps`).
2. Abre `app/state.tmp` y ejecuta `os.fsync(f.fileno())` (**fuerza vaciado físico de sectores en el disco**).
3. Copia `app/state.json` a `app/state.bak` vía `shutil.copyfile`.
4. Ejecuta `os.replace` para reemplazo atómico en Windows.

#### El Riesgo
Si Telegram entrega una ráfaga de 10 mensajes o eventos en un solo `getUpdates`, el monitor realiza **10 escrituras físicas a disco y 10 reemplazos de archivo atómicos consecutivos** en menos de 50 milisegundos.
En Windows NTFS, si un proceso de indexación, el antivirus de Windows Defender o un backup bloquea el descriptor de archivo durante `os.replace`, se lanza `PermissionError: [WinError 5] Acceso denegado`, registrando `[WARN] No se pudo guardar state.json`.

#### Recomendación de Ingeniería
Mover la invocación de `_flush_state_payload` **fuera del bucle `for item in result:`**, guardando en disco una sola vez al finalizar el procesamiento de todo el lote de actualizaciones recibidas.

---

### 🟡 Hallazgo 3: Muestreo HTTP Redundante a Placas Controladoras de ASICs (Port 80 Contention)

#### El Problema
En cada ciclo nominal de 30 segundos, el monitor ejecuta múltiples consultas HTTP independientes hacia el puerto 80 de cada minero:
1. **Adaptive Acquisition**: Sondeo de puerto 4028 (CGMiner).
2. **Fan Governor**: Consulta y ajuste vía `/api/v1/cooling`.
3. **Autotune Watchdog** ([`app/miner_monitor.py#L3795`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py#L3795)): Consulta serial sincrónica a `/api/v1/summary`.
4. **Overclock Sync** ([`app/miner_monitor.py#L3353`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py#L3353)): Consulta a `/api/v1/settings`.
5. **Chain Telemetry Worker**: Consulta a `/api/v1/chains`.

#### El Riesgo
Las controladoras de los S19j Pro (BeagleBone Black / Xilinx Zynq de un solo núcleo) ejecutan un servidor web embebido ligero (`lighttpd`/`nginx`). Recibir 3 o 4 peticiones HTTP por separado cada 30 segundos agota los sockets efímeros de la controladora, provocando respuestas lentas (timeouts de 2.5s) o caídas esporádicas de conexión (`ConnectionResetError`).
Además, si un minero se congela, el `check_autotune_watchdog` itera de forma serial bloqueando el hilo principal por hasta $4 \times 2.5\text{s} = 10\text{ segundos}$.

#### Recomendación de Ingeniería
Implementar **Adquisición Unificada de Paso Único (Single-Pass Ingestion)**:
- Al inicio de cada tick, un único pool de hilos consulta `/api/v1/summary` y `/api/v1/settings` en paralelo para los 4 mineros una sola vez.
- Se crea una instantánea inmutable en memoria (`MinerVnishSnapshot`).
- El Fan Governor, el Autotune Watchdog, el FGA y el Orquestador consumen todos esa misma instantánea sin emitir tráfico de red adicional.

---

## 4. Hallazgos de Duplicación y Código Muerto

### 🟡 Hallazgo 4: Código Duplicado entre `app/telegram/poller.py` y `app/miner_monitor.py`

#### El Problema
En la Spec 058 se creó el módulo desacoplado [`app/telegram/poller.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/telegram/poller.py) con las funciones `fetch_telegram_updates()` y `process_telegram_update()`.
Sin embargo, [`app/miner_monitor.py#L5230-L5500`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py#L5230-L5500) contiene una implementación **inline idéntica de 270 líneas** del bucle de sondeo, cálculo de offset y backoff exponencial.

#### El Riesgo
`app/telegram/poller.py` es **código muerto** en producción. Cualquier mejora de timeout, manejo de errores HTTP o sanitización de tokens aplicada en `poller.py` no tiene ningún efecto en el monitor real.

#### Recomendación de Ingeniería
Conectar `miner_monitor.py` directamente con `fetch_telegram_updates()` de `poller.py` y eliminar las 270 líneas duplicadas del monitor principal.

---

### 🟡 Hallazgo 5: Lista Blanca Estática `CMD_WHITELIST` Desincronizada

#### El Problema ([`app/miner_monitor.py#L158-L217`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py#L158-L217))
El monitor define un set de strings fijo:
```python
CMD_WHITELIST = {
    "help", "status", "info", "events", "fans", "reboot", ...
}
```
utilizado por la función auxiliar `_is_command_like(cmd_name)` para filtrar logs cuando `DBG_TELEGRAM_COMMANDS_ONLY=1`.
Los nuevos comandos de gobernanza y progresión añadidos recientemente:
- `/agent`, `/agente`, `/fga`
- `/strategy`, `/estrategia`
- `/fwhy`, `/razon`
- `/progression`, `/prog`, `/perfil`, `/profiles`

**No están incluidos en `CMD_WHITELIST`**.

#### El Riesgo
Si el operador activa el modo de diagnóstico de Telegram (`DBG_TELEGRAM_COMMANDS_ONLY=1`), el monitor descarta y silencia en los logs de depuración la recepción de `/agent` o `/progression`, dificultando el diagnóstico si un comando no responde.

#### Recomendación de Ingeniería
Eliminar la lista estática y hacer que `_is_command_like(cmd_name)` consulte dinámicamente las claves registradas en `_command_router._command_map.keys()`.

---

### 🟡 Hallazgo 6: Asimetría en el Despachador de Comandos de Telegram

#### El Problema ([`app/miner_monitor.py#L5425-L5449`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py#L5425-L5449))
```python
if False:
    pass
elif cmd_name == "diagnose":
    handled = _command_router.dispatch("diagnose", args, req_context, update_id=update_id, from_id=msg_chat_id)
elif cmd_name == "firmware":
    handled = _command_router.dispatch("firmware", args, req_context, update_id=update_id, from_id=msg_chat_id)
# ... status, quality, health ...
else:
    handled = _command_router.dispatch(
        cmd_name, args, req_context, update_id=update_id, from_id=msg_chat_id,
        message_id=message.get("message_id") if isinstance(message, dict) else None,
    )
```
En las ramas explícitas (`diagnose`, `firmware`, `quality`, `health`, `status`), no se envía el parámetro `message_id`. Solo se envía en la rama `else:`.

#### El Riesgo
Si el manejador de `/status` o `/diagnose` quisiera implementar edición de mensaje (`editMessageText`) o respuesta contextual en Telegram, recibe `message_id=None`. Además, las ramas `elif` son redundantes puesto que el enrutador `_command_router` ya maneja el despacho por tabla hash.

#### Recomendación de Ingeniería
Colapsar todo el bloque `if/elif/else` en una única llamada uniforme:
```python
handled = _command_router.dispatch(
    cmd_name, args, req_context, update_id=update_id, from_id=msg_chat_id,
    message_id=message.get("message_id") if isinstance(message, dict) else None,
)
```

---

### 🟡 Hallazgo 7: Dispersión de Constantes Térmicas Críticas

#### El Problema
Las temperaturas umbral de protección del silicio se encuentran dispersas y desacopladas en 5 archivos distintos con valores similares pero no idénticos:
- `app/governance/fan_governor.py`: `emergency_spike_temp_c = 83.0`, `deadband_high_c = 82.5`.
- `app/governance/facility_agent.py`: `SAFE_TARGET_TEMP_C = 82.5`, `TRIPWIRE_TEMP_C = 84.0`.
- `app/governance/power_progression.py`: `DEFAULT_THERMAL_TRIPWIRE_C = 83.5`, `DEFAULT_SUSTAINED_TRIPWIRE_C = 83.0`.
- `app/governance/elevator_budget.py`: `DEFAULT_VALLEY_STEP_UP_MAX_CHIP_TEMP_C = 80.0`.
- `app/miner_monitor.py#L8225`: Constante hardcodeada `_mt >= 84.0`.

#### El Riesgo
Si en temporada de verano el operador desea ajustar el margen preventivo de planta (por ejemplo, reducir el techo de 84.0°C a 82.0°C), debe recordar modificar múltiples parámetros en `config.json` y corre el riesgo de que constantes hardcodeadas en código fuente continúen operando bajo el umbral anterior.

#### Recomendación de Ingeniería
Crear un módulo centralizado de dominio térmico (ej. `app/domain/thermal_thresholds.py` o sección `"thermal_policy"` en `config.json`) que actúe como única fuente de verdad para la escalera térmica:
1. `TARGET_TEMP`: 81.0°C
2. `STEP_UP_CEILING`: 80.0°C (ventiladores < 90%)
3. `GOVERNOR_EMERGENCY`: 83.0°C (fans al 100%)
4. `PROGRESSION_FALLBACK`: 83.5°C (retorno inmediato a 2500W)
5. `CRITICAL_DOWNSTEP`: 84.0°C (desescalada forzosa)

---

## 5. Hallazgo de Mantenibilidad: Tamaño Monolítico de `miner_monitor.py`

### 🔵 Hallazgo 8: Monolito de 8.633 Líneas

#### El Problema
El archivo principal [`app/miner_monitor.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py) ha crecido a lo largo de 79 especificaciones hasta alcanzar **8.633 líneas y 411 KB**.
Contiene simultáneamente:
- Red TCP por sockets raw.
- Cliente REST HTTP y autenticación Bearer de VNish.
- Lógica de persistencia en disco y nombrado de copias `.bak`.
- Despacho de comandos de Telegram y formateo de Markdown.
- Bucle principal del servicio Windows y Named Pipes IPC.
- Gestión de reinicios por SSH/retransmisión.
- Orquestación de valle, envolvente solar y soft-contingencia.

#### El Riesgo
- Elevada carga cognitiva para mantenimiento e inspección.
- Fragilidad ante modificaciones: un cambio en la lógica de alertas puede impactar de forma inadvertida el lazo de control de ventiladores o la adquisición de telemetría.
- Dificultad para pruebas unitarias aisladas sin recurrir a complejas baterías de mocks.

#### Recomendación de Ingeniería
Aprovechar la arquitectura de hooks supervisores ([Spec 065](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/065-supervisory-hooks)) para segregar `miner_monitor.py` en etapas de pipeline modulares e independientes:
- `app/pipeline/acquisition_stage.py`
- `app/pipeline/detection_stage.py`
- `app/pipeline/governance_stage.py`
- `app/pipeline/telegram_stage.py`

---

## 6. Matriz de Priorización de Mejoras Futuras

| Prioridad | Área | Hallazgo | Riesgo Mitigado | Esfuerzo Estimado |
| :---: | :--- | :--- | :--- | :---: |
| **P1** | **Gobernanza** | Unificar lazos de decisión (Preset Balancer vs Soft Contingency vs Power Progression) | Elimina bucles oscilatorios y desescaladas no deseadas ante reinicios viejos | 3-4 horas (Refactor de gobernanza) |
| **P1** | **Persistencia** | Mover `_flush_state_payload` fuera del bucle de mensajes de Telegram | Elimina ráfagas de I/O físico (`os.fsync`) y bloqueos de archivo en Windows | 30 minutos |
| **P2** | **Red / ASICs** | Unificar consultas HTTP a controladoras en un solo snapshot por tick | Previene sobrecarga de controladoras y timeouts en puerto 80 | 2-3 horas |
| **P2** | **Comandos** | Conectar `_is_command_like` con el router y unificar paso de `message_id` | Visibilidad completa en logs de depuración para `/agent` y `/progression` | 30 minutos |
| **P2** | **Dominio** | Centralizar la escalera de umbrales térmicos en un único módulo | Garantiza coherencia de temperaturas entre Governor, Watchdog y FGA | 1 hora |
| **P3** | **Limpieza** | Eliminar código muerto en `poller.py` o migrar `miner_monitor.py` a su uso | Reduce deuda técnica y líneas duplicadas | 1-2 horas |
| **P3** | **Arquitectura** | Modularización progresiva del monolito de 8.633 líneas | Mantenibilidad a largo plazo y facilidad de testing | Planificado a mediano plazo |

---

## 7. Conclusión de la Auditoría

El sistema en su estado actual se encuentra **estable y seguro en producción**, operando con 0 reinicios en más de 5 horas.
Ninguno de los hallazgos señalados provoca fallos bajo la configuración actual (`preset_balancer_dry_run: true`, `presets_allowed: true` supervisado).
Sin embargo, esta auditoría establece la **hoja de ruta preventiva** clara y priorizada para blindar la arquitectura antes de activar modulaciones de potencia más agresivas o modificar parámetros de balanceo.
