# Contrato Técnico: Vnish Fan Governor & REST Client

## 1. Contrato de la API REST de Vnish

### 1.1 Autenticación (`POST /api/v1/unlock`)
- **Endpoint**: `POST http://<miner_host>/api/v1/unlock`
- **Headers**: `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "pw": "admin"
  }
  ```
- **Response Exitosa (HTTP 200)**:
  ```json
  {
    "token": "r11CLdycJmTymBIwUrT9V0gnfIIweHDH"
  }
  ```
- **Timeout Requerido**: 3.0 segundos.
- **Manejo de Errores**: HTTP 401 (Credencial inválida), HTTP 404/500, Timeout/ConnectionError.

### 1.2 Lectura de Estado de Enfriamiento (`GET /api/v1/summary` y `GET /api/v1/settings`)
- **Headers**: `Authorization: Bearer <token>`
- **Lectura Rápida (Sin Auth)**: `GET /api/v1/summary` -> extrae `miner.cooling.settings.mode.name` y `miner.cooling.fan_duty`.
- **Lectura Autenticada**: `GET /api/v1/settings` -> extrae `miner.cooling`:
  ```json
  {
    "mode": {
      "name": "manual",
      "param": 100
    },
    "fan_min_count": 4,
    "fan_min_duty": 40,
    "fan_max_duty": 100
  }
  ```

### 1.3 Modulación de Velocidad de Ventiladores (`POST /api/v1/settings`)
- **Headers**: `Authorization: Bearer <token>`, `Content-Type: application/json`
- **Payload Atómico**:
  ```json
  {
    "miner": {
      "cooling": {
        "mode": {
          "name": "manual",
          "param": 85
        }
      }
    }
  }
  ```
- **Response Exitosa (HTTP 200)**:
  ```json
  {
    "status": "ok"
  }
  ```
- **Invariante**: Solo se envía el bloque `miner.cooling.mode`, preservando intactos los demás parámetros de overclock, pools y red.

### 1.4 Bloqueo de Sesión (`POST /api/v1/lock`)
- **Headers**: `Authorization: Bearer <token>`
- **Response Exitosa (HTTP 200)**:
  ```json
  {
    "status": "ok"
  }
  ```
- **Garantía**: Debe invocarse siempre en un bloque `try ... finally` para garantizar que la sesión HTTP no quede abierta en el minero.

---

## 2. Contrato de Datos del Gobernador (`app/fan_governor.py`)

### 2.1 Modelo de Configuración (`GovernorConfig`)
```python
@dataclass(frozen=True)
class GovernorConfig:
    enabled: bool = False
    dry_run: bool = True
    target_temp_c: float = 82.0
    deadband_low_c: float = 81.0
    deadband_high_c: float = 82.5
    emergency_spike_temp_c: float = 83.0
    min_fan_duty_percent: int = 70
    max_fan_duty_percent: int = 100
    step_down_percent: int = 2
    step_up_percent: int = 3
    dwell_seconds: int = 90
    request_timeout_seconds: float = 3.0
```

### 2.2 Evaluación de Acción de Control (`GovernorDecision`)
Dado:
- $T_{max}$: Temperatura máxima actual de chips (°C).
- $Duty_{current}$: Porcentaje de PWM actual (0-100).
- $\Delta t$: Segundos transcurridos desde el último cambio de duty en este minero.

Reglas deterministas de decisión:
1. **Regla de Emergencia**:
   - Si $T_{max} \ge 83.0^\circ\text{C}$ y $Duty_{current} < 100$:
     - Acción: `EMERGENCY_SPIKE`
     - Nuevo Duty: $100\%$
     - Reset de dwell time: Inmediato.
2. **Regla de Asentamiento (Dwell)**:
   - Si $\Delta t < \text{dwell\_seconds}$ (y no es emergencia):
     - Acción: `HOLD_DWELL`
     - Nuevo Duty: $Duty_{current}$
3. **Regla de Calentamiento Moderado**:
   - Si $T_{max} > 82.5^\circ\text{C}$ y $T_{max} < 83.0^\circ\text{C}$:
     - Acción: `STEP_UP`
     - Nuevo Duty: $\min(100, Duty_{current} + \text{step\_up\_percent})$
4. **Regla de Banda Muerta (Estabilidad Óptima)**:
   - Si $81.0^\circ\text{C} \le T_{max} \le 82.5^\circ\text{C}$:
     - Acción: `HOLD_TARGET`
     - Nuevo Duty: $Duty_{current}$
5. **Regla de Enfriamiento / Reducción Acústica**:
   - Si $T_{max} < 81.0^\circ\text{C}$:
     - Acción: `STEP_DOWN`
     - Nuevo Duty: $\max(\text{min\_fan\_duty\_percent}, Duty_{current} - \text{step\_down\_percent})$

---

## 3. Estado Persistido del Gobernador (`app/state.json`)

En `app/state.json` se persiste por cada minero:
```json
{
  "fan_governor": {
    "last_adjustment_ts": 1788883200.0,
    "last_action": "STEP_DOWN",
    "last_target_duty": 92,
    "consecutive_holds": 4,
    "emergency_trips_24h": 0
  }
}
```
Invariante: La persistencia se realiza bajo el mutex `state_lock` con copias inmutables (`list(states.items())`).
