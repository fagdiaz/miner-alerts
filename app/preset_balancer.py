from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

ACTION_HOLD_STABLE = "HOLD_STABLE"
ACTION_STEP_DOWN_RESTARTS = "STEP_DOWN_RESTARTS"
ACTION_STEP_DOWN_CASCADE = "STEP_DOWN_CASCADE"
ACTION_STEP_UP_OPTIMIZE = "STEP_UP_OPTIMIZE"
ACTION_LOCKED_MAX = "LOCKED_MAX"
ACTION_LOCKED_MIN = "LOCKED_MIN"
ACTION_UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class PresetTier:
    name: str
    nominal_power_w: int
    nominal_ths: float
    order: int


# Standard Vnish overclock ladder for Antminer S19j Pro
DEFAULT_PRESET_LADDER: Tuple[PresetTier, ...] = (
    PresetTier(name="1600W", nominal_power_w=1600, nominal_ths=68.0, order=0),
    PresetTier(name="1740W", nominal_power_w=1740, nominal_ths=72.0, order=1),
    PresetTier(name="1900W", nominal_power_w=1900, nominal_ths=78.0, order=2),
    PresetTier(name="2100W", nominal_power_w=2100, nominal_ths=83.0, order=3),
    PresetTier(name="2300W", nominal_power_w=2300, nominal_ths=88.0, order=4),
    PresetTier(name="2500W", nominal_power_w=2500, nominal_ths=93.0, order=5),
    PresetTier(name="2700W", nominal_power_w=2700, nominal_ths=98.0, order=6),
    PresetTier(name="2800W", nominal_power_w=2800, nominal_ths=102.0, order=7),
)


@dataclass(frozen=True)
class StabilityMetrics:
    miner_name: str
    electrical_group: str              # e.g. "elevator_1", "elevator_2", "default"
    current_preset: str                # e.g. "2700W"
    restarts_24h: int                  # Restarts in last 24 hours
    restarts_72h: int                  # Restarts in last 72 hours
    hours_since_last_restart: float    # Continuous uptime hours without restart
    avg_hashrate_24h_ths: float        # Observed 24h average hashrate
    downtime_minutes_24h: float        # Total downtime minutes in 24h
    thermal_headroom_c: float          # Distance to 85.0°C thermal limit
    last_restart_epoch_s: float = 0.0  # Timestamp of most recent restart


@dataclass(frozen=True)
class BalancerConfig:
    enabled: bool = False
    dry_run: bool = True
    restarts_threshold_step_down: int = 2     # >= 2 restarts in 24h forces step down
    soak_hours_step_up: float = 72.0          # 72 hours without restarts to consider step up
    group_cascade_threshold: int = 2          # 2 miners restarting in group window triggers cascade step down
    group_cascade_window_s: float = 1800.0    # 30-minute cascade correlation window
    min_thermal_headroom_c: float = 4.0       # Minimum headroom below 85°C to allow step up
    default_max_preset: str = "2700W"         # Global default ceiling
    reboot_penalty_ths: float = 2.0           # Penalty per reboot in cost/benefit model


@dataclass(frozen=True)
class BalancerDecision:
    action: str
    miner_name: str
    electrical_group: str
    current_preset: str
    target_preset: str
    reason: str
    requires_write: bool
    estimated_effective_hashrate: float = 0.0


def compute_effective_hashrate(
    nominal_ths: float,
    restarts_count: int,
    reboot_penalty_ths: float = 2.0,
    avg_reboot_downtime_min: float = 10.0,
    window_hours: float = 24.0,
) -> float:
    """
    Calculate Net Effective Hashrate:
    H_eff = H_nominal * (1 - (N_restarts * T_downtime) / (window_hours * 60)) - (N_restarts * penalty)
    """
    total_minutes = max(1.0, window_hours * 60.0)
    downtime_ratio = min(1.0, (restarts_count * avg_reboot_downtime_min) / total_minutes)
    effective = (nominal_ths * (1.0 - downtime_ratio)) - (restarts_count * reboot_penalty_ths)
    return max(0.0, round(effective, 2))


def find_preset_index(preset_name: str, ladder: Optional[List[PresetTier]] = None) -> int:
    """Find index in ladder by name. Returns -1 if not found."""
    tiers = ladder or list(DEFAULT_PRESET_LADDER)
    clean = str(preset_name).strip().upper()
    for idx, tier in enumerate(tiers):
        if tier.name.upper() == clean or tier.name.upper() in clean:
            return idx
    return -1


