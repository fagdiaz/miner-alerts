"""Telegram interactive callbacks and inline keyboard helpers (Spec 031).

Provides pure data models, serialization grammar, validation, and bounded
in-memory token registry for 1-Tap interactive buttons.
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

MAX_CALLBACK_DATA_BYTES = 64
DEFAULT_TOKEN_TTL_SECONDS = 60.0
DEFAULT_MAX_TOKENS = 10


@dataclass(frozen=True)
class CallbackAction:
    action_type: str
    miner_id: str
    token: Optional[str] = None
    param: Optional[str] = None


def parse_callback_data(raw_data: str) -> Optional[CallbackAction]:
    """Parse a callback_data string into a structured CallbackAction.
    
    Supported formats:
    - diag:<miner_id>
    - chart:<miner_id>
    - snz:<miner_id>:<minutes>
    - rb_req:<miner_id>
    - rb_cfm:<token>:<miner_id>
    - rb_ccl:<miner_id>
    - noop
    """
    if not raw_data or not isinstance(raw_data, str):
        return None
    
    parts = raw_data.strip().split(":")
    tag = parts[0]

    if tag == "noop":
        return CallbackAction(action_type="noop", miner_id="")
    elif tag in ("diag", "chart", "rb_req", "rb_ccl"):
        if len(parts) == 2 and parts[1]:
            return CallbackAction(action_type=tag, miner_id=parts[1])
        return None
    elif tag == "snz":
        if len(parts) == 3 and parts[1] and parts[2]:
            return CallbackAction(action_type="snz", miner_id=parts[1], param=parts[2])
        return None
    elif tag == "rb_cfm":
        if len(parts) == 3 and parts[1] and parts[2]:
            return CallbackAction(action_type="rb_cfm", miner_id=parts[2], token=parts[1])
        return None

    return None


def build_callback_data(
    action_type: str,
    miner_id: str,
    token: Optional[str] = None,
    param: Optional[str] = None,
) -> str:
    """Build a normalized callback_data string guaranteed under 64 bytes."""
    if action_type == "noop":
        return "noop"
    elif action_type in ("diag", "chart", "rb_req", "rb_ccl"):
        res = f"{action_type}:{miner_id}"
    elif action_type == "snz":
        res = f"snz:{miner_id}:{param or '60'}"
    elif action_type == "rb_cfm":
        res = f"rb_cfm:{token or ''}:{miner_id}"
    else:
        res = f"{action_type}:{miner_id}"

    if len(res.encode("utf-8")) > MAX_CALLBACK_DATA_BYTES:
        raise ValueError(f"callback_data exceeds {MAX_CALLBACK_DATA_BYTES} bytes: {res}")
    return res


class CallbackTokenRegistry:
    """Bounded, thread-safe in-memory confirmation token cache."""

    def __init__(self, ttl_seconds: float = DEFAULT_TOKEN_TTL_SECONDS, max_tokens: int = DEFAULT_MAX_TOKENS):
        self._ttl_seconds = ttl_seconds
        self._max_tokens = max_tokens
        self._lock = threading.Lock()
        # Mapping: token -> (miner_id, action, created_ts)
        self._tokens: Dict[str, Tuple[str, str, float]] = {}

    def _prune(self, now: float):
        expired = [tok for tok, (_, _, ts) in list(self._tokens.items()) if now - ts > self._ttl_seconds]
        for tok in expired:
            self._tokens.pop(tok, None)

        if len(self._tokens) >= self._max_tokens:
            # Sort by created_ts ascending and drop oldest
            sorted_tokens = sorted(self._tokens.items(), key=lambda item: item[1][2])
            to_remove = len(self._tokens) - self._max_tokens + 1
            for tok, _ in sorted_tokens[:to_remove]:
                self._tokens.pop(tok, None)

    def create_token(self, miner_id: str, action: str = "reboot") -> str:
        now = time.time()
        with self._lock:
            self._prune(now)
            token = secrets.token_hex(3)  # 6 hex chars
            self._tokens[token] = (miner_id, action, now)
            return token

    def consume_token(self, token: str) -> Tuple[bool, Optional[str], str]:
        now = time.time()
        with self._lock:
            entry = self._tokens.pop(token, None)
            self._prune(now)

            if entry is None:
                return False, None, "token_not_found"

            miner_id, action, created_ts = entry
            if now - created_ts > self._ttl_seconds:
                return False, None, "token_expired"

            return True, miner_id, "ok"

    def invalidate_miner(self, miner_id: str) -> int:
        with self._lock:
            to_del = [tok for tok, (m_id, _, _) in list(self._tokens.items()) if m_id == miner_id]
            for tok in to_del:
                self._tokens.pop(tok, None)
            return len(to_del)


def build_alert_keyboard(miner_id: str) -> Dict[str, Any]:
    """Build the 1-Tap action bar for episode alerts."""
    return {
        "inline_keyboard": [
            [
                {"text": "🩺 Diagnosticar", "callback_data": build_callback_data("diag", miner_id)},
                {"text": "📊 Ver Gráfico", "callback_data": build_callback_data("chart", miner_id)},
            ],
            [
                {"text": f"🔄 Reiniciar {miner_id}", "callback_data": build_callback_data("rb_req", miner_id)},
                {"text": "🔕 Silenciar 1h", "callback_data": build_callback_data("snz", miner_id, param="60")},
            ],
        ]
    }


def build_confirmation_keyboard(miner_id: str, token: str) -> Dict[str, Any]:
    """Build the safe 2-step confirmation keyboard."""
    return {
        "inline_keyboard": [
            [
                {
                    "text": f"⚠️ CONFIRMAR REINICIO {miner_id}",
                    "callback_data": build_callback_data("rb_cfm", miner_id, token=token),
                }
            ],
            [
                {
                    "text": "❌ Cancelar",
                    "callback_data": build_callback_data("rb_ccl", miner_id),
                }
            ],
        ]
    }


def build_settled_keyboard(text: str = "Reinicio Solicitado") -> Dict[str, Any]:
    """Build a neutral settled action bar after confirmation."""
    return {
        "inline_keyboard": [
            [
                {"text": text, "callback_data": "noop"}
            ]
        ]
    }
