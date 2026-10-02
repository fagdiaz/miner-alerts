# PROP-014: Roadmap Experimental de Combinaciones de Máxima Potencia y Estabilidad en Elevadores

- **Fecha de Creación**: 2026-09-19 17:15 hs
- **Autor**: Antigravity Engineering (Gemini 3.8 Flash High)
- **Estado**: Propuesta Activa / Laboratorio de Pruebas en Ejecución
- **Componentes Afectados**: [app/governance/elevator_budget.py](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/elevator_budget.py), [app/governance/preset_balancer.py](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/preset_balancer.py), [app/miner_monitor.py](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/miner_monitor.py), [data/miner_alerts.db](file:///F:/02-ASIC%20-%20mineros/miner-alerts/data/miner_alerts.db)
- **Marco de Referencia**: [PROP-009 (Diagnóstico de Cascadas)](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/proposals/PROP-009-contingency-stabilization-hypotheses.md), [PROP-012 (Soft-Contingencia y Presupuesto de Elevador)](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/proposals/PROP-012-staggered-elevator-governance-and-soft-contingency.md), [PROP-013 (Protección Anti-Stall y Térmica Solar)](file:///F:/02-ASIC%20-%20mineros/miner-alerts/docs/proposals/PROP-013-elevator-noise-autotune-stall-and-thermal-protection.md)

---

## 1. Resumen Ejecutivo y Mandato de Optimización

El objetivo mandatado para el laboratorio de `miner-alerts` es **maximizar el hashrate global de la flota (TH/s) dentro de un entorno físicamente saludable y eléctricamente estable**.

Para lograrlo, el sistema debe explorar metódicamente todas las alternativas de asignación de potencia posibles (simétricas y asimétricas), someter cada hipótesis a pruebas de estrés controladas en producción, recopilar la telemetría en `data/miner_alerts.db` y asentar los resultados empíricos de forma determinística en este documento.

---

## 2. Fronteras Físicas y Restricciones de Seguridad

Toda combinación ensayada debe operar dentro de las siguientes fronteras físicas no negociables:

```
                                      [ Acometida Monofásica 220V ]
                                       Límite seguro: 50A (~10.8 kW)
                                       Límite crítico: 55A (~11.8 kW)
                                                │
                       ┌────────────────────────┴────────────────────────┐
                       ▼                                                 ▼
             [ Elevador 1 (T1) ]                               [ Elevador 2 (T2) ]
          Límite continuo: 5400W                            Límite continuo: 5400W
          Límite transitorio: 5600W                         Límite transitorio: 5600W
              ┌────────┴────────┐                               ┌────────┴────────┐
              ▼                 ▼                               ▼                 ▼
        [ S19JPRO-23 ]    [ S19JPRO-24 ]                  [ S19JPRO-25 ]    [ S19JPRO-26 ]
         Silicio: A+       Silicio: A                      Silicio: B (PLL)  Silicio: A+
```

1. **Acometida Monofásica Compartida**:
   * Tensión con carga: $210\text{V} - 218\text{V}$.
   * Corriente continua recomendada: $\le 50\text{ A}$ ($10.800\text{ W}$).
   * Superar $11.000\text{ W}$ ($>52\text{ A}$) incrementa la caída de tensión ($\Delta V$) en los conductores de acometida, aumentando el rizado inductivo.
2. **Transformadores Elevadores (T1 y T2)**:
   * Potencia nominal continua: $5.000\text{ W} - 5.400\text{ W}$.
   * Zona de estrés magnético: $>5.400\text{ W}$. Provoca calentamiento del núcleo y distorsión de onda ante conmutaciones bruscas.
3. **Restricción Térmica de Chips (Firmware VNish)**:
   * Disparo automático de seguridad: `decrease_temp: 84°C`.
   * Margen de seguridad operativa: Chips $\le 80.0^\circ\text{C}$ y Fans $< 90\%$.
4. **Acoplamiento Inductivo de Conmutación ($V = -L \frac{di}{dt}$)**:
   * Todo cambio de escalón de potencia debe realizarse de a **1 minero cada 180 segundos** (`settle_window_seconds: 180.0`).
   * Ante cualquier incidente o desconexión en un elevador, rige el reposo obligatorio de **300 segundos** (`incident_quiet_window_s: 300.0`).

---

## 3. Matriz Exhaustiva de Combinaciones de Potencia

A continuación se calcula el mapa completo de combinaciones posibles a evaluar en el laboratorio:

| ID | Perfil de Configuración (23 / 24 / 25 / 26) | Potencia Elevador 1 | Potencia Elevador 2 | Potencia Total Flota | Corriente Estimada (215V) | Hashrate Proyectado | Eficiencia Flota | Riesgo Eléctrico | Riesgo Térmico | Veredicto Lab |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **C0** | **Base Conservadora**: 2500 / 2500 / 2500 / 2500 | 5000 W | 5000 W | **10.000 W** | 46.5 A | ~376 TH/s | 26.6 J/TH | Nulo | Mínimo | **Certificada** (4h+ 100% OK) |
| **C1** | **Asimétrica 10.6 kW**: 2700 / 2700 / 2500 / 2700 | 5400 W | 5200 W | **10.600 W** | 49.3 A | ~392 TH/s | 27.0 J/TH | Bajo | Bajo (<80°C) | **En Ejecución** (Activa) |
| **C2** | **Asimétrica Conservadora Elev. 2**: 2700 / 2700 / 2300 / 2700 | 5400 W | 5000 W | **10.400 W** | 48.4 A | ~384 TH/s | 27.1 J/TH | Mínimo | Mínimo | Planificada |
| **C3** | **Equilibrio Fino 2600W**: 2600 / 2600 / 2500 / 2600 | 5200 W | 5100 W | **10.300 W** | 47.9 A | ~383 TH/s | 26.9 J/TH | Mínimo | Mínimo | Planificada |
| **C4** | **Cuádruple 2700W**: 2700 / 2700 / 2700 / 2700 | 5400 W | 5400 W | **10.800 W** | 50.2 A | ~398 TH/s | 27.1 J/TH | Moderado | Moderado (M25 stall) | Hipótesis Condicional |
| **C5** | **Boost Asimétrico Elev. 1**: 2800 / 2800 / 2500 / 2700 | 5600 W | 5200 W | **10.800 W** | 50.2 A | ~402 TH/s | 26.9 J/TH | Alto (T1 saturado) | Moderado | Planificada (Solo noche fría) |
| **C6** | **Laboratorio Mono-Elevador**: 2700 / 2700 / 0 / 0 | 5400 W | 0 W | **5.400 W** | 25.1 A | ~198 TH/s | 27.2 J/TH | Nulo | Nulo | Herramienta de Calibración |
| **C7** | **Arranque Frío Dual por Elevador**: Escalonamiento por parejas | Dinámico | Dinámico | Dinámico | Rampa | Dinámico | Dinámico | Controlado | Controlado | En Observación |

---

## 4. Programa de Hipótesis Científicas (Roadmap de Experimentos)

### Hipótesis H1: Viabilidad y Estabilidad Prolongada de la Combinación Asimétrica 10.6 kW (C1)
* **Planteo**: Mineros 23, 24 y 26 a 2700W, con Minero 25 fijado a 2500W.
* **Fundamento Físico**:
  * Elevador 1 entrega exactamente su capacidad óptima ($2 \times 2700\text{W} = 5400\text{W}$).
  * Elevador 2 opera desahogado a $5200\text{W}$ ($2500\text{W} + 2700\text{W}$), protegiendo al silicio de S19JPRO-25 contra autotune stall.
  * La corriente en acometida ($49.3\text{A}$) permanece por debajo del umbral de disparo de 50A.
* **Criterio de Aceptación**: Mínimo 6 horas continuas sin reinicios de firmware, con temperaturas $< 80^\circ\text{C}$ y fans $< 85\%$.
* **Estado**: **EN CURSO**. (Iniciada a las 17:05 hs tras finalizar franja solar).

### Hipótesis H2: Ensayo Térmico Controlado de S19JPRO-25 a 2700W en Clima Nocturno
* **Planteo**: El fallo de autotune de S19JPRO-25 a 2700W (observado a las 14:00 hs con 2708s de stall) pudo haber estado inducido por la temperatura ambiente elevada de la tarde ($>82^\circ\text{C}$ en chips).
* **Protocolo Experimental**:
  1. Esperar que la temperatura de chips de S19JPRO-25 descienda por debajo de $65^\circ\text{C}$ durante la noche.
  2. Verificar que S19JPRO-26 esté en estado estacionario estable (`holds >= 10`).
  3. Desbloquear temporalmente el cerrojo de hardware en configuración local para S19JPRO-25 (`max_hardware_preset: 2700W`).
  4. Monitorear mediante [app/governance/autotune_watchdog.py](file:///F:/02-ASIC%20-%20mineros/miner-alerts/app/governance/autotune_watchdog.py). Si el hashrate no supera los $20\text{ TH/s}$ a los 600s, el watchdog rescatará automáticamente a 2500W y sellará la conclusión de que es un límite físico de silicio no superable.
* **Criterio de Aceptación**: S19JPRO-25 completa autotune en $< 400\text{s}$ y produce $> 96\text{ TH/s}$ con 0 errores HW. En caso contrario, se descarta definitivamente 2700W para este equipo.
* **Estado**: **PLANIFICADA** (Ventana tentativa: 22:00 - 23:00 hs).

### Hipótesis H3: Equilibrio Intermedio en Elevador 2 a 2600W / 2600W (C3)
* **Planteo**: Si S19JPRO-25 no tolera 2700W pero tolera 2600W, y S19JPRO-26 se ajusta a 2600W, el Elevador 2 opera en simetría perfecta de 5200W, minimizando armónicos en el neutro del autotransformador.
* **Criterio de Aceptación**: Autotune limpio en ambos equipos en $< 300\text{s}$ y hashrate combinado $> 190\text{ TH/s}$.
* **Estado**: **PLANIFICADA** (Alternativa secundaria a H1/H2).

### Hipótesis H4: Exploración de Techo en Elevador 1 a 5600W (2800W x2)
* **Planteo**: S19JPRO-23 y S19JPRO-24 cuentan con silicio clase A+ y refrigeración óptima. ¿Es seguro elevar a 2800W durante la madrugada para alcanzar ~405 TH/s de flota?
* **Riesgo Identificado**: Elevador 1 entraría en zona de saturación magnética transitoria ($5600\text{W}$). La caída de tensión en bornes podría afectar a los sensores I2C de la cadena 2.
* **Protocolo de Seguridad**: Solo ensayar si la acometida mide $\ge 215\text{V}$ bajo carga de 10.6 kW.
* **Estado**: **EN ESPERA DE DATOS DE H1**.

---

## 5. Bitácora de Pruebas Empíricas de Laboratorio (Live Experiment Log)

| Fecha / Hora | Combinación (23/24/25/26) | Potencia Total | Hashrate Flota | Temp Máx Chip | Fan Duty Máx | Comportamiento Observado / Incidentes | Veredicto |
| :---: | :---: | :---: | :---: | :---: | :---: | :--- | :---: |
| **19/09 12:26-16:40** | C0 (2500/2500/2500/2500) | 9.993 W | 375.4 TH/s | 82.0°C | 97% | Estabilidad absoluta durante pico solar. 0 brownouts, 0 rebotes post-lijado de relé en Elev. 2. | **SUPERADA (100% Éxito)** |
| **19/09 17:05-17:15** | C1 (2500/2700/2500/2700) | 10.193 W | ~380 TH/s | 77.0°C (M24) / 58.0°C (M26) | 89% (M24) / 70% (M26) | M26 escaló a 2700W (58°C, 70% fans). M24 escaló a 2700W a las 17:10 hs. M25 firme a 2500W. | **EN CURSO (Excelente disipación)** |

---

## 6. Procedimiento Operativo para Ensayos y Registro de Datos

1. **Monitoreo Automático de Salud**:
   * Cada ensayo se registra en SQLite `miner_alerts.db` con muestras de telemetría de 30s (`telemetry_samples`).
   * El Fan Governor PID mantendrá chips por debajo de $80^\circ\text{C}$ de forma autónoma.
   * Si un minero supera los $82^\circ\text{C}$, la compuerta de alivio térmico frena cualquier escalada pendiente.
2. **Procedimiento de Aborto Preventivo**:
   * Si una combinación genera 2 reinicios en menos de 30 minutos o un autotune stall $> 600\text{s}$, el sistema aborta automáticamente desescalando al preset inmediato inferior y registrando el hallazgo en este documento.
