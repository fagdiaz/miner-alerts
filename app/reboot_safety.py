from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Optional


INTERLOCK_HIGH_TEMPERATURE = "high_temperature"
INTERLOCK_FIRMWARE_TRANSITION = "firmware_transition"
INTERLOCK_FLEET_INCIDENT = "fleet_incident"

_AFFECTED_SIGNAL_CLASSES = frozenset(("eligible", "invalid_signal"))


@dataclass(frozen=True)
class RebootInterlockDecision:
    allowed: bool
    reason: Optional[str] = None
    affected_miners: tuple[str, ...] = ()
    max_temp_c: Optional[float] = None
    fleet_snapshot_age_seconds: Optional[float] = None
    chains_transitioning_count: Optional[int] = None


def _finite_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _nonnegative_integer(value: Any) -> Optional[int]:
    number = _finite_number(value)
    if number is None or number < 0 or not number.is_integer():
        return None
    return int(number)


def evaluate_auto_reboot_interlocks(
    *,
    current_miner_key: str,
    current_signal: str,
    previous_signals: Mapping[str, str],
    previous_signals_observed_ts: Optional[float],
    evaluated_ts: float,
    fleet_snapshot_max_age_seconds: float,
    max_temp_c: Any,
    thermal_guard_enabled: bool,
    thermal_limit_c: float,
    fleet_guard_enabled: bool,
    fleet_min_affected: int,
    firmware_transition_guard_enabled: bool = True,
    chains_transitioning_count: Any = None,
) -> RebootInterlockDecision:
    """Evaluate conservative no-action gates using already collected evidence."""
    current_temp = _finite_number(max_temp_c)
    current_transition_count = _nonnegative_integer(chains_transitioning_count)
    safe_thermal_limit = _finite_number(thermal_limit_c)
    if safe_thermal_limit is None:
        safe_thermal_limit = 85.0

    observed_ts = _finite_number(previous_signals_observed_ts)
    now_ts = _finite_number(evaluated_ts)
    snapshot_max_age = _finite_number(fleet_snapshot_max_age_seconds)
    snapshot_age: Optional[float] = None
    if observed_ts is not None and now_ts is not None:
        snapshot_age = max(0.0, now_ts - observed_ts)
    snapshot_fresh = (
        snapshot_age is not None
        and snapshot_max_age is not None
        and snapshot_max_age > 0
        and snapshot_age <= snapshot_max_age
    )

    latest_signals = dict(previous_signals) if snapshot_fresh else {}
    latest_signals[current_miner_key] = current_signal
    affected = tuple(
        sorted(
            miner_key
            for miner_key, signal in latest_signals.items()
            if signal in _AFFECTED_SIGNAL_CLASSES
        )
    )

    if (
        thermal_guard_enabled
        and current_temp is not None
        and current_temp >= safe_thermal_limit
    ):
        return RebootInterlockDecision(
            allowed=False,
            reason=INTERLOCK_HIGH_TEMPERATURE,
            affected_miners=affected,
            max_temp_c=current_temp,
            fleet_snapshot_age_seconds=snapshot_age,
            chains_transitioning_count=current_transition_count,
        )

    if (
        firmware_transition_guard_enabled
        and current_transition_count is not None
        and current_transition_count > 0
    ):
        return RebootInterlockDecision(
            allowed=False,
            reason=INTERLOCK_FIRMWARE_TRANSITION,
            affected_miners=affected,
            max_temp_c=current_temp,
            fleet_snapshot_age_seconds=snapshot_age,
            chains_transitioning_count=current_transition_count,
        )

    safe_min_affected = max(2, int(fleet_min_affected))
    if fleet_guard_enabled and len(affected) >= safe_min_affected:
        return RebootInterlockDecision(
            allowed=False,
            reason=INTERLOCK_FLEET_INCIDENT,
            affected_miners=affected,
            max_temp_c=current_temp,
            fleet_snapshot_age_seconds=snapshot_age,
            chains_transitioning_count=current_transition_count,
        )

    return RebootInterlockDecision(
        allowed=True,
        affected_miners=affected,
        max_temp_c=current_temp,
        fleet_snapshot_age_seconds=snapshot_age,
        chains_transitioning_count=current_transition_count,
    )
