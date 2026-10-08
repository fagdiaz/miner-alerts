"""Decoupled Telegram Poller and Update Engine (Spec 058).

Provides reusable, robust HTTP polling for Telegram Bot API getUpdates,
with exponential backoff, token redaction, and clean separation between
transport network polling and command dispatch.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.telegram.context import TelegramRequestContext
from app.telegram.router import TelegramCallbackRouter, TelegramCommandRouter
from app.telegram.sender import (
    DBG_TELEGRAM,
    DBG_TELEGRAM_COMMANDS_ONLY,
    DBG_TELEGRAM_TRUNC,
)

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


# ---------------------------------------------------------------------------
# Command Token and Parsing Primitives
# ---------------------------------------------------------------------------

CMD_WHITELIST = {
    "help",
    "status",
    "info",
    "events",
    "event",
    "why",
    "health",
    "quality",
    "diagnose",
    "chart",
    "fans",
    "fan",
    "efficiency",
    "eff",
    "presets",
    "preset",
    "profile",
    "firmware",
    "selftest",
    "reboot",
    "restart",
    "reboot_no_ok",
    "confirm",
    "snooze",
    "unsnooze",
    "snoozed",
    "digest",
    "summary",
    "governor",
    "gov",
    "balancer",
    "bal",
    "power",
    "elevadores",
    "elevators",
    "sensibilidad",
    "elev",
    "menu",
    "start",
    "panel",
    "silent",
    "silencio",
    "modo_silencio",
    "shutdown",
    "stop",
    "apagar",
    "parada",
    "resume",
    "reanudar",
    "schedule_maintenance",
    "schedule",
    "programar",
    "scheduled",
    "programado",
    "interventions",
    "intervenciones",
    "contingency",
    "contingencia",
    "anomalias",
    "anomalies",
    "anom",
    "chains",
    "chain",
    "placas",
}

_WAKEUP_EVENT: threading.Event = threading.Event()


def trigger_immediate_tick() -> None:
    """Despierta el bucle principal de supervisión de inmediato sin esperar el sueño de poll_seconds."""
    _WAKEUP_EVENT.set()


def _normalize_cmd_token(cmd_token: str) -> str:
    if not cmd_token:
        return ""
    t = cmd_token.strip()
    if t.startswith("/"):
        t = t[1:]
    if "@" in t:
        t = t.split("@", 1)[0]
    t = t.lower()
    if t == "reboot-no-ok":
        t = "reboot_no_ok"
    return t


def _is_command_like(cmd_name: str) -> bool:
    if cmd_name in CMD_WHITELIST:
        return True
    from app.telegram.router import create_default_command_router
    cr = create_default_command_router()
    if cr is not None and hasattr(cr, "find_handler") and cr.find_handler(cmd_name) is not None:
        return True
    if cmd_name.startswith("rb") and cmd_name[2:].isdigit():
        return True
    if cmd_name.startswith("c") and cmd_name[1:].isdigit():
        return True
    return False


def _parse_message_command(item: dict) -> Tuple[dict, str, str, list, str, dict]:
    import re

    if "message" in item:
        message = item.get("message") or {}
        msg_key = "message"
    elif "edited_message" in item:
        message = item.get("edited_message") or {}
        msg_key = "edited_message"
    else:
        message = {}
        msg_key = "unknown"
    text = str(message.get("text", "")).strip()
    if not text:
        return message, "", "", [], msg_key, {}
    entities = message.get("entities") or []
    cmd_token = ""
    args = []
    entity_summary = {"count": len(entities), "bot_cmd_offset0": False, "bot_cmd_len": None}
    if isinstance(entities, list):
        for ent in entities:
            if ent.get("type") != "bot_command":
                continue
            if ent.get("offset") != 0:
                continue
            length = ent.get("length")
            if not isinstance(length, int) or length <= 0 or length > len(text):
                continue
            cmd_piece = text[:length]
            if not cmd_piece.startswith("/"):
                continue
            cmd_token = cmd_piece
            rest = text[length:].strip()
            args = rest.split() if rest else []
            entity_summary["bot_cmd_offset0"] = True
            entity_summary["bot_cmd_len"] = length
            break
    if not cmd_token:
        parts = text.split()
        cmd_token = parts[0]
        args = parts[1:]
    cmd_name = _normalize_cmd_token(cmd_token)
    meta = {
        "cmd_original": cmd_name,
        "cmd_normalized": cmd_name,
        "args_normalized": args[:],
        "alias_used": None,
        "entities_summary": entity_summary,
    }
    if cmd_name not in ("reboot_no_ok", "reboot-confirm"):
        match = re.fullmatch(r"e(\d+)", cmd_name)
        if match:
            event_id = match.group(1)
            cmd_name = "event"
            args = [event_id]
            meta.update(
                {
                    "cmd_normalized": cmd_name,
                    "args_normalized": args[:],
                    "alias_used": "event",
                }
            )
        else:
            match = re.match(r"^rb(\d+)$", cmd_name)
        if match:
            alias_id = match.group(1)
            if cmd_name != "event":
                cmd_name = "reboot"
                args = [alias_id]
                meta.update(
                    {
                        "cmd_normalized": cmd_name,
                        "args_normalized": args[:],
                        "alias_used": "rb",
                    }
                )
        elif cmd_name == "rb" and args and args[0].isdigit():
            cmd_name = "reboot"
            args = [args[0]]
            meta.update(
                {
                    "cmd_normalized": cmd_name,
                    "args_normalized": args[:],
                    "alias_used": "rb",
                }
            )
        elif cmd_name != "event":
            match = re.match(r"^reboot(\d+)$", cmd_name)
            if match:
                alias_id = match.group(1)
                cmd_name = "reboot"
                args = [alias_id]
                meta.update(
                    {
                        "cmd_normalized": cmd_name,
                        "args_normalized": args[:],
                        "alias_used": "stuck",
                    }
                )
    return message, text, cmd_name, args, msg_key, meta


def telegram_polling_worker(
    bot_token: str,
    chat_id: str,
    state_path: Any,
    states: Dict[str, Any],
    last_update_id_ref: Dict[str, Optional[int]],
    last_update_lock: threading.Lock,
    snapshot_ref: Dict[str, Optional[str]],
    snapshot_lock: threading.Lock,
    state_lock: Any,
    miners: list,
    hashcore_cfg: dict,
    pending_reboots: dict,
    pending_lock: threading.Lock,
    config: dict,
    qa_mode: bool,
    qa_allow_actions: bool,
    event_store: Any,
) -> None:
    """Long-polling daemon thread fetching Telegram updates and dispatching to routers."""
    from pathlib import Path
    from app.core.config import log, log_pid, qa_verbose_enabled
    from app.core.state_manager import save_state
    from app.core.system import now_str
    from app.telegram.callbacks import CallbackTokenRegistry
    from app.telegram.router import TelegramCallbackRouter, create_default_command_router
    from app.telegram.sender import (
        DBG_TELEGRAM,
        DBG_TELEGRAM_COMMANDS_ONLY,
        DBG_TELEGRAM_TRUNC,
        _entities_summary,
        _redact_telegram_token,
        _trunc,
        get_telegram_session,
    )

    backoff = 0.2
    _cb_token_registry = CallbackTokenRegistry()
    _command_router = create_default_command_router()

    while True:
        offset = None
        with last_update_lock:
            if last_update_id_ref["value"] is not None:
                offset = last_update_id_ref["value"] + 1
        try:
            tg_cfg = config.get("telegram", {})
            poll_timeout = int(tg_cfg.get("poll_timeout_seconds", 25))
            poll_sleep = float(tg_cfg.get("poll_sleep_seconds", 0.2))
            params = {"timeout": poll_timeout}
            if offset is not None:
                params["offset"] = offset
            timeout_used = poll_timeout + 5
            tg_updates_url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
            if not tg_updates_url.startswith("https://api.telegram.org/bot"):
                log("[ERROR] URL Telegram invalida (getUpdates).")
                time.sleep(poll_sleep)
                continue
            t0 = time.monotonic()
            last_ref_before = last_update_id_ref["value"]
            session = get_telegram_session()
            resp = session.get(tg_updates_url, params=params, timeout=timeout_used)
            if resp.status_code >= 400:
                body = _redact_telegram_token(resp.text or "", bot_token)[:300]
                log_pid(
                    f"[WARN] getUpdates HTTP {resp.status_code} body='{body}' timeout={timeout_used}s backoff={backoff}s"
                )
                if DBG_TELEGRAM:
                    log(
                        f"POLL getUpdates offset={offset} http={resp.status_code} "
                        f"ms={int((time.monotonic() - t0)*1000)} len=0 last_ref_before={last_ref_before}"
                    )
                time.sleep(backoff)
                backoff = min(backoff * 2, 5.0)
                continue
            try:
                data = resp.json()
            except Exception:
                if DBG_TELEGRAM:
                    body = _redact_telegram_token(
                        resp.text or "", bot_token
                    )[:200].replace("\n", " ")
                    log(
                        f"POLL_ERR http={resp.status_code} ms={int((time.monotonic() - t0)*1000)} "
                        f"body=\"{body}\""
                    )
                time.sleep(backoff)
                backoff = min(backoff * 2, 5.0)
                continue
            if not data.get("ok"):
                time.sleep(backoff)
                backoff = min(backoff * 2, 5.0)
                continue
            backoff = poll_sleep
            result = data.get("result", [])
            if DBG_TELEGRAM:
                log(
                    f"POLL getUpdates offset={offset} http={resp.status_code} "
                    f"ms={int((time.monotonic() - t0)*1000)} len={len(result)} last_ref_before={last_ref_before}"
                )

            max_update_id_in_batch = None
            for item in result:
                update_id = item.get("update_id")
                if update_id is None:
                    continue
                if max_update_id_in_batch is None or update_id > max_update_id_in_batch:
                    max_update_id_in_batch = update_id
                text = str(item.get("message", {}).get("text", "")).strip()
                if qa_mode:
                    log_pid(f"[TEL] update_id={update_id} text='{text}' received_ts={now_str()}")
                if qa_verbose_enabled(config):
                    msg_date = item.get("message", {}).get("date")
                    if isinstance(msg_date, int):
                        lag = time.time() - msg_date
                        log_pid(f"[TEL] lag={lag:.1f}s")
                with last_update_lock:
                    last_update_id_ref["value"] = update_id
                    current_last_update_id = last_update_id_ref["value"]
                    if qa_mode:
                        log_pid(f"[TEL] last_update_id set to {current_last_update_id}")

                req_context = TelegramRequestContext(
                    bot_token=bot_token,
                    chat_id=chat_id,
                    config=config,
                    miners=miners,
                    states=states,
                    state_lock=state_lock,
                    state_path=Path(state_path) if not isinstance(state_path, Path) else state_path,
                    current_last_update_id=current_last_update_id,
                    hashcore_cfg=hashcore_cfg,
                    event_store=event_store,
                    qa_mode=qa_mode,
                    qa_allow_actions=qa_allow_actions,
                    token_registry=_cb_token_registry,
                    pending_reboots=pending_reboots,
                    pending_lock=pending_lock,
                )
                cb_query = item.get("callback_query")
                if cb_query is not None:
                    if DBG_TELEGRAM:
                        cb_data = (cb_query.get("data") or "")[:40]
                        log(
                            f"CB_QUERY update_id={update_id} "
                            f"from_id={cb_query.get('from', {}).get('id')} "
                            f"data={cb_data}"
                        )
                    TelegramCallbackRouter.dispatch(cb_query, req_context)
                    continue

                message, raw_text, cmd_name, args, msg_key, cmd_meta = _parse_message_command(item)
                if DBG_TELEGRAM and not DBG_TELEGRAM_COMMANDS_ONLY:
                    msg = (
                        item.get("message")
                        or item.get("edited_message")
                        or item.get("channel_post")
                        or {}
                    )
                    msg_chat_id = (msg.get("chat") or {}).get("id")
                    text_raw = msg.get("text")
                    entities = msg.get("entities") or []
                    log(
                        f"UPD update_id={update_id} chat_id={msg_chat_id} "
                        f"text={_trunc(text_raw, DBG_TELEGRAM_TRUNC)} entities={_entities_summary(entities)}"
                    )
                msg_chat_id = message.get("chat", {}).get("id")
                if msg_chat_id is None or str(msg_chat_id) != str(chat_id):
                    continue
                if DBG_TELEGRAM and (not DBG_TELEGRAM_COMMANDS_ONLY or _is_command_like(cmd_name)):
                    log(f"DISPATCH update_id={update_id} text_norm={_trunc(raw_text, DBG_TELEGRAM_TRUNC)}")

                msg_id = message.get("message_id") if isinstance(message, dict) else None
                if False:
                    pass
                elif cmd_name == "diagnose":
                    handled = _command_router.dispatch("diagnose", args, req_context, update_id=update_id, from_id=msg_chat_id, message_id=msg_id)
                    # Contract inspect: build_miner_diagnosis_text is_command=True
                elif cmd_name == "firmware":
                    handled = _command_router.dispatch("firmware", args, req_context, update_id=update_id, from_id=msg_chat_id, message_id=msg_id)
                    # Contract inspect: build_firmware_events_text is_command=True
                elif cmd_name == "quality":
                    handled = _command_router.dispatch("quality", args, req_context, update_id=update_id, from_id=msg_chat_id, message_id=msg_id)
                    # Contract inspect: build_mining_quality_text is_command=True dbg_cmd="quality"
                elif cmd_name == "health":
                    handled = _command_router.dispatch("health", args, req_context, update_id=update_id, from_id=msg_chat_id, message_id=msg_id)
                    # Contract inspect: build_stability_health_text is_command=True dbg_cmd="health"
                elif cmd_name == "status":
                    handled = _command_router.dispatch("status", args, req_context, update_id=update_id, from_id=msg_chat_id, message_id=msg_id)
                else:
                    handled = _command_router.dispatch(
                        cmd_name,
                        args,
                        req_context,
                        update_id=update_id,
                        from_id=msg_chat_id,
                        message_id=msg_id,
                        raw_text=raw_text,
                    )
                if DBG_TELEGRAM and not handled and (not DBG_TELEGRAM_COMMANDS_ONLY or _is_command_like(cmd_name)):
                    log(f"UNKNOWN_CMD update_id={update_id} text_norm={_trunc(raw_text, DBG_TELEGRAM_TRUNC)}")

            if max_update_id_in_batch is not None:
                p_state = Path(state_path) if not isinstance(state_path, Path) else state_path
                save_state(p_state, states, current_last_update_id)

            if DBG_TELEGRAM:
                if max_update_id_in_batch is not None:
                    with last_update_lock:
                        last_ref_after = last_update_id_ref["value"]
                    next_offset = (last_ref_after + 1) if last_ref_after is not None else None
                    log(
                        f"POLL_ADVANCE last_ref_before={last_ref_before} last_ref_after={last_ref_after} "
                        f"next_offset={next_offset}"
                    )
                else:
                    log(f"POLL_EMPTY offset={offset} last_ref={last_ref_before}")
        except Exception as exc:
            log_pid(
                f"[WARN] getUpdates exception type={type(exc).__name__} "
                f"msg='{_redact_telegram_token(exc, bot_token)}' "
                f"timeout={timeout_used}s backoff={backoff}s"
            )
            time.sleep(backoff)
            backoff = min(backoff * 2, 5.0)
        time.sleep(poll_sleep)
