from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Optional


STATE_OK = "OK"
STATE_LOW = "LOW"
STATE_OFFLINE = "OFFLINE"
STATE_HASHBOARD = "HASHBOARD"

AUTO_REBOOT_SIGNAL_ELIGIBLE = "eligible"
AUTO_REBOOT_SIGNAL_INVALID = "invalid_signal"
AUTO_REBOOT_SIGNAL_NOT_LOW = "not_low"

INTERLOCK_HIGH_TEMPERATURE = "high_temperature"
INTERLOCK_FIRMWARE_TRANSITION = "firmware_transition"
INTERLOCK_FLEET_INCIDENT = "fleet_incident"
INTERLOCK_HARDWARE_FAULT = "hardware_fault"
INTERLOCK_STOCK_FIRMWARE = "stock_firmware_fallback"

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
    hardware_fault_present: bool = False,
    stock_firmware_present: bool = False,
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

    if stock_firmware_present:
        return RebootInterlockDecision(
            allowed=False,
            reason=INTERLOCK_STOCK_FIRMWARE,
            affected_miners=affected,
            max_temp_c=current_temp,
            fleet_snapshot_age_seconds=snapshot_age,
            chains_transitioning_count=current_transition_count,
        )

    if hardware_fault_present:
        return RebootInterlockDecision(
            allowed=False,
            reason=INTERLOCK_HARDWARE_FAULT,
            affected_miners=affected,
            max_temp_c=current_temp,
            fleet_snapshot_age_seconds=snapshot_age,
            chains_transitioning_count=current_transition_count,
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


def classify_auto_reboot_signal(
    responded: bool,
    rate_ths: Optional[float],
    threshold_ths: float,
) -> str:
    """Classify miner telemetry response into an auto-reboot signal category."""
    if not responded or rate_ths is None:
        return AUTO_REBOOT_SIGNAL_INVALID
    try:
        numeric_rate = float(rate_ths)
    except (TypeError, ValueError):
        return AUTO_REBOOT_SIGNAL_INVALID
    if not math.isfinite(numeric_rate):
        return AUTO_REBOOT_SIGNAL_INVALID
    if numeric_rate >= float(threshold_ths):
        return AUTO_REBOOT_SIGNAL_NOT_LOW
    return AUTO_REBOOT_SIGNAL_ELIGIBLE


def auto_reboot_signal_allows_evaluation(
    new_state: str,
    low_since_ts: Optional[float],
    signal_classification: str,
    hashboard_since_ts: Optional[float] = None,
    active_boards: Optional[int] = None,
    expected_boards: int = 3,
    allow_partial_hashboard: bool = False,
    hashboard_reboot_enabled: bool = True,
) -> bool:
    """Evaluate whether the given signal meets requirements for reboot evaluation."""
    if new_state == STATE_LOW:
        return (
            low_since_ts is not None
            and signal_classification == AUTO_REBOOT_SIGNAL_ELIGIBLE
        )
    if new_state == STATE_HASHBOARD and hashboard_reboot_enabled:
        if hashboard_since_ts is None:
            return False
        if signal_classification == AUTO_REBOOT_SIGNAL_INVALID:
            return False
        if active_boards is not None:
            if active_boards == 0:
                return True
            elif active_boards < expected_boards:
                return bool(allow_partial_hashboard)
            else:
                return False
        return signal_classification == AUTO_REBOOT_SIGNAL_ELIGIBLE
    return False


def reset_sustained_low_if_signal_ineligible(
    state: Any,
    signal_classification: str,
) -> bool:
    """Reset low_since_ts if the signal classification is no longer eligible."""
    if signal_classification == AUTO_REBOOT_SIGNAL_ELIGIBLE:
        return False
    state.low_since_ts = None
    return True


def reset_sustained_hashboard_if_ineligible(
    state: Any,
    signal_classification: str,
    active_boards: Optional[int],
    expected_boards: int = 3,
    allow_partial_hashboard: bool = False,
) -> bool:
    """Reset hashboard_since_ts if the signal classification or board count is ineligible."""
    if signal_classification == AUTO_REBOOT_SIGNAL_INVALID:
        state.hashboard_since_ts = None
        return True
    if active_boards is not None:
        if active_boards >= expected_boards:
            state.hashboard_since_ts = None
            return True
        if active_boards > 0 and not allow_partial_hashboard:
            state.hashboard_since_ts = None
            return True
    return False
