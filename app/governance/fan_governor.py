from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

ACTION_EMERGENCY_SPIKE = "EMERGENCY_SPIKE"
ACTION_HOLD_DWELL = "HOLD_DWELL"
ACTION_HOLD_TARGET = "HOLD_TARGET"
ACTION_STEP_UP = "STEP_UP"
ACTION_STEP_DOWN = "STEP_DOWN"
ACTION_RECOVERY_MAX_COOLING = "RECOVERY_MAX_COOLING"
ACTION_FAILSAFE_FAULT = "FAILSAFE_FAULT"
ACTION_UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class GovernorConfig:
    enabled: bool = False
    dry_run: bool = True
    target_temp_c: float = 82.0
    deadband_low_c: float = 81.0
    deadband_high_c: float = 82.5
    emergency_spike_temp_c: float = 83.0
    min_fan_duty_percent: int = 75           # R4: Piso elevado a 75%
    max_fan_duty_percent: int = 100
    step_down_percent: int = 2
    step_up_percent: int = 3
    dwell_seconds: int = 90                  # R1: Dwell base 90s
    adaptive_dwell_seconds: int = 120        # R1: Dwell extendido 120s para holds >= 3
    consecutive_holds_threshold: int = 3     # R1: Umbral de estabilización
    request_timeout_seconds: float = 2.5     # R2: Timeout individual
    fleet_timeout_seconds: float = 5.0       # R2: Timeout global flota
    max_consecutive_failures: int = 3        # R3: Fallos antes de fallback a 100%
    power_margin_w: float = 120.0            # Margen bajo target_power_w considerado 'en techo'


@dataclass(frozen=True)
class GovernorDecision:
    action: str
    target_duty: int
    current_duty: int
    reason: str
    dwell_effective: int
    is_emergency: bool = False
    requires_write: bool = False


