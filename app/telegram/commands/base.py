"""Base Command Handler Abstraction (Spec 058).

Defines the contract for decoupled Telegram command processors,
including authentication, argument parsing, error boundaries, and No-Silence enforcement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
from typing import Any, List, Optional

from app.telegram.context import TelegramRequestContext

logger = logging.getLogger("miner-alerts")


class BaseCommandHandler(ABC):
    """Abstract base class for all discrete Telegram command processors."""

    name: str = ""
    aliases: List[str] = []
    description: str = ""

    def matches(self, cmd_token: str) -> bool:
        """Check if incoming command token matches canonical name or any alias."""
        clean = (cmd_token or "").strip().lower()
        if clean.startswith("/"):
            clean = clean[1:]
        if "@" in clean:
            clean = clean.split("@", 1)[0]
        if clean == self.name:
            return True
        return clean in self.aliases

    def check_authorization(self, context: TelegramRequestContext, from_id: Any) -> bool:
        """Validate sender identity against configured authorized chat_id."""
        if from_id is None:
            return False
        try:
            return int(from_id) == int(context.chat_id)
        except (TypeError, ValueError):
            return False

    @abstractmethod
    def handle(
        self,
        context: TelegramRequestContext,
        args: List[str],
        update_id: Optional[int] = None,
        from_id: Optional[Any] = None,
        message_id: Optional[int] = None,
        cmd_name: str = "",
        **kwargs: Any,
    ) -> bool:
        """Execute command logic. Must return True if handled successfully."""
        pass
