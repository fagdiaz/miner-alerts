"""Reusable test fixtures and coordinator factories for compact UX tests (Spec 073)."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from app.core.alert_episodes import IrregularEpisodeCoordinator


def make_test_coordinator(
    coalesce: float = 30.0,
    schedule: Tuple[float, ...] = (300.0, 600.0, 900.0, 1800.0, 3600.0, 7200.0),
    repeat: float = 3600.0,
) -> IrregularEpisodeCoordinator:
    """Create an IrregularEpisodeCoordinator configured with standard intervals."""
    return IrregularEpisodeCoordinator(
        coalesce_seconds=coalesce,
        reminder_schedule_seconds=schedule,
        steady_repeat_seconds=repeat,
    )


def observe_test_episode(
    c: IrregularEpisodeCoordinator,
    *,
    miner: str = "24",
    previous: str = "OK",
    state: str = "OFFLINE",
    now: float = 100.0,
    rate: Optional[float] = None,
    responded: bool = False,
    boards: Optional[int] = None,
    event_id: Optional[int] = 123,
    restart: Optional[Dict[str, Any]] = None,
) -> None:
    """Record a test state observation into an episode coordinator."""
    c.observe(
        miner_key=f"S19JPRO-{miner}|192.168.100.{miner}:4028",
        name_display=miner,
        host=f"192.168.100.{miner}",
        previous_state=previous,
        state=state,
        responded=responded,
        rate_ths=rate,
        threshold_ths=60.0,
        active_boards=boards if boards is not None else (3 if responded else None),
        expected_boards=3,
        now_ts=now,
        transition_event_id=event_id,
        restart=restart,
    )
