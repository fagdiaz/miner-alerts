"""Telegram Request Context & Runtime References (Spec 058).

Encapsulates all runtime dependencies needed by Telegram command handlers
and callback routers, ensuring safe concurrency, anti-deadlock state persistence,
and uniform messaging abstractions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional


@dataclass
class TelegramRequestContext:
    """Carries runtime execution context for an incoming Telegram update or command."""
    bot_token: str
    chat_id: str
    config: dict
    miners: list
    states: Dict[str, Any]
    state_lock: threading.Lock
    state_path: Path
    current_last_update_id: Optional[int] = None
    hashcore_cfg: dict = field(default_factory=dict)
    event_store: Optional[Any] = None
    qa_mode: bool = False
    qa_allow_actions: bool = False
    token_registry: Optional[Any] = None
    pending_reboots: Optional[Dict[str, Any]] = None
    pending_lock: Optional[threading.Lock] = None

    def get_states_snapshot(self) -> Dict[str, Any]:
        """Obtain a point-in-time snapshot of the states dictionary under state_lock."""
        with self.state_lock:
            return {k: v for k, v in self.states.items()}

    def persist_state_safely(self) -> None:
        """Persist states adhering strictly to anti-deadlock hierarchy:
        build in-memory payload under state_lock (<0.1ms), flush to disk outside state_lock.
        """
        from app.miner_monitor import _build_state_payload, _flush_state_payload
        with self.state_lock:
            payload = _build_state_payload(self.states, self.current_last_update_id)
        _flush_state_payload(self.state_path, payload)

    def send_message(
        self,
        text: str,
        target_chat_id: Optional[str] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
        msg_type: str = "COMMAND",
        dedup_key: Optional[str] = None,
        parse_mode: Optional[str] = "Markdown",
        dbg_cmd: Optional[str] = None,
        dbg_update_id: Optional[int] = None,
    ) -> bool:
        """Send a message back to the operator via Telegram sender queue/fallback."""
        from app.miner_monitor import send_telegram
        cid = str(target_chat_id or self.chat_id)
        return send_telegram(
            self.bot_token,
            cid,
            text,
            msg_type=msg_type,
            dedup_key=dedup_key or "",
            is_command=True,
            reply_markup=reply_markup,
            dbg_cmd=dbg_cmd,
            dbg_update_id=dbg_update_id,
        )
