# PROP-010: Arquitectura de Recuperación Suave de Hasheo, Desescalada Pre-Reinicio y Blindaje Anticolapso de Fuentes APW12
## (Soft-Landing Recovery & APW12 Latch-Off Defense)

- **Fecha de Creación**: 2026-09-18 11:45 hs
- **Autor**: Antigravity Engineering (Gemini 3.8 Flash High)
- **Estado**: Propuesta Técnica de Arquitectura / Documento Base para Futura Spec
- **Línea Base Operativa**: Flota en producción supervisada con Spec 074 activa (1221 tests PASS, Servicio Windows `MinerAlerts` PID 19204).
- **Incidentes de Origen**: Bloqueo de fuente Bitmain APW12 en Minero 25 (17/09 19:11 hs y 18/09 05:50 hs).
- **Documentos Relacionados**:
  - [PROP-009: Diagnóstico Exhaustivo de Reinicios Múltiples en Contingencia](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/proposals/PROP-009-contingency-stabilization-hypotheses.md)
  - [Spec 074: Amortiguador de Inrush Pareado](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/074-paired-elevator-contingency/spec.md)
  - [Spec 066: Cold-Boot Fleet Grace Period](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/066-cold-boot-grace/spec.md)

---

## 1. Motivación y Análisis del Problema Físico

### 1.1 El Síntoma: Colapso por Latch-Off de la Fuente APW12
En las últimas 24 horas se observó que el minero **S19JPRO-25** quedó completamente fuera de línea (`OFFLINE`, sin ping, sin puerto 80 ni 4028, desaparecido de la tabla ARP) exactamente tras intentar arrancar el minado en dos ocasiones:
1. **17/09 a las 19:11 hs**: Al alcanzar plena frecuencia tras un rearranque.
2. **18/09 a las 05:50 hs**: Tras recibir dos comandos automáticos consecutivos de `safe_restart_mining` emitidos por el monitor al detectar placa detenida (`stopped_state` / `CHAIN_FAULT`).

En ambos episodios:
- La llave termomagnética del tablero eléctrico general **permaneció levantada**.
- La fuente de poder **Bitmain APW12** entró en estado de **auto-protección (*Latch-Off*)**, cortando la línea secundaria de 12V DC para evitar daños internos por sobrecorriente (OCP) o caída severa de tensión (UVP).
- Al cortarse los 12V, la placa de control (alimentada por ese bus) se apaga totalmente, dejando la máquina inerte hasta que un operador realiza un ciclo manual de corte de 220V CA en el enchufe.

### 1.2 La Física de la Falla: Por qué una acción brusca de software destruye la disponibilidad
Cuando el software del monitor observa que una cadena se detiene o cgminer reporta `stopped_state`, la lógica actual de Nivel 1 (`auto_restart_mining`) envía de inmediato un comando REST `/api/v1/mining/restart` a VNish.

Este procedimiento presenta tres vulnerabilidades críticas:
1. **Escalón de Carga Violento ($\Delta I / \Delta t$)**:
   El minero se encuentra configurado en un preset intermedio o alto (ej. 2300 W o 2500 W). Al enviar el reinicio de minado, los tres hashboards se energizan simultáneamente desde 0 A hasta ~11 A. En una fuente con varios meses de fatiga térmica o inductancia de línea, el transitorio de corriente dispara el comparador de corte OCP de la APW12.
2. **Re-arranque Forzado sobre Hardware con Falla Transitoria**:
   Si la Cadena 1 tiene un problema físico incipiente (un capacitor de desacoplo con micro-fuga o falla de comunicación I2C), forzar un reinicio brusco a plena potencia amplifica la corriente de falla y precipita el apagado de la fuente.
3. **Colisión con el Watchdog Nativo de VNish**:
   VNish posee rutinas internas de recuperación (`watchdog_chain_restart`). Si el monitor externo envía un comando `restart_mining` mientras el firmware ya está intentando estabilizar los rieles, se produce una interferencia de estados que desbalancea la secuencia de arranque.

