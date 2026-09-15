"""Monitor Context — Dependency injection container (Spec 060).

MonitorContext is a plain dataclass that transports all runtime dependencies
into the supervisory engine and the Telegram dispatcher, replacing the module-level
mutable globals that currently couple main() to telegram_polling_worker.

Design goals:
  - Zero circular imports: this module only imports from stdlib and app.core.state_manager.
  - Fully type-annotated for static analysis.
  - Backwards-compatible: main() can construct a MonitorContext and pass it to new
    engine helpers without removing any existing code from miner_monitor.py.

Globals this container eventually replaces (Spec 060 migration):
  _GLOBAL_INTERVENTION_GOV    -> context.governance
  _ELEVATOR_CONTINGENCY_STATES -> context.elevator_contingency
  _ACTIVE_SCHEDULED_WINDOW    -> context.scheduled_window
  _QA_MODE                    -> context.qa_mode
  _LAST_DAILY_DIGEST_DATE     -> context.last_daily_digest_date
  _TELEGRAM_QUEUE             -> context.telegram_queue
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.state_manager import StateManager


@dataclass
class MonitorContext:
    """Immutable-by-convention dependency container for the monitor runtime.

    Fields are mutable references to shared runtime objects.  The container
    itself is not frozen — it is passed by reference so all consumers share
    the same instance.  Individual fields like ``governance`` must be replaced
    atomically (assignment is GIL-safe in CPython).
    """

    # ------------------------------------------------------------------ #
    # Identity & runtime paths
    # ------------------------------------------------------------------ #
    config: Dict[str, Any]
    """Raw config.json dict (read-only after startup)."""

    state_path: Path
    """Absolute path to state.json."""

    miners: List[Dict[str, Any]]
    """Validated miner list (read-only after startup)."""

    # ------------------------------------------------------------------ #
    # Telegram
    # ------------------------------------------------------------------ #
    bot_token: str
    chat_id: str
    telegram_queue: queue.Queue  # type: ignore[type-arg]
    """Bounded queue consumed by telegram_sender_worker."""

    # ------------------------------------------------------------------ #
    # Concurrency primitives
    # ------------------------------------------------------------------ #
    state_lock: threading.RLock
    """L1 — guards the in-memory states dict."""

    state_manager: StateManager
    """Atomic persistence helper; shares state_lock and flush_lock with main()."""

    # ------------------------------------------------------------------ #
    # Runtime mode flags
    # ------------------------------------------------------------------ #
    qa_mode: bool = False
    qa_allow_actions: bool = False
    qa_notify: bool = False
    qa_verbose: bool = False

    # ------------------------------------------------------------------ #
    # Governance — replaced atomically on user toggle (GIL-safe assignment)
    # ------------------------------------------------------------------ #
    governance: Optional[Any] = None
    """InterventionGovernance instance (frozen dataclass, thread-safe by design)."""

    elevator_contingency: Dict[str, Any] = field(default_factory=dict)
    """Dict[group_name, GroupContingencyState] — mutated only under state_lock."""

    scheduled_window: Optional[Any] = None
    """ScheduledWindow instance or None."""

    # ------------------------------------------------------------------ #
    # Operational counters (owned by main loop, not shared across threads)
    # ------------------------------------------------------------------ #
    last_daily_digest_date: Optional[str] = None

    # ------------------------------------------------------------------ #
    # External service handles
    # ------------------------------------------------------------------ #
    event_store: Optional[Any] = None
    """EventStore instance or None when disabled."""

    hashcore_cfg: Dict[str, Any] = field(default_factory=dict)
    """Hashcore CLI configuration dict."""

    # ------------------------------------------------------------------ #
    # Convenience accessors
    # ------------------------------------------------------------------ #

    @property
    def threshold_ths(self) -> float:
        return float(self.config.get("threshold_ths", 60.0))

    @property
    def poll_seconds(self) -> int:
        if self.qa_mode:
            return int(self.config.get("qa_poll_seconds", 2))
        return int(self.config.get("poll_seconds", 30))

    @property
    def startup_guard_seconds(self) -> int:
        return int(self.config.get("startup_guard_seconds", 600))

    @property
    def vnish_api_password(self) -> str:
        return str(self.config.get("vnish_api_password", "admin"))


def build_monitor_context(
    config: Dict[str, Any],
    state_path: Path,
    miners: List[Dict[str, Any]],
    bot_token: str,
    chat_id: str,
    state_lock: threading.RLock,
    telegram_queue: "queue.Queue[Any]",
    state_manager: StateManager,
    event_store: Optional[Any] = None,
    qa_mode: bool = False,
    qa_allow_actions: bool = False,
    qa_notify: bool = False,
    qa_verbose: bool = False,
    hashcore_cfg: Optional[Dict[str, Any]] = None,
    governance: Optional[Any] = None,
    elevator_contingency: Optional[Dict[str, Any]] = None,
    scheduled_window: Optional[Any] = None,
    last_daily_digest_date: Optional[str] = None,
) -> MonitorContext:
    """Factory function for MonitorContext — validates required fields and sets defaults."""
    if not bot_token:
        raise ValueError("bot_token is required")
    if not chat_id:
        raise ValueError("chat_id is required")
    if not miners:
        raise ValueError("miners list must not be empty")

    return MonitorContext(
        config=config,
        state_path=state_path,
        miners=miners,
        bot_token=bot_token,
        chat_id=chat_id,
        telegram_queue=telegram_queue,
        state_lock=state_lock,
        state_manager=state_manager,
        event_store=event_store,
        qa_mode=qa_mode,
        qa_allow_actions=qa_allow_actions,
        qa_notify=qa_notify,
        qa_verbose=qa_verbose,
        hashcore_cfg=hashcore_cfg or {},
        governance=governance,
        elevator_contingency=elevator_contingency if elevator_contingency is not None else {},
        scheduled_window=scheduled_window,
        last_daily_digest_date=last_daily_digest_date,
    )
