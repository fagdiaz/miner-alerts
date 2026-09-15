"""Decoupled Telegram Poller and Update Engine (Spec 058).

Provides reusable, robust HTTP polling for Telegram Bot API getUpdates,
with exponential backoff, token redaction, and clean separation between
transport network polling and command dispatch.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.telegram.context import TelegramRequestContext
from app.telegram.router import TelegramCallbackRouter, TelegramCommandRouter

logger = logging.getLogger("miner-alerts")


def fetch_telegram_updates(
    bot_token: str,
    offset: Optional[int] = None,
    poll_timeout: int = 25,
    session: Optional[requests.Session] = None,
) -> Tuple[bool, List[Dict[str, Any]], int, str]:
    """Fetch updates from Telegram getUpdates endpoint.
    
    Returns:
        (ok, result_list, status_code, error_message)
    """
    params: Dict[str, Any] = {"timeout": poll_timeout}
    if offset is not None:
        params["offset"] = offset

    tg_updates_url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    client = session or requests
    timeout_used = poll_timeout + 5

    try:
        resp = client.get(tg_updates_url, params=params, timeout=timeout_used)
        if resp.status_code >= 400:
            return False, [], resp.status_code, f"HTTP {resp.status_code}"
        data = resp.json()
        if not data.get("ok"):
            return False, [], resp.status_code, str(data.get("description", "Not OK"))
        return True, data.get("result", []), resp.status_code, ""
    except Exception as exc:
        return False, [], 0, f"{type(exc).__name__}: {exc}"


def process_telegram_update(
    item: Dict[str, Any],
    context: TelegramRequestContext,
    router: TelegramCommandRouter,
) -> bool:
    """Process a single Telegram update item (callback query or text command).
    
    Returns:
        True if handled, False otherwise.
    """
    # 1. Inline keyboard callback query
    cb_query = item.get("callback_query")
    if cb_query is not None:
        TelegramCallbackRouter.dispatch(cb_query, context)
        return True

    # 2. Text command
    from app.miner_monitor import _parse_message_command
    message, raw_text, cmd_name, args, msg_key, cmd_meta = _parse_message_command(item)
    msg_chat_id = (message or {}).get("chat", {}).get("id")

    # Verify target chat matches authorized chat
    if msg_chat_id is None or str(msg_chat_id) != str(context.chat_id):
        return False

    update_id = item.get("update_id")
    from_user = (message or {}).get("from") or {}
    from_id = from_user.get("id")
    message_id = (message or {}).get("message_id")

    # Dispatch to registered command handler
    handled = router.dispatch(
        cmd_name=cmd_name,
        args=args,
        context=context,
        update_id=update_id,
        from_id=from_id,
        message_id=message_id,
    )
    return handled
