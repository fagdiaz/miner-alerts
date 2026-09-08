"""Miner Maintenance Snooze helpers (Spec 033).

Provides pure duration parsing, time formatting, snooze predicates, and
Telegram status text generation for temporary maintenance windows.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_SNOOZE_MINUTES = 60.0
MIN_SNOOZE_MINUTES = 1.0
MAX_SNOOZE_MINUTES = 1440.0  # 24 hours max

# Argentina Standard Time (UTC-3)
ARGENTINA_TZ = timezone(timedelta(hours=-3))


def parse_snooze_args(arg_str: str) -> Tuple[Optional[str], float]:
    """Parse a snooze command argument into (target, duration_minutes).
    
    Examples:
        "" -> (None, 60.0)
        "23" -> ("23", 60.0)
        "23 45" -> ("23", 45.0)
        "all 120" -> ("all", 120.0)
        "fleet" -> ("fleet", 60.0)
    """
    raw = (arg_str or "").strip()
    if not raw:
        return None, DEFAULT_SNOOZE_MINUTES

    parts = raw.split()
    target = parts[0].strip()
    minutes = DEFAULT_SNOOZE_MINUTES

    if len(parts) >= 2:
        part1 = parts[1].lower()
        try:
            if part1.endswith("h"):
                val = float(part1[:-1]) * 60.0
            else:
                val_str = part1.replace("min", "").replace("m", "")
                val = float(val_str)
            minutes = max(MIN_SNOOZE_MINUTES, min(MAX_SNOOZE_MINUTES, val))
        except ValueError:
            minutes = DEFAULT_SNOOZE_MINUTES

    return target, minutes


def is_miner_snoozed(state: Any, now_ts: Optional[float] = None) -> bool:
    """Return True if the miner state has an active, unexpired snooze."""
    if state is None:
        return False
    until = getattr(state, "snooze_until_ts", None)
    if until is None:
        return False
    curr = now_ts if now_ts is not None else time.time()
    return until > curr


def get_snooze_remaining_seconds(state: Any, now_ts: Optional[float] = None) -> float:
    """Return remaining seconds of snooze, or 0.0 if not snoozed."""
    if not is_miner_snoozed(state, now_ts):
        return 0.0
    curr = now_ts if now_ts is not None else time.time()
    return max(0.0, float(state.snooze_until_ts) - curr)


def format_snooze_remaining(remaining_seconds: float) -> str:
    """Format remaining seconds as human-readable string (e.g. 45m, 1h 15m)."""
    if remaining_seconds <= 0:
        return "0m"
    if remaining_seconds < 60:
        return "< 1m"
    total_minutes = int(remaining_seconds // 60)
    hours = total_minutes // 60
    mins = total_minutes % 60
    if hours == 0:
        return f"{mins}m"
    if mins == 0:
        return f"{hours}h"
    return f"{hours}h {mins}m"


def format_snooze_expiry_time(expiry_ts: float) -> str:
    """Format an expiry epoch timestamp to HH:MM in Argentina time."""
    dt = datetime.fromtimestamp(expiry_ts, tz=ARGENTINA_TZ)
    return dt.strftime("%H:%M")


def format_snooze_tag(state: Any, now_ts: Optional[float] = None) -> str:
    """Return a short status line tag like ' [🔕 Silenciado: 45m]' or ''."""
    rem = get_snooze_remaining_seconds(state, now_ts)
    if rem <= 0:
        return ""
    return f" [🔕 Silenciado: {format_snooze_remaining(rem)}]"


def build_snooze_status_text(
    miners: List[Dict[str, Any]],
    states: Dict[str, Any],
    now_ts: Optional[float] = None,
) -> str:
    """Build the response text for the /snoozed Telegram command."""
    curr = now_ts if now_ts is not None else time.time()
    snoozed_items = []

    for m in miners:
        key = f"{m['name']}|{m['host']}:{m['port']}"
        st = states.get(key)
        if is_miner_snoozed(st, curr):
            rem = get_snooze_remaining_seconds(st, curr)
            exp_str = format_snooze_expiry_time(st.snooze_until_ts)
            display_n = m["name"].replace("S19JPRO-", "").replace("s19jpro-", "")
            snoozed_items.append(
                f"• {m['name']} ({display_n}): resta {format_snooze_remaining(rem)} (hasta las {exp_str})"
            )

    if not snoozed_items:
        return "🔔 No hay mineros silenciados actualmente. Todos están bajo supervisión activa."

    header = "🔕 *Mineros en Mantenimiento (Silenciados)*:\n"
    footer = "\n_Alertas y autorreinicios suspendidos durante la ventana activa._"
    return header + "\n".join(snoozed_items) + footer


def filter_snoozed_episodes(
    batch: Any,
    states: Dict[str, Any],
    now_ts: Optional[float] = None,
) -> Any:
    """Filter out opened and persistent episodes for miners that are currently snoozed.
    
    Recoveries are preserved so the operator is informed if an ASIC resumes normal mining.
    """
    if batch is None or getattr(batch, "empty", False):
        return batch

    curr = now_ts if now_ts is not None else time.time()
    filtered_opened = []
    for ep in getattr(batch, "opened", []):
        st = states.get(getattr(ep, "miner_key", ""))
        if not is_miner_snoozed(st, curr):
            filtered_opened.append(ep)

    filtered_persistent = []
    for ep in getattr(batch, "persistent", []):
        st = states.get(getattr(ep, "miner_key", ""))
        if not is_miner_snoozed(st, curr):
            filtered_persistent.append(ep)

    return type(batch)(
        opened=filtered_opened,
        persistent=filtered_persistent,
        recovered=list(getattr(batch, "recovered", [])),
    )