---

## 2. Principios de Diseño del Nuevo Algoritmo

Para resolver este problema sin perder hashrate ni arriesgar el hardware, la arquitectura debe regirse por cuatro premisas:

1. **"Nunca re-arrancar en caliente a plena potencia"**: Antes de enviar cualquier reinicio de minado, la potencia del equipo debe fijarse en un escalón ultrabajo de seguridad.
2. **"Esperar antes de actuar (Ventana de Normalización Pasiva)"**: Dar tiempo al firmware para que intente su ciclo nativo antes de emitir órdenes externas.
3. **"Aislar la degradación (Minería Asimétrica Segura)"**: Si una placa no responde, permitir que el equipo opere temporalmente a 2 placas (o en preset de contención) en lugar de intentar resucitarla violentamente arriesgando las otras dos.
4. **"Rampa Escalonada Post-Estabilización"**: La potencia solo debe subir cuando el equipo demuestre salud térmica y hashrate sostenido en frío.

---

## 3. Arquitectura Técnica de PROP-010

```
                   ┌────────────────────────────────────────────────────────┐
                   │             DETECCIÓN DE PLACA DETENIDA /              │
                   │           HASHEO INTERRUMPIDO (CHAIN_FAULT)            │
                   └──────────────────────────┬─────────────────────────────┘
                                              │
                                              ▼
                   ┌────────────────────────────────────────────────────────┐
                   │ FASE 1: VENTANA DE OBSERVACIÓN PASIVA (SETTLE WINDOW)  │
                   │ - Esperar 120s a 180s sin emitir comandos REST.        │
                   │ - Permitir que el watchdog nativo de VNish actúe.      │
                   │ - Si el minero se normaliza solo -> RETORNO A OK.      │
                   └──────────────────────────┬─────────────────────────────┘
                                              │ (Si persiste el fallo)
                                              ▼
                   ┌────────────────────────────────────────────────────────┐
                   │ FASE 2: DESESCALADA PRE-REINICIO (SOFT-LANDING CLAMP)  │
                   │ - Clampear preset al mínimo de seguridad (1800W-2000W) │
                   │   con clamp_top_preset=True.                           │
                   │ - Fijar voltaje bajo de hashboards (11.5V).            │
                   │ - Reducir a la mitad el escalón de corriente (di/dt).  │
                   └──────────────────────────┬─────────────────────────────┘
                                              │
                                              ▼
                   ┌────────────────────────────────────────────────────────┐
                   │ FASE 3: DISPARO CONTROLADO DE REINICIO DE MINADO       │
                   │ - Enviar safe_restart_mining en baja potencia.         │
                   │ - Ventiladores en piso seguro (Thermal Warmup Floor).  │
                   │ - APW12 arranca con margen holgado (cero latch-off).   │
                   └──────────────────────────┬─────────────────────────────┘
                                              │
                                              ▼
                   ┌────────────────────────────────────────────────────────┐
                   │ FASE 4: RAMPA ASCENDENTE ESCALONADA (STAGED RAMP-UP)   │
                   │ - Confirmar 3/3 placas (o 2/3) y hashrate estable.     │
                   │ - Esperar 180s sostenidos en estado OK.                │
                   │ - Subir escalonadamente: 2000W -> 2200W -> Nominal.    │
                   └────────────────────────────────────────────────────────┘
```

---

## 4. Módulos y Componentes Afectados

