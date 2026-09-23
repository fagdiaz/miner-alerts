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

# Spec 063: Ambient-Aware Thermal PID Modes
SEASONAL_MODE_WINTER = "WINTER"
SEASONAL_MODE_STANDARD = "STANDARD"
SEASONAL_MODE_SUMMER = "SUMMER"


@dataclass(frozen=True)
class GovernorConfig:
    enabled: bool = False
    dry_run: bool = True
    target_temp_c: float = 82.0
    deadband_low_c: float = 81.0
    deadband_high_c: float = 82.5
    emergency_spike_temp_c: float = 83.0
    min_fan_duty_percent: int = 30           # Safe hardware minimum floor (30%)
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
    # Spec 063: Ambient-Aware Thermal PID (GOV-02)
    seasonal_enabled: bool = True
    winter_ambient_threshold_c: float = 18.0
    summer_ambient_threshold_c: float = 28.0
    winter_target_temp_c: float = 76.0
    winter_min_duty_percent: int = 45
    summer_target_temp_c: float = 80.0
    summer_min_duty_percent: int = 65
    summer_step_up_percent: int = 5
    power_floor_2700w: int = 70
    power_floor_2500w: int = 60
    power_floor_2300w: int = 50
    power_floor_1800w: int = 40
    recovery_max_cooling_timeout_seconds: float = 900.0


@dataclass(frozen=True)
class SeasonalGovernorParams:
    mode: str
    ambient_temp_c: Optional[float]
    target_temp_c: float
    deadband_low_c: float
    deadband_high_c: float
    min_duty_percent: int
    step_up_percent: int


@dataclass(frozen=True)
class GovernorDecision:
    action: str
    target_duty: int
    current_duty: int
    reason: str
    dwell_effective: int
    is_emergency: bool = False
    requires_write: bool = False
    seasonal_mode: Optional[str] = None


def resolve_seasonal_parameters(
    ambient_temp_c: Optional[float],
    config: Optional[GovernorConfig] = None,
) -> SeasonalGovernorParams:
    """
    Pure functional resolution of seasonal temperature targets and fan curves.
    Enforces 3 inviolable safety invariants:
    1. effective_target_temp_c <= 82.0°C (Never elevate chip target above 82°C)
    2. effective_min_duty_percent >= 30% (Never lower floor below hardware safe minimum)
    3. Emergency thermal spike is preserved externally in compute_governor_step
    """
    cfg = config or GovernorConfig()

    # Fallback to standard if seasonal disabled, no ambient telemetry, or sensor invalid
    if (
        not cfg.seasonal_enabled
        or ambient_temp_c is None
        or not (-10.0 <= ambient_temp_c <= 60.0)
    ):
        target = min(cfg.target_temp_c, 82.0)
        dead_high = min(cfg.deadband_high_c, 82.5)
        dead_low = min(cfg.deadband_low_c, dead_high - 0.5)
        min_duty = max(30, cfg.min_fan_duty_percent)
        return SeasonalGovernorParams(
            mode=SEASONAL_MODE_STANDARD,
            ambient_temp_c=ambient_temp_c if (ambient_temp_c is not None and -10.0 <= ambient_temp_c <= 60.0) else None,
            target_temp_c=target,
            deadband_low_c=dead_low,
            deadband_high_c=dead_high,
            min_duty_percent=min_duty,
            step_up_percent=cfg.step_up_percent,
        )

    # 1. Winter Mode: T_amb < winter_ambient_threshold_c (default 18°C)
    if ambient_temp_c < cfg.winter_ambient_threshold_c:
        mode = SEASONAL_MODE_WINTER
        target = min(cfg.winter_target_temp_c, 82.0)
        dead_low = target - 1.0
        dead_high = target + 1.0
        min_duty = max(30, cfg.winter_min_duty_percent)
        step_up = cfg.step_up_percent

    # 2. Summer Mode: T_amb > summer_ambient_threshold_c (default 28°C)
    elif ambient_temp_c > cfg.summer_ambient_threshold_c:
        mode = SEASONAL_MODE_SUMMER
        target = min(cfg.summer_target_temp_c, 82.0)
        dead_low = target - 1.0
        dead_high = target + 1.0
        min_duty = max(30, cfg.summer_min_duty_percent)
        step_up = max(cfg.step_up_percent, cfg.summer_step_up_percent)

    # 3. Standard Mode: winter_ambient_threshold_c <= T_amb <= summer_ambient_threshold_c
    else:
        mode = SEASONAL_MODE_STANDARD
        target = min(cfg.target_temp_c, 82.0)
        dead_high = min(cfg.deadband_high_c, 82.5)
        dead_low = min(cfg.deadband_low_c, dead_high - 0.5)
        min_duty = max(30, cfg.min_fan_duty_percent)
        step_up = cfg.step_up_percent

    # Inviolable Invariant 1: target <= 82.0°C and deadband_high <= 82.5°C
    target = min(target, 82.0)
    dead_high = min(dead_high, 82.5)
    dead_low = min(dead_low, dead_high - 0.5)
    # Inviolable Invariant 2: min_duty >= 30%
    min_duty = max(30, min_duty)

    return SeasonalGovernorParams(
        mode=mode,
        ambient_temp_c=ambient_temp_c,
        target_temp_c=target,
        deadband_low_c=dead_low,
        deadband_high_c=dead_high,
        min_duty_percent=min_duty,
        step_up_percent=step_up,
    )