def evaluate_balancer_step(
    metrics: StabilityMetrics,
    config: Optional[BalancerConfig] = None,
    ladder: Optional[List[PresetTier]] = None,
    group_metrics: Optional[List[StabilityMetrics]] = None,
    max_preset_override: Optional[str] = None,
) -> BalancerDecision:
    """
    Pure mathematical decision engine for Dynamic Power & Preset Balancer.
    Calculates whether to step down, step up, or hold current preset based on
    voltage sensitivity, restart frequency, and thermal headroom.
    Zero side-effects, zero I/O, 100% testable.
    """
    cfg = config or BalancerConfig()
    tiers = ladder or list(DEFAULT_PRESET_LADDER)
    curr_idx = find_preset_index(metrics.current_preset, tiers)

    if curr_idx < 0:
        return BalancerDecision(
            action=ACTION_UNKNOWN,
            miner_name=metrics.miner_name,
            electrical_group=metrics.electrical_group,
            current_preset=metrics.current_preset,
            target_preset=metrics.current_preset,
            reason=f"Preset actual '{metrics.current_preset}' desconocido en la escalera",
            requires_write=False,
            estimated_effective_hashrate=metrics.avg_hashrate_24h_ths,
        )

    current_tier = tiers[curr_idx]
    ceiling_name = max_preset_override or cfg.default_max_preset
    ceiling_idx = find_preset_index(ceiling_name, tiers)
    if ceiling_idx < 0:
        ceiling_idx = len(tiers) - 1

    eff_current = compute_effective_hashrate(
        nominal_ths=current_tier.nominal_ths,
        restarts_count=metrics.restarts_24h,
        reboot_penalty_ths=cfg.reboot_penalty_ths,
    )

    # 1. Check Group Cascade Condition
    # If other miners in the same electrical group had restarts recently,
    # the entire group steps down to relieve the sensitive voltage elevator.
    if group_metrics and metrics.electrical_group != "default":
        recent_peer_restarts = 0
        for peer in group_metrics:
            if peer.miner_name != metrics.miner_name and peer.electrical_group == metrics.electrical_group:
                if peer.restarts_24h >= 1 and peer.hours_since_last_restart < (cfg.group_cascade_window_s / 3600.0):
                    recent_peer_restarts += 1

        if recent_peer_restarts >= 1 and metrics.restarts_24h >= 1:
            if curr_idx > 0:
                target_tier = tiers[curr_idx - 1]
                return BalancerDecision(
                    action=ACTION_STEP_DOWN_CASCADE,
                    miner_name=metrics.miner_name,
                    electrical_group=metrics.electrical_group,
                    current_preset=current_tier.name,
                    target_preset=target_tier.name,
                    reason=f"Caída en cascada en elevador '{metrics.electrical_group}': {recent_peer_restarts} par(es) caídos",
                    requires_write=True,
                    estimated_effective_hashrate=eff_current,
                )

    # 2. Individual Step-Down: restarts in last 24h exceed threshold
    if metrics.restarts_24h >= cfg.restarts_threshold_step_down:
        if curr_idx > 0:
            target_tier = tiers[curr_idx - 1]
            return BalancerDecision(
                action=ACTION_STEP_DOWN_RESTARTS,
                miner_name=metrics.miner_name,
                electrical_group=metrics.electrical_group,
                current_preset=current_tier.name,
                target_preset=target_tier.name,
                reason=f"Inestabilidad eléctrica ({metrics.restarts_24h} reinicios en 24h >= {cfg.restarts_threshold_step_down}): desescalando a {target_tier.name}",
                requires_write=True,
                estimated_effective_hashrate=eff_current,
            )
        else:
            return BalancerDecision(
                action=ACTION_LOCKED_MIN,
                miner_name=metrics.miner_name,
                electrical_group=metrics.electrical_group,
                current_preset=current_tier.name,
                target_preset=current_tier.name,
                reason=f"Ya en preset mínimo ({current_tier.name}) pese a {metrics.restarts_24h} reinicios",
                requires_write=False,
                estimated_effective_hashrate=eff_current,
            )

    # 3. Individual Step-Up: long soak stability, zero restarts, comfortable thermal headroom
    if (
        metrics.hours_since_last_restart >= cfg.soak_hours_step_up
        and metrics.restarts_72h == 0
        and metrics.thermal_headroom_c >= cfg.min_thermal_headroom_c
    ):
        if curr_idx < ceiling_idx and curr_idx < len(tiers) - 1:
            target_tier = tiers[curr_idx + 1]
            return BalancerDecision(
                action=ACTION_STEP_UP_OPTIMIZE,
                miner_name=metrics.miner_name,
                electrical_group=metrics.electrical_group,
                current_preset=current_tier.name,
                target_preset=target_tier.name,
                reason=f"Estabilidad comprobada ({metrics.hours_since_last_restart:.0f}h sin reinicios, margen {metrics.thermal_headroom_c:.1f}°C): subiendo a {target_tier.name}",
                requires_write=True,
                estimated_effective_hashrate=eff_current,
            )
        else:
            return BalancerDecision(
                action=ACTION_LOCKED_MAX,
                miner_name=metrics.miner_name,
                electrical_group=metrics.electrical_group,
                current_preset=current_tier.name,
                target_preset=current_tier.name,
                reason=f"Alcanzado techo máximo configurado ({tiers[ceiling_idx].name}) con alta estabilidad",
                requires_write=False,
                estimated_effective_hashrate=eff_current,
            )

    # 4. Hold Stable: currently in balance
    return BalancerDecision(
        action=ACTION_HOLD_STABLE,
        miner_name=metrics.miner_name,
        electrical_group=metrics.electrical_group,
        current_preset=current_tier.name,
        target_preset=current_tier.name,
        reason=f"Operación estable en {current_tier.name} ({metrics.hours_since_last_restart:.0f}h uptime, {metrics.restarts_24h} reinicios 24h)",
        requires_write=False,
        estimated_effective_hashrate=eff_current,
    )