def compute_governor_step(
    max_temp_c: Optional[float],
    current_duty: Optional[int],
    seconds_since_last_change: float,
    consecutive_holds: int = 0,
    consecutive_failures: int = 0,
    config: Optional[GovernorConfig] = None,
    current_power_w: Optional[float] = None,
    target_power_w: Optional[float] = None,
) -> GovernorDecision:
    """
    Pure mathematical decision engine for Vnish closed-loop fan modulation.
    Determines whether to step down, step up, hold, or trigger emergency spike.
    Zero side-effects, zero I/O, 100% deterministic and testable.
    """
    cfg = config or GovernorConfig()
    curr_duty = int(current_duty) if current_duty is not None else cfg.max_fan_duty_percent
    curr_duty = max(cfg.min_fan_duty_percent, min(cfg.max_fan_duty_percent, curr_duty))

    # 1. Unknown telemetry
    if max_temp_c is None:
        return GovernorDecision(
            action=ACTION_UNKNOWN,
            target_duty=curr_duty,
            current_duty=curr_duty,
            reason="Sin telemetría de temperatura disponible",
            dwell_effective=cfg.dwell_seconds,
            is_emergency=False,
            requires_write=False,
        )

    # 2. R3: Failsafe on consecutive HTTP / hardware failures
    if consecutive_failures >= cfg.max_consecutive_failures:
        return GovernorDecision(
            action=ACTION_FAILSAFE_FAULT,
            target_duty=cfg.max_fan_duty_percent,
            current_duty=curr_duty,
            reason=f"Failsafe defensivo: {consecutive_failures} fallos consecutivos de comunicación",
            dwell_effective=0,
            is_emergency=True,
            requires_write=(curr_duty < cfg.max_fan_duty_percent),
        )

    # 3. P0: Emergency Thermal Spike (T >= 83.0°C)
    if max_temp_c >= cfg.emergency_spike_temp_c:
        needs_write = curr_duty < cfg.max_fan_duty_percent
        return GovernorDecision(
            action=ACTION_EMERGENCY_SPIKE,
            target_duty=cfg.max_fan_duty_percent,
            current_duty=curr_duty,
            reason=f"Pico térmico ({max_temp_c:.1f}°C >= {cfg.emergency_spike_temp_c:.1f}°C): salto a 100%",
            dwell_effective=0,
            is_emergency=True,
            requires_write=needs_write,
        )

    # 4. Autoswitch Recovery / Power Deficit Protection:
    # If miner is hashing below its established autoswitch ceiling (e.g. 2300W < 2500W or 2700W),
    # fans MUST be at 100% to lower chip temp <= 79°C and allow Vnish autoswitch to step up.
    # We NEVER modulate fans down when the miner is working under its power limit!
    if target_power_w is not None and current_power_w is not None and target_power_w > 0:
        if current_power_w < (target_power_w - cfg.power_margin_w):
            needs_write = curr_duty < cfg.max_fan_duty_percent
            return GovernorDecision(
                action=ACTION_RECOVERY_MAX_COOLING,
                target_duty=cfg.max_fan_duty_percent,
                current_duty=curr_duty,
                reason=(
                    f"Bajo potencia objetivo ({current_power_w:.0f}W < {target_power_w:.0f}W): "
                    "100% PWM para permitir subida de autoswitch Vnish"
                ),
                dwell_effective=0,
                is_emergency=False,
                requires_write=needs_write,
            )

    # 4. R1: Adaptive Dwell Time calculation
    dwell_effective = (
        cfg.adaptive_dwell_seconds
        if consecutive_holds >= cfg.consecutive_holds_threshold
        else cfg.dwell_seconds
    )

    if seconds_since_last_change < dwell_effective:
        return GovernorDecision(
            action=ACTION_HOLD_DWELL,
            target_duty=curr_duty,
            current_duty=curr_duty,
            reason=f"Ventana de asentamiento activa ({seconds_since_last_change:.0f}s < {dwell_effective}s)",
            dwell_effective=dwell_effective,
            is_emergency=False,
            requires_write=False,
        )

    # 5. Moderate heating (82.5°C < T < 83.0°C): Step Up (+3%)
    if max_temp_c > cfg.deadband_high_c:
        new_duty = min(cfg.max_fan_duty_percent, curr_duty + cfg.step_up_percent)
        needs_write = new_duty != curr_duty
        return GovernorDecision(
            action=ACTION_STEP_UP,
            target_duty=new_duty,
            current_duty=curr_duty,
            reason=f"Calentamiento ({max_temp_c:.1f}°C > {cfg.deadband_high_c:.1f}°C): subiendo PWM a {new_duty}%",
            dwell_effective=dwell_effective,
            is_emergency=False,
            requires_write=needs_write,
        )

    # 6. Deadband stability (81.0°C <= T <= 82.5°C): Hold Target
    if cfg.deadband_low_c <= max_temp_c <= cfg.deadband_high_c:
        return GovernorDecision(
            action=ACTION_HOLD_TARGET,
            target_duty=curr_duty,
            current_duty=curr_duty,
            reason=f"Temperatura en banda objetivo ({max_temp_c:.1f}°C in [{cfg.deadband_low_c:.1f}, {cfg.deadband_high_c:.1f}]°C)",
            dwell_effective=dwell_effective,
            is_emergency=False,
            requires_write=False,
        )

    # 7. Cool regime (T < 81.0°C): Step Down (-2%)
    new_duty = max(cfg.min_fan_duty_percent, curr_duty - cfg.step_down_percent)
    needs_write = new_duty != curr_duty
    return GovernorDecision(
        action=ACTION_STEP_DOWN,
        target_duty=new_duty,
        current_duty=curr_duty,
        reason=f"Margen térmico disponible ({max_temp_c:.1f}°C < {cfg.deadband_low_c:.1f}°C): reduciendo PWM a {new_duty}%",
        dwell_effective=dwell_effective,
        is_emergency=False,
        requires_write=needs_write,
    )