### 4.1 Gobernador de Reinicio Seguro (`app/governance/safe_recovery.py` o ampliación de `miner_monitor.py`)
- **Parámetro `safe_recovery_pre_clamp_preset`**: Preset al cual descender antes de enviar `safe_restart_mining` (por defecto: `"2000"` o `"1800"` W).
- **Parámetro `safe_recovery_settle_window_seconds`**: Tiempo de observación pasiva antes de intervenir (por defecto: `120` segundos).
- **Lógica de Ejecución**:
  ```python
  def execute_soft_landing_restart(host: str, current_preset: str, target_safe_preset: str = "2000") -> bool:
      # 1. Bajar el preset a nivel seguro antes del reinicio
      safe_set_miner_preset(host, target_safe_preset, clamp_top_preset=True)
      time.sleep(2.0)
      # 2. Enviar el reinicio de minado en condiciones suaves
      ok, err = safe_restart_mining(host, password)
      # 3. Registrar marca temporal para rampa ascendente diferida
      return ok
  ```

### 4.2 Restricción de `auto_restart_mining` ante `CHAIN_FAULT` Físico
- Si la telemetría indica que una cadena física está reportando cero ASICs o desconexión de bus:
  - **Inhibir el reinicio automático reiterativo** (máximo 1 intento suave con pre-clamp).
  - Si no recupera la placa, no forzar un segundo reinicio: degradar el perfil a **modo seguro de contingencia** para que las placas sanas sigan minando sin castigar la fuente.

### 4.3 Alertas Especializadas en Telegram (Diagnóstico Claro)
- Si un minero deja de responder por completo justo tras un rearranque:
  - Notificar como:
    ```text
    ⚠️ POSIBLE BLOQUEO DE FUENTE (APW12 LATCH-OFF)
    Equipo: 25 (192.168.100.25)
    Causa: Pérdida total de telemetría tras pico de arranque.
    Acción sugerida: Desconectar alimentación de 220V por 30s para descargar capacitores y reconectar. Revisar bornera de Cadena 1.
    ```
  - Evita que el operador reciba alertas genéricas y confusas de `OFFLINE / LOW`.

---

## 5. Coordinación Termo-Energética: Preset Balancer ↔ Fan Governor (Headroom Chilling)

