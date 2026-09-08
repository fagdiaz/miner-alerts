# Implementation Plan: Spec 040 - Dynamic Power & Preset Balancer

## 1. Arquitectura de Módulos

```
   +-------------------------------------------------------------+
   |                Telegram User Interface                      |
   |      /balancer (estado) | /balancer setmax | /balancer on   |
   +------------------------------+------------------------------+
                                  |
                                  v
   +-------------------------------------------------------------+
   |                     app/miner_monitor.py                    |
   |            Authoritative Acquisition & Event Store          |
   |              (Historial de Reinicios y Telemetría)          |
   +--------------+-------------------------------+--------------+
                  |                               |
                  v                               v
   +------------------------------+ +------------------------------+
   |      app/vnish_presets.py    | |    app/preset_balancer.py    |
   | - Telemetría de Frecuencias  | | - Modelo Costo/Beneficio     |
   | - Detección de Downclocking  | | - Hysteresis 72h / 24h       |
   | - Rendimiento y Tensión      | | - Decisión de Desescalado    |
   +------------------------------+ +--------------+---------------+
                                                  |
                                                  v
                                    +------------------------------+
                                    |     app/vnish_client.py      |
                                    | - GET /api/v1/presets        |
                                    | - POST /api/v1/settings      |
                                    |   (overclock: {preset: ...}) |
                                    +--------------+---------------+
                                                   | HTTP (2.5s)
                                                   v
                                    +------------------------------+
                                    |   Vnish Firmware (Miners)    |
                                    +------------------------------+
```

---

## 2. Fases de Implementación

### Fase 1: Extensión de Cliente REST Vnish (`app/vnish_client.py`)
- Añadir métodos:
  - `get_available_presets(host, token, timeout=2.5) -> (bool, list, err)`
  - `set_miner_preset(host, token, preset_name, timeout=2.5) -> (bool, err)`
  - `safe_set_miner_preset(host, password, preset_name, timeout=2.5) -> (bool, err)`
- Tests unitarios con mocks HTTP en `tests/test_vnish_client.py`.

### Fase 2: Motor Matemático Puro (`app/preset_balancer.py`)
- Función pura `evaluate_balancer_step(metrics: StabilityMetrics, config: BalancerConfig, ladder: List[PresetTier], group_metrics: Optional[List[StabilityMetrics]]) -> BalancerDecision`.
- Implementación de reglas:
  - Regla de Desescalado Individual ($\ge 2$ reinicios en 24h -> -1 preset).
  - Regla de Desescalado en Cascada (caída conjunta en el mismo elevador -> -1 preset a todos los mineros del grupo).
  - Regla de Escalado por Estabilidad ($> 72\text{h}$ sin reinicios y margen térmico $\ge 4^\circ\text{C}$ -> +1 preset hasta `max_preset`).
- Cero dependencias de I/O ni red; 100% determinista.

### Fase 3: Suite de Pruebas Unitarias Deterministas (`tests/test_preset_balancer.py`)
- Tests de simulación:
  - Minero en elevador inestable con 3 reinicios -> verifica desescalado de 2700W a 2500W.
  - Minero en 2500W estable durante 80 horas -> verifica propuesta de subida a 2700W.
  - Minero con límite `max_preset: 2500W` -> impide subir a 2700W.
  - Dos mineros en el mismo elevador reiniciándose simultáneamente -> verifica protección de cascada grupal.

### Fase 4: Integración en Monitor y Comandos Telegram
- Ingestión de `electrical_group` en `app/config.json`.
- Extracción de historial de reinicios desde `data/miner_alerts.db` / `state.json`.
- Comando Telegram `/balancer` (alias `/power`) con formateador de tabla por elevador.
- Comandos `/balancer setmax <miner|all> <preset>` y `/balancer on` / `/balancer off`.
- Modo inicial: `preset_balancer_dry_run: true`.

### Fase 5: Concurrencia, Regresiones y Documentación SpecKit
- Verificación de no-bloqueo del tick de 30s.
- Verificación del 100% de la suite global de tests (>560 tests).
- Actualización de `ROADMAP.md` y `DEVELOPMENT_LOG.md`.

---

## 3. Matriz de Riesgos y Mitigaciones

| Riesgo Identificado | Impacto | Probabilidad | Mitigación Arquitectónica |
| :--- | :--- | :--- | :--- |
| **Oscilación entre Presets (*Hunting*)** | Alto | Media | Hysteresis asimétrica: Desescalar con 2 reinicios en 24h, pero exigir 72h continuas de estabilidad para ensayar 1 subida. |
| **Sobrecarga de Hardware por Preset Incompatible** | Crítico | Baja | El balanceador únicamente selecciona nombres válidos de la lista devuelta por `GET /api/v1/presets` del propio equipo. |
| **Corte General de Elevador por Subida Agregada** | Crítico | Baja | Las subidas se realizan de a 1 solo minero por elevador por ventana de 24h (staggered step-up). |
| **Pérdida de Configuración tras Reinicio del Monitor** | Medio | Baja | Persistencia del preset objetivo y timestamps en `state.json` bajo `state_lock`. |
