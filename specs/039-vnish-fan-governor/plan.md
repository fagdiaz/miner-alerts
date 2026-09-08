# Implementation Plan: Spec 039 - Vnish Thermal & Acoustic Fan Governor

## 1. Arquitectura y Módulos

```
   +-------------------------------------------------------------+
   |                Telegram User Interface                      |
   |   /fans (modo visible) | /gov (estado) | /gov set | /gov on/off |
   +------------------------------+------------------------------+
                                  |
                                  v
   +-------------------------------------------------------------+
   |                     app/miner_monitor.py                    |
   |              Authoritative Polling (API 4028)               |
   |                 + Telemetry Ingestion Pipeline              |
   +--------------+-------------------------------+--------------+
                  |                               |
                  v                               v
   +------------------------------+ +------------------------------+
   |      app/fan_health.py       | |      app/fan_governor.py     |
   | - Parse fan_mode & fan_pwm   | | - Thermal Governor Algorithm |
   | - Headroom & Warning Streaks | | - Dwell time & Spike Override|
   | - Format /fans output        | | - Step calculations          |
   +------------------------------+ +--------------+---------------+
                                                  |
                                                  v
                                    +------------------------------+
                                    |     app/vnish_client.py      |
                                    | - POST /unlock (Bearer token)|
                                    | - GET /settings (read-only)  |
                                    | - POST /settings (atomic PWM)|
                                    | - POST /lock (session close) |
                                    +--------------+---------------+
                                                   | HTTP (3s timeout)
                                                   v
                                    +------------------------------+
                                    |   Vnish Firmware (Miners)    |
                                    |   192.168.100.23 .. 26:80    |
                                    +------------------------------+
```

---

## 2. Fases de Implementación

### Fase 1: Detección y Visibilidad de Modo (Quick Win - Cero Escritura)
- Modificar `app/vnish_telemetry.py` para capturar `fan_mode` (`1 = manual`, `0 = auto`) y `fan_pwm` desde los payloads STATS de la API 4028.
- Modificar `app/fan_health.py` para incluir `fan_mode: str` (`"MANUAL"`, `"AUTO"`, `"IMMERS"`) en `CoolingAssessment`.
- Actualizar `build_fans_table_text` y `build_miner_fan_detail_text` para renderizar el modo actual en Telegram:
  `S19JPRO-23: 78°C | 5.8k-6.0k RPM | PWM: 100% (MANUAL)`
- **Riesgo**: Nulo (solo lectura, sin interacción con hardware).

### Fase 2: Cliente HTTP Vnish REST (`app/vnish_client.py`)
- Crear módulo desacoplado puro `app/vnish_client.py`.
- Funciones:
  - `unlock_miner(host, password, timeout=3.0) -> Optional[str]`
  - `lock_miner(host, token, timeout=3.0) -> bool`
  - `get_cooling_settings(host, token, timeout=3.0) -> Optional[dict]`
  - `set_manual_fan_duty(host, token, duty_percent, timeout=3.0) -> bool`
  - `safe_set_fan_duty(host, password, duty_percent) -> bool`: Wrapper que ejecuta unlock -> set -> lock en bloque `try ... finally`.
- Manejo de excepciones, timeouts cortos (3.0s) y redacción de contraseñas.

### Fase 3: Algoritmo Regulador Térmico (`app/fan_governor.py`)
- Función pura `compute_governor_step(...) -> GovernorDecision`:
  - Entrada: $T_{max}$, $Duty_{current}$, $\Delta t_{dwell}$, configuración.
  - Salida: `action`, `target_duty`, `reason`.
- Cero dependencias de sockets ni I/O; 100% testeable de forma determinista.
- Disparo de emergencia a 100% ante $T \ge 83.0^\circ\text{C}$.

### Fase 4: Integración en Monitor y Comandos Telegram
- Hook en `app/miner_monitor.py` ejecutado al final de cada ciclo de adquisición sólo si `fan_governor_enabled == True`.
- Modo inicial `fan_governor_dry_run: True` (registra la decisión en logs sin escribir en hardware).
- Comandos Telegram: `/governor` (estado), `/gov set <temp>`, `/gov on`, `/gov off`.
- Entrada de configuración en `app/config.example.json`.

### Fase 5: Suite de Tests y Certificación
- Tests unitarios de telemetría de modo (`test_vnish_telemetry_fan_mode.py`).
- Tests unitarios del cliente HTTP con mocks (`test_vnish_client.py`).
- Tests unitarios deterministas del algoritmo del gobernador (`test_fan_governor.py`).
- Tests de concurrencia y timeouts (`test_fan_governor_concurrency.py`).

---

## 3. Matriz de Riesgos y Mitigaciones

| Riesgo Identificado | Impacto | Probabilidad | Mitigación Arquitectónica |
| :--- | :--- | :--- | :--- |
| **Oscilación Térmica (*Hunting*)** | Medio | Media | Banda muerta de 1.5°C ($[81.0, 82.5]^\circ\text{C}$) y tiempo de asentamiento (*dwell*) de 90s entre pasos. |
| **Retardo en Disipación y Downclock Vnish** | Alto | Baja | Target en 82.0°C (margen de 2°C antes de los 84°C) y salto defensivo inmediato a 100% ante $\ge 83.0^\circ\text{C}$. |
| **Bloqueo del Monitor por Timeout HTTP** | Crítico | Baja | Timeout estricto de 3.0s por minero, ejecutor desacoplado y captura defensiva de excepciones. |
| **Fuga de Credenciales Vnish** | Crítico | Baja | Contraseña cargada desde `app/config.json` (no trackeado), redacción en logs con asteriscos (`admin` -> `***`). |
| **Desconexión o Reinicio del Minero** | Medio | Baja | Sesión desbloqueada se re-autentica en cada modulación; `lock` asegurado con `finally`. Si el minero no responde, continúa en su último duty de hardware. |
