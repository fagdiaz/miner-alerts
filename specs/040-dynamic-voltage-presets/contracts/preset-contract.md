# Contrato de Datos y API: Spec 040 - Dynamic Power & Preset Balancer

## 1. Escalera Estándar de Presets Vnish (Antminer S19j Pro)

```
Nivel 0: 1600W (~68 TH/s)  [Modo Ultra-Eco / Resguardo de Red]
Nivel 1: 1740W (~72 TH/s)  [Modo Bajo Consumo]
Nivel 2: 1900W (~78 TH/s)  [Modo Eficiente]
Nivel 3: 2100W (~83 TH/s)  [Modo Intermedio]
Nivel 4: 2300W (~88 TH/s)  [Modo Balanceado]
Nivel 5: 2500W (~93 TH/s)  [Modo Rendimiento Seguro]
Nivel 6: 2700W (~98 TH/s)  [Modo Alto Rendimiento]
Nivel 7: 2800W (~102 TH/s) [Modo Extremo / Requiere Elevador Muy Estable]
```

---

## 2. Modelos de Datos en Dominio Puro (`app/preset_balancer.py`)

### 2.1 Estructura del Preset (`PresetTier`)
```python
@dataclass(frozen=True)
class PresetTier:
    name: str              # Ej: "2500W", "2700W"
    nominal_power_w: int   # Consumo estimado en Watts
    nominal_ths: float     # Hashrate esperado
    order: int             # Índice en la escalera (0 a 7)
```

### 2.2 Métricas de Estabilidad (`StabilityMetrics`)
```python
@dataclass(frozen=True)
class StabilityMetrics:
    miner_name: str
    electrical_group: str          # Ej: "elevator_1", "elevator_2"
    current_preset: str
    restarts_24h: int              # Cantidad de reinicios en las últimas 24 horas
    restarts_72h: int              # Cantidad de reinicios en las últimas 72 horas
    hours_since_last_restart: float# Horas continuas sin reinicio
    avg_hashrate_24h_ths: float    # Hashrate promedio real registrado
    downtime_minutes_24h: float    # Minutos acumulados con hashrate = 0 TH/s
    thermal_headroom_c: float      # Margen térmico actual hacia los 85.0°C
```

### 2.3 Configuración del Balanceador (`BalancerConfig`)
```python
@dataclass(frozen=True)
class BalancerConfig:
    enabled: bool = False
    dry_run: bool = True
    restarts_threshold_step_down: int = 2     # >= 2 reinicios en 24h fuerza desescalado
    soak_hours_step_up: float = 72.0          # Requiere 72h continuas para subir preset
    group_cascade_threshold: int = 2          # 2 mineros en mismo elevador en <30m
    group_cascade_window_s: float = 1800.0    # 30 minutos
    min_thermal_headroom_c: float = 4.0       # Mínimo 4°C libres hacia 85°C para step-up
    default_max_preset: str = "2700W"         # Límite superior por defecto
```

### 2.4 Decisión del Balanceador (`BalancerDecision`)
```python
@dataclass(frozen=True)
class BalancerDecision:
    action: str            # "HOLD_STABLE", "STEP_DOWN_RESTARTS", "STEP_DOWN_CASCADE", "STEP_UP_OPTIMIZE", "LOCKED_MAX"
    miner_name: str
    electrical_group: str
    current_preset: str
    target_preset: str
    reason: str
    requires_write: bool
```

---

## 3. Función Objetivo de Costo/Beneficio

El algoritmo cuantifica el **Hashrate Neto Efectivo** ($H_{\text{eff}}$) de un minero en un preset $P_i$:

$$H_{\text{eff}}(P_i) = H_{\text{nominal}}(P_i) \times \left(1 - \frac{T_{\text{reboot}} \times N_{\text{restarts}}}{24 \times 60}\right) - C_{\text{penalty}} \times N_{\text{restarts}}$$

Donde:
- $T_{\text{reboot}}$: Tiempo medio de recuperación por reinicio (estimado en 10 minutos).
- $C_{\text{penalty}}$: Penalización por degradación de hardware y riesgo de sobrecarga al elevador (equivalente a 2.0 TH/s virtuales por evento).

**Ejemplo Práctico de Decisión**:
- **Escenario A (Forzado a 2700W)**:
  $H_{\text{nominal}} = 98\text{ TH/s}$. Supongamos que por tensión sensible sufre 3 reinicios diarios:
  $Downtime = 30\text{ min} = 2.08\%$.
  $H_{\text{eff}} = 98 \times (1 - 0.0208) - (2.0 \times 3) = 95.96 - 6.0 = \mathbf{89.96\text{ TH/s}}$.
- **Escenario B (Calibrado a 2500W)**:
  $H_{\text{nominal}} = 93\text{ TH/s}$. Alivio en el elevador: 0 reinicios diarios.
  $H_{\text{eff}} = 93 \times (1 - 0) - 0 = \mathbf{93.00\text{ TH/s}}$.

**Resultado del Modelo**: Calibrar a 2500W produce **+3.04 TH/s netos reales**, cero estrés en el elevador y elimina los micro-cortes.

---

## 4. Contrato REST Vnish para Presets

### 4.1 Lectura de Presets Disponibles
- **Endpoint**: `GET http://<host>/api/v1/presets`
- **Headers**: `Authorization: Bearer <token>`
- **Respuesta 200 OK**:
  ```json
  [
    {"name": "1600W", "power": 1600, "nominal_rate": 68.0},
    {"name": "2300W", "power": 2300, "nominal_rate": 88.0},
    {"name": "2500W", "power": 2500, "nominal_rate": 93.0},
    {"name": "2700W", "power": 2700, "nominal_rate": 98.0}
  ]
  ```

### 4.2 Modificación de Preset Activo
- **Endpoint**: `POST http://<host>/api/v1/settings`
- **Headers**: `Authorization: Bearer <token>`, `Content-Type: application/json`
- **Payload**:
  ```json
  {
    "miner": {
      "overclock": {
        "preset": "2500W"
      }
    }
  }
  ```
- **Respuesta 200 OK**: Confirmación de aplicación en caliente.
