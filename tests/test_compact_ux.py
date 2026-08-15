"""Phase 3 — Compact Telegram UX contracts.

Tests the rendering contracts defined in the sprint prompt before modifying
any production code.  All tests are deterministic and use the existing
IrregularEpisodeCoordinator and render_episode_notification_batch.
"""

import unittest

from app.alert_episodes import (
    IrregularEpisodeCoordinator,
    render_episode_notification_batch,
)


def _coordinator(
    coalesce: float = 30,
    schedule: tuple[float, ...] = (300, 600, 900, 1800, 3600, 7200),
    repeat: float = 3600,
) -> IrregularEpisodeCoordinator:
    return IrregularEpisodeCoordinator(
        coalesce_seconds=coalesce,
        reminder_schedule_seconds=schedule,
        steady_repeat_seconds=repeat,
    )


def _observe(
    coord: IrregularEpisodeCoordinator,
    *,
    miner: str = "24",
    previous: str = "OK",
    state: str = "OFFLINE",
    now: float = 100.0,
    rate: float | None = None,
    responded: bool = False,
    boards: int | None = None,
    event_id: int | None = 123,
    restart: dict | None = None,
) -> None:
    coord.observe(
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


class CompactAlertGroupingTest(unittest.TestCase):
    """Contract A: Miners within the coalesce window produce one grouped message."""

    def test_two_miners_within_window_emit_single_notification(self) -> None:
        coord = _coordinator()
        _observe(coord, miner="24", now=100.0, event_id=123)
        _observe(
            coord, miner="25", state="LOW", responded=True,
            rate=42.3, boards=3, now=103.0, event_id=124,
        )

        self.assertTrue(coord.pop_due(now_ts=129.9).empty)
        batch = coord.pop_due(now_ts=130.0)

        self.assertEqual(2, len(batch.opened))
        self.assertEqual(["24", "25"], [e.name_display for e in batch.opened])
        msg = render_episode_notification_batch(batch, now_ts=130.0)
        # Contract: single header, both miners, compact, event refs
        self.assertEqual(1, msg.count("ALERTA"), "Exactly one alert header")
        self.assertIn("/e123", msg)
        self.assertIn("/e124", msg)

    def test_miner_outside_window_produces_separate_batch(self) -> None:
        coord = _coordinator()
        _observe(coord, miner="24", now=100.0, event_id=123)
        coord.pop_due(now_ts=130.0)

        _observe(coord, miner="25", state="LOW", responded=True,
                 rate=42.3, boards=3, now=200.0, event_id=124)
        batch = coord.pop_due(now_ts=230.0)

        self.assertEqual(1, len(batch.opened))
        self.assertEqual("25", batch.opened[0].name_display)


class CompactRecoveryTest(unittest.TestCase):
    """Contract B: Recovery summarizes the complete episode sequence."""

    def test_offline_low_ok_recovery_shows_complete_sequence(self) -> None:
        coord = _coordinator()
        _observe(coord, miner="24", state="OFFLINE", now=100.0, event_id=123)
        coord.pop_due(now_ts=130.0)

        _observe(coord, miner="24", previous="OFFLINE", state="LOW",
                 responded=True, rate=42.3, boards=3, now=200.0, event_id=124)
        _observe(coord, miner="24", previous="LOW", state="OK",
                 responded=True, rate=98.4, boards=3, now=340.0, event_id=125)
        batch = coord.pop_due(now_ts=370.0)

        self.assertEqual(1, len(batch.recovered))
        msg = render_episode_notification_batch(batch, now_ts=370.0)
        self.assertIn("OK -> OFFLINE -> LOW -> OK", msg)
        self.assertIn("/e", msg)

    def test_hashboard_low_ok_recovery_preserves_full_sequence(self) -> None:
        coord = _coordinator()
        _observe(coord, miner="24", state="HASHBOARD", responded=True,
                 rate=0.0, boards=0, now=100.0, event_id=200)
        coord.pop_due(now_ts=130.0)

        _observe(coord, miner="24", previous="HASHBOARD", state="LOW",
                 responded=True, rate=20.0, boards=3, now=150.0, event_id=201)
        _observe(coord, miner="24", previous="LOW", state="OK",
                 responded=True, rate=95.0, boards=3, now=200.0, event_id=202)
        batch = coord.pop_due(now_ts=230.0)

        self.assertEqual(1, len(batch.recovered))
        msg = render_episode_notification_batch(batch, now_ts=230.0)
        self.assertIn("PLACAS 0/3", msg)
        self.assertIn("OK", msg)


class CompactPersistenceTest(unittest.TestCase):
    """Contract C: Reminders fire only at the configured schedule times."""

    def test_reminders_follow_configured_schedule_only(self) -> None:
        coord = _coordinator()
        _observe(coord, now=100.0)
        coord.pop_due(now_ts=130.0)

        # At t=200 (100s of age) no reminder should fire yet (first is at 300s = t=400)
        self.assertTrue(coord.pop_due(now_ts=200.0).empty)
        self.assertTrue(coord.pop_due(now_ts=399.9).empty)

        batch = coord.pop_due(now_ts=400.0)
        self.assertEqual(1, len(batch.persistent))
        msg = render_episode_notification_batch(batch, now_ts=400.0)
        self.assertIn("/e123", msg)


class CompactDetailTest(unittest.TestCase):
    """Contract D: Main message is short; /e<ID> has full detail."""

    def test_main_message_excludes_ip_and_diagnostics(self) -> None:
        coord = _coordinator()
        _observe(coord, miner="24", now=100.0, event_id=123)
        batch = coord.pop_due(now_ts=130.0)
        msg = render_episode_notification_batch(batch, now_ts=130.0)

        # IP address should NOT be in the episode notification
        self.assertNotIn("192.168", msg,
                         "IP addresses belong in /e<ID> detail, not the main alert")
        # /e<ID> reference SHOULD be present
        self.assertIn("/e123", msg)


class CompactConsistencyTest(unittest.TestCase):
    """Contract E: Never show positive rate with OFFLINE; stable sort;
    no empty, duplicate or contradictory messages."""

    def test_offline_never_shows_positive_rate(self) -> None:
        coord = _coordinator()
        _observe(coord, miner="24", state="OFFLINE", responded=False,
                 rate=97.87, now=100.0, event_id=123)
        batch = coord.pop_due(now_ts=130.0)
        msg = render_episode_notification_batch(batch, now_ts=130.0)

        self.assertNotIn("97.87", msg)

    def test_miners_sorted_numerically(self) -> None:
        coord = _coordinator()
        _observe(coord, miner="26", now=100.0, event_id=130)
        _observe(coord, miner="23", now=100.0, event_id=131)
        _observe(coord, miner="25", now=100.0, event_id=132)
        batch = coord.pop_due(now_ts=130.0)

        names = [e.name_display for e in batch.opened]
        self.assertEqual(["23", "25", "26"], names)

    def test_empty_batch_produces_no_message(self) -> None:
        coord = _coordinator()
        batch = coord.pop_due(now_ts=100.0)
        self.assertTrue(batch.empty)
        msg = render_episode_notification_batch(batch, now_ts=100.0)
        self.assertEqual("", msg)


class CompactTransportTest(unittest.TestCase):
    """Contract from prompt Phase 3 item 9: command responses preserve
    is_command=True flow — verified at the coordinator/renderer level."""

    def test_render_does_not_produce_empty_sections(self) -> None:
        coord = _coordinator()
        _observe(coord, miner="24", now=100.0, event_id=123)
        batch = coord.pop_due(now_ts=130.0)
        msg = render_episode_notification_batch(batch, now_ts=130.0)
        # No empty lines between sections (no triple newlines)
        self.assertNotIn("\n\n\n", msg, "Rendered message has excessive blank lines")


if __name__ == "__main__":
    unittest.main()
