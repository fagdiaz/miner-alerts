"""Telegram domain package for Miner Alerts (Spec 041).

Consolidates messaging, interactive inline callbacks, visual charts,
maintenance snooze modes, and daily executive digests.
"""

from __future__ import annotations

from app.telegram.callbacks import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TOKEN_TTL_SECONDS,
    MAX_CALLBACK_DATA_BYTES,
    CallbackAction,
    CallbackTokenRegistry,
    build_alert_keyboard,
    build_callback_data,
    build_confirmation_keyboard,
    build_settled_keyboard,
    parse_callback_data,
)
from app.telegram.charts import (
    fetch_fleet_chart_data,
    fetch_miner_chart_data,
    render_fleet_chart_png,
    render_miner_chart_png,
)
from app.telegram.daily_digest import (
    fetch_daily_digest_metrics,
    format_daily_digest,
    inspect_latest_backup,
    is_digest_due,
)
from app.telegram.messages import (
    TELEGRAM_TEXT_LIMIT,
    classify_delivery,
    normalize_telegram_text,
    split_telegram_message,
)
from app.telegram.snooze import (
    ARGENTINA_TZ,
    DEFAULT_SNOOZE_MINUTES,
    MAX_SNOOZE_MINUTES,
    MIN_SNOOZE_MINUTES,
    build_snooze_status_text,
    format_snooze_expiry_time,
    format_snooze_remaining,
    format_snooze_tag,
    get_snooze_remaining_seconds,
    is_miner_snoozed,
    parse_snooze_args,
)

# Convenience alias
TokenRegistry = CallbackTokenRegistry

__all__ = [
    "ARGENTINA_TZ",
    "CallbackAction",
    "CallbackTokenRegistry",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_SNOOZE_MINUTES",
    "DEFAULT_TOKEN_TTL_SECONDS",
    "MAX_CALLBACK_DATA_BYTES",
    "MAX_SNOOZE_MINUTES",
    "MIN_SNOOZE_MINUTES",
    "TELEGRAM_TEXT_LIMIT",
    "TokenRegistry",
    "build_alert_keyboard",
    "build_callback_data",
    "build_confirmation_keyboard",
    "build_settled_keyboard",
    "build_snooze_status_text",
    "classify_delivery",
    "fetch_daily_digest_metrics",
    "fetch_fleet_chart_data",
    "fetch_miner_chart_data",
    "format_daily_digest",
    "format_snooze_expiry_time",
    "format_snooze_remaining",
    "format_snooze_tag",
    "get_snooze_remaining_seconds",
    "inspect_latest_backup",
    "is_digest_due",
    "is_miner_snoozed",
    "normalize_telegram_text",
    "parse_callback_data",
    "parse_snooze_args",
    "render_fleet_chart_png",
    "render_miner_chart_png",
    "split_telegram_message",
]