def resolve_power_fan_floor(
    current_power_w: Optional[float],
    target_power_w: Optional[float] = None,
    is_warming_up: bool = False,
    floor_2700w: Optional[int] = None,
    floor_2500w: Optional[int] = None,
    floor_2300w: Optional[int] = None,
    floor_1800w: Optional[int] = None,
) -> int:
    """Determine physical minimum fan duty to prevent thermal runaway when hashing.
    
    When an ASIC draws 2400W-2700W, running fans at 30%-60% causes rapid chip heating
    (>0.5°C/s) leading to emergency thermal tripwires (84°C-86°C).
    Floor is strictly based on real consumed power (current_power_w).
    """
    f2700 = floor_2700w if floor_2700w is not None else 70
    f2500 = floor_2500w if floor_2500w is not None else 60
    f2300 = floor_2300w if floor_2300w is not None else 50
    f1800 = floor_1800w if floor_1800w is not None else 40

    if current_power_w is None or current_power_w < 500.0:
        return 30
    if is_warming_up and current_power_w < 1700.0:
        return 30
    if current_power_w >= 2600.0:
        return max(30, f2700)
    elif current_power_w >= 2400.0:
        return max(30, f2500)
    elif current_power_w >= 2100.0:
        return max(30, f2300)
    elif current_power_w >= 1700.0:
        return max(30, f1800)
    return 30


