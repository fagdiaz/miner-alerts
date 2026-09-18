# Implementation Plan: Spec 075 — Recuperación Suave de Hasheo, Headroom Chilling y Blindaje Anticolapso de Fuentes APW12

## 1. Architectural Overview & Component Structure

Spec 075 introduce un lazo de protección coordinada para evitar los bloqueos por *Latch-Off* en fuentes APW12 y optimizar el rendimiento térmico mediante acoplamiento Balancer ↔ Fan Governor:

```
+-------------------------------------------------------------------------+
|                          SUPERVISOR PRINCIPAL                           |
|                         (app/miner_monitor.py)                          |
+-------------------------------------------------------------------------+
       |                                                |
       v                                                v
+-------------------------------+              +--------------------------+
|      PRESET BALANCER          |  solicitud   |       FAN GOVERNOR       |
| (adaptive_power_balancer.py)  | -----------> |    (fan_governor.py)     |
| - Detecta bloqueo térmico     | boost_chilling| - Fuerza 100% PWM 180s   |
|   a 2500W con fans < 98%      |              |   para desbloquear 2700W |
+-------------------------------+              +--------------------------+
       |
       v
+-------------------------------+
|    SAFE RECOVERY GOVERNOR     |
|   (safe_recovery.py)          |
| - Ventana pasiva settle 120s  |
| - Desescalada pre-reinicio    |
|   (fija 1800W antes de REST)  |
| - Inhibe bucle en CHAIN_FAULT |
+-------------------------------+
       |
       v
+-------------------------------+
|      VNISH REST CLIENT        |
|     (app/vnish/client.py)     |
| - safe_set_miner_preset(1800W)|
| - safe_restart_mining()       |
+-------------------------------+
```

---

## 2. Module Specifications

### 2.1 Nuevo Módulo: `app/governance/safe_recovery.py`
Módulo determinista y funcional encargado de la lógica de decisión de recuperación:
- **`SafeRecoveryState`**:
  ```python
  @dataclass
  class SafeRecoveryState:
      stopped_since_ts: Optional[float] = None
      settle_window_seconds: float = 120.0
      pre_clamp_preset: str = "1800"
      recovery_attempts: int = 0
      max_soft_attempts: int = 1
      is_soft_clamped: bool = False
      original_preset: Optional[str] = None
      boost_chilling_active: bool = False
      boost_chilling_expires_ts: Optional[float] = None
  ```
- **`evaluate_safe_recovery(state, current_ts, miner_status, chain_health)`**:
  Retorna una decisión inmutable `RecoveryDecision` con acciones:
  - `ACTION_WAIT_SETTLE`: Aún en ventana pasiva de 120s.
  - `ACTION_PRE_CLAMP_AND_RESTART`: Ejecutar desescalada a 1800W y luego reinicio suave.
  - `ACTION_HOLD_DEGRADED`: Cadena física en falla persistente, no insistir con reinicios.
  - `ACTION_STAGED_RAMP_UP`: Minero estabilizado en OK, habilitado para subir de preset.

### 2.2 Integración en `app/governance/fan_governor.py`
- Añadir soporte para `boost_cooling: bool = False` en `compute_governor_step`.
- Si `boost_cooling is True`, el governor fuerza `target_duty = 100%` con razón `Enfriamiento proactivo (Headroom Chilling) para desbloqueo de preset`.
- Invariante de seguridad: `EMERGENCY_SPIKE` tiene prioridad absoluta a $T \ge 83.0^\circ\text{C}$.

### 2.3 Integración en `app/miner_monitor.py`
- En el lazo de dos niveles de recuperación de minado:
  * Sustituir la llamada directa a `safe_restart_mining` por la orquestación de recuperación suave:
    1. Comprobar ventana pasiva de 120s.
    2. Si expira y el fallo persiste, aplicar pre-clamp a 1800W con `clamp_top_preset=True`.
    3. Disparar `safe_restart_mining`.
    4. Proteger contra bucles si la falla es de hardware (`CHAIN_FAULT`).
- En la coordinación Balancer ↔ Governor:
  * Conectar la bandera de solicitud de enfriamiento cuando un minero califica para subir a 2700W pero tiene $80.5^\circ\text{C} \le T \le 82.0^\circ\text{C}$.

---

## 3. Verification & Safety Protocol

1. **Suite de Pruebas Unitarias Dedicada (`tests/test_safe_recovery.py`)**:
   - Validación de la ventana pasiva de settle (no actúa antes de los 120s).
   - Validación de la desescalada previa a 1800W.
   - Validación de inhibición de reinicios ante fallas físicas de cadena.
   - Validación de la solicitud y expiración de Headroom Chilling.
2. **Suite de Regresión Completa**:
   - Garantizar 1236/1236 tests existentes PASS (100% de éxito, 0 regresiones).
3. **Auditoría Exhaustiva de Concurrencia y Subprocesos**:
   - Revisión y blindaje de cerrojos (`state_lock`, `_SAVE_STATE_LOCK`), llamadas de red fuera de locks, hilos daemon `AutoRestart_{name}` y mutaciones de estado antes de activar en producción.
4. **Herramienta de Respaldo y Restauración de Perfiles**:
   - Implementación de `tools/backup_miner_profiles.py` para respaldar y restaurar matrices completas de chips afinados en `data/miner_profiles/`.
