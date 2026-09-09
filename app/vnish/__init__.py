"""Vnish firmware integration package for Miner Alerts (Spec 041).

Consolidates REST client communication, preset monitoring and autotuning tracking,
firmware log parsing and normalized telemetry extraction.
"""

from __future__ import annotations

from app.vnish.client import (
    DEFAULT_HTTP_TIMEOUT,
    get_available_presets,
    get_cooling_settings,
    get_miner_status,
    get_overclock_settings,
    get_summary_cooling,
    lock_miner,
    mask_secret,
    resume_mining,
    safe_get_overclock_settings,
    safe_resume_mining,
    safe_set_fan_duty,
    safe_set_miner_preset,
    safe_stop_mining,
    set_manual_fan_duty,
    set_miner_preset,
    stop_mining,
    unlock_miner,
)
from app.vnish.logs import (
    ALLOWED_LOG_TABS,
    VnishLogEvent,
    parse_vnish_log_text,
    render_firmware_events,
)
from app.vnish.presets import (
    STATUS_AUTOTUNING,
    STATUS_DOWNCLOCKED,
    STATUS_LABELS,
    STATUS_STABLE,
    STATUS_UNKNOWN,
    PresetAssessment,
    assess_miner_preset,
    build_miner_preset_detail_text,
    build_presets_table_text,
    evaluate_preset_alerts,
    fetch_latest_preset_assessments,
    infer_operating_profile,
)
from app.vnish.telemetry import (
    VnishTelemetry,
    normalize_vnish_stats,
)

__all__ = [
    "ALLOWED_LOG_TABS",
    "DEFAULT_HTTP_TIMEOUT",
    "PresetAssessment",
    "STATUS_AUTOTUNING",
    "STATUS_DOWNCLOCKED",
    "STATUS_LABELS",
    "STATUS_STABLE",
    "STATUS_UNKNOWN",
    "VnishLogEvent",
    "VnishTelemetry",
    "assess_miner_preset",
    "build_miner_preset_detail_text",
    "build_presets_table_text",
    "evaluate_preset_alerts",
    "fetch_latest_preset_assessments",
    "get_available_presets",
    "get_cooling_settings",
    "get_miner_status",
    "get_overclock_settings",
    "get_summary_cooling",
    "infer_operating_profile",
    "lock_miner",
    "mask_secret",
    "normalize_vnish_stats",
    "parse_vnish_log_text",
    "render_firmware_events",
    "resume_mining",
    "safe_get_overclock_settings",
    "safe_resume_mining",
    "safe_set_fan_duty",
    "safe_set_miner_preset",
    "safe_stop_mining",
    "set_manual_fan_duty",
    "set_miner_preset",
    "stop_mining",
    "unlock_miner",
]