def compute_governor_step(
    max_temp_c: Optional[float],
    current_duty: Optional[int],
    seconds_since_last_change: float,
    consecutive_holds: int = 0,
    consecutive_failures: int = 0,
    config: Optional[GovernorConfig] = None,
    current_power_w: Optional[float] = None,
    target_power_w: Optional[float] = None,
    ambient_temp_c: Optional[float] = None,
    is_warming_up: bool = False,
    boost_cooling: bool = False,
    recovery_cooling_seconds: float = 0.0,
) -> GovernorDecision:
    """
    Pure mathematical decision engine for Vnish closed-loop fan modulation.
    Determines whether to step down, step up, hold, or trigger emergency spike.
    Zero side-effects, zero I/O, 100% deterministic and testable.
    """
    cfg = config or GovernorConfig()
    seasonal = resolve_seasonal_parameters(ambient_temp_c, cfg)

    pwr_floor = resolve_power_fan_floor(
        current_power_w,
        target_power_w,
        is_warming_up=is_warming_up,
        floor_2700w=cfg.power_floor_2700w,
        floor_2500w=cfg.power_floor_2500w,
        floor_2300w=cfg.power_floor_2300w,
        floor_1800w=cfg.power_floor_1800w,
    )
    eff_min_duty = min(
        cfg.max_fan_duty_percent,
        max(30, cfg.min_fan_duty_percent, pwr_floor, seasonal.min_duty_percent),
    )
    raw_duty = int(current_duty) if current_duty is not None else cfg.max_fan_duty_percent
    curr_duty = max(eff_min_duty, min(cfg.max_fan_duty_percent, raw_duty))

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
            seasonal_mode=seasonal.mode,
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
            requires_write=(raw_duty < cfg.max_fan_duty_percent),
            seasonal_mode=seasonal.mode,
        )

    # 3. P0: Emergency Thermal Spike (T >= emergency_spike_temp_c) — Inviolable Safety Invariant
    if max_temp_c >= cfg.emergency_spike_temp_c:
        needs_write = raw_duty != cfg.max_fan_duty_percent
        return GovernorDecision(
            action=ACTION_EMERGENCY_SPIKE,
            target_duty=cfg.max_fan_duty_percent,
            current_duty=curr_duty,
            reason=f"Pico térmico ({max_temp_c:.1f}°C >= {cfg.emergency_spike_temp_c:.1f}°C): salto a 100%",
            dwell_effective=0,
            is_emergency=True,
            requires_write=needs_write,
            seasonal_mode=seasonal.mode,
        )

    # 4. Out-of-bounds ceiling clamp: if hardware is currently running above max ceiling (e.g. at silent mode activation),
    # immediately step down to acoustic ceiling without waiting for dwell.
    if raw_duty > cfg.max_fan_duty_percent:
        return GovernorDecision(
            action=ACTION_STEP_DOWN,
            target_duty=cfg.max_fan_duty_percent,
            current_duty=raw_duty,
            reason=f"Exceso sobre techo acústico/máximo ({raw_duty}% > {cfg.max_fan_duty_percent}%): limitando a {cfg.max_fan_duty_percent}%",
            dwell_effective=cfg.dwell_seconds,
            is_emergency=False,
            requires_write=True,
            seasonal_mode=seasonal.mode,
        )

    # 5. Out-of-bounds floor clamp: if hardware is currently below min floor, immediately step up to floor
    if raw_duty < eff_min_duty:
        return GovernorDecision(
            action=ACTION_STEP_UP,
            target_duty=eff_min_duty,
            current_duty=raw_duty,
            reason=f"Por debajo del piso mínimo ({raw_duty}% < {eff_min_duty}%): elevando a {eff_min_duty}%",
            dwell_effective=cfg.dwell_seconds,
            is_emergency=False,
            requires_write=True,
            seasonal_mode=seasonal.mode,
        )

    # 6. Autoswitch Recovery / Power Deficit Protection:
    # If miner is hashing below its established autoswitch ceiling (e.g. 2300W < 2500W or 2700W),
    # fans MUST be at 100% to lower chip temp <= 79°C and allow Vnish autoswitch to step up.
    # We NEVER modulate fans down when the miner is working under its power limit!
    # Guard 1: Do not trigger 100% cooling when miner is warming up post-reboot or has not started hashing (<500W),
    # to allow the ASIC silicon to reach operational temperature without cold-chip autotuning faults.
    # Guard 2 (Safety Timeout): If recovery cooling has exceeded recovery_max_cooling_timeout_seconds (default 900s)
    # and chip temp is within safe operating range (<= deadband_high_c), do not hold 100% indefinitely.
    # Allow the governor to proceed with normal thermal modulation (respecting power fan floors).
    if (
        not is_warming_up
        and target_power_w is not None
        and current_power_w is not None
        and target_power_w > 0
        and current_power_w >= 500.0
    ):
        if current_power_w < (target_power_w - cfg.power_margin_w):
            is_timed_out = (
                recovery_cooling_seconds >= cfg.recovery_max_cooling_timeout_seconds
                and max_temp_c is not None
                and max_temp_c <= seasonal.deadband_high_c
            )
            if not is_timed_out:
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
                    seasonal_mode=seasonal.mode,
                )

    # 6b. Headroom Chilling (Spec 075 / PROP-010):
    # If the balancer requests boost cooling to enable stepping up preset (e.g. from 2500W to 2700W),
    # force fans to 100% PWM to bring chip temperature down without waiting for dwell.
    if boost_cooling and not is_warming_up:
        needs_write = curr_duty < cfg.max_fan_duty_percent
        return GovernorDecision(
            action=ACTION_STEP_UP,
            target_duty=cfg.max_fan_duty_percent,
            current_duty=curr_duty,
            reason="Enfriamiento proactivo (Headroom Chilling) para habilitar escalamiento de potencia",
            dwell_effective=0,
            is_emergency=False,
            requires_write=needs_write,
            seasonal_mode=seasonal.mode,
        )

    # 7. R1: Adaptive Dwell Time calculation
    dwell_effective = (
        cfg.adaptive_dwell_seconds
        if consecutive_holds >= cfg.consecutive_holds_threshold
        else cfg.dwell_seconds
    )
    # Deep cool regime (T <= deadband_low - 5.0): allow agile 60s dwell when not holding deadband
    if max_temp_c is not None and (seasonal.deadband_low_c - max_temp_c) >= 5.0 and consecutive_holds == 0:
        dwell_effective = min(dwell_effective, 60)

    if seconds_since_last_change < dwell_effective:
        return GovernorDecision(
            action=ACTION_HOLD_DWELL,
            target_duty=curr_duty,
            current_duty=curr_duty,
            reason=f"Ventana de asentamiento activa ({seconds_since_last_change:.0f}s < {dwell_effective}s)",
            dwell_effective=dwell_effective,
            is_emergency=False,
            requires_write=False,
            seasonal_mode=seasonal.mode,
        )

    # 8. Moderate heating: Step Up
    if max_temp_c > seasonal.deadband_high_c:
        new_duty = min(cfg.max_fan_duty_percent, curr_duty + seasonal.step_up_percent)
        needs_write = new_duty != curr_duty
        return GovernorDecision(
            action=ACTION_STEP_UP,
            target_duty=new_duty,
            current_duty=curr_duty,
            reason=f"Calentamiento ({max_temp_c:.1f}°C > {seasonal.deadband_high_c:.1f}°C): subiendo PWM a {new_duty}%",
            dwell_effective=dwell_effective,
            is_emergency=False,
            requires_write=needs_write,
            seasonal_mode=seasonal.mode,
        )

    # 9. Deadband stability: Hold Target
    if seasonal.deadband_low_c <= max_temp_c <= seasonal.deadband_high_c:
        return GovernorDecision(
            action=ACTION_HOLD_TARGET,
            target_duty=curr_duty,
            current_duty=curr_duty,
            reason=f"Temperatura en banda objetivo ({max_temp_c:.1f}°C in [{seasonal.deadband_low_c:.1f}, {seasonal.deadband_high_c:.1f}]°C)",
            dwell_effective=dwell_effective,
            is_emergency=False,
            requires_write=False,
            seasonal_mode=seasonal.mode,
        )

    # 10. Cool regime: Adaptive Gradient Step Down
    # Guard: During warmup / post-reboot autotuning, chips are artificially cold because hashing
    # just started or has not started yet. Stepping down fans during warmup causes thermal runaway
    # (heat surge to 86°C) as soon as hashboards reach full power. Hold dwell and preserve fans!
    if is_warming_up:
        return GovernorDecision(
            action=ACTION_HOLD_DWELL,
            target_duty=curr_duty,
            current_duty=curr_duty,
            reason="Fase de calentamiento post-arranque activa: inhibiendo desescalada de ventiladores para prevenir saturación térmica",
            dwell_effective=dwell_effective,
            is_emergency=False,
            requires_write=False,
            seasonal_mode=seasonal.mode,
        )

    delta_cool = seasonal.deadband_low_c - max_temp_c
    if delta_cool >= 5.0:
        # Deep cold regime: agile step-down (-5%)
        eff_step_down = max(cfg.step_down_percent, 5)
    elif delta_cool >= 2.5:
        # Moderate cold regime: intermediate step-down (-3%)
        eff_step_down = max(cfg.step_down_percent, 3)
    else:
        # Fine approach zone: gentle landing (-2%)
        eff_step_down = cfg.step_down_percent

    new_duty = max(eff_min_duty, curr_duty - eff_step_down)
    needs_write = new_duty != curr_duty
    return GovernorDecision(
        action=ACTION_STEP_DOWN,
        target_duty=new_duty,
        current_duty=curr_duty,
        reason=(
            f"Margen térmico disponible ({max_temp_c:.1f}°C < {seasonal.deadband_low_c:.1f}°C, "
            f"delta={delta_cool:.1f}°C): reduciendo PWM a {new_duty}% (-{eff_step_down}%)"
        ),
        dwell_effective=dwell_effective,
        is_emergency=False,
        requires_write=needs_write,
        seasonal_mode=seasonal.mode,
    )
