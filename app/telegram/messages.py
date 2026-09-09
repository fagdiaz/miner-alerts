from __future__ import annotations

import re
import unicodedata


TELEGRAM_TEXT_LIMIT = 3900
_PART_HEADER_RESERVE = 32
_CRITICAL_TYPES = {"ERROR", "REBOOT"}
_NOTIFICATION_TYPES = {"EPISODE_ALERT", "STATE_CHANGE"}


def normalize_telegram_text(value: object) -> str:
    text = unicodedata.normalize("NFC", str(value or ""))
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n")).strip()
    return re.sub(r"\n{3,}", "\n\n", text)


def classify_delivery(message_type: str, *, is_command: bool) -> str:
    if is_command:
        return "command"
    normalized = str(message_type or "").strip().upper()
    if normalized in _CRITICAL_TYPES:
        return "critical"
    if normalized in _NOTIFICATION_TYPES:
        return "notification"
    return "informational"


def split_telegram_message(
    value: object,
    *,
    limit: int = TELEGRAM_TEXT_LIMIT,
) -> list[str]:
    text = normalize_telegram_text(value)
    if not text:
        return [""]
    if len(text) <= limit:
        return [text]
    if limit <= _PART_HEADER_RESERVE:
        raise ValueError("Telegram message limit is too small")

    payload_limit = limit - _PART_HEADER_RESERVE
    raw_parts: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= payload_limit:
            raw_parts.append(remaining)
            break
        cut = _preferred_cut(remaining, payload_limit)
        raw_parts.append(remaining[:cut])
        remaining = remaining[cut:]

    count = len(raw_parts)
    return [
        f"Parte {index}/{count}\n\n{part}"
        for index, part in enumerate(raw_parts, start=1)
    ]


def _preferred_cut(text: str, limit: int) -> int:
    for separator in ("\n\n", "\n", " "):
        index = text.rfind(separator, 0, limit + 1)
        if index > 0:
            return index + len(separator)
    return limit