### 5.1 El Problema de Suboptimización en Estado Estacionario
Actualmente, el **Fan Governor** ([Spec 039](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/039-fan-governor-pid-tuning/spec.md)) y el **Preset Balancer** ([Spec 040](file:///F:/02-ASIC%20-%20mineros/miner-alerts/specs/040-dynamic-power-preset-balancer/spec.md)) operan de forma desacoplada:
- **Fan Governor**: Modula ventiladores para buscar el punto de equilibrio térmico (`target_temp_c = 82.0°C`, `deadband_low = 81.0°C`, `deadband_high = 82.5°C`). Si la temperatura está en 81°C, retiene (*HOLD*) los ventiladores al 88-90% para ahorrar ruido y energía de ventiladores.
- **Preset Balancer**: Evalúa si es seguro subir de preset (ej. de 2500W a 2700W). Requiere un margen térmico mínimo hacia 84.0°C de al menos 3.0°C (`step_up_min_thermal_margin_c = 3.0°C`), lo que exige $T_{max} \le 81.0°C$.
- **Falso Atascamiento (Sub-optimal Trap)**:
  Un minero operando a 2500W con 81.5°C y ventiladores al 90% **tiene un 10% de capacidad de enfriamiento ociosa**.
  * El Governor no sube los ventiladores porque 81.5°C está dentro de su zona muerta.
  * El Balancer no sube la potencia a 2700W porque 81.5°C no le da el margen requerido de 3°C.
  * **Consecuencia**: El minero se queda estancado en 2500W perdiendo entre 5 y 8 TH/s de hashrate que podría generar si los ventiladores subieran al 100% y bajaran la temperatura a 78°C.

### 5.2 Solución Propuesta: Enfriamiento de Oportunidad (*Headroom Chilling*)
Introducir un lazo de acoplamiento bidireccional:
- Si el Balancer detecta que un minero está listo para subir de preset (estabilidad eléctrica, 0 reinicios, sin contingencia) pero está bloqueado *únicamente* por margen térmico ($80.5°C \le T \le 82.0°C$) y los ventiladores están por debajo del 98% PWM:
  * El Balancer emite una señal de solicitud de enfriamiento (`request_boost_cooling = True`).
  * El Fan Governor fuerza temporalmente los ventiladores al **100% PWM** durante una ventana de 180 segundos.
  * Si la temperatura desciende a $\le 78.5°C$, el Balancer desbloquea de inmediato el escalón a 2700W.
  * Una vez estabilizado en 2700W, el Governor retoma la modulación normal del lazo cerrado.

---

## 6. Calibración y Comportamiento del Fan Governor ante Temperaturas de 83.0°C

### 6.1 Por qué los ventiladores estaban al 96% y no al 100% a los 83.0°C
En la observación de las 11:38 hs se detectó al minero 24 en 83.0°C con ventiladores al 96% PWM:
1. **Umbral de Disparo de Emergencia (`EMERGENCY_SPIKE`)**:
   En `app/config.json`, `"fan_governor_emergency_temp_c"` está calibrado en **83.5°C**.
   Por lo tanto, a los 83.0°C no se gatilla el salto instantáneo a 100%.
2. **Modulación por Escalones (`STEP_UP`)**:
   A los 83.0°C, la temperatura supera `deadband_high_c` (82.5°C).
   El Governor incrementa el PWM en pasos de `+3%` (`fan_governor_step_up_pct: 3`) cada 90 segundos (`dwell_seconds: 90`).
   El minero transitó: 90% $\to$ 93% $\to$ 96% $\to$ 100%. De hecho, a las 11:50 hs el minero 24 ya se encontraba al **100% PWM**.

### 6.2 Propuesta de Calibración
Para acelerar la respuesta ante temperaturas superiores a 82.5°C sin esperar dos ciclos de 90s:
- Si $T \ge 83.0°C$ (a solo 1.5°C del corte de saturación de 84.5°C), duplicar el paso de subida (`step_up_percent = 6%`) o forzar salto inmediato a 100% ajustando `"fan_governor_emergency_temp_c": 83.0`.

---

## 7. Evento de Corte General de Energía en Granja (11:52 hs)

A las **11:52:45 hs**, se interrumpió el suministro eléctrico en la granja.
El sistema de supervisión en el host demostró su robustez arquitectónica:
```text
[2026-09-18 11:52:45] [PHASE_DROP] Alerting verdict=phase_drop_fleet affected=['elevator_1', 'elevator_2'] failed=['S19JPRO-23', 'S19JPRO-24', 'S19JPRO-25', 'S19JPRO-26']
```
- **Comportamiento Seguro**: El detector de caída de fase / corte masivo (`PHASE_DROP`) identificó la desconexión simultánea de los 4 mineros en ambos elevadores.
- **Inhibición de Falsos Reinicios**: El *Fleet Guard* bloqueó cualquier intento de auto-reinicio espurio.
- **Preparación para el Retorno**: Al volver la energía, entrará en juego la **Spec 066 (Cold-Boot Fleet Grace Period)**, esperando los 180s de calentamiento pasivo sin emitir spam de falsas alertas.

---

## 8. Plan de Iteraciones y Auditoría

| Iteración | Alcance | Estado |
| :---: | :--- | :---: |
| **Iteración 1** | Documento base de arquitectura (`PROP-010`), formalización de Latch-Off y acoplamiento Balancer-Governor. | **Completado** |
| **Iteración 2** | Refinamiento de umbrales con el operador y diseño de la Especificación Formal (`specs/075-soft-landing-recovery/`). | **En curso** |
| **Iteración 3** | Auditoría de Concurrencia y Estados (Claude Sonnet 4.6 Thinking) previa a la codificación. | **Planificado** |
| **Iteración 4** | Implementación de desescalada pre-reinicio, Headroom Chilling y suite de pruebas (1221 tests + tests nuevos). | **Planificado** |
| **Iteración 5** | Despliegue seguro en producción con validación post-retorno de energía. | **Planificado** |

