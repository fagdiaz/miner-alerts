"""Detection-loop-owned observation of sustained ASIC power changes; no actuators."""
from dataclasses import dataclass
from math import isfinite
from typing import Optional, Tuple


@dataclass
class PowerObservation:
    baseline: Optional[int] = None
    candidate: Optional[int] = None
    since: float = 0.0
    last_notice: Optional[float] = None


def observe_power(
    observation: PowerObservation, watts: Optional[float], now: float,
    valid: bool = True, settle_seconds: float = 90.0,
    cooldown_seconds: float = 900.0,
) -> Optional[Tuple[int, int]]:
    """Coalesce noise and flapping; startup and stopped miners never emit a notice."""
    if not valid or watts is None or not isfinite(watts) or watts < 1000:
        observation.candidate = None
        return None
    power = int(round(watts / 50.0) * 50)
    if observation.baseline is None:
        observation.baseline = power
        return None
    if abs(power - observation.baseline) < 100:
        observation.candidate = None
        return None
    if power != observation.candidate:
        observation.candidate = power
        observation.since = now
        return None
    if now - observation.since < settle_seconds:
        return None
    if observation.last_notice is not None and now - observation.last_notice < cooldown_seconds:
        return None
    previous = observation.baseline
    observation.baseline = power
    observation.candidate = None
    observation.last_notice = now
    return previous, power
