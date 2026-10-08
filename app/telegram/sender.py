"""Telegram Sender and Transport Subsystem (Spec 091).

Handles message delivery queues, payload batching, direct and asynchronous
dispatching, inline keyboard editing, photo rendering, and error redaction.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import queue
import re
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.core.config import log, log_pid
from app.core.system import now_str
from app.telegram.messages import classify_delivery, split_telegram_message

logger = logging.getLogger("miner-alerts")

# ---------------------------------------------------------------------------
# Globals and connection pooling
# ---------------------------------------------------------------------------
_HTTP_SESSION: Optional[requests.Session] = None
_HTTP_SESSION_LOCK = threading.Lock()

_TELEGRAM_QUEUE: Optional[queue.Queue] = None
_TELEGRAM_QUEUE_LOCK = threading.Lock()
_TELEGRAM_SENDER_TS: Optional[float] = None
_TELEGRAM_POLLER_TS: Optional[float] = None

_LAST_ENQUEUED: Dict[str, float] = {}
_LAST_SENT_HASH: Dict[str, str] = {}
_LAST_SENT_TS: Dict[str, float] = {}
_LAST_SENT_META: Dict[str, Any] = {}
_COALESCE_WINDOWS: Dict[str, float] = {
    "STATE_CHANGE": 30.0,
    "EPISODE_ALERT": 60.0,
}

_QA_TX_COUNTS: Dict[int, int] = {}
_PERF_LOGGED: Dict[int, bool] = {}

DBG_TELEGRAM = os.getenv("DBG_TELEGRAM", "0") == "1"
DBG_TELEGRAM_COMMANDS_ONLY = os.getenv("DBG_TELEGRAM_COMMANDS_ONLY", "1") == "1"
DBG_TELEGRAM_TRUNC = int(os.getenv("DBG_TELEGRAM_TRUNC", "120"))


def get_telegram_session() -> requests.Session:
    """Return a persistent, thread-safe requests.Session with HTTP Keep-Alive connection pooling."""
    global _HTTP_SESSION
    if _HTTP_SESSION is None:
        with _HTTP_SESSION_LOCK:
            if _HTTP_SESSION is None:
                s = requests.Session()
                adapter = requests.adapters.HTTPAdapter(
                    pool_connections=20,
                    pool_maxsize=20,
                    max_retries=2,
                )
                s.mount("https://", adapter)
                s.mount("http://", adapter)
                _HTTP_SESSION = s
    return _HTTP_SESSION


def _short_text(text: str, limit: int = 160) -> str:
    if text is None:
        return ""
    clean = text.replace("\n", " ").replace("\r", " ")
    if len(clean) <= limit:
        return clean
    return clean[:limit] + "..."


def _trunc(text: Optional[str], limit: int) -> str:
    if text is None:
        return ""
    raw = repr(str(text))
    if len(raw) <= limit:
        return raw
    return raw[:limit] + "..."


def _redact_telegram_token(value: object, bot_token: Optional[str]) -> str:
    text = str(value)
    if bot_token:
        text = text.replace(bot_token, "<redacted>")
    return re.sub(
        r"(https://api\.telegram\.org/bot)[^/\s?'\"]+",
        r"\1<redacted>",
        text,
    )


def _entities_summary(entities: list) -> str:
    if not isinstance(entities, list) or not entities:
        return "none"
    parts = []
    for ent in entities[:6]:
        etype = ent.get("type", "?")
        off = ent.get("offset", "?")
        length = ent.get("length", "?")
        parts.append(f"{etype}@{off}+{length}")
    more = ""
    if len(entities) > 6:
        more = f"+{len(entities) - 6}more"
    return ",".join(parts) + (f" {more}" if more else "")


def send_telegram(
    bot_token: str,
    chat_id: str,
    message: str,
    msg_type: str,
    reason: str = "",
    qa_update_id: Optional[int] = None,
    qa_cmd: Optional[str] = None,
    perf_ctx: Optional[dict] = None,
    is_command: bool = False,
    dbg_update_id: Optional[int] = None,
    dbg_cmd: Optional[str] = None,
    reply_markup: Optional[Dict[str, Any]] = None,
    dedup_key: Optional[str] = None,
    **kwargs: Any,
) -> None:
    """Enqueue or directly dispatch an outgoing message to Telegram."""
    from app.core.config import _GLOBAL_LOADED_CONFIG
    from app.miner_monitor import _QA_MODE

    global _TELEGRAM_QUEUE
    mm = sys.modules.get("app.miner_monitor")
    if mm is not None:
        mm_queue = getattr(mm, "_TELEGRAM_QUEUE", None)
        if mm_queue is not None:
            _TELEGRAM_QUEUE = mm_queue
        log_fn = getattr(mm, "log", log)
    else:
        log_fn = log

    if not msg_type:
        msg_type = "ERROR"
    if not is_command:
        if _GLOBAL_LOADED_CONFIG is not None and not bool(_GLOBAL_LOADED_CONFIG.get("telegram_alerts_enabled", True)):
            return
    parts = split_telegram_message(message)
    delivery_class = classify_delivery(msg_type, is_command=is_command)
    if _TELEGRAM_QUEUE is None:
        log_fn(
            f"TG ENQUEUE_FAIL queue=None cmd={dbg_cmd or ''} update_id={dbg_update_id} "
            f"is_command={is_command} msg_type={msg_type}"
        )
        if is_command:
            _send_telegram_direct(
                bot_token,
                chat_id,
                parts,
                dbg_update_id=dbg_update_id,
                dbg_cmd=dbg_cmd,
                reply_markup=reply_markup,
            )
        return
    direct_send = False
    with _TELEGRAM_QUEUE_LOCK:
        now_ts = time.time()
        if DBG_TELEGRAM and (not DBG_TELEGRAM_COMMANDS_ONLY or is_command):
            log_fn(
                f"TGQ update_id={dbg_update_id} cmd={dbg_cmd or ''} qsize_before={_TELEGRAM_QUEUE.qsize()} "
                f"type={msg_type} text_len={len(message or '')} parts={len(parts)}"
            )
        maxsize = _TELEGRAM_QUEUE.maxsize
        capacity_needed = len(parts)
        has_capacity = maxsize <= 0 or (_TELEGRAM_QUEUE.qsize() + capacity_needed) <= maxsize
        if not has_capacity and is_command:
            direct_send = True
            log_fn(
                f"TG QUEUE_BYPASS class=command reason=full type={msg_type} "
                f"update_id={dbg_update_id} parts={len(parts)}"
            )
        elif not has_capacity:
            log_fn(
                f"TG QUEUE_DROP class={delivery_class} reason=full type={msg_type} "
                f"update_id={dbg_update_id} parts={len(parts)}"
            )
            return

        if direct_send:
            pass
        else:
            _LAST_ENQUEUED[msg_type] = now_ts
            batch_id = f"{time.time_ns()}-{threading.get_ident()}"
            for part_index, part in enumerate(parts, start=1):
                _TELEGRAM_QUEUE.put_nowait(
                    (
                        now_ts,
                        chat_id,
                        part,
                        msg_type,
                        reason,
                        qa_update_id,
                        qa_cmd,
                        perf_ctx,
                        is_command,
                        dbg_update_id,
                        dbg_cmd,
                        batch_id,
                        part_index,
                        len(parts),
                        reply_markup if part_index == len(parts) else None,
                    )
                )
            if DBG_TELEGRAM and (not DBG_TELEGRAM_COMMANDS_ONLY or is_command):
                log_fn(
                    f"TGQ update_id={dbg_update_id} cmd={dbg_cmd or ''} "
                    f"ENQUEUED qsize_after={_TELEGRAM_QUEUE.qsize()} "
                    f"type={msg_type} parts={len(parts)}"
                )
        _LAST_SENT_META["type"] = msg_type
        _LAST_SENT_META["ts"] = now_str()
        if _QA_MODE:
            log_pid(f"[QA] enqueue type={msg_type} reason={reason} qsize={_TELEGRAM_QUEUE.qsize()}")
    if direct_send:
        _send_telegram_direct(
            bot_token,
            chat_id,
            parts,
            dbg_update_id=dbg_update_id,
            dbg_cmd=dbg_cmd,
            reply_markup=reply_markup,
        )


def _send_telegram_direct(
    bot_token: str,
    chat_id: str,
    parts: list[str],
    *,
    dbg_update_id: Optional[int],
    dbg_cmd: Optional[str],
    reply_markup: Optional[Dict[str, Any]] = None,
) -> bool:
    """Send parts directly via HTTP without queueing (fallback for full queues or commands)."""
    tg_send_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    mm = sys.modules.get("app.miner_monitor")
    if mm is not None and getattr(mm, "_HTTP_SESSION", None) is not None:
        session = mm._HTTP_SESSION
    else:
        session = _HTTP_SESSION or requests.Session()
    log_fn = getattr(mm, "log", log) if mm else log

    if not tg_send_url.startswith("https://api.telegram.org/bot"):
        log_fn("[ERROR] URL Telegram invalida (sendMessage).")
        return False
    for part_index, part in enumerate(parts, start=1):
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": part,
            "disable_web_page_preview": True,
        }
        if reply_markup is not None and part_index == len(parts):
            payload["reply_markup"] = reply_markup
        t0 = time.perf_counter()
        try:
            resp = session.post(tg_send_url, json=payload, timeout=(1.5, 4.0))
            ms = int((time.perf_counter() - t0) * 1000)
            if resp.status_code == 200:
                log(
                    f"TG FALLBACK_SEND ok http=200 ms_send={ms} cmd={dbg_cmd or ''} "
                    f"update_id={dbg_update_id} part={part_index}/{len(parts)}"
                )
                continue
            body = _redact_telegram_token(
                resp.text or "", bot_token
            )[:200].replace("\n", "\\n")
            log(
                f"TG FALLBACK_SEND err http={resp.status_code} ms_send={ms} "
                f"cmd={dbg_cmd or ''} update_id={dbg_update_id} "
                f"part={part_index}/{len(parts)} body=\"{body}\""
            )
            return False
        except Exception as exc:
            ms = int((time.perf_counter() - t0) * 1000)
            log(
                f"TG FALLBACK_SEND exc ms_send={ms} cmd={dbg_cmd or ''} "
                f"update_id={dbg_update_id} part={part_index}/{len(parts)} "
                f"err={type(exc).__name__}:{_redact_telegram_token(exc, bot_token)}"
            )
            return False
    return True


def answer_callback_query(
    bot_token: str,
    callback_query_id: str,
    text: Optional[str] = None,
    show_alert: bool = False,
) -> None:
    """Acknowledge a Telegram callback_query within the mandatory window."""
    url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
    payload: Dict[str, Any] = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    if show_alert:
        payload["show_alert"] = True
    t0 = time.perf_counter()
    try:
        session = get_telegram_session()
        resp = session.post(url, json=payload, timeout=5.0)
        ms = int((time.perf_counter() - t0) * 1000)
        if resp.status_code != 200:
            body = _redact_telegram_token(resp.text or "", bot_token)[:200]
            log(
                f"TG ANSWER_CB err http={resp.status_code} ms={ms} "
                f"cb_id={callback_query_id} body=\"{body}\""
            )
        elif DBG_TELEGRAM:
            log(f"TG ANSWER_CB ok ms={ms} cb_id={callback_query_id}")
    except Exception as exc:
        ms = int((time.perf_counter() - t0) * 1000)
        log(
            f"TG ANSWER_CB exc ms={ms} cb_id={callback_query_id} "
            f"err={type(exc).__name__}:{_redact_telegram_token(exc, bot_token)}"
        )


def edit_message_reply_markup(
    bot_token: str,
    chat_id: str,
    message_id: int,
    reply_markup: Dict[str, Any],
) -> None:
    """Replace the inline keyboard of an existing message in-place."""
    url = f"https://api.telegram.org/bot{bot_token}/editMessageReplyMarkup"
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "reply_markup": reply_markup,
    }
    t0 = time.perf_counter()
    try:
        session = get_telegram_session()
        resp = session.post(url, json=payload, timeout=5.0)
        ms = int((time.perf_counter() - t0) * 1000)
        if resp.status_code != 200:
            body = _redact_telegram_token(resp.text or "", bot_token)[:200]
            log(
                f"TG EDIT_MARKUP err http={resp.status_code} ms={ms} "
                f"chat_id={chat_id} msg_id={message_id} body=\"{body}\""
            )
        elif DBG_TELEGRAM:
            log(f"TG EDIT_MARKUP ok ms={ms} chat_id={chat_id} msg_id={message_id}")
    except Exception as exc:
        ms = int((time.perf_counter() - t0) * 1000)
        log(
            f"TG EDIT_MARKUP exc ms={ms} chat_id={chat_id} msg_id={message_id} "
            f"err={type(exc).__name__}:{_redact_telegram_token(exc, bot_token)}"
        )


def edit_message_text(
    bot_token: str,
    chat_id: str,
    message_id: int,
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None,
    parse_mode: Optional[str] = "Markdown",
) -> bool:
    """Edit both the text and inline keyboard of an existing message in-place."""
    url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    if parse_mode is not None:
        payload["parse_mode"] = parse_mode

    t0 = time.perf_counter()
    try:
        session = get_telegram_session()
        resp = session.post(url, json=payload, timeout=5.0)
        ms = int((time.perf_counter() - t0) * 1000)
        if resp.status_code == 200:
            if DBG_TELEGRAM:
                log(f"TG EDIT_TEXT ok ms={ms} chat_id={chat_id} msg_id={message_id}")
            return True
        body = (resp.text or "").lower()
        if "message is not modified" in body:
            return True
        redacted_body = _redact_telegram_token(resp.text or "", bot_token)[:200]
        log(
            f"TG EDIT_TEXT err http={resp.status_code} ms={ms} "
            f"chat_id={chat_id} msg_id={message_id} body=\"{redacted_body}\""
        )
        return False
    except Exception as exc:
        ms = int((time.perf_counter() - t0) * 1000)
        log(
            f"TG EDIT_TEXT exc ms={ms} chat_id={chat_id} msg_id={message_id} "
            f"err={type(exc).__name__}:{_redact_telegram_token(exc, bot_token)}"
        )
        return False


def send_telegram_photo(
    bot_token: str,
    chat_id: str,
    photo_bytes: bytes,
    caption: Optional[str] = None,
    reply_markup: Optional[Dict[str, Any]] = None,
    timeout: float = 15.0,
) -> bool:
    """Send a binary PNG image directly to Telegram via sendPhoto."""
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    data: Dict[str, Any] = {"chat_id": str(chat_id)}
    if caption:
        data["caption"] = caption
    if reply_markup is not None:
        data["reply_markup"] = json.dumps(reply_markup)
    files = {"photo": ("chart.png", photo_bytes, "image/png")}
    t0 = time.perf_counter()
    try:
        session = get_telegram_session()
        resp = session.post(url, data=data, files=files, timeout=timeout)
        ms = int((time.perf_counter() - t0) * 1000)
        if resp.status_code != 200:
            body = _redact_telegram_token(resp.text or "", bot_token)[:200]
            log(f"TG SEND_PHOTO err http={resp.status_code} ms={ms} body=\"{body}\"")
            return False
        if DBG_TELEGRAM:
            log(f"TG SEND_PHOTO ok ms={ms}")
        return True
    except Exception as exc:
        ms = int((time.perf_counter() - t0) * 1000)
        log(f"TG SEND_PHOTO exc ms={ms} err={type(exc).__name__}:{_redact_telegram_token(exc, bot_token)}")
        return False


def edit_telegram_photo(
    bot_token: str,
    chat_id: str,
    message_id: int,
    photo_bytes: bytes,
    caption: Optional[str] = None,
    reply_markup: Optional[Dict[str, Any]] = None,
    timeout: float = 15.0,
) -> bool:
    """Edit an existing photo message in-place using editMessageMedia."""
    url = f"https://api.telegram.org/bot{bot_token}/editMessageMedia"
    media_obj: Dict[str, Any] = {
        "type": "photo",
        "media": "attach://file_0",
    }
    if caption:
        media_obj["caption"] = caption
    data: Dict[str, Any] = {
        "chat_id": str(chat_id),
        "message_id": int(message_id),
        "media": json.dumps(media_obj),
    }
    if reply_markup is not None:
        data["reply_markup"] = json.dumps(reply_markup)
    files = {"file_0": ("chart.png", photo_bytes, "image/png")}
    t0 = time.perf_counter()
    try:
        session = get_telegram_session()
        resp = session.post(url, data=data, files=files, timeout=timeout)
        ms = int((time.perf_counter() - t0) * 1000)
        if resp.status_code != 200:
            body = _redact_telegram_token(resp.text or "", bot_token)[:200]
            if "message is not modified" in body.lower():
                if DBG_TELEGRAM:
                    log(f"TG EDIT_PHOTO not modified ms={ms}")
                return True
            log(f"TG EDIT_PHOTO err http={resp.status_code} ms={ms} body=\"{body}\"")
            return False
        if DBG_TELEGRAM:
            log(f"TG EDIT_PHOTO ok ms={ms}")
        return True
    except Exception as exc:
        ms = int((time.perf_counter() - t0) * 1000)
        log(f"TG EDIT_PHOTO exc ms={ms} err={type(exc).__name__}:{_redact_telegram_token(exc, bot_token)}")
        return False


def telegram_sender_worker(bot_token: str, q: queue.Queue, qa_mode: bool) -> None:
    """Background worker continuously pulling from _TELEGRAM_QUEUE and sending to Telegram."""
    global _TELEGRAM_SENDER_TS
    session = get_telegram_session()
    tg_send_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    if not tg_send_url.startswith("https://api.telegram.org/bot"):
        log("[ERROR] URL Telegram invalida (sendMessage).")
        return
    last_hb = 0.0
    while True:
        is_command = False
        dbg_update_id = None
        dbg_cmd = None
        try:
            _TELEGRAM_SENDER_TS = time.time()
            try:
                item = q.get(timeout=5.0)
            except queue.Empty:
                _TELEGRAM_SENDER_TS = time.time()
                continue
            (
                enqueue_ts,
                chat_id,
                message,
                msg_type,
                _reason,
                qa_update_id,
                qa_cmd,
                perf_ctx,
                is_command,
                dbg_update_id,
                dbg_cmd,
                batch_id,
                part_index,
                part_count,
                reply_markup,
            ) = item
            if DBG_TELEGRAM and (time.time() - last_hb) >= 30:
                log(f"SENDER_HB alive=1 qsize={q.qsize()}")
                last_hb = time.time()
            with _TELEGRAM_QUEUE_LOCK:
                last_ts = _LAST_ENQUEUED.get(msg_type, 0.0)
            window = _COALESCE_WINDOWS.get(msg_type)
            if part_count == 1 and not is_command and window and enqueue_ts < last_ts and (last_ts - enqueue_ts) <= window:
                if DBG_TELEGRAM and (not DBG_TELEGRAM_COMMANDS_ONLY or is_command):
                    log(
                        f"SEND_SKIP update_id={dbg_update_id} reason=coalesce type={msg_type} "
                        f"window_s={window}"
                    )
                continue
            msg_hash = hashlib.sha256(message.encode("utf-8", errors="ignore")).hexdigest()
            last_hash = _LAST_SENT_HASH.get(msg_type)
            last_sent = _LAST_SENT_TS.get(msg_type, 0.0)
            if part_count == 1 and not is_command and msg_type == "STATE_CHANGE" and last_hash == msg_hash:
                if DBG_TELEGRAM and (not DBG_TELEGRAM_COMMANDS_ONLY or is_command):
                    log(
                        f"SEND_SKIP update_id={dbg_update_id} reason=dedupe type={msg_type} hash={msg_hash[:8]}"
                    )
                continue
            if part_count == 1 and not is_command and last_hash == msg_hash and (time.time() - last_sent) < 60:
                if DBG_TELEGRAM and (not DBG_TELEGRAM_COMMANDS_ONLY or is_command):
                    log(
                        f"SEND_SKIP update_id={dbg_update_id} reason=dedupe type={msg_type} hash={msg_hash[:8]} "
                        f"age_s={int(time.time() - last_sent)}"
                    )
                continue
            payload = {
                "chat_id": chat_id,
                "text": message,
                "disable_web_page_preview": True,
            }
            if reply_markup is not None:
                payload["reply_markup"] = reply_markup
            start = time.monotonic()
            resp = session.post(tg_send_url, json=payload, timeout=(2.0, 6.0))
            _TELEGRAM_SENDER_TS = time.time()
            duration = time.monotonic() - start
            if qa_mode:
                log_pid(
                    f"[TEL] sendMessage duration={duration:.3f}s status={resp.status_code} "
                    f"qsize={q.qsize()} msg_type={msg_type}"
                )
                if qa_update_id is not None:
                    count = _QA_TX_COUNTS.get(qa_update_id, 0) + 1
                    _QA_TX_COUNTS[qa_update_id] = count
                    log_pid(
                        f"TX id={qa_update_id} n={count} cmd={qa_cmd or 'N/A'} status={resp.status_code}"
                    )
            if perf_ctx:
                perf_id = perf_ctx.get("update_id")
                if perf_id is None or not _PERF_LOGGED.get(perf_id):
                    ms_send = int(duration * 1000)
                    start_ts = perf_ctx.get("start_ts", time.time())
                    ms_total = int((time.time() - start_ts) * 1000)
                    log(
                        f"PERF cmd={perf_ctx.get('cmd','')} handler={perf_ctx.get('handler','')} "
                        f"ms_total={ms_total} ms_send={ms_send}"
                    )
                    if ms_send > 2000:
                        log(f"SAFETY slow_send cmd={perf_ctx.get('cmd','')} ms_send={ms_send}")
                    if resp.status_code != 200:
                        body = _redact_telegram_token(
                            resp.text or "", bot_token
                        )[:200].replace("\n", " ")
                        log(f"ERROR telegram_send status={resp.status_code} body=\"{body}\"")
                    if perf_id is not None:
                        _PERF_LOGGED[perf_id] = True
            if resp.status_code != 200:
                body = _redact_telegram_token(
                    resp.text or "", bot_token
                )[:200].replace("\n", " ")
                log(
                    f"TG SEND_ERR http={resp.status_code} cmd={dbg_cmd or ''} "
                    f"update_id={dbg_update_id} body=\"{body}\""
                )
            if DBG_TELEGRAM and (not DBG_TELEGRAM_COMMANDS_ONLY or is_command):
                log(
                    f"SEND_POST update_id={dbg_update_id} cmd={dbg_cmd or ''} "
                    f"http={resp.status_code} ms={int(duration*1000)} type={msg_type}"
                )
                if resp.status_code != 200:
                    body = _redact_telegram_token(
                        resp.text or "", bot_token
                    )[:200].replace("\n", " ")
                    log(f"SEND_ERR update_id={dbg_update_id} cmd={dbg_cmd or ''} http={resp.status_code} body=\"{body}\"")
            if resp.status_code >= 400:
                log(
                    f"[WARN] Telegram retorno {resp.status_code}: "
                    f"{_redact_telegram_token(resp.text, bot_token)}"
                )
            _LAST_SENT_HASH[msg_type] = msg_hash
            _LAST_SENT_TS[msg_type] = time.time()
        except Exception as exc:
            _TELEGRAM_SENDER_TS = time.time()
            if DBG_TELEGRAM and (not DBG_TELEGRAM_COMMANDS_ONLY or is_command):
                log(
                    f"SEND_EXC update_id={dbg_update_id} err={type(exc).__name__}:"
                    f"{_redact_telegram_token(exc, bot_token)}"
                )
            log(
                "[WARN] No se pudo enviar mensaje a Telegram "
                f"({_redact_telegram_token(exc, bot_token)})"
            )
            time.sleep(2)
