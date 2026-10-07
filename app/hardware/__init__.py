"""Hardware telemetry, chain inspection and board health modules (Spec 089)."""
from app.hardware.chain_collector import (
    _CHAIN_HEALTH_STREAKS,
    _SETTINGS_CORRUPTION_ALERTS,
    _SETTINGS_HEALTH_TIMESTAMPS,
    _async_collect_chain_telemetry,
    _async_evaluate_predictive_chain_break,
)

__all__ = [
    "_CHAIN_HEALTH_STREAKS",
    "_SETTINGS_CORRUPTION_ALERTS",
    "_SETTINGS_HEALTH_TIMESTAMPS",
    "_async_collect_chain_telemetry",
    "_async_evaluate_predictive_chain_break",
]
